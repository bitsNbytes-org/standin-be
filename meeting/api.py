# API for managing meetings and scheduling

import os
from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    BackgroundTasks,
    Form,
    File,
    UploadFile,
)
from sqlalchemy.orm import Session, joinedload
from database import get_db
from models import Meeting, Document, Project
from schemas import (
    DocumentResponse,
    MeetingCreate,
    MeetingResponse,
    MeetingUpdate,
    DocumentImportResponse,
)
from google_calendar_service import GoogleCalendarService
from google_service_account import GoogleCalendarServiceAccount
from minio_client import upload_file_content
from typing import List, Optional
import json
import logging
import requests

# Import document handling functions from document API
try:
    from document.api import (
        _handle_url_import,
        _handle_file_import,
        _handle_content_import,
    )
except ImportError:
    # Fallback if import fails
    _handle_url_import = None
    _handle_file_import = None
    _handle_content_import = None

logger = logging.getLogger(__name__)
router = APIRouter()

MEETING_BASE_URL = os.getenv(
    "MEETING_BASE_URL", "http://localhost:3000/meetings"
)

EXTERNAL_SERVICE_URL = os.getenv(
    "EXTERNAL_SERVICE_URL", "https://fd3b0768cccc.ngrok-free.app"
)


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


async def import_meeting_document(
    source: str,
    meeting_id: int,
    db: Session,
    url: Optional[str] = None,
    filename: Optional[str] = None,
    include_subtasks: bool = True,
    content: Optional[str] = None,
    file: Optional[UploadFile] = None,
) -> Optional[DocumentImportResponse]:
    """Import a document and link it to a meeting using the document API functions"""
    try:
        document_response = None

        if source == "url" and url and _handle_url_import:
            document_response = await _handle_url_import(
                url, include_subtasks, db
            )
        elif source == "file" and file and _handle_file_import:
            document_response = await _handle_file_import(file, filename, db)
        elif source == "content" and content and _handle_content_import:
            document_response = await _handle_content_import(
                content, filename, db
            )

        if document_response:
            # Link the created document to the meeting
            document = (
                db.query(Document)
                .filter(Document.id == document_response.document_id)
                .first()
            )
            if document:
                document.meeting_id = meeting_id
                db.commit()
                logger.info(
                    f"Document {document.id} linked to meeting {meeting_id}"
                )

        return document_response

    except Exception as e:
        logger.error(
            f"Failed to import document for meeting {meeting_id}: {e}"
        )
        return None


def get_calendar_service():
    """Get the appropriate calendar service (service account or OAuth)"""
    import os

    # Try service account first if available
    if os.path.exists(
        os.getenv("GOOGLE_SERVICE_ACCOUNT_FILE", "service-account-key.json")
    ):
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
                "\nDocumentation Links:\n"
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
async def schedule_meeting(
    meeting_data: MeetingCreate,
    background_tasks: BackgroundTasks = BackgroundTasks(),
    db: Session = Depends(get_db),
):
    """Schedule a new AI meeting with Google Calendar integration and document import"""
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

        # Validate time range
        if meeting_data.end_time <= meeting_data.start_time:
            raise HTTPException(
                status_code=400,
                detail=(
                    f"End time ({meeting_data.end_time}) must be after "
                    f"start time ({meeting_data.start_time})"
                ),
            )

        logger.info(
            f"Creating meeting with start_time: {meeting_data.start_time}, "
            f"end_time: {meeting_data.end_time}"
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
            status="scheduled",
        )

        db.add(meeting)
        db.commit()
        db.refresh(meeting)

        meeting.meeting_link = f"{MEETING_BASE_URL}/{meeting.id}"
        db.add(meeting)
        db.commit()
        db.refresh(meeting)

        # Import document if provided (except file uploads)
        document_response = None
        if (
            meeting_data.document_source
            and meeting_data.document_source != "file"
        ):
            document_response = await import_meeting_document(
                source=meeting_data.document_source,
                meeting_id=meeting.id,
                db=db,
                url=meeting_data.document_url,
                filename=meeting_data.document_filename,
                include_subtasks=meeting_data.include_subtasks,
                content=meeting_data.document_content,
                file=None,
            )

        # Schedule in Google Calendar (background task)
        background_tasks.add_task(schedule_google_calendar_event, meeting)

        logger.info(f"Meeting {meeting.id} scheduled successfully")
        if document_response:
            logger.info(
                f"Document {document_response.document_id} imported and "
                f"linked to meeting {meeting.id}"
            )

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
    query = db.query(Meeting).options(joinedload(Meeting.documents))

    if project_id:
        query = query.filter(Meeting.project_id == project_id)

    if status:
        query = query.filter(Meeting.status == status)

    meetings = query.offset(skip).limit(limit).all()
    return meetings


@router.get("/{meeting_id}", response_model=MeetingResponse)
def get_meeting(meeting_id: int, db: Session = Depends(get_db)):
    """Get a specific meeting by ID"""
    meeting = (
        db.query(Meeting)
        .options(joinedload(Meeting.documents))
        .filter(Meeting.id == meeting_id)
        .first()
    )
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
    # In the future, you might want to create a relationship
    # between meetings and documents
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


