from typing import List
from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm.session import Session
import uvicorn
from datetime import datetime

from database import engine, Base, get_db
from models import User, Project
from schemas import UserResponse
from document.api import router as document_api
from confluence.api import router as confluence_api
from jira.api import router as jira_api
from project.api import router as project_api

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


app.include_router(document_api, prefix="/document", tags=["document"])
app.include_router(confluence_api, prefix="/confluence", tags=["confluence"])
app.include_router(jira_api, prefix="/jira", tags=["jira"])
app.include_router(project_api, prefix="/project", tags=["project"])


if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
