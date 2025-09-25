from document.service import DocumentService
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from database import get_db
from models import Document
from schemas import ConfluencePageRequest, ConfluencePageResponse
from confluence_service import ConfluenceService
from minio_client import upload_file_content, create_bucket_if_not_exists
import logging

logger = logging.getLogger(__name__)

router = APIRouter()

@router.post("/pull", response_model=ConfluencePageResponse)
def pull_confluence_page(
    request: ConfluencePageRequest, 
    db: Session = Depends(get_db)
):
    """
    Pull a Confluence page by URL and save it to MinIO and database
    """
    try:
        # Initialize Confluence service
        confluence_service = ConfluenceService()
        
        # Fetch page data from Confluence
        logger.info(f"Fetching Confluence page from URL: {request.url}")
        page_data = confluence_service.fetch_page_by_url(request.url)
        
        # Extract content
        content_data = confluence_service.extract_page_content(page_data, request.url)
        
        # Ensure bucket exists
        create_bucket_if_not_exists()
        
        # Upload content to MinIO
        logger.info(f"Uploading content to MinIO: {content_data['filename']}")
        upload_success = upload_file_content(
            content_data['content'], 
            content_data['filename']
        )
        
        if not upload_success:
            raise HTTPException(
                status_code=500, 
                detail="Failed to upload content to MinIO"
            )
        
        document_service = DocumentService(db)
        document = document_service.create_document(Document(
            content=content_data['json_content'],
            filename=content_data['filename'],
            bucket=request.bucket,
            external_link=request.url
        ))
        logger.info(f"Successfully created document with ID: {document.id}")
        
        return ConfluencePageResponse(
            document_id=document.id,
            title=content_data['title'],
            filename=content_data['filename'],
            page_id=content_data['page_id'],
            space_name=content_data['space_name'],
            message=f"Successfully pulled Confluence page '{content_data['title']}' and saved as document {document.id}"
        )
        
    except ValueError as e:
        logger.error(f"Validation error: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error pulling Confluence page: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to pull Confluence page: {str(e)}")


@router.get("/test")
def test_confluence_connection():
    """
    Test Confluence connection
    """
    try:
        confluence_service = ConfluenceService()
        # Try to get a simple API response
        client = confluence_service._client()
        # This will raise an exception if connection fails
        return {"status": "success", "message": "Confluence connection is working"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Confluence connection failed: {str(e)}")
