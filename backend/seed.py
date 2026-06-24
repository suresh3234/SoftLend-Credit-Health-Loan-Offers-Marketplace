import datetime
from database import SessionLocal, engine
import models

def seed_db():
    # Recreate tables to start clean
    models.Base.metadata.drop_all(bind=engine)
    models.Base.metadata.create_all(bind=engine)
    
    db = SessionLocal()
    
    try:
        # 1. Create Customer
        customer = models.Customer(
            id=1,
            name="Ravi Kumar",
            mobile="9876543210",
            pan="ABCDE1234F",
            cibil_score=620,
            score_fetched_at=datetime.datetime.strptime("2024-01-10 00:00:00", "%Y-%m-%d %H:%M:%S")
        )
        db.add(customer)
        db.commit()
        db.refresh(customer)
        print(f"Seeded Customer: {customer.name} (ID: {customer.id})")
        
        # 2. Create Credit Gaps
        gaps = [
            models.CreditGap(
                customer_id=customer.id,
                factor="Credit utilisation",
                current_value="87%",
                ideal_value="below 30%",
                impact="high",
                estimated_score_gain=35,
                action_description="Pay down your HDFC credit card from ₹43,500 to below ₹15,000",
                status="open"
            ),
            models.CreditGap(
                customer_id=customer.id,
                factor="Missed EMI",
                current_value="2 missed in 2023",
                ideal_value="0 missed",
                impact="high",
                estimated_score_gain=25,
                action_description="Clear overdue amount of ₹4,200 on Bajaj Finserv loan",
                status="open"
            ),
            models.CreditGap(
                customer_id=customer.id,
                factor="Credit age",
                current_value="1.2 years",
                ideal_value="3+ years",
                impact="medium",
                estimated_score_gain=10,
                action_description="Avoid closing your oldest credit card — let it age",
                status="open"
            )
        ]
        db.add_all(gaps)
        db.commit()
        print(f"Seeded {len(gaps)} credit gaps.")
        
        # 3. Create Offers
        offers = [
            models.Offer(
                customer_id=customer.id,
                lender="HDFC Bank",
                amount=500000.0,
                interest_rate=10.5,
                tenure_months=36,
                min_score_required=700,
                status="pending"
            ),
            models.Offer(
                customer_id=customer.id,
                lender="Bajaj Finserv",
                amount=300000.0,
                interest_rate=13.0,
                tenure_months=24,
                min_score_required=620,
                status="pending"
            ),
            models.Offer(
                customer_id=customer.id,
                lender="ICICI Bank",
                amount=750000.0,
                interest_rate=11.0,
                tenure_months=48,
                min_score_required=720,
                status="pending"
            )
        ]
        db.add_all(offers)
        db.commit()
        print(f"Seeded {len(offers)} loan offers.")
        
    except Exception as e:
        print(f"Error seeding database: {e}")
        db.rollback()
    finally:
        db.close()

if __name__ == "__main__":
    seed_db()
