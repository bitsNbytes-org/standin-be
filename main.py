from typing import List
from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm.session import Session
import uvicorn
from datetime import datetime

from database import SessionLocal, engine, Base
from models import User
from schemas import UserResponse


# Create database tables
Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="FastAPI Boilerplate",
    description="A FastAPI application with PostgreSQL and MinIO",
    version="1.0.0",
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure this properly for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Dependency to get database session
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@app.get("/")
async def root():
    return {
        "message": "Welcome to FastAPI Boilerplate with PostgreSQL and MinIO"
    }


@app.get("/health")
async def health_check():
    return {
        "status": "healthy",
        "timestamp": datetime.now(datetime.timezone.utc),
    }


@app.get("/users/", response_model=List[UserResponse])
async def get_users(
    skip: int = 0, limit: int = 100, db: Session = Depends(get_db)
):
    users = db.query(User).offset(skip).limit(limit).all()
    return users


if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
