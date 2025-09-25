"""
Comprehensive Document API for handling Confluence, JIRA, and file imports
"""

import json
import logging
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from sqlalchemy.orm import Session

from database import get_db
from models import Document
from schemas import (
    DocumentCreate, DocumentImportRequest, DocumentImportResponse, 
    DocumentResponse, ConfluencePageRequest, JiraIssueRequest
)
from minio_client import download_file, upload_file_content, create_bucket_if_not_exists
from services.url_detector import URLDetector, SourceType
from services.file_processor import FileProcessor
from document.service import DocumentService
from config import settings

# Import services
try:
    from confluence_service import ConfluenceService
    from services.jira_service import JiraService
except ImportError:
    ConfluenceService = None
    JiraService = None

logger = logging.getLogger(__name__)
router = APIRouter()

@router.post("/import", response_model=DocumentImportResponse)
async def import_document(
    source: str = Form(...),
    url: Optional[str] = Form(None),
    filename: Optional[str] = Form(None),
    include_subtasks: bool = Form(True),
    content: Optional[str] = Form(None),
    file: Optional[UploadFile] = File(None),
    db: Session = Depends(get_db)
):
    """
    Comprehensive document import endpoint that handles:
    - Confluence URLs (auto-detected)
    - JIRA URLs (auto-detected) 
    - Raw file uploads
    - Direct content input
    """
    try:
        # Ensure bucket exists
        create_bucket_if_not_exists()
        
        if source == "url" and url:
            return await _handle_url_import(url, include_subtasks, db)
        
        elif source == "file" and file:
            return await _handle_file_import(file, filename, db)
        
        elif source == "content" and content:
            return await _handle_content_import(content, filename, db)
        
        else:
            raise HTTPException(
                status_code=400, 
                detail="Invalid source type or missing required parameters"
            )
    
    except Exception as e:
        logger.error(f"Error importing document: {str(e)}")
       
        raise HTTPException(status_code=500, detail=f"Failed to import document: {str(e)}")


async def _handle_url_import(url: str, include_subtasks: bool, db: Session) -> DocumentImportResponse:
    """Handle URL-based imports (Confluence/JIRA)"""
    
    # Detect URL type
    url_info = URLDetector.parse_url(url)
    
    if not url_info["is_valid"]:
        raise HTTPException(status_code=400, detail="Invalid or unsupported URL")
    
    source_type = url_info["source_type"]
    
    if source_type == SourceType.CONFLUENCE:
        if not ConfluenceService:
            raise HTTPException(status_code=500, detail="Confluence service not available")
        
        confluence_service = ConfluenceService()
        page_data = confluence_service.fetch_page_by_url(url)
        content_data = confluence_service.extract_page_content(page_data, url)
        
        # Create document using DocumentService
        document_service = DocumentService(db)
        document = Document(
            content=content_data["json_content"],
            filename=content_data["filename"],
            bucket=settings.MINIO_BUCKET_NAME,
            external_link=url
        )
        
        document = document_service.create_document(document, content_data["content"])
        
        return DocumentImportResponse(
            document_id=document.id,
            source_type="confluence",
            title=content_data["title"],
            filename=content_data["filename"],
            bucket=settings.MINIO_BUCKET_NAME,
            external_link=url,
            message=f"Successfully imported Confluence page: {content_data['page_id']}",
            metadata={"page_id": content_data["page_id"], "space_name": content_data["space_name"]}
        )
    
    elif source_type == SourceType.JIRA:
        if not JiraService:
            raise HTTPException(status_code=500, detail="JIRA service not available")
        
        jira_service = JiraService()
        
        # Check if it's a board URL or issue URL
        if url_info.get("url_type") == "board":
            # Handle board import
            board_info = url_info["identifier"]
            project_key = board_info.get("project_key")
            board_id = board_info.get("board_id")
            
            if not project_key:
                raise HTTPException(status_code=400, detail="Could not extract project key from board URL")
            
            content_data = jira_service.fetch_board_issues(project_key, board_id)
        else:
            # Handle single issue import
            issue_data = jira_service.fetch_issue_by_url(url)
            
            # Fetch subtasks if requested
            subtasks = []
            if include_subtasks:
                issue_key = jira_service.extract_issue_key_from_url(url)
                if issue_key:
                    subtasks = jira_service.fetch_issue_subtasks(issue_key)
            
            content_data = jira_service.format_issue_content(issue_data, subtasks)
        
        # Create document using DocumentService
        document_service = DocumentService(db)
        document = Document(
            content=content_data["json_content"],
            filename=content_data["filename"],
            bucket=settings.MINIO_BUCKET_NAME,
            external_link=url
        )
        
        document = document_service.create_document(document, content_data["content"])
        
        # Create appropriate response based on import type
        if url_info.get("url_type") == "board":
            return DocumentImportResponse(
                document_id=document.id,
                source_type="jira",
                title=content_data["title"],
                filename=content_data["filename"],
                bucket=settings.MINIO_BUCKET_NAME,
                external_link=url,
                message=f"Successfully imported JIRA board: {content_data['project_key']} ({content_data['total_issues']} issues)",
                metadata={"project_key": content_data["project_key"], "board_id": content_data.get("board_id"), "total_issues": content_data["total_issues"]}
            )
        else:
            return DocumentImportResponse(
                document_id=document.id,
                source_type="jira",
                title=content_data["title"],
                filename=content_data["filename"],
                bucket=settings.MINIO_BUCKET_NAME,
                external_link=url,
                message=f"Successfully imported JIRA issue: {content_data['issue_key']}",
                metadata={"issue_key": content_data["issue_key"], "project_name": content_data.get("project_name", "Unknown")}
            )
    
    else:
        raise HTTPException(status_code=400, detail="Unsupported URL type")


