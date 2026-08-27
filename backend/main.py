import os
import time
import joblib
import numpy as np
import pandas as pd
from datetime import datetime, timedelta, timezone
from sqlalchemy import func

# The model learned transaction_hour from data in the cardholders' local time,
# where 00:00-03:00 carries a 7.3% fraud rate against 0.36% for the rest of the
# day. Vercel runs on UTC, so reading the hour off the server clock scored
# 05:30-09:30 IST -- ordinary Indian morning activity -- as middle-of-the-night.
# Derive the hour in the cardholders' timezone instead of the server's.
LOCAL_TZ = timezone(timedelta(hours=5, minutes=30))  # IST

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
        "https://argus-fraud-intelligence.netlify.app"
    ],
    allow_credentials=False,
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

def classify_risk_tier(fraud_probability):
    """Operational risk taxonomy shown as the verdict and banner text.

    Bands come from the risk matrix:
        0.00 <= P < 0.30   Tier 1: Minimal Risk
        0.30 <= P < 0.40   Tier 2: Low-Moderate Risk
        0.40 <= P < 0.70   Tier 3: Elevated Risk
        0.70 <= P <= 1.00  Tier 4: Critical Risk
    """
    if fraud_probability >= 0.70:
        return (
            "Tier 4: Critical Risk",
            "High-confidence fraud signal detected across multiple model features"
        )

    if fraud_probability >= 0.40:
        return (
            "Tier 3: Elevated Risk",
            "Elevated risk parameters detected; manual risk inspection advised"
        )

    if fraud_probability >= 0.30:
        return (
            "Tier 2: Low-Moderate Risk",
            "Transaction appears predominantly legitimate, but secondary risk factors are present"
        )

    return (
        "Tier 1: Minimal Risk",
        "Transaction parameters align with normal legitimate behavior"
    )
    
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
    total_start = time.perf_counter()
    start = time.perf_counter()

    card = db.query(Card).filter(Card.card_id == transaction.card_id).first()

    card_lookup_time = time.perf_counter() - start

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
    
    start = time.perf_counter()
    velocity_24h = db.query(func.count(TransactionModel.id)).filter(
        TransactionModel.card_id == card.id,
        TransactionModel.transaction_time >= start_time,
        TransactionModel.transaction_time < current_time
    ).scalar()
    velocity_query_time = time.perf_counter() - start
    
    model_warnings = check_model_input_range(transaction, velocity_24h)
    # Cardholder-local hour, not the server's. current_time stays naive so the
    # stored timestamp and the 24h velocity window are unchanged.
    transaction_hour = datetime.now(LOCAL_TZ).hour
    
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
    # These edges must match the training pipeline, which binned this feature
    # with pd.qcut(device_trust_score, q=5) -> quintile edges 25/40/54/69/84/99
    # (see notebooks/final_modeling.ipynb). The previous fixed 20/40/60/80 edges
    # were a train/serve mismatch: they agreed with training on only 42% of rows
    # and cost roughly two thirds of fraud recall.
    input_df['trust_score_binned'] = pd.cut(
        input_df['device_trust_score'],
        bins=[-np.inf, 40, 54, 69, 84, np.inf],
        labels=[0, 1, 2, 3, 4]
    ).astype(int)
    
    clean_input_df = input_df.drop(columns=['amount', 'device_trust_score'])
    
    start = time.perf_counter()

    fraud_probability = float(model.predict_proba(clean_input_df)[0][1])
    fraud_percentage = float(fraud_probability * 100)

    model_prediction_time = time.perf_counter() - start

    risk_factors, recommendation = generate_risk_factors(
        transaction,
        velocity_24h,
        fraud_probability
    )

    risk_tier, tier_message = classify_risk_tier(fraud_probability)

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

    start = time.perf_counter()

    db.add(new_transaction)
    db.commit()
    db.refresh(new_transaction)

    transaction_save_time = time.perf_counter() - start

    return {
        "card_id": transaction.card_id,
        "card_status": card_status,
        "fraud_probability": round(fraud_percentage, 2),
        "status": "Fraud" if fraud_probability >= 0.5 else "Legitimate",
        "velocity_last_24h": velocity_24h,
        "transaction_time": current_time,
        "model_warnings": [],
        "risk_tier": risk_tier,
        "message": tier_message,
        "risk_factors": risk_factors,
        "recommendation": recommendation,
        "debug_timings": {
            "card_lookup": round(card_lookup_time, 3),
            "velocity_query": round(velocity_query_time, 3),
            "model_prediction": round(model_prediction_time, 3),
            "transaction_save": round(transaction_save_time, 3),
            "total": round(time.perf_counter() - total_start, 3)
        }
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