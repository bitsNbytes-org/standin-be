# API for managing projects and their documents

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session, joinedload
from database import get_db
from models import Project, Document
from schemas import (
    ProjectCreate,
    ProjectResponse,
    ProjectWithDocumentsResponse,
)
from typing import List

router = APIRouter()


@router.post("/", response_model=ProjectResponse)
def create_project(project: ProjectCreate, db: Session = Depends(get_db)):
    """Create a new project"""
    db_project = Project(name=project.name, description=project.description)
    db.add(db_project)
    db.commit()
    db.refresh(db_project)
    return db_project


@router.get("/", response_model=List[ProjectWithDocumentsResponse])
def get_all_projects_with_documents(db: Session = Depends(get_db)):
    """Get all projects with their corresponding documents"""
    projects = db.query(Project).options(joinedload(Project.documents)).all()
    return projects


@router.get("/{project_id}", response_model=ProjectWithDocumentsResponse)
def get_project_with_documents(project_id: int, db: Session = Depends(get_db)):
    """Get a specific project with its documents"""
    project = (
        db.query(Project)
        .options(joinedload(Project.documents))
        .filter(Project.id == project_id)
        .first()
    )
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    return project


@router.get("/{project_id}/documents")
def get_project_documents(project_id: int, db: Session = Depends(get_db)):
    """Get all documents for a specific project"""
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    documents = (
        db.query(Document).filter(Document.project_id == project_id).all()
    )
    return documents
