"""
Meeting API with document relationships
"""

import logging
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import and_

from database import get_db
from models import Meeting, Document, DocumentType
from schemas import MeetingCreate, MeetingResponse, MeetingWithDocumentsResponse, DocumentResponse

logger = logging.getLogger(__name__)
router = APIRouter()


@router.post("/", response_model=MeetingResponse)
def create_meeting(meeting: MeetingCreate, db: Session = Depends(get_db)):
    """Create a new meeting"""
    try:
        db_meeting = Meeting(**meeting.dict())
        db.add(db_meeting)
        db.commit()
        db.refresh(db_meeting)
        
        # Initialize empty documents list
        db_meeting.documents = []
        
        return db_meeting
    except Exception as e:
        logger.error(f"Error creating meeting: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to create meeting: {str(e)}")


@router.get("/", response_model=List[MeetingWithDocumentsResponse])
def get_meetings(
    skip: int = 0, 
    limit: int = 100, 
    include_documents: bool = True,
    db: Session = Depends(get_db)
):
    """Get all meetings with optional document inclusion via left join"""
    try:
        query = db.query(Meeting)
        
        if include_documents:
            # Use joinedload for left join to include documents
            query = query.options(joinedload(Meeting.documents))
        
        meetings = query.offset(skip).limit(limit).all()
        return meetings
    except Exception as e:
        logger.error(f"Error fetching meetings: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to fetch meetings: {str(e)}")


@router.get("/{meeting_id}", response_model=MeetingWithDocumentsResponse)
def get_meeting(meeting_id: int, db: Session = Depends(get_db)):
    """Get a specific meeting by ID with documents via left join"""
    try:
        meeting = db.query(Meeting).options(joinedload(Meeting.documents)).filter(Meeting.id == meeting_id).first()
        if not meeting:
            raise HTTPException(status_code=404, detail="Meeting not found")
        return meeting
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching meeting {meeting_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to fetch meeting: {str(e)}")


@router.put("/{meeting_id}", response_model=MeetingResponse)
def update_meeting(meeting_id: int, meeting: MeetingCreate, db: Session = Depends(get_db)):
    """Update a meeting"""
    try:
        db_meeting = db.query(Meeting).filter(Meeting.id == meeting_id).first()
        if not db_meeting:
            raise HTTPException(status_code=404, detail="Meeting not found")
        
        # Update fields
        for field, value in meeting.dict(exclude_unset=True).items():
            setattr(db_meeting, field, value)
        
        db.commit()
        db.refresh(db_meeting)
        return db_meeting
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating meeting {meeting_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to update meeting: {str(e)}")


@router.delete("/{meeting_id}")
def delete_meeting(meeting_id: int, db: Session = Depends(get_db)):
    """Delete a meeting"""
    try:
        meeting = db.query(Meeting).filter(Meeting.id == meeting_id).first()
        if not meeting:
            raise HTTPException(status_code=404, detail="Meeting not found")
        
        db.delete(meeting)
        db.commit()
        return {"message": f"Meeting {meeting_id} deleted successfully"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting meeting {meeting_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to delete meeting: {str(e)}")


@router.post("/{meeting_id}/documents/{document_id}")
def link_document_to_meeting(meeting_id: int, document_id: int, db: Session = Depends(get_db)):
    """Link an existing document to a meeting"""
    try:
        # Check if meeting exists
        meeting = db.query(Meeting).filter(Meeting.id == meeting_id).first()
        if not meeting:
            raise HTTPException(status_code=404, detail="Meeting not found")
        
        # Check if document exists
        document = db.query(Document).filter(Document.id == document_id).first()
        if not document:
            raise HTTPException(status_code=404, detail="Document not found")
        
        # Link document to meeting
        document.meeting_id = meeting_id
        db.commit()
        
        return {"message": f"Document {document_id} linked to meeting {meeting_id}"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error linking document {document_id} to meeting {meeting_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to link document: {str(e)}")


@router.delete("/{meeting_id}/documents/{document_id}")
def unlink_document_from_meeting(meeting_id: int, document_id: int, db: Session = Depends(get_db)):
    """Unlink a document from a meeting"""
    try:
        # Check if meeting exists
        meeting = db.query(Meeting).filter(Meeting.id == meeting_id).first()
        if not meeting:
            raise HTTPException(status_code=404, detail="Meeting not found")
        
        # Check if document exists and is linked to this meeting
        document = db.query(Document).filter(
            and_(Document.id == document_id, Document.meeting_id == meeting_id)
        ).first()
        if not document:
            raise HTTPException(status_code=404, detail="Document not found or not linked to this meeting")
        
        # Unlink document from meeting
        document.meeting_id = None
        db.commit()
        
        return {"message": f"Document {document_id} unlinked from meeting {meeting_id}"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error unlinking document {document_id} from meeting {meeting_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to unlink document: {str(e)}")


@router.get("/{meeting_id}/documents", response_model=List[DocumentResponse])
def get_meeting_documents(meeting_id: int, db: Session = Depends(get_db)):
    """Get all documents linked to a specific meeting"""
    try:
        # Check if meeting exists
        meeting = db.query(Meeting).filter(Meeting.id == meeting_id).first()
        if not meeting:
            raise HTTPException(status_code=404, detail="Meeting not found")
        
        # Get documents linked to this meeting
        documents = db.query(Document).filter(Document.meeting_id == meeting_id).all()
        return documents
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching documents for meeting {meeting_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to fetch meeting documents: {str(e)}")


@router.get("/{meeting_id}/documents/by-type/{doc_type}", response_model=List[DocumentResponse])
def get_meeting_documents_by_type(meeting_id: int, doc_type: DocumentType, db: Session = Depends(get_db)):
    """Get documents of a specific type linked to a meeting"""
    try:
        # Check if meeting exists
        meeting = db.query(Meeting).filter(Meeting.id == meeting_id).first()
        if not meeting:
            raise HTTPException(status_code=404, detail="Meeting not found")
        
        # Get documents of specific type linked to this meeting
        documents = db.query(Document).filter(
            and_(Document.meeting_id == meeting_id, Document.doc_type == doc_type)
        ).all()
        return documents
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching {doc_type} documents for meeting {meeting_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to fetch meeting documents by type: {str(e)}")
