from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from apscheduler.schedulers.background import BackgroundScheduler

from app.database import engine, Base, get_db, ensure_schema
from app import models, routes
from app.auth import create_access_token, verify_token
from app.scheduler_jobs import run_sensor_retention_job
import hashlib

scheduler = BackgroundScheduler()


@asynccontextmanager
async def lifespan(app: FastAPI):
    scheduler.add_job(
        run_sensor_retention_job,
        "cron",
        hour=3,
        minute=0,
        id="sensor_retention_30d",
    )
    scheduler.start()
    yield
    scheduler.shutdown(wait=False)


app = FastAPI(title="SmartCampus Backend API", version="1.0.0", lifespan=lifespan)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Create tables on startup (optional — prefer using init_db.py manually)
Base.metadata.create_all(bind=engine)
ensure_schema(engine)

@app.post("/login", tags=["Authentication"])
def login(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    """
    Handle user login. OAuth2 standard:
    - 'username' field captures the email
    - 'password' field captures the password
    """
    user = db.query(models.User).filter(models.User.email == form_data.username).first()
    hashed_password = hashlib.sha256(form_data.password.encode()).hexdigest()
    if not user or user.hashed_password != hashed_password:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    if getattr(user, "is_active", True) is False:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account is deactivated",
        )

    token = create_access_token(user_id=user.id)
    return {"access_token": token, "token_type": "bearer"}

@app.get("/me", tags=["Authentication"])
def get_current_user_profile(current_user: models.User = Depends(verify_token)):
    """
    An extra endpoint to prove your JWT verification works.
    Only accessible with a valid token.
    """
    return {
        "id": current_user.id,
        "name": current_user.name,
        "email": current_user.email,
        "role": current_user.role
    }


@app.get("/")
def read_root():
    return {
        "message": "Welcome to SmartCampus Backend API",
        "version": "1.0.0",
        "endpoints": {
            "docs": "/docs",
            "redoc": "/redoc",
            "users": "/users",
            "login": "/login"
        }
    }

@app.get("/health")
def health_check():
    return {"status": "ok"}

@app.get("/test-token/{user_id}")
def get_test_token(user_id: int):
    token = create_access_token(user_id=user_id)
    return {
        "access_token": token,
        "token_type": "bearer",
        "instructions": "Add this to your request header: Authorization: Bearer <token>",
        "user_id": user_id
    }

# Include routers
app.include_router(routes.router)
from app.routes_campus import router as campus_router
from app.routes_booking import router as booking_router
from app.routes_iot import router as iot_router
from app.routes_notifications import router as notifications_router
from app.routes_analytics import router as analytics_router
from app.routes_allocations import router as allocations_router
from app.routes_maintenance import router as maintenance_router
from app.routes_maintenance_schedule import router as maintenance_schedule_router
from app.routes_emergency import router as emergency_router
from app.routes_facility_menu_inventory import router as facility_menu_inventory_router

app.include_router(campus_router)
app.include_router(facility_menu_inventory_router)
app.include_router(booking_router)
app.include_router(iot_router)
app.include_router(notifications_router)
app.include_router(analytics_router)
app.include_router(allocations_router)
app.include_router(maintenance_router)
app.include_router(maintenance_schedule_router)
app.include_router(emergency_router)

_uploads_dir = Path(__file__).resolve().parent / "uploads"
_uploads_dir.mkdir(parents=True, exist_ok=True)
app.mount("/uploads", StaticFiles(directory=str(_uploads_dir)), name="uploads")

if __name__ == "__main__":
    import uvicorn
    # Finalized the port as 8000
    uvicorn.run(app, host="0.0.0.0", port=8000)
