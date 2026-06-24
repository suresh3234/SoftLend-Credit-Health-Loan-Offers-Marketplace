import os
import sys
import time
import datetime
import re
import yaml
import logging
from fastapi import FastAPI, Depends, HTTPException, Request, Response, Query
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from pydantic import BaseModel, Field, validator
from typing import List, Optional

# Configure structured logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger("softlend-backend")

# Add parent and current directories to sys.path to resolve imports
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
if current_dir not in sys.path:
    sys.path.append(current_dir)
if parent_dir not in sys.path:
    sys.path.append(parent_dir)

from rule_engine.engine import run_gap_analysis, run_eligibility_evaluation
import models
import database
from database import get_db, engine

# Ensure database tables exist
models.Base.metadata.create_all(bind=engine)

app = FastAPI(title="Softlend API")

# Enable CORS for frontend connectivity
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- MIDDLEWARE: Request-level logging ---
@app.middleware("http")
async def request_logger(request: Request, call_next):
    start_time = time.time()
    response = await call_next(request)
    process_time_ms = int((time.time() - start_time) * 1000)
    logger.info(f"{request.method} {request.url.path} {response.status_code} - {process_time_ms}ms")
    return response

# --- EXCEPTION HANDLERS: Consistent JSON error response ---
@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    errors = exc.errors()
    # Construct a readable error description
    err_msgs = []
    for err in errors:
        loc = " -> ".join(str(l) for l in err.get("loc", []))
        msg = err.get("msg", "invalid value")
        err_msgs.append(f"Field '{loc}': {msg}")
    
    error_msg = "; ".join(err_msgs)
    return JSONResponse(
        status_code=422,
        content={"error": f"Validation failed: {error_msg}", "code": "VALIDATION_ERROR"}
    )

@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    # Extract code from headers if present, or guess from status code
    code = "HTTP_ERROR"
    if exc.status_code == 404:
        code = "NOT_FOUND"
    elif exc.status_code == 409:
        code = "ALREADY_EXISTS"
    elif exc.status_code == 422:
        code = "UNPROCESSABLE_ENTITY"
    
    # Check if a custom detail dict is passed
    detail = exc.detail
    if isinstance(detail, dict) and "error" in detail and "code" in detail:
        return JSONResponse(
            status_code=exc.status_code,
            content=detail
        )
        
    return JSONResponse(
        status_code=exc.status_code,
        content={"error": str(exc.detail), "code": code}
    )

@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    return JSONResponse(
        status_code=500,
        content={"error": f"Internal server error: {str(exc)}", "code": "INTERNAL_SERVER_ERROR"}
    )

# --- REQUEST/RESPONSE PYDANTIC SCHEMAS ---
class CustomerCreate(BaseModel):
    name: str = Field(..., min_length=1)
    mobile: str = Field(...)
    pan: str

    @validator('mobile')
    def validate_mobile(cls, v):
        normalized = re.sub(r'\D', '', v)
        if not re.match(r'^\d{10}$', normalized):
            raise ValueError('Mobile number must be exactly 10 digits')
        return normalized

    @validator('pan')
    def validate_pan(cls, v):
        normalized = v.strip().upper()
        pan_regex = r'^[A-Z]{5}[0-9]{4}[A-Z]{1}$'
        if not re.match(pan_regex, normalized):
            raise ValueError('PAN must match regex ^[A-Z]{5}[0-9]{4}[A-Z]{1}$')
        return normalized

class CreditScoreUpdate(BaseModel):
    cibil_score: int = Field(..., ge=300, le=900)

class CreditGapCreate(BaseModel):
    factor: str
    current_value: str
    ideal_value: str
    impact: str # 'high', 'medium', 'low'
    estimated_score_gain: int
    action_description: str

    @validator('impact')
    def validate_impact(cls, v):
        if v not in ('high', 'medium', 'low'):
            raise ValueError("Impact must be 'high', 'medium', or 'low'")
        return v

