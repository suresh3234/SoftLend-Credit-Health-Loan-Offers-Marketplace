import datetime
from sqlalchemy import Column, Integer, String, Float, DateTime, ForeignKey, Numeric
from sqlalchemy.orm import relationship
from database import Base

class Customer(Base):
    __tablename__ = "customers"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    name = Column(String(100), nullable=False)
    mobile = Column(String(15), nullable=False, unique=True)
    pan = Column(String(10), nullable=False)
    cibil_score = Column(Integer, default=None, nullable=True)
    score_fetched_at = Column(DateTime, default=None, nullable=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

    gaps = relationship("CreditGap", back_populates="customer", cascade="all, delete-orphan")
    offers = relationship("Offer", back_populates="customer", cascade="all, delete-orphan")

class CreditGap(Base):
    __tablename__ = "credit_gaps"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    customer_id = Column(Integer, ForeignKey("customers.id"), nullable=False)
    factor = Column(String(100), nullable=False)
    current_value = Column(String(100), nullable=False)
    ideal_value = Column(String(100), nullable=False)
    impact = Column(String(20), nullable=False)  # 'high', 'medium', 'low'
    estimated_score_gain = Column(Integer, nullable=False)
    action_description = Column(String, nullable=False)
    status = Column(String(20), default="open")  # 'open', 'resolved'
    resolved_at = Column(DateTime, default=None, nullable=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

    customer = relationship("Customer", back_populates="gaps")

class Offer(Base):
    __tablename__ = "offers"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    customer_id = Column(Integer, ForeignKey("customers.id"), nullable=False)
    lender = Column(String(100), nullable=False)
    amount = Column(Float, nullable=False)
    interest_rate = Column(Float, nullable=False)
    tenure_months = Column(Integer, nullable=False)
    min_score_required = Column(Integer, nullable=False, default=650)
    status = Column(String(20), default="pending")  # 'pending', 'active', 'disbursed'
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

    customer = relationship("Customer", back_populates="offers")
