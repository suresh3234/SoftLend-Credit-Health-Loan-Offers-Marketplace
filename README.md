# SoftLend — Credit Health & Loan Offers Marketplace

[![FastAPI](https://img.shields.io/badge/FastAPI-005571?style=flat&logo=fastapi)](https://fastapi.tiangolo.com/)
[![React](https://img.shields.io/badge/React-20232A?style=flat&logo=react&logoColor=61DAFB)](https://react.dev/)
[![SQLite](https://img.shields.io/badge/SQLite-07405E?style=flat&logo=sqlite&logoColor=white)](https://sqlite.org/)
[![Pytest](https://img.shields.io/badge/Pytest-0A9EDC?style=flat&logo=pytest&logoColor=white)](https://docs.pytest.org/)
[![Python](https://img.shields.io/badge/Python-3776AB?style=flat&logo=python&logoColor=white)](https://www.python.org/)

Welcome to **SoftLend**! SoftLend is an integrated, end-to-end credit assessment and fintech marketplace monorepo. It features a config-driven credit rules engine, a FastAPI/SQLAlchemy/SQLite backend REST API, and an interactive glassmorphism dashboard built in React.

The platform simulates how credit bureau metrics impact a customer's CIBIL score, guides customers through resolving credit gaps, gates loan offers based on real-time score criteria, and provides interactive tools such as a loan EMI simulator.

---

## 📂 Project Architecture

```
softlend/
├── backend/
│   ├── database.py              # SQLite connection pool and session engine
│   ├── main.py                  # FastAPI server, schemas, middleware, and routers
│   ├── models.py                # SQLAlchemy database schema models
│   ├── seed.py                  # Database initialization and sample data seeder
│   ├── test_main.py             # Pytest REST API integration suite
│   ├── migrations/
│   │   ├── 001_init.sql         # SQL schema migration definition
│   │   └── migrate.py           # Database migration runner script
│   └── postman_collection.json  # Preconfigured Postman API collection
├── frontend/
│   ├── src/
│   │   ├── components/
│   │   │   ├── Dashboard.jsx    # SVG score gauge, credit factor list, and simulator
│   │   │   ├── Navbar.jsx       # Header navigation component
│   │   │   └── OffersList.jsx   # Search, filters, loan cards, and modal EMI calculator
│   │   ├── App.jsx              # Global state manager and API connectivity
│   │   ├── App.module.css       # Skeletons, transitions, and toast style rules
│   │   └── index.css            # Typography (Outfit/Inter) and theme variables
│   └── package.json             # React application dependencies
└── rule_engine/
    ├── rules.yaml               # Config-driven rules (gap analysis and eligibility weights)
    ├── engine.py                # Core Python evaluator and CLI interpreter
    └── test_engine.py           # Unit tests validating key engine behaviors
```

---

## 🛠️ 1. Core Component Breakdown

### A. Configurable Rule Engine (`/rule_engine`)
A YAML-configured credit assessment engine (`rules.yaml`) designed to interpret credit parameters and calculate customer metrics.
* **Gap Analysis**: Triggers action steps when a customer's metrics exceed acceptable ranges (e.g. credit utilization > 30%).
* **Eligibility Evaluator**: Applies AND/OR logic constraints to grade a customer's profile, calculating a risk score using weights assigned to rules.
* **Operators Supported**: `gte` (>=), `lte` (<=), `gt` (>), `lt` (<), `eq` (==), `between` (range), `in` (list inclusion), and `lte_multiplier` (comparative validation based on multiplier fields).

### B. REST API Backend (`/backend`)
A FastAPI application connected to a SQLite database. Features:
* **Structured Logging**: Built-in HTTP logging providing method, path, status codes, and latencies.
* **Input Normalization**: Trims and capitalizes PAN identifiers to uppercase and cleanses phone numbers of common symbols/spaces automatically.
* **Database Consistency**: Automatically increments the customer's score in the database upon resolving a credit gap.
* **Automated Credit Evaluation API**: Dynamically assess a customer's financial health, record their credit gaps, recalculate their CIBIL score, and evaluate overall eligibility.

### C. Dashboard Frontend (`/frontend`)
An interactive React single-page dashboard designed using CSS Modules and premium glassmorphism layouts.
* **CIBIL Score Gauge**: An animated SVG dial displaying current score and potential improvements.
* **What-If Simulator**: Toggle credit gaps to preview score gains and see gated loan offers unlock in real-time.
* **EMI Calculator**: A visual slider-driven loan principal, tenure, and interest calculator.
* **Interactive Gaps**: Resolve issues directly on-screen to persist results in the backend database.

---

## ⚡ 2. Getting Started

### Prerequisites
* Python 3.10+
* Node.js 18+

### Setup the Backend REST API
1. Navigate to the backend directory and install dependencies:
   ```bash
   pip install -r backend/requirements.txt
   ```
2. Apply the database migrations to initialize SQLite:
   ```bash
   python backend/migrations/migrate.py
   ```
3. Seed the database with demo accounts (e.g., Ravi Kumar, sample gaps, and offers):
   ```bash
   python backend/seed.py
   ```
4. Start the FastAPI development server:
   ```bash
   python -m uvicorn backend.main:app --reload
   ```
   The interactive API docs will be available at `http://localhost:8000/docs`.

### Setup the Frontend Dashboard
1. Navigate to the frontend directory and install Node packages:
   ```bash
   cd frontend
   npm install
   ```
2. Start the React frontend server:
   ```bash
   npm start
   ```
3. Open `http://localhost:5173` in your browser.

---

## 🔌 3. API Documentation & Integration

### Primary Endpoints

| Method | Endpoint | Description |
| :--- | :--- | :--- |
| `POST` | `/customers` | Register a new customer (validates PAN and normalizes mobile) |
| `POST` | `/customers/{id}/credit-score` | Manually update a customer's CIBIL score |
| `GET` | `/customers/{id}/credit-profile` | Fetch customer info, open/resolved gaps, and potential score |
| `POST` | `/customers/{id}/credit-gaps` | Add a new credit gap to a customer |
| `PATCH` | `/credit-gaps/{id}/resolve` | Resolve a gap and automatically update the customer's CIBIL score |
| `POST` | `/customers/{id}/offers` | Create a new gated loan offer |
| `GET` | `/customers/{id}/offers` | List offers (supports `locked` filter query parameter) |
| `PATCH` | `/offers/{id}/status` | Transition offer status (`pending` -> `active` -> `disbursed`) |
| `GET` | `/offers/{id}/emi` | Calculate principal and monthly EMI |
| `POST` | `/customers/{id}/evaluate` | **[New]** Automatically run rule engine, seed gaps, update score, and evaluate eligibility |
| `POST` | `/analyse` | Run raw Rule Engine evaluations (Gap Analysis or Eligibility check) |

### [New] Automated Credit Evaluation Flow

You can evaluate any customer by sending their raw financial parameters to:
`POST /customers/{customer_id}/evaluate`

#### Request Payload Example:
```json
{
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
}
```

#### Response Payload Example:
```json
{
  "customer_id": 1,
  "name": "Ravi Kumar",
  "cibil_score": 770,
  "score_fetched_at": "2026-06-24T15:15:30Z",
  "eligibility": {
    "eligible": true,
    "risk_score": 0.0,
    "fail_reasons": [],
    "rules": [
      { "rule": "age", "passed": true },
      { "rule": "cibil_score", "passed": true }
    ],
    "next_step": "Proceed with loan disbursement."
  },
  "gaps_found": 4,
  "total_potential_score_gain": 80,
  "potential_score": 850,
  "offers": [
    {
      "id": 1,
      "lender": "HDFC Bank",
      "amount": 500000.0,
      "interest_rate": 10.5,
      "tenure_months": 36,
      "locked": false,
      "score_gap": 0,
      "emi": 16252.79
    }
  ]
}
```

---

## 🧪 4. Testing & Verification

A robust suite of automated tests ensures that both backend routing and rule logic operate flawlessly.

### Running Backend API Integration Tests
The backend features integration tests inside `backend/test_main.py` using `pytest`. They execute on an in-memory SQLite database connection:
```bash
python -m pytest backend/test_main.py -v
```

### Running Rule Engine CLI Tests
Unit tests validating Rule Engine configurations, calculations, weights, and logic bounds can be executed using:
```bash
python rule_engine/test_engine.py
```
