from fastapi import requests
from config import settings
from models import Meeting
from database import get_db
from sqlalchemy.orm import Session

from schemas import AIMeetingNarrationRequest


def create_narration(meeting: Meeting, db: Session) -> Meeting:
    """Create a narration for the meeting"""
    documents = meeting.documents
    attendee = meeting.attendees[0]
    duration = meeting.end_time - meeting.start_time
    external_api_url = f"{settings.AI_MEETING_SERVICE_END_POINT}/create_meeting_narration"
    response = requests.post(external_api_url, json=AIMeetingNarrationRequest(documents=documents, attendee=attendee, duration=duration).dict())
    """the response will be an array of narrations it should be stored in the meeting meta_data"""
    meeting.meta_data = response.json()
    db.commit()
    db.refresh(meeting)
    return meeting