class OfferCreate(BaseModel):
    lender: str
    amount: float = Field(..., gt=0)
    interest_rate: float = Field(..., gt=0)
    tenure_months: int = Field(..., gt=0)
    min_score_required: int = Field(650, ge=300, le=900)

class AnalyseRequest(BaseModel):
    mode: str # 'gap_analysis' or 'eligibility'
    # Rest will be parsed dynamically inside

class EvaluateRequest(BaseModel):
    age: int = Field(..., ge=18, le=100)
    monthly_income: float = Field(..., gt=0)
    requested_amount: float = Field(..., gt=0)
    employment_type: str = Field(...)
    foir: float = Field(..., ge=0, le=10)
    credit_utilisation_pct: float = Field(..., ge=0, le=100)
    missed_payments_12m: int = Field(..., ge=0)
    written_off_accounts: int = Field(..., ge=0)
    credit_age_months: int = Field(..., ge=0)
    hard_enquiries_6m: int = Field(..., ge=0)

    @validator('employment_type')
    def validate_employment(cls, v):
        normalized = v.strip().lower()
        allowed = ("salaried", "self_employed", "unemployed", "retired", "student")
        if normalized not in allowed:
            raise ValueError(f"Employment type must be one of: {allowed}")
        return normalized

# --- API ENDPOINTS ---

# 1. POST /customers — Create a customer
@app.post("/customers", status_code=201)
def create_customer(customer: CustomerCreate, db: Session = Depends(get_db)):
    # Check if mobile already exists
    existing = db.query(models.Customer).filter(models.Customer.mobile == customer.mobile).first()
    if existing:
        raise HTTPException(
            status_code=409, 
            detail={"error": f"Customer with mobile {customer.mobile} already exists", "code": "MOBILE_ALREADY_EXISTS"}
        )
    
    db_cust = models.Customer(
        name=customer.name,
        mobile=customer.mobile,
        pan=customer.pan
    )
    db.add(db_cust)
    db.commit()
    db.refresh(db_cust)
    return {
        "id": db_cust.id,
        "name": db_cust.name,
        "mobile": db_cust.mobile
    }

# 2. POST /customers/:id/credit-score — Update credit score
@app.post("/customers/{customer_id}/credit-score")
def update_credit_score(customer_id: int, score_data: CreditScoreUpdate, db: Session = Depends(get_db)):
    customer = db.query(models.Customer).filter(models.Customer.id == customer_id).first()
    if not customer:
        raise HTTPException(status_code=404, detail="Customer not found")
        
    customer.cibil_score = score_data.cibil_score
    customer.score_fetched_at = datetime.datetime.utcnow()
    db.commit()
    db.refresh(customer)
    return {
        "customer_id": customer.id,
        "cibil_score": customer.cibil_score,
        "score_fetched_at": customer.score_fetched_at.isoformat() + "Z"
    }

# 3. POST /customers/:id/credit-gaps — Add a credit gap / action
@app.post("/customers/{customer_id}/credit-gaps", status_code=201)
def add_credit_gap(customer_id: int, gap_data: CreditGapCreate, db: Session = Depends(get_db)):
    customer = db.query(models.Customer).filter(models.Customer.id == customer_id).first()
    if not customer:
        raise HTTPException(status_code=404, detail="Customer not found")
        
    db_gap = models.CreditGap(
        customer_id=customer_id,
        factor=gap_data.factor,
        current_value=gap_data.current_value,
        ideal_value=gap_data.ideal_value,
        impact=gap_data.impact,
        estimated_score_gain=gap_data.estimated_score_gain,
        action_description=gap_data.action_description,
        status="open"
    )
    db.add(db_gap)
    db.commit()
    db.refresh(db_gap)
    return {
        "id": db_gap.id,
        "factor": db_gap.factor,
        "status": db_gap.status
    }

