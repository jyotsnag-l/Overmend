# Demo Faulty Target Repository (`demo-repo`)

This repository serves as a live target application for demonstrating the **Autonomous Software Recovery & Trust PaaS**.

It contains realistic Python microservice endpoints with intentional bugs and corresponding test suites:

| Scenario | Fault Type | Faulty File | Trigger Endpoint / Function | Recovery Mechanism |
|---|---|---|---|---|
| **User Profile Lookup** | `NameError` (undefined `profile_db`) | `users.py:5` | `GET /users/1` | AST fault localization + dict mapping fix |
| **Payment Refund** | `ZeroDivisionError` (div by zero) | `payments.py:4` | `GET /payments/refund?amount=100&ratio=0` | Logic edge-case patch + test assertion |
| **Order Total Calculation** | `KeyError` (unhandled discount) | `orders.py:14` | `POST /orders/calculate` | Safe `.get()` fallback + policy check |

---

## Running the Demo App Locally

```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Run the FastAPI application on port 5000
python app.py
```

Any unhandled exception encountered by the application is automatically captured by `RecoveryMiddleware` and ingested into the Autonomous Recovery PaaS control plane at `http://localhost:8000`.
