from pydantic import BaseModel


class Transaction(BaseModel):
    card_id: str
    amount: float
    cardholder_age: int
    merchant_category: str
    foreign_transaction: int
    location_mismatch: int
    device_trust_score: float