# 4. PATCH /credit-gaps/:id/resolve — Mark a gap as resolved
@app.patch("/credit-gaps/{gap_id}/resolve")
def resolve_credit_gap(gap_id: int, db: Session = Depends(get_db)):
    gap = db.query(models.CreditGap).filter(models.CreditGap.id == gap_id).first()
    if not gap:
        raise HTTPException(status_code=404, detail="Credit gap not found")
        
    if gap.status != "resolved":
        gap.status = "resolved"
        gap.resolved_at = datetime.datetime.utcnow()
        
        # Auto-update associated customer's CIBIL score
        customer = db.query(models.Customer).filter(models.Customer.id == gap.customer_id).first()
        if customer:
            current_score = customer.cibil_score if customer.cibil_score is not None else 300
            customer.cibil_score = min(900, current_score + gap.estimated_score_gain)
            customer.score_fetched_at = datetime.datetime.utcnow()
            logger.info(f"Automatically increased customer {customer.id} CIBIL score by +{gap.estimated_score_gain} to {customer.cibil_score} on resolving gap {gap.id}")
            
    db.commit()
    db.refresh(gap)
    return {
        "id": gap.id,
        "factor": gap.factor,
        "status": gap.status,
        "resolved_at": gap.resolved_at.isoformat() + "Z" if gap.resolved_at else None
    }

# 5. GET /customers/:id/credit-profile — Get full credit profile
@app.get("/customers/{customer_id}/credit-profile")
def get_credit_profile(customer_id: int, db: Session = Depends(get_db)):
    customer = db.query(models.Customer).filter(models.Customer.id == customer_id).first()
    if not customer:
        raise HTTPException(status_code=404, detail="Customer not found")
        
    open_gaps = db.query(models.CreditGap).filter(
        models.CreditGap.customer_id == customer_id, 
        models.CreditGap.status == "open"
    ).all()
    
    resolved_gaps = db.query(models.CreditGap).filter(
        models.CreditGap.customer_id == customer_id, 
        models.CreditGap.status == "resolved"
    ).all()
    
    all_gaps = db.query(models.CreditGap).filter(models.CreditGap.customer_id == customer_id).all()
    
    cibil = customer.cibil_score if customer.cibil_score is not None else 0
    # Potential score calculation
    potential_score = cibil + sum(g.estimated_score_gain for g in open_gaps)
    
    gaps_list = []
    for g in all_gaps:
        gaps_list.append({
            "id": g.id,
            "factor": g.factor,
            "impact": g.impact,
            "estimated_score_gain": g.estimated_score_gain,
            "action_description": g.action_description,
            "status": g.status,
            "current_value": g.current_value,
            "ideal_value": g.ideal_value,
            "resolved_at": g.resolved_at.isoformat() + "Z" if g.resolved_at else None
        })
        
    return {
        "customer_id": customer.id,
        "name": customer.name,
        "cibil_score": customer.cibil_score,
        "score_fetched_at": customer.score_fetched_at.isoformat() + "Z" if customer.score_fetched_at else None,
        "potential_score": potential_score,
        "gaps": gaps_list,
        "open_gaps": len(open_gaps),
        "resolved_gaps": len(resolved_gaps)
    }

# 6. POST /customers/:id/offers — Create an offer for a customer
@app.post("/customers/{customer_id}/offers", status_code=201)
def create_offer(customer_id: int, offer: OfferCreate, db: Session = Depends(get_db)):
    customer = db.query(models.Customer).filter(models.Customer.id == customer_id).first()
    if not customer:
        raise HTTPException(status_code=404, detail="Customer not found")
        
    db_offer = models.Offer(
        customer_id=customer_id,
        lender=offer.lender,
        amount=offer.amount,
        interest_rate=offer.interest_rate,
        tenure_months=offer.tenure_months,
        min_score_required=offer.min_score_required,
        status="pending"
    )
    db.add(db_offer)
    db.commit()
    db.refresh(db_offer)
    return {
        "id": db_offer.id,
        "lender": db_offer.lender,
        "status": db_offer.status
    }