@router.post("/{meeting_id}/start", response_model=MeetingResponse)
def start_meeting(meeting_id: int, db: Session = Depends(get_db)):
    """Start a meeting and get a process ID from an external service."""
    meeting = db.query(Meeting).filter(Meeting.id == meeting_id).first()
    if not meeting:
        raise HTTPException(status_code=404, detail="Meeting not found")

    if meeting.status == "started":
        raise HTTPException(
            status_code=400, detail="Meeting has already started"
        )

    try:
        response = requests.post(f"{EXTERNAL_SERVICE_URL}/start")
        response.raise_for_status()  # Raise an exception for bad status codes
        data = response.json()
        pid = data.get("pid")

        if pid is None:
            raise HTTPException(
                status_code=500,
                detail="Failed to get PID from external service",
            )

        meeting.status = "started"
        meeting.pid = pid
        db.commit()
        db.refresh(meeting)

        return meeting

    except requests.exceptions.RequestException as e:
        logger.error(
            f"Error calling external service for starting meeting {meeting_id}: {e}"
        )
        raise HTTPException(status_code=502, detail="External service error")


@router.post("/{meeting_id}/stop", response_model=MeetingResponse)
def stop_meeting(meeting_id: int, db: Session = Depends(get_db)):
    """Stop a meeting and notify the external service."""
    meeting = db.query(Meeting).filter(Meeting.id == meeting_id).first()
    if not meeting:
        raise HTTPException(status_code=404, detail="Meeting not found")

    if meeting.status != "started":
        raise HTTPException(
            status_code=400, detail="Meeting is not in 'started' state"
        )

    if meeting.pid is None:
        raise HTTPException(
            status_code=400, detail="Meeting does not have a process ID"
        )

    try:
        response = requests.post(
            f"{EXTERNAL_SERVICE_URL}/stop?pid={meeting.pid}"
        )
        response.raise_for_status()

        meeting.status = "completed"
        db.commit()
        db.refresh(meeting)

        return meeting

    except requests.exceptions.RequestException as e:
        logger.error(
            f"Error calling external service for stopping meeting {meeting_id}: {e}"
        )
        raise HTTPException(status_code=502, detail="External service error")


@router.post(
    "/{meeting_id}/documents/import", response_model=DocumentImportResponse
)
async def import_document_to_meeting(
    meeting_id: int,
    source: str = Form(...),
    url: Optional[str] = Form(None),
    filename: Optional[str] = Form(None),
    include_subtasks: bool = Form(True),
    content: Optional[str] = Form(None),
    file: Optional[UploadFile] = File(None),
    db: Session = Depends(get_db),
):
    """Import a document and link it to an existing meeting"""
    try:
        # Check if meeting exists
        meeting = db.query(Meeting).filter(Meeting.id == meeting_id).first()
        if not meeting:
            raise HTTPException(status_code=404, detail="Meeting not found")

        # Import document using the same logic as document API
        document_response = await import_meeting_document(
            source=source,
            meeting_id=meeting_id,
            db=db,
            url=url,
            filename=filename,
            include_subtasks=include_subtasks,
            content=content,
            file=file,
        )

        if not document_response:
            raise HTTPException(
                status_code=400, detail="Failed to import document"
            )

        return document_response

    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            f"Error importing document to meeting {meeting_id}: {str(e)}"
        )
        raise HTTPException(
            status_code=500, detail=f"Failed to import document: {str(e)}"
        )


@router.post("/{meeting_id}/documents/{document_id}")
def link_document_to_meeting(
    meeting_id: int, document_id: int, db: Session = Depends(get_db)
):
    """Link an existing document to a meeting"""
    try:
        # Check if meeting exists
        meeting = db.query(Meeting).filter(Meeting.id == meeting_id).first()
        if not meeting:
            raise HTTPException(status_code=404, detail="Meeting not found")

        # Check if document exists
        document = (
            db.query(Document).filter(Document.id == document_id).first()
        )
        if not document:
            raise HTTPException(status_code=404, detail="Document not found")

        # Link document to meeting
        document.meeting_id = meeting_id
        db.commit()

        return {
            "message": f"Document {document_id} linked to meeting {meeting_id}"
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            f"Error linking document {document_id} to meeting {meeting_id}: {e}"
        )
        raise HTTPException(
            status_code=500, detail=f"Failed to link document: {str(e)}"
        )


@router.get("/{meeting_id}/documents", response_model=List[DocumentResponse])
def get_meeting_documents(meeting_id: int, db: Session = Depends(get_db)):
    """Get all documents linked to a specific meeting"""
    try:
        # Check if meeting exists
        meeting = db.query(Meeting).filter(Meeting.id == meeting_id).first()
        if not meeting:
            raise HTTPException(status_code=404, detail="Meeting not found")

        # Get documents linked to this meeting
        documents = (
            db.query(Document).filter(Document.meeting_id == meeting_id).all()
        )
        return documents
    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            f"Error fetching documents for meeting {meeting_id}: {str(e)}"
        )
        raise HTTPException(
            status_code=500,
            detail=f"Failed to fetch meeting documents: {str(e)}",
        )
