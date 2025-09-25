# API for managing docs if given content it should create a doc and store it in minio

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from database import get_db
from models import Document
from schemas import DocumentCreate
from minio_client import download_file, upload_file_content


router = APIRouter()


@router.post("/")
def create_document(document: DocumentCreate, db: Session = Depends(get_db)):
    # create a document in minio

    # Store the JSON content as-is in MinIO
    import json

    json_content = json.dumps(document.content, indent=2)

    db_document = Document(
        content=document.content,
        filename=document.filename,
        bucket=document.bucket,
        project_id=document.project_id,
        external_link=document.external_link,
    )
    db.add(db_document)
    db.commit()
    db.refresh(db_document)

    # Upload the JSON content to MinIO
    upload_file_content(
        json_content, str(db_document.id) + "_" + document.filename
    )
    return db_document


@router.get("/")
def get_documents(db: Session = Depends(get_db)):
    documents = db.query(Document).all()
    return documents


@router.get("/{document_id}")
def get_document(document_id: int, db: Session = Depends(get_db)):
    document = db.query(Document).filter(Document.id == document_id).first()
    return document


@router.delete("/{document_id}")
def delete_document(document_id: int, db: Session = Depends(get_db)):
    document = db.query(Document).filter(Document.id == document_id).first()
    db.delete(document)
    db.commit()
    return True


@router.get("/{document_id}/download")
def download_document(document_id: int, db: Session = Depends(get_db)):
    document = db.query(Document).filter(Document.id == document_id).first()
    return download_file(str(document.id) + "_" + document.filename)
