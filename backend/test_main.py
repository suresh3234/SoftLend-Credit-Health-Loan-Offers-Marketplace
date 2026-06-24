import os
import sys
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

# Add current and parent directories to sys.path
backend_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(backend_dir)
if backend_dir not in sys.path:
    sys.path.append(backend_dir)
if parent_dir not in sys.path:
    sys.path.append(parent_dir)

import models
from database import Base, get_db
from main import app

# In-memory SQLite with StaticPool to keep the database alive across connections
SQLALCHEMY_DATABASE_URL = "sqlite:///:memory:"
engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

@pytest.fixture(name="db_session")
def fixture_db_session():
    # Create tables
    Base.metadata.create_all(bind=engine)
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()
        # Clean up tables
        Base.metadata.drop_all(bind=engine)

@pytest.fixture(name="client")
def fixture_client(db_session):
    def override_get_db():
        try:
            yield db_session
        finally:
            pass
    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()

def test_create_customer(client):
    # Success case
    response = client.post("/customers", json={
        "name": "Jane Doe",
        "mobile": "9998887776",
        "pan": "ABCDE1234F"
    })
    assert response.status_code == 201
    data = response.json()
    assert data["name"] == "Jane Doe"
    assert data["mobile"] == "9998887776"
    assert "id" in data

    # Duplicate mobile case
    response2 = client.post("/customers", json={
        "name": "Another Doe",
        "mobile": "9998887776",
        "pan": "ABCDE1234F"
    })
    assert response2.status_code == 409
    assert response2.json()["code"] == "MOBILE_ALREADY_EXISTS"

    # Validation: invalid mobile format
    response_invalid_mob = client.post("/customers", json={
        "name": "Jane Doe",
        "mobile": "99988877",  # too short
        "pan": "ABCDE1234F"
    })
    assert response_invalid_mob.status_code == 422

    # Validation: invalid PAN format
    response_invalid_pan = client.post("/customers", json={
        "name": "Jane Doe",
        "mobile": "9998887776",
        "pan": "invalidpan"
    })
    assert response_invalid_pan.status_code == 422

def test_create_customer_normalization(client):
    response = client.post("/customers", json={
        "name": "John Doe",
        "mobile": " 999-888-7776 ",  # formatted phone number with spaces and symbols
        "pan": " abcde1234f "       # lowercase and trailing spaces
    })
    assert response.status_code == 201
    data = response.json()
    assert data["mobile"] == "9998887776"  # normalized

    # Verify normalization fetched via profile
    profile = client.get(f"/customers/{data['id']}/credit-profile").json()
    assert profile["name"] == "John Doe"

def test_update_credit_score(client):
    # Create customer
    c_res = client.post("/customers", json={"name": "Alice", "mobile": "9000000000", "pan": "ABCDE1234Z"})
    c_id = c_res.json()["id"]

    # Update score
    res = client.post(f"/customers/{c_id}/credit-score", json={"cibil_score": 750})
    assert res.status_code == 200
    data = res.json()
    assert data["cibil_score"] == 750
    assert "score_fetched_at" in data

    # Verify score fetched via profile
    profile = client.get(f"/customers/{c_id}/credit-profile").json()
    assert profile["cibil_score"] == 750

def test_resolve_gap_increases_score(client):
    # Create customer with starting score 600
    c_res = client.post("/customers", json={"name": "Bob", "mobile": "9111111111", "pan": "ABCDE1234Z"})
    c_id = c_res.json()["id"]
    client.post(f"/customers/{c_id}/credit-score", json={"cibil_score": 600})

    # Add credit gap with estimated gain 40
    gap_res = client.post(f"/customers/{c_id}/credit-gaps", json={
        "factor": "Credit age",
        "current_value": "12 months",
        "ideal_value": "36 months",
        "impact": "medium",
        "estimated_score_gain": 40,
        "action_description": "Keep oldest card open"
    })
    assert gap_res.status_code == 201
    gap_id = gap_res.json()["id"]

    # Resolve gap
    resolve_res = client.patch(f"/credit-gaps/{gap_id}/resolve")
    assert resolve_res.status_code == 200
    assert resolve_res.json()["status"] == "resolved"

    # Verify customer CIBIL score increased by 40 to 640
    profile = client.get(f"/customers/{c_id}/credit-profile").json()
    assert profile["cibil_score"] == 640

