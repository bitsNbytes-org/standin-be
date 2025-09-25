from database import get_db
from models import Document
from minio_client import download_file, upload_file_content
from sqlalchemy.orm import Session


class DocumentService:
    def __init__(self, db: Session):
        self.db = db

    def create_document(self, document: Document, minio_content: str = None):
        self.db.add(document)
        self.db.commit()
        self.db.refresh(document)
        
        # Use provided content for MinIO or fallback to JSON dump
        if minio_content is not None:
            content = minio_content
        else:
            import json
            content = json.dumps(document.content, indent=2)
        
        upload_file_content(content, str(document.id) + "_" + document.filename)
        return document
    
    def get_document(self, document_id: int):  #return the document
        return self.db.query(Document).filter(Document.id == document_id).first()
    
    def delete_document(self, document_id: int):  #delete the document
        document = self.get_document(document_id)
        self.db.delete(document)
        self.db.commit()
        return True
    
    def get_documents(self):
        return self.db.query(Document).all()

    def download_document(self, document_id: int):  #return the content of the document
        document = self.get_document(document_id)
        return download_file(str(document.id) + "_" + document.filename)