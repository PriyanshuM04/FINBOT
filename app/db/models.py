from sqlalchemy import Column, Integer, String, Float, DateTime, Boolean, ForeignKey, Enum
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.db.database import Base
import enum


class CategoryEnum(str, enum.Enum):
    food        = "Food"
    travel      = "Travel"
    shopping    = "Shopping"
    medicine    = "Medicine"
    entertainment = "Entertainment"
    utilities   = "Utilities"
    other       = "Other"


class User(Base):
    __tablename__ = "users"

    id            = Column(Integer, primary_key=True, index=True)
    phone_number  = Column(String(50), unique=True, nullable=False, index=True)
    name          = Column(String(100), nullable=True)
    created_at    = Column(DateTime(timezone=True), server_default=func.now())
    is_active     = Column(Boolean, default=True)

    transactions  = relationship("Transaction", back_populates="user")
    merchants     = relationship("Merchant", back_populates="user")
    budgets       = relationship("Budget", back_populates="user")


class Merchant(Base):
    __tablename__ = "merchants"

    id            = Column(Integer, primary_key=True, index=True)
    user_id       = Column(Integer, ForeignKey("users.id"), nullable=False)
    upi_id        = Column(String(255), nullable=False)       # raw UPI ID e.g. shyamlal@paytm
    nickname      = Column(String(100), nullable=True)        # user-given name e.g. "Chai wala"
    category      = Column(Enum(CategoryEnum), nullable=False)
    appearance_count = Column(Integer, default=1)
    is_permanent  = Column(Boolean, default=False)            # promoted from cache to DB
    created_at    = Column(DateTime(timezone=True), server_default=func.now())
    updated_at    = Column(DateTime(timezone=True), onupdate=func.now())

    user          = relationship("User", back_populates="merchants")
    transactions  = relationship("Transaction", back_populates="merchant")


class Transaction(Base):
    __tablename__ = "transactions"

    id            = Column(Integer, primary_key=True, index=True)
    user_id       = Column(Integer, ForeignKey("users.id"), nullable=False)
    merchant_id   = Column(Integer, ForeignKey("merchants.id"), nullable=True)  # null for cash
    amount        = Column(Float, nullable=False)
    category      = Column(Enum(CategoryEnum), nullable=False)
    description   = Column(String(255), nullable=True)        # e.g. "pav bhaji", "auto"
    source        = Column(String(50), nullable=False)        # "text", "upi_screenshot", "bill", "pdf"
    raw_input     = Column(String(500), nullable=True)        # original message user sent
    transaction_at = Column(DateTime(timezone=True), nullable=True)  # actual txn time if known
    created_at    = Column(DateTime(timezone=True), server_default=func.now())

    user          = relationship("User", back_populates="transactions")
    merchant      = relationship("Merchant", back_populates="transactions")


class Budget(Base):
    __tablename__ = "budgets"

    id            = Column(Integer, primary_key=True, index=True)
    user_id       = Column(Integer, ForeignKey("users.id"), nullable=False)
    category      = Column(Enum(CategoryEnum), nullable=False)
    monthly_limit = Column(Float, nullable=False)
    created_at    = Column(DateTime(timezone=True), server_default=func.now())
    updated_at    = Column(DateTime(timezone=True), onupdate=func.now())

    user          = relationship("User", back_populates="budgets")