async def _handle_file_import(file: UploadFile, filename: Optional[str], db: Session) -> DocumentImportResponse:
    """Handle file upload imports"""
    
    # Validate file type
    if not FileProcessor.is_supported_file_type(file.content_type):
        raise HTTPException(
            status_code=400, 
            detail=f"Unsupported file type: {file.content_type}"
        )
    
    # Read file content
    content, original_filename = await FileProcessor.read_file_content(file)
    
    # Generate filename if not provided
    if not filename:
        filename = FileProcessor.generate_filename(original_filename, file.content_type)
    
    # Create metadata
    metadata = FileProcessor.create_file_metadata(file, content)
    metadata["upload_timestamp"] = datetime.utcnow().isoformat()
    
    # Format content for storage
    formatted_content = FileProcessor.format_file_content(content, filename, file.content_type)
    
    # Create document using DocumentService
    document_service = DocumentService(db)
    document = Document(
        content=metadata,
        filename=filename,
        bucket=settings.MINIO_BUCKET_NAME,
        external_link=None
    )
    
    document = document_service.create_document(document, formatted_content)
    
    return DocumentImportResponse(
        document_id=document.id,
        source_type="file",
        title=f"Uploaded file: {filename}",
        filename=filename,
        bucket=settings.MINIO_BUCKET_NAME,
        external_link=None,
        message=f"Successfully uploaded file: {filename}",
        metadata=metadata
    )


async def _handle_content_import(content: str, filename: Optional[str], db: Session) -> DocumentImportResponse:
    """Handle direct content imports"""
    
    if not filename:
        filename = f"content-{datetime.utcnow().strftime('%Y%m%d-%H%M%S')}.txt"
    
    # Create metadata
    metadata = {
        "source_type": "content",
        "content_length": len(content),
        "upload_timestamp": datetime.utcnow().isoformat(),
        "is_text_content": True
    }
    
    # Create document using DocumentService
    document_service = DocumentService(db)
    document = Document(
        content=metadata,
        filename=filename,
        bucket=settings.MINIO_BUCKET_NAME,
        external_link=None
    )
    
    document = document_service.create_document(document, content)
    
    return DocumentImportResponse(
        document_id=document.id,
        source_type="content",
        title=f"Direct content: {filename}",
        filename=filename,
        bucket=settings.MINIO_BUCKET_NAME,
        external_link=None,
        message=f"Successfully imported content as: {filename}",
        metadata=metadata
    )

@router.post("/", response_model=DocumentResponse)
def create_document(document: DocumentCreate, db: Session = Depends(get_db)):
    """Create a document with direct content (legacy endpoint)"""
    try:
        # Create document using DocumentService
        document_service = DocumentService(db)
        db_document = Document(
            content=document.content,
            filename=document.filename,
            bucket=document.bucket,
            external_link=document.external_link
        )
        
        # Store the JSON content as-is in MinIO
        content = json.dumps(document.content, indent=2)
        db_document = document_service.create_document(db_document, content)
        return db_document
    
    except Exception as e:
        logger.error(f"Error creating document: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to create document: {str(e)}")


@router.get("/", response_model=list[DocumentResponse])
def get_documents(db: Session = Depends(get_db)):
    """Get all documents"""
    try:
        document_service = DocumentService(db)
        documents = document_service.get_documents()
        return documents
    except Exception as e:
        logger.error(f"Error fetching documents: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to fetch documents: {str(e)}")


@router.get("/{document_id}", response_model=DocumentResponse)
def get_document(document_id: int, db: Session = Depends(get_db)):
    """Get a specific document by ID"""
    try:
        document_service = DocumentService(db)
        document = document_service.get_document(document_id)
        if not document:
            raise HTTPException(status_code=404, detail="Document not found")
        return document
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching document {document_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to fetch document: {str(e)}")



@router.delete("/{document_id}")
def delete_document(document_id: int, db: Session = Depends(get_db)):
    """Delete a document by ID"""
    try:
        document_service = DocumentService(db)
        document = document_service.get_document(document_id)
        if not document:
            raise HTTPException(status_code=404, detail="Document not found")
            
        document_service.delete_document(document_id)
        return {"message": f"Document {document_id} deleted successfully"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting document {document_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to delete document: {str(e)}")


@router.get("/{document_id}/download")
def download_document(document_id: int, db: Session = Depends(get_db)):
    """Download document content from MinIO"""
    try:
        document_service = DocumentService(db)
        document = document_service.get_document(document_id)
        if not document:
            raise HTTPException(status_code=404, detail="Document not found")
            
        content = document_service.download_document(document_id)
        return {"content": content, "filename": document.filename}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error downloading document {document_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to download document: {str(e)}")


@router.post("/detect-url")
def detect_url_type(url: str):
    """Detect URL type (Confluence/JIRA/Unknown)"""
    try:
        url_info = URLDetector.parse_url(url)
        return {
            "url": url,
            "source_type": url_info["source_type"],
            "is_valid": url_info["is_valid"],
            "domain": url_info["domain"],
            "identifier": url_info["identifier"]
        }
    except Exception as e:
        logger.error(f"Error detecting URL type: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to detect URL type: {str(e)}")