# 7. GET /customers/:id/offers — List offers, score-gated
@app.get("/customers/{customer_id}/offers")
def get_offers(
    customer_id: int, 
    locked: Optional[bool] = Query(None), 
    db: Session = Depends(get_db)
):
    customer = db.query(models.Customer).filter(models.Customer.id == customer_id).first()
    if not customer:
        raise HTTPException(status_code=404, detail="Customer not found")
        
    offers = db.query(models.Offer).filter(models.Offer.customer_id == customer_id).all()
    cibil = customer.cibil_score if customer.cibil_score is not None else 0
    
    result = []
    for offer in offers:
        is_locked = cibil < offer.min_score_required
        score_gap = max(0, offer.min_score_required - cibil)
        
        # Filter logic
        if locked is not None and is_locked != locked:
            continue
            
        # EMI estimation
        p = offer.amount
        r = offer.interest_rate / 12 / 100
        n = offer.tenure_months
        if r > 0:
            emi = (p * r * ((1 + r) ** n)) / (((1 + r) ** n) - 1)
        else:
            emi = p / n
            
        result.append({
            "id": offer.id,
            "lender": offer.lender,
            "amount": offer.amount,
            "interest_rate": offer.interest_rate,
            "tenure_months": offer.tenure_months,
            "min_score_required": offer.min_score_required,
            "status": offer.status,
            "locked": is_locked,
            "score_gap": score_gap,
            "emi": round(emi, 2)
        })
        
    return result

# 8. PATCH /offers/:id/status — Transition offer status
@app.patch("/offers/{offer_id}/status")
def transition_offer_status(offer_id: int, payload: dict, db: Session = Depends(get_db)):
    new_status = payload.get("status")
    if not new_status:
        raise HTTPException(status_code=422, detail="Missing 'status' in payload")
        
    offer = db.query(models.Offer).filter(models.Offer.id == offer_id).first()
    if not offer:
        raise HTTPException(status_code=404, detail="Offer not found")
        
    # Get associated customer cibil_score
    customer = db.query(models.Customer).filter(models.Customer.id == offer.customer_id).first()
    cibil = customer.cibil_score if customer else 0
    is_locked = cibil < offer.min_score_required
    
    current_status = offer.status
    
    # Validation transitions
    # Valid transitions: pending -> active -> disbursed
    valid = False
    if current_status == "pending" and new_status == "active":
        # Check locked constraint when moving to active
        if is_locked:
            raise HTTPException(
                status_code=422,
                detail={
                    "error": f"Offer is locked. Customer score {cibil} is below required {offer.min_score_required}.",
                    "code": "OFFER_LOCKED"
                }
            )
        valid = True
    elif current_status == "active" and new_status == "disbursed":
        valid = True
        
    if not valid:
        raise HTTPException(
            status_code=422,
            detail={
                "error": f"Invalid status transition from {current_status} to {new_status}.",
                "code": "INVALID_STATUS_TRANSITION"
            }
        )
        
    offer.status = new_status
    db.commit()
    db.refresh(offer)
    return {
        "id": offer.id,
        "lender": offer.lender,
        "status": offer.status
    }

# 9. GET /offers/:id/emi — Calculate EMI (no DB write)
@app.get("/offers/{offer_id}/emi")
def calculate_emi(offer_id: int, db: Session = Depends(get_db)):
    offer = db.query(models.Offer).filter(models.Offer.id == offer_id).first()
    if not offer:
        raise HTTPException(status_code=404, detail="Offer not found")
        
    p = offer.amount
    r = offer.interest_rate / 12 / 100
    n = offer.tenure_months
    
    if r > 0:
        monthly_emi = (p * r * ((1 + r) ** n)) / (((1 + r) ** n) - 1)
    else:
        monthly_emi = p / n
        
    return {
        "offer_id": offer.id,
        "principal": offer.amount,
        "interest_rate": offer.interest_rate,
        "tenure_months": offer.tenure_months,
        "monthly_emi": round(monthly_emi, 2)
    }

