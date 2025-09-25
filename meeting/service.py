from fastapi import requests
from config import settings
from models import Meeting
from database import get_db
from sqlalchemy.orm import Session


def create_narration(meeting: Meeting, db: Session) -> Meeting:
    """Create a narration for the meeting"""
    external_api_url = f"{settings.AI_MEETING_SERVICE_END_POINT}/create_meeting_narration"
    response = requests.post(external_api_url, json=meeting.dict())
    """the response will be an array of narrations it should be stored in the meeting meta_data"""
    meeting.meta_data = response.json()
    db.commit()
    db.refresh(meeting)
    return meeting