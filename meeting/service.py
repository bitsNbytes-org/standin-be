import logging
import requests
from config import settings
from models import Document, Meeting
from database import get_db
from sqlalchemy.orm import Session

from schemas import AIMeetingNarrationRequest, DocumentSchema
logger = logging.getLogger(__name__)


def create_narration(meeting: Meeting, db: Session) -> Meeting:
    """Create a narration for the meeting"""

    project_id = meeting.project_id

    project_docs = db.query(Document).filter(Document.project_id == project_id).all()
    # Convert Document model objects to DocumentSchema objects
    documents = [
        DocumentSchema(
            id=doc.id,
            content=doc.content,
            filename=doc.filename,
            bucket=doc.bucket,
            doc_type=doc.doc_type,
            external_link=doc.external_link
        )
        for doc in meeting.documents + project_docs
    ]
    
    

    # Handle attendees - get first attendee or use empty string if none
    attendee = meeting.attendees[0] if meeting.attendees and len(meeting.attendees) > 0 else ""
    
    # Convert timedelta to seconds (integer)
    duration = int((meeting.end_time - meeting.start_time).total_seconds())
    
    external_api_url = f"{settings.AI_MEETING_SERVICE_END_POINT}/create_meeting_narration"
    response = requests.post(external_api_url, json=AIMeetingNarrationRequest(documents=documents, attendee=attendee, duration=duration).dict())
    """the response will be an array of narrations it should be stored in the meeting meta_data"""
    meeting.meta_data = response.json()
    db.commit()
    db.refresh(meeting)
    logger.info(f"Meeting {meeting.id} narration created successfully for {attendee} with duration {duration} for {len(documents)} documents")
    return meeting