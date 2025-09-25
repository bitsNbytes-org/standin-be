# API for managing meetings and scheduling

from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.orm import Session, joinedload
from database import get_db
from models import Meeting, Document, Project
from schemas import (
    MeetingCreate,
    MeetingResponse,
    MeetingUpdate,
    DocumentCreate,
)
from google_calendar_service import GoogleCalendarService
from google_service_account import GoogleCalendarServiceAccount
from minio_client import upload_file_content
from typing import List
import json
import logging

logger = logging.getLogger(__name__)
router = APIRouter()


def create_meeting_documents(
    documents_data: List[dict], meeting_id: int, db: Session
) -> List[int]:
    """Create documents associated with a meeting"""
    document_ids = []

    for doc_data in documents_data:
        try:
            # Create document in database
            document = Document(
                content=doc_data.get("content", {}),
                filename=doc_data.get(
                    "filename", f"meeting_{meeting_id}_doc.json"
                ),
                bucket=doc_data.get("bucket", "meeting-docs"),
                external_link=doc_data.get("external_link"),
            )
            db.add(document)
            db.commit()
            db.refresh(document)

            # Upload to MinIO
            json_content = json.dumps(document.content, indent=2)
            upload_file_content(
                json_content, f"{document.id}_{document.filename}"
            )

            document_ids.append(document.id)
            logger.info(
                f"Created document {document.id} for meeting {meeting_id}"
            )

        except Exception as e:
            logger.error(
                f"Failed to create document for meeting {meeting_id}: {e}"
            )
            continue

    return document_ids


def get_calendar_service():
    """Get the appropriate calendar service (service account or OAuth)"""
    import os
    
    # Try service account first if available
    if os.path.exists(os.getenv('GOOGLE_SERVICE_ACCOUNT_FILE', 'service-account-key.json')):
        return GoogleCalendarServiceAccount()
    else:
        return GoogleCalendarService()


def schedule_google_calendar_event(meeting: Meeting) -> str:
    """Schedule meeting in Google Calendar"""
    try:
        calendar_service = get_calendar_service()
        
        # Prepare description with additional info and documentation links
        description_parts = []
        if meeting.description:
            description_parts.append(meeting.description)

        if meeting.additional_information:
            description_parts.append(
                f"\nAdditional Information:\n{meeting.additional_information}"
            )

        if meeting.documentation_links:
            description_parts.append(
                f"\nDocumentation Links:\n"
                + "\n".join(
                    f"- {link}" for link in meeting.documentation_links
                )
            )

        description = "\n".join(description_parts)

        # Create Google Calendar event
        event_id = calendar_service.create_event(
            title=meeting.title,
            description=description,
            start_time=meeting.start_time,
            end_time=meeting.end_time,
            attendees=meeting.attendees or [],
            meeting_link=meeting.meeting_link,
        )

        return event_id

    except Exception as e:
        logger.error(f"Failed to create Google Calendar event: {e}")
        return None


@router.post("/schedule", response_model=MeetingResponse)
def schedule_meeting(
    meeting_data: MeetingCreate,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
):
    """Schedule a new AI meeting with Google Calendar integration"""
    try:
        # Validate project exists if provided
        if meeting_data.project_id:
            project = (
                db.query(Project)
                .filter(Project.id == meeting_data.project_id)
                .first()
            )
            if not project:
                raise HTTPException(
                    status_code=404, detail="Project not found"
                )

        # Create meeting in database
        meeting = Meeting(
            title=meeting_data.title,
            description=meeting_data.description,
            project_id=meeting_data.project_id,
            start_time=meeting_data.start_time,
            end_time=meeting_data.end_time,
            attendees=meeting_data.attendees,
            documentation_links=meeting_data.documentation_links,
            additional_information=meeting_data.additional_information,
            meeting_link=meeting_data.meeting_link,
            status="scheduled",
        )

        db.add(meeting)
        db.commit()
        db.refresh(meeting)

        # Create associated documents if provided
        document_ids = []
        if meeting_data.documents:
            document_ids = create_meeting_documents(
                meeting_data.documents, meeting.id, db
            )

        # Schedule in Google Calendar (background task)
        background_tasks.add_task(schedule_google_calendar_event, meeting)

        logger.info(f"Meeting {meeting.id} scheduled successfully")

        return meeting

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to schedule meeting: {e}")
        raise HTTPException(
            status_code=500, detail=f"Failed to schedule meeting: {str(e)}"
        )