# 10. GET /customers/:id/improvement-summary (Bonus)
@app.get("/customers/{customer_id}/improvement-summary")
def get_improvement_summary(customer_id: int, db: Session = Depends(get_db)):
    customer = db.query(models.Customer).filter(models.Customer.id == customer_id).first()
    if not customer:
        raise HTTPException(status_code=404, detail="Customer not found")
        
    resolved_gaps = db.query(models.CreditGap).filter(
        models.CreditGap.customer_id == customer_id,
        models.CreditGap.status == "resolved"
    ).all()
    
    open_gaps = db.query(models.CreditGap).filter(
        models.CreditGap.customer_id == customer_id,
        models.CreditGap.status == "open"
    ).all()
    
    recovered = sum(g.estimated_score_gain for g in resolved_gaps)
    remaining = sum(g.estimated_score_gain for g in open_gaps)
    
    cibil = customer.cibil_score if customer.cibil_score is not None else 0
    
    return {
        "customer_id": customer.id,
        "resolved_gaps_count": len(resolved_gaps),
        "total_score_points_recovered": recovered,
        "remaining_potential_score_gain": remaining,
        "projected_potential_score": cibil + remaining
    }

# 11. POST /analyse (Bonus rule engine endpoint)
@app.post("/analyse")
async def analyse_rules(request: Request):
    try:
        body = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail={"error": "Malformed JSON body", "code": "MALFORMED_JSON"})
        
    mode = body.get("mode")
    if not mode or mode not in ("gap_analysis", "eligibility"):
        raise HTTPException(status_code=422, detail={"error": "Field 'mode' must be 'gap_analysis' or 'eligibility'", "code": "INVALID_MODE"})
        
    # Read rules.yaml
    rules_path = os.path.join(parent_dir, 'rule_engine', 'rules.yaml')
    if not os.path.exists(rules_path):
        raise HTTPException(status_code=500, detail={"error": "Rules YAML file not found", "code": "CONFIG_NOT_FOUND"})
        
    try:
        with open(rules_path, 'r') as f:
            rules = yaml.safe_load(f)
    except Exception as e:
        raise HTTPException(status_code=500, detail={"error": f"Failed to parse rules YAML: {str(e)}", "code": "INVALID_CONFIG"})
        
    try:
        if mode == "gap_analysis":
            output = run_gap_analysis(rules, body)
        else:
            output = run_eligibility_evaluation(rules, body)
        return output
    except KeyError as ke:
        raise HTTPException(
            status_code=422,
            detail={"error": f"Missing required field in input: '{ke.args[0]}'", "code": "MISSING_INPUT_FIELD"}
        )
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail={"error": f"Rule evaluation error: {str(e)}", "code": "RULE_ENGINE_ERROR"}
        )

