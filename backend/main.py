import os
import joblib
import numpy as np
import pandas as pd
from datetime import datetime, timedelta
from sqlalchemy import func

from fastapi import FastAPI, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from backend.database import engine, SessionLocal
from backend.schemas import Transaction as TransactionSchema
from backend.models import Base, Card, Transaction as TransactionModel

Base.metadata.create_all(bind=engine)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
MODEL_PATH = os.path.abspath(os.path.join(BASE_DIR, "..", "model", "final_xgboost_fraud_pipeline.pkl"))

if not os.path.exists(MODEL_PATH):
    raise FileNotFoundError(f"Model file not found at: {MODEL_PATH}")

model = joblib.load(MODEL_PATH)

app = FastAPI(title="Credit Card Fraud Detection API", version="1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "https://flourishing-biscuit-0da377.netlify.app"
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

@app.get("/health")
def health_check():
    return {"status": "healthy"}

def generate_risk_factors(transaction, velocity_24h, fraud_probability):
    factors = []

    if transaction.location_mismatch == 1:
        factors.append("Location mismatch detected")

    if transaction.foreign_transaction == 1:
        factors.append("Foreign transaction detected")

    if transaction.device_trust_score < 0.4:
        factors.append("Low device trust score")

    if velocity_24h >= 4:
        factors.append(f"High transaction velocity: {velocity_24h} transactions in 24h")

    if transaction.amount >= 20000:
        factors.append("High transaction amount")

    if not factors:
        factors.append("No major risk indicators detected")

    if fraud_probability >= 0.8:
        recommendation = "Review transaction immediately."
    elif fraud_probability >= 0.5:
        recommendation = "Manual analyst review recommended."
    else:
        recommendation = "Transaction appears low risk."

    return factors, recommendation

def check_model_input_range(transaction, velocity_24h):
    warnings = []

    if transaction.amount > 1471.04:
        warnings.append(
            f"Amount ₹{transaction.amount:,.2f} is outside "
            "the model's training range (₹0–₹1,471.04)."
        )

    if transaction.cardholder_age < 18 or transaction.cardholder_age > 69:
        warnings.append(
            f"Cardholder age {transaction.cardholder_age} is outside "
            "the model's training range (18–69)."
        )

    if velocity_24h > 9:
        warnings.append(
            f"Transaction velocity of {velocity_24h} exceeds "
            "the model's training range (0–9 transactions in 24h)."
        )

    return []

@app.post("/predict")
def predict(transaction: TransactionSchema, db=Depends(get_db)):
    card = db.query(Card).filter(Card.card_id == transaction.card_id).first()

    if not card:
        card = Card(card_id=transaction.card_id)
        db.add(card)
        db.commit()
        db.refresh(card)
        card_status = "New card registered"
    else:
        card_status = "Existing card"
        
    current_time = datetime.now()
    start_time = current_time - timedelta(hours=24)

    velocity_24h = db.query(func.count(TransactionModel.id)).filter(
        TransactionModel.card_id == card.id,
        TransactionModel.transaction_time >= start_time,
        TransactionModel.transaction_time < current_time
    ).scalar()
    
    model_warnings = check_model_input_range(transaction, velocity_24h)
    transaction_hour = current_time.hour
    
    clamped_age = max(18, min(69, transaction.cardholder_age))

    input_data = {
        "amount": transaction.amount,
        "transaction_hour": transaction_hour,
        "foreign_transaction": transaction.foreign_transaction,
        "location_mismatch": transaction.location_mismatch,
        "device_trust_score": transaction.device_trust_score * 100 if transaction.device_trust_score <= 1.0 else transaction.device_trust_score,
        "velocity_last_24h": velocity_24h+1,
        "cardholder_age": clamped_age,
        "merchant_category": transaction.merchant_category
    }
    input_df = pd.DataFrame([input_data])
    
    input_df['amount_log'] = np.log1p(input_df['amount'])
    input_df['trust_score_binned'] = pd.cut(
        input_df['device_trust_score'], 
        bins=[-np.inf, 40.0, 54.0, 69.0, 84.0, np.inf], 
        labels=[0, 1, 2, 3, 4]
    ).astype(int)
    
    clean_input_df = input_df.drop(columns=['amount', 'device_trust_score'])
    
    fraud_probability = float(model.predict_proba(clean_input_df)[0][1])
    fraud_percentage = float(fraud_probability * 100)

    risk_factors, recommendation = generate_risk_factors(
        transaction,
        velocity_24h,
        fraud_probability
    )

    new_transaction = TransactionModel(
        card_id=card.id,
        amount=transaction.amount,
        cardholder_age=transaction.cardholder_age,
        merchant_category=transaction.merchant_category,
        foreign_transaction=transaction.foreign_transaction,
        location_mismatch=transaction.location_mismatch,
        device_trust_score=transaction.device_trust_score,
        fraud_probability=fraud_percentage,
        status="Fraud" if fraud_probability >= 0.5 else "Legitimate",
        transaction_time=current_time
    )

    db.add(new_transaction)
    db.commit()
    db.refresh(new_transaction)

    return {
        "card_id": transaction.card_id,
        "card_status": card_status,
        "fraud_probability": round(fraud_percentage, 2),
        "status": "Fraud" if fraud_probability >= 0.5 else "Legitimate",
        "velocity_last_24h": velocity_24h,
        "transaction_time": current_time,
        "model_warnings": [],
        "message": (
            "Transaction flagged as potentially fraudulent"
            if fraud_probability >= 0.5
            else "Transaction appears legitimate"
        ),
        "risk_factors": risk_factors,
        "recommendation": recommendation
    }

@app.get("/transactions/{card_id}")
def get_transactions(card_id: str, db=Depends(get_db)):
    card = db.query(Card).filter(Card.card_id == card_id).first()

    if not card:
        raise HTTPException(status_code=404, detail="Card not found")

    transactions = db.query(TransactionModel).filter(
        TransactionModel.card_id == card.id
    ).order_by(TransactionModel.transaction_time.desc()).all()

    return [
        {
            "transaction_id": transaction.id,
            "amount": transaction.amount,
            "cardholder_age": transaction.cardholder_age,
            "merchant_category": transaction.merchant_category,
            "foreign_transaction": transaction.foreign_transaction,
            "location_mismatch": transaction.location_mismatch,
            "device_trust_score": transaction.device_trust_score,
            "fraud_probability": transaction.fraud_probability,
            "status": transaction.status,
            "transaction_time": transaction.transaction_time
        }
        for transaction in transactions
    ]    

app.mount(
    "/",
    StaticFiles(directory="frontend", html=True),
    name="frontend"
)