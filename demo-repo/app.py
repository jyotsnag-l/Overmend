import os
from fastapi import FastAPI, HTTPException
from recovery_sdk.integrations.fastapi import RecoveryMiddleware
import users
import payments
import orders

app = FastAPI(
    title="Faulty Demo Microservice",
    description="Demo target repository with deliberate runtime error paths to demonstrate Autonomous Recovery & Trust PaaS",
    version="1.0.0"
)

# Attach Recovery SDK Middleware to automatically intercept uncaught exceptions
app.add_middleware(
    RecoveryMiddleware,
    project_id=os.getenv("PROJECT_ID", "proj_123"),
    api_url=os.getenv("API_URL", "http://localhost:8000")
)

@app.get("/")
def read_root():
    return {
        "service": "faulty-demo-service",
        "status": "healthy",
        "description": "Trigger endpoints below to test autonomous self-healing recovery"
    }

@app.get("/users/{user_id}")
def get_user_profile(user_id: int):
    """
    Triggers NameError in users.py (undefined variable: profile_db).
    """
    return users.get_user_profile(user_id)

@app.get("/payments/refund")
def calculate_refund(amount: float, ratio: float):
    """
    Triggers ZeroDivisionError in payments.py when ratio is 0.0.
    """
    return {"refund": payments.calculate_refund(amount, ratio)}

@app.post("/orders/calculate")
def calculate_orders(payload: dict):
    """
    Triggers KeyError in orders.py if items or discount code are unhandled.
    """
    items = payload.get("items", [])
    discount = payload.get("discount_code")
    return {"total": orders.calculate_order_total(items, discount)}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=5000)