@router.get("/", response_model=List[MeetingResponse])
def get_meetings(
    skip: int = 0,
    limit: int = 100,
    project_id: int = None,
    status: str = None,
    db: Session = Depends(get_db),
):
    """Get all meetings with optional filtering"""
    query = db.query(Meeting)

    if project_id:
        query = query.filter(Meeting.project_id == project_id)

    if status:
        query = query.filter(Meeting.status == status)

    meetings = query.offset(skip).limit(limit).all()
    return meetings


@router.get("/{meeting_id}", response_model=MeetingResponse)
def get_meeting(meeting_id: int, db: Session = Depends(get_db)):
    """Get a specific meeting by ID"""
    meeting = db.query(Meeting).filter(Meeting.id == meeting_id).first()
    if not meeting:
        raise HTTPException(status_code=404, detail="Meeting not found")
    return meeting


@router.put("/{meeting_id}", response_model=MeetingResponse)
def update_meeting(
    meeting_id: int,
    meeting_update: MeetingUpdate,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
):
    """Update an existing meeting"""
    meeting = db.query(Meeting).filter(Meeting.id == meeting_id).first()
    if not meeting:
        raise HTTPException(status_code=404, detail="Meeting not found")

    # Update fields
    update_data = meeting_update.dict(exclude_unset=True)
    for field, value in update_data.items():
        setattr(meeting, field, value)

    db.commit()
    db.refresh(meeting)

    # Update Google Calendar event if it exists
    if meeting.google_calendar_event_id:
        calendar_service = GoogleCalendarService()
        background_tasks.add_task(
            calendar_service.update_event,
            meeting.google_calendar_event_id,
            meeting_update.title,
            meeting_update.description,
            meeting_update.start_time,
            meeting_update.end_time,
            meeting_update.attendees,
            meeting_update.meeting_link,
        )

    return meeting


@router.delete("/{meeting_id}")
def cancel_meeting(
    meeting_id: int,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
):
    """Cancel a meeting and remove from Google Calendar"""
    meeting = db.query(Meeting).filter(Meeting.id == meeting_id).first()
    if not meeting:
        raise HTTPException(status_code=404, detail="Meeting not found")

    # Update status to cancelled
    meeting.status = "cancelled"
    db.commit()

    # Delete from Google Calendar if it exists
    if meeting.google_calendar_event_id:
        calendar_service = GoogleCalendarService()
        background_tasks.add_task(
            calendar_service.delete_event, meeting.google_calendar_event_id
        )

    return {"message": f"Meeting {meeting_id} has been cancelled"}


@router.get("/{meeting_id}/documents")
def get_meeting_documents(meeting_id: int, db: Session = Depends(get_db)):
    """Get all documents associated with a meeting"""
    meeting = db.query(Meeting).filter(Meeting.id == meeting_id).first()
    if not meeting:
        raise HTTPException(status_code=404, detail="Meeting not found")

    # For now, return documentation links
    # In the future, you might want to create a relationship between meetings and documents
    return {
        "meeting_id": meeting_id,
        "documentation_links": meeting.documentation_links or [],
        "additional_information": meeting.additional_information,
    }


@router.post("/{meeting_id}/complete")
def complete_meeting(meeting_id: int, db: Session = Depends(get_db)):
    """Mark a meeting as completed"""
    meeting = db.query(Meeting).filter(Meeting.id == meeting_id).first()
    if not meeting:
        raise HTTPException(status_code=404, detail="Meeting not found")

    meeting.status = "completed"
    db.commit()

    return {"message": f"Meeting {meeting_id} marked as completed"}