def test_resolve_gap_caps_score(client):
    c_res = client.post("/customers", json={"name": "Charlie", "mobile": "9222222222", "pan": "ABCDE1234Z"})
    c_id = c_res.json()["id"]
    client.post(f"/customers/{c_id}/credit-score", json={"cibil_score": 880})

    gap_res = client.post(f"/customers/{c_id}/credit-gaps", json={
        "factor": "Written-off accounts",
        "current_value": "1 account",
        "ideal_value": "0 accounts",
        "impact": "high",
        "estimated_score_gain": 40,
        "action_description": "Settle account"
    })
    gap_id = gap_res.json()["id"]

    client.patch(f"/credit-gaps/{gap_id}/resolve")
    profile = client.get(f"/customers/{c_id}/credit-profile").json()
    assert profile["cibil_score"] == 900  # Capped at 900

def test_loan_offers_gating(client):
    # Customer with score 620
    c_res = client.post("/customers", json={"name": "Dan", "mobile": "9333333333", "pan": "ABCDE1234Z"})
    c_id = c_res.json()["id"]
    client.post(f"/customers/{c_id}/credit-score", json={"cibil_score": 620})

    # Create two offers
    off1 = client.post(f"/customers/{c_id}/offers", json={
        "lender": "Lender A", "amount": 100000, "interest_rate": 12.0, "tenure_months": 12, "min_score_required": 600
    }).json()
    off2 = client.post(f"/customers/{c_id}/offers", json={
        "lender": "Lender B", "amount": 200000, "interest_rate": 10.0, "tenure_months": 24, "min_score_required": 700
    }).json()

    # Get offers list
    offers = client.get(f"/customers/{c_id}/offers").json()
    assert len(offers) == 2
    
    # Offer 1 should be unlocked
    o1 = next(o for o in offers if o["id"] == off1["id"])
    assert o1["locked"] is False
    assert o1["score_gap"] == 0

    # Offer 2 should be locked
    o2 = next(o for o in offers if o["id"] == off2["id"])
    assert o2["locked"] is True
    assert o2["score_gap"] == 80

    # Verify locked filter parameter
    unlocked_only = client.get(f"/customers/{c_id}/offers?locked=false").json()
    assert len(unlocked_only) == 1
    assert unlocked_only[0]["id"] == off1["id"]

    locked_only = client.get(f"/customers/{c_id}/offers?locked=true").json()
    assert len(locked_only) == 1
    assert locked_only[0]["id"] == off2["id"]

def test_offer_transitions(client):
    # Customer score 620
    c_res = client.post("/customers", json={"name": "Eve", "mobile": "9444444444", "pan": "ABCDE1234Z"})
    c_id = c_res.json()["id"]
    client.post(f"/customers/{c_id}/credit-score", json={"cibil_score": 620})

    # Unlocked offer
    off_unlocked = client.post(f"/customers/{c_id}/offers", json={
        "lender": "Lender A", "amount": 100000, "interest_rate": 12.0, "tenure_months": 12, "min_score_required": 600
    }).json()
    
    # Locked offer
    off_locked = client.post(f"/customers/{c_id}/offers", json={
        "lender": "Lender B", "amount": 200000, "interest_rate": 10.0, "tenure_months": 24, "min_score_required": 700
    }).json()

    # Try accepting locked offer -> should fail with OFFER_LOCKED
    res_fail = client.patch(f"/offers/{off_locked['id']}/status", json={"status": "active"})
    assert res_fail.status_code == 422
    assert res_fail.json()["code"] == "OFFER_LOCKED"

    # Accept unlocked offer -> should succeed
    res_ok = client.patch(f"/offers/{off_unlocked['id']}/status", json={"status": "active"})
    assert res_ok.status_code == 200
    assert res_ok.json()["status"] == "active"

    # Disburse -> should succeed
    res_disbursed = client.patch(f"/offers/{off_unlocked['id']}/status", json={"status": "disbursed"})
    assert res_disbursed.status_code == 200
    assert res_disbursed.json()["status"] == "disbursed"

    # Try invalid transition
    res_inv = client.patch(f"/offers/{off_unlocked['id']}/status", json={"status": "active"})
    assert res_inv.status_code == 422
    assert res_inv.json()["code"] == "INVALID_STATUS_TRANSITION"

