from sqlalchemy import Column, Integer, String, Float, DateTime, ForeignKey
from sqlalchemy.orm import relationship

from backend.database import Base


class Card(Base):
    __tablename__ = "cards"

    id = Column(Integer, primary_key=True, index=True)
    card_id = Column(String, unique=True, index=True, nullable=False)

    transactions = relationship("Transaction", back_populates="card")


class Transaction(Base):
    __tablename__ = "transactions"

    id = Column(Integer, primary_key=True, index=True)

    card_id = Column(Integer, ForeignKey("cards.id"), nullable=False)

    amount = Column(Float, nullable=False)
    cardholder_age = Column(Integer, nullable=False)
    merchant_category = Column(String, nullable=False)

    foreign_transaction = Column(Integer, nullable=False)
    location_mismatch = Column(Integer, nullable=False)
    device_trust_score = Column(Float, nullable=False)
    fraud_probability = Column(Float, nullable=False)
    status = Column(String, nullable=False)

    transaction_time = Column(DateTime, nullable=False)

    card = relationship("Card", back_populates="transactions")