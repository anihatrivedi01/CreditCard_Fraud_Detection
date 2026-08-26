# ARGUS — Credit Card Fraud Detection

ARGUS is an end-to-end credit card fraud detection project that predicts the fraud probability of a transaction and classifies it as legitimate or potentially fraudulent.

I built this project because I wanted to work with a real-world problem involving highly imbalanced data and learn how to take an ML model beyond a notebook and turn it into a working application.

The application also shows risk factors associated with a transaction and stores transaction history so that recent card activity can be used during fraud assessment.

## Live Demo

**Frontend:** https://argus-fraud-intelligence.netlify.app

## Why I Built This

I chose credit card fraud detection because I wanted to learn how to deal with real-world imbalanced data.

Fraud detection is a problem where fraudulent transactions are much fewer than legitimate transactions, so accuracy alone is not enough to judge whether a model is actually useful.

This project gave me the opportunity to work through the complete process:

1. Dataset
2. Data preprocessing
3. Feature engineering
4. Imbalanced data handling
5. Model training & tuning
6. FastAPI backend
7. PostgreSQL database
8. Frontend
9. Cloud deployment

## What ARGUS Does

ARGUS takes transaction information such as:

- Card ID
- Transaction amount
- Cardholder age
- Merchant category
- Foreign transaction
- Location mismatch
- Device trust score

and returns:

- Fraud probability
- Fraud / Legitimate classification
- Risk factors
- Recommendation
- Card status
- 24-hour transaction velocity

The transaction is also stored in the database so that the card's transaction history can be viewed later.

## Dataset

The dataset was obtained from Kaggle.

- Rows: **10,000**
- Columns: **10**
- Target: `is_fraud`
- Class distribution: **Highly imbalanced**
- Missing values: **None**
- Duplicate rows: **None**

Because of the class imbalance, I focused more on metrics such as **PR-AUC, precision, recall and F1-score** instead of relying only on accuracy.

## Data Preprocessing

The dataset did not contain missing values or duplicate rows.

The main preprocessing and feature engineering steps included:

- Separating features and target
- Transforming transaction amount
- Binning device trust score
- Encoding categorical features
- Applying a power transformation to numerical features
- Handling class imbalance using SMOTE

### Transaction Amount

One of the problems I noticed was that the transaction amount in the training data was limited to a relatively small range, around ₹0–₹1,500.

To make the model handle larger transaction amounts more reasonably, I created a log-transformed version of the amount:

`amount_log = np.log1p(amount)`

The transformed `amount_log` feature is used by the final model.

### Device Trust Score

Another issue I noticed was the sensitivity of the model to small changes in the device trust score.

For example, a transaction with a trust score around `0.20` could receive a very high fraud probability, while increasing the score to around `0.25–0.35` could cause the predicted probability to drop significantly.

To reduce this sensitivity to small changes, I introduced **device trust score binning**.

The score is converted into bins:

- 0–40
- 40–54
- 54–69
- 69–84
- 84+

The binned feature is then used by the model.

## Model

I used **XGBoost** as the final classifier.

The final training pipeline combines:

ColumnTransformer
↓
Numerical features → PowerTransformer
Categorical features → OneHotEncoder
↓
SMOTE
↓
XGBClassifier
↓
scale_pos_weight

I used both:

- **SMOTE**
- **`scale_pos_weight`**

to handle the class imbalance.

I then used **RandomizedSearchCV** to search for better XGBoost hyperparameters.

The final model was saved as:

`model/final_xgboost_fraud_pipeline.pkl`

## Model Evaluation

Since this is an imbalanced fraud detection problem, **PR-AUC was treated as the primary metric**.

### Test Set Results

| Metric | Score |
|---|---:|
| Accuracy | 0.99 |
| Fraud Precision | 0.64 |
| Fraud Recall | 1.00 |
| Fraud F1-score | 0.78 |
| **PR-AUC** | **0.9831** |
| ROC-AUC | 0.9997 |

### Test Confusion Matrix

1953   17
0      30

The model detected all **30 fraud transactions** in the test set.

There were **17 legitimate transactions incorrectly classified as fraud**.

I also checked the training performance.

### Training Results

- PR-AUC: **0.9972**
- ROC-AUC: **1.0000**

Training confusion matrix:

7867   12
0      121

## Feature Importance

The feature importance analysis showed that several transaction context and behavioral features had a strong influence on the model.

The top features included:

1. `foreign_transaction`
2. `transaction_hour`
3. `location_mismatch`
4. `trust_score_binned`
5. `velocity_last_24h`
6. `merchant_category_Travel`
7. `amount_log`
8. `merchant_category_Clothing`
9. `merchant_category_Food`
10. `merchant_category_Grocery`

This helped me understand that the model was relying heavily on transaction context and behavioral information rather than only the transaction amount.

## Risk Assessment

ARGUS does not only return a binary fraud prediction.

It also generates risk factors based on the transaction.

Examples include:

- Location mismatch
- Foreign transaction
- Low device trust score
- High transaction velocity
- High transaction amount

The application also provides a recommendation based on the predicted fraud probability.

- Probability >= 0.80 → Review transaction immediately
- Probability >= 0.50 → Manual analyst review recommended
- Probability < 0.50 → Transaction appears low risk

## 24-Hour Transaction Velocity

One of the application features is tracking the number of transactions made by a card during the previous 24 hours.

For example:

Card 1001

Previous transactions in 24h: 3
Current transaction: 1

Velocity considered: 4

This information is stored and calculated using the transaction history in PostgreSQL.

The idea was to include some behavioral information instead of treating every transaction completely independently.

## Backend

I used **FastAPI** because I wanted to learn how ML models are served through a backend.

The backend:

1. Receives transaction data from the frontend.
2. Checks the card in the database.
3. Calculates the card's recent transaction velocity.
4. Prepares the features required by the trained model.
5. Runs the XGBoost pipeline.
6. Generates risk factors and a recommendation.
7. Stores the transaction and prediction in PostgreSQL.
8. Sends the result back to the frontend.

### API Endpoints

#### Health Check

`GET /health`

Example response:

`{"status": "healthy"}`

#### Fraud Prediction

`POST /predict`

Returns information such as:

- Fraud probability
- Status
- Card status
- 24-hour velocity
- Risk factors
- Recommendation
- Transaction time

#### Transaction History

`GET /transactions/{card_id}`

Returns the transaction history for a particular card.

## Database

I used **PostgreSQL with Neon**.

The database stores transaction history so that the application can:

- Keep a record of transactions made by users
- Display transaction history
- Calculate activity during the previous 24 hours
- Calculate 24-hour transaction velocity

### Cards

Stores registered cards.

Fields:

- `id`
- `card_id`

### Transactions

Stores transaction and prediction information.

Fields:

- `id`
- `card_id`
- `amount`
- `cardholder_age`
- `merchant_category`
- `foreign_transaction`
- `location_mismatch`
- `device_trust_score`
- `fraud_probability`
- `status`
- `transaction_time`

## Frontend

The frontend is built using:

- HTML
- CSS
- JavaScript

The interface allows the user to enter transaction details and displays:

- Fraud probability
- Fraud / Legitimate verdict
- Risk assessment
- Risk factors
- Recommendation
- Card status
- 24-hour velocity
- Session transaction log
- Transaction history

## Deployment

I deployed the frontend and backend separately.

ARGUS deployment:

1. User
2. Netlify Frontend
3. HTTPS / CORS
4. Vercel FastAPI Backend
5. XGBoost Model + Neon PostgreSQL

### Frontend

Deployed using **Netlify**.

### Backend

FastAPI backend deployed using **Vercel**.

### Database

PostgreSQL hosted using **Neon**.

## Deployment Challenges

Deploying the application was one of the more challenging parts of the project.

Since the frontend and backend were deployed separately, connecting them required dealing with **CORS**.

I initially faced several CORS issues while making requests from the Netlify frontend to the Vercel backend.

I also had to deal with deployment-specific issues such as:

- PostgreSQL connection configuration
- Psycopg driver configuration
- Large Python ML dependencies
- Serverless backend behavior
- Connecting the deployed frontend to the deployed API

Working through these issues helped me understand that deploying an ML project involves much more than just training a model.

## Project Structure

CreditCard_Fraud_Detection/

├── backend/
│   ├── database.py
│   ├── main.py
│   ├── models.py
│   └── schemas.py
│
├── frontend/
│   ├── index.html
│   ├── script.js
│   └── styles.css
│
├── model/
│   └── final_xgboost_fraud_pipeline.pkl
│
├── notebooks/
│   └── ...
│
├── app.py
├── requirements.txt
├── .gitignore
└── README.md

## Running Locally

### 1. Clone the repository

`git clone https://github.com/anihatrivedi01/CreditCard_Fraud_Detection.git`

`cd CreditCard_Fraud_Detection`

### 2. Create a virtual environment

`python -m venv venv`

On Windows:

`venv\Scripts\activate`

### 3. Install dependencies

`pip install -r requirements.txt`

### 4. Configure the database

Create a `.env` file and add your PostgreSQL connection string:

`DATABASE_URL=your_postgresql_connection_string`

Do not commit `.env` to GitHub.

### 5. Start the backend

`uvicorn app:app --reload`

The API will be available at:

`http://127.0.0.1:8000`

Health check:

`http://127.0.0.1:8000/health`

## Limitations

There are still several areas where ARGUS can be improved:

- No authentication yet
- The training dataset could be larger and more diverse
- Serverless cold starts can make the first backend request slower
- Model explanations could be improved further
- The current model is dependent on the distribution of the training data

## Future Improvements

The next things I would like to work on are:

- Add user authentication
- Train using a larger and more diverse dataset
- Improve backend response time
- Add a fraud monitoring dashboard
- Add model monitoring and drift detection
- Add automated model retraining
- Add API testing
- Add CI/CD
- Improve overall production reliability

## What I Learned

The main thing I wanted from this project was to go beyond training a model in a notebook.

While building ARGUS, I worked with:

- Imbalanced classification
- SMOTE
- XGBoost
- Hyperparameter tuning with RandomizedSearchCV
- Feature engineering
- Model evaluation using PR-AUC
- FastAPI
- SQLAlchemy
- PostgreSQL
- REST APIs
- CORS
- Netlify
- Vercel
- Neon
- Deploying an ML model as a working application

The part I am most proud of is getting the ML model into a **working end-to-end application** and deploying the complete system instead of keeping the project limited to a Jupyter notebook.

## Author

**Aniha Trivedi**

Built as an end-to-end machine learning project focused on learning how to handle imbalanced real-world data and deploy an ML model as a working application.