def test_emi_calculation(client):
    c_res = client.post("/customers", json={"name": "Frank", "mobile": "9555555555", "pan": "ABCDE1234Z"})
    c_id = c_res.json()["id"]

    off = client.post(f"/customers/{c_id}/offers", json={
        "lender": "Lender A", "amount": 100000, "interest_rate": 12.0, "tenure_months": 12, "min_score_required": 600
    }).json()

    res = client.get(f"/offers/{off['id']}/emi")
    assert res.status_code == 200
    data = res.json()
    assert data["offer_id"] == off["id"]
    assert data["monthly_emi"] > 0

def test_analyse_rules(client):
    # Gap analysis
    res_gap = client.post("/analyse", json={
        "mode": "gap_analysis",
        "credit_utilisation_pct": 45,
        "missed_payments_12m": 1,
        "written_off_accounts": 0,
        "credit_age_months": 24,
        "hard_enquiries_6m": 4
    })
    assert res_gap.status_code == 200
    data_gap = res_gap.json()
    assert data_gap["mode"] == "gap_analysis"
    assert data_gap["gaps_found"] > 0

    # Eligibility analysis
    res_el = client.post("/analyse", json={
        "mode": "eligibility",
        "age": 30,
        "cibil_score": 620,
        "foir": 0.35,
        "employment_type": "salaried",
        "written_off_accounts": 0,
        "requested_amount": 200000.0,
        "monthly_income": 30000.0
    })
    assert res_el.status_code == 200
    data_el = res_el.json()
    assert data_el["mode"] == "eligibility"

def test_evaluate_customer_endpoint(client):
    # Create customer
    c_res = client.post("/customers", json={"name": "Grace", "mobile": "9666666666", "pan": "ABCDE1234Z"})
    c_id = c_res.json()["id"]

    # Seed an offer
    client.post(f"/customers/{c_id}/offers", json={
        "lender": "Lender Test", "amount": 100000, "interest_rate": 12.0, "tenure_months": 12, "min_score_required": 650
    })

    # Evaluate financials
    eval_res = client.post(f"/customers/{c_id}/evaluate", json={
        "age": 30,
        "monthly_income": 50000.0,
        "requested_amount": 200000.0,
        "employment_type": "salaried",
        "foir": 0.35,
        "credit_utilisation_pct": 45,
        "missed_payments_12m": 1,
        "written_off_accounts": 0,
        "credit_age_months": 24,
        "hard_enquiries_6m": 4
    })
    assert eval_res.status_code == 200
    data = eval_res.json()
    assert data["customer_id"] == c_id
    assert data["cibil_score"] == 770
    assert data["gaps_found"] == 4
    assert data["total_potential_score_gain"] == 80
    assert data["potential_score"] == 850
    assert data["eligibility"]["eligible"] is True

    # Checking database gaps directly
    profile = client.get(f"/customers/{c_id}/credit-profile").json()
    assert len(profile["gaps"]) == 4
    assert profile["open_gaps"] == 4