# 12. POST /customers/:id/evaluate (Automated credit evaluation)
@app.post("/customers/{customer_id}/evaluate")
def evaluate_customer(customer_id: int, data: EvaluateRequest, db: Session = Depends(get_db)):
    customer = db.query(models.Customer).filter(models.Customer.id == customer_id).first()
    if not customer:
        raise HTTPException(status_code=404, detail="Customer not found")
        
    # Read rules.yaml
    rules_path = os.path.join(parent_dir, 'rule_engine', 'rules.yaml')
    if not os.path.exists(rules_path):
        raise HTTPException(status_code=500, detail={"error": "Rules YAML file not found", "code": "CONFIG_NOT_FOUND"})
        
    try:
        with open(rules_path, 'r') as f:
            rules = yaml.safe_load(f)
    except Exception as e:
        raise HTTPException(status_code=500, detail={"error": f"Failed to parse rules YAML: {str(e)}", "code": "INVALID_CONFIG"})
        
    # Prepare input for gap analysis
    input_data = data.dict()
    input_data['customer_id'] = customer_id
    
    # Run gap analysis
    try:
        gap_report = run_gap_analysis(rules, input_data)
    except Exception as e:
        raise HTTPException(status_code=500, detail={"error": f"Gap analysis error: {str(e)}", "code": "RULE_ENGINE_ERROR"})
        
    # Delete existing open gaps for this customer
    db.query(models.CreditGap).filter(
        models.CreditGap.customer_id == customer_id,
        models.CreditGap.status == "open"
    ).delete()
    
    # Insert new open gaps from gap analysis
    gap_rules_dict = {r['id']: r for r in rules.get('gap_rules', [])}
    
    new_gaps = []
    for g in gap_report.get('gaps', []):
        rule_def = gap_rules_dict.get(g['id'], {})
        field_name = rule_def.get('field', 'Credit utilization')
        factor_title = field_name.replace('_', ' ').capitalize()
        
        # Construct current and ideal values dynamically
        val = input_data.get(field_name, "")
        current_str = f"{val}%" if "pct" in field_name else str(val)
        ideal_str = f"below {rule_def.get('value')}%" if "pct" in field_name else f"0 missed" if "missed" in field_name else f"36+ months" if "age" in field_name else f"0 accounts" if "written_off" in field_name else "ideal"
        
        # Override with exact seed conventions if preferred
        if g['id'] == 'high_utilisation':
            factor_title = "Credit utilisation"
            current_str = f"{val}%"
            ideal_str = "below 30%"
        elif g['id'] == 'missed_payments':
            factor_title = "Missed EMI"
            current_str = f"{val} missed in 12m"
            ideal_str = "0 missed"
        elif g['id'] == 'written_off_account':
            factor_title = "Written-off accounts"
            current_str = f"{val} accounts"
            ideal_str = "0 accounts"
        elif g['id'] == 'short_credit_age':
            factor_title = "Credit age"
            current_str = f"{round(val / 12, 1)} years"
            ideal_str = "3+ years"
        elif g['id'] == 'too_many_enquiries':
            factor_title = "Credit enquiries"
            current_str = f"{val} hard enquiries"
            ideal_str = "3 or fewer"

        db_gap = models.CreditGap(
            customer_id=customer_id,
            factor=factor_title,
            current_value=current_str,
            ideal_value=ideal_str,
            impact=g['impact'],
            estimated_score_gain=g['estimated_score_gain'],
            action_description=g['action'],
            status="open"
        )
        db.add(db_gap)
        new_gaps.append(db_gap)
        
    db.commit()
    
    # Recalculate CIBIL score based on open gaps
    open_gaps = db.query(models.CreditGap).filter(
        models.CreditGap.customer_id == customer_id,
        models.CreditGap.status == "open"
    ).all()
    
    total_deductions = sum(og.estimated_score_gain for og in open_gaps)
    new_cibil_score = max(300, 850 - total_deductions)
    
    customer.cibil_score = new_cibil_score
    customer.score_fetched_at = datetime.datetime.utcnow()
    db.commit()
    db.refresh(customer)
    
    # Now run eligibility with the new CIBIL score included
    input_data['cibil_score'] = customer.cibil_score
    try:
        eligibility_report = run_eligibility_evaluation(rules, input_data)
    except Exception as e:
        raise HTTPException(status_code=500, detail={"error": f"Eligibility evaluation error: {str(e)}", "code": "RULE_ENGINE_ERROR"})
        
    # Also fetch gated offers
    offers_res = get_offers(customer_id=customer_id, locked=None, db=db)
    
    return {
        "customer_id": customer.id,
        "name": customer.name,
        "cibil_score": customer.cibil_score,
        "score_fetched_at": customer.score_fetched_at.isoformat() + "Z",
        "eligibility": {
            "eligible": eligibility_report.get("eligible"),
            "risk_score": eligibility_report.get("risk_score"),
            "fail_reasons": eligibility_report.get("fail_reasons"),
            "rules": eligibility_report.get("rules"),
            "next_step": eligibility_report.get("next_step")
        },
        "gaps_found": len(new_gaps),
        "total_potential_score_gain": sum(g.estimated_score_gain for g in new_gaps),
        "potential_score": customer.cibil_score + sum(g.estimated_score_gain for g in new_gaps),
        "offers": offers_res
    }
