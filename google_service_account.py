"""
Google Calendar Service Account implementation for StandIn
This allows calendar invites to come from your organization email
"""

import os
import json
from datetime import datetime
from typing import List, Optional, Dict, Any
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
import logging

logger = logging.getLogger(__name__)


class GoogleCalendarServiceAccount:
    def __init__(self, delegated_user_email: str = None):
        self.service = None
        self.delegated_user_email = delegated_user_email or os.getenv(
            'STANDIN_CALENDAR_EMAIL', 'standin@yourcompany.com'
        )
        self.service_account_file = os.getenv(
            'GOOGLE_SERVICE_ACCOUNT_FILE', 'service-account-key.json'
        )
        self.scopes = ['https://www.googleapis.com/auth/calendar']
        
    def authenticate(self) -> bool:
        """Authenticate using service account with domain-wide delegation"""
        try:
            if not os.path.exists(self.service_account_file):
                logger.error(f"Service account file not found: {self.service_account_file}")
                return False
            
            # Load service account credentials
            credentials = service_account.Credentials.from_service_account_file(
                self.service_account_file,
                scopes=self.scopes
            )
            
            # Delegate to specific user
            delegated_credentials = credentials.with_subject(self.delegated_user_email)
            
            # Build service
            self.service = build('calendar', 'v3', credentials=delegated_credentials)
            
            # Test the connection
            self.service.calendarList().list().execute()
            
            logger.info(f"Successfully authenticated as {self.delegated_user_email}")
            return True
            
        except Exception as e:
            logger.error(f"Service account authentication failed: {e}")
            return False
    
    def create_event(
        self,
        title: str,
        description: str,
        start_time: datetime,
        end_time: datetime,
        attendees: List[str],
        meeting_link: Optional[str] = None,
        calendar_id: str = 'primary'
    ) -> Optional[str]:
        """Create calendar event using service account"""
        if not self.service:
            if not self.authenticate():
                return None
        
        # Prepare event data
        event_data = {
            'summary': f"[StandIn] {title}",
            'description': f"📅 Scheduled by StandIn Meeting Scheduler\n\n{description}",
            'start': {
                'dateTime': start_time.isoformat(),
                'timeZone': str(start_time.tzinfo) if start_time.tzinfo else 'UTC',
            },
            'end': {
                'dateTime': end_time.isoformat(),
                'timeZone': str(end_time.tzinfo) if end_time.tzinfo else 'UTC',
            },
            'attendees': [{'email': email} for email in attendees],
            'reminders': {
                'useDefault': False,
                'overrides': [
                    {'method': 'email', 'minutes': 24 * 60},
                    {'method': 'popup', 'minutes': 30},
                ],
            },
            'organizer': {
                'email': self.delegated_user_email,
                'displayName': 'StandIn Meeting Scheduler'
            }
        }
        
        if meeting_link:
            event_data['location'] = meeting_link
        
        try:
            event = self.service.events().insert(
                calendarId=calendar_id,
                body=event_data,
                sendUpdates='all'
            ).execute()
            
            logger.info(f"Event created by {self.delegated_user_email}: {event.get('htmlLink')}")
            return event.get('id')
            
        except HttpError as error:
            logger.error(f"Failed to create event: {error}")
            return None
    
    def update_event(
        self,
        event_id: str,
        title: Optional[str] = None,
        description: Optional[str] = None,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        attendees: Optional[List[str]] = None,
        meeting_link: Optional[str] = None,
        calendar_id: str = 'primary'
    ) -> bool:
        """Update an existing calendar event"""
        if not self.service:
            if not self.authenticate():
                return False
        
        try:
            # Get existing event
            event = self.service.events().get(
                calendarId=calendar_id,
                eventId=event_id
            ).execute()
            
            # Update fields if provided
            if title:
                event['summary'] = f"[StandIn] {title}"
            if description:
                event['description'] = f"📅 Scheduled by StandIn Meeting Scheduler\n\n{description}"
            if start_time:
                event['start'] = {
                    'dateTime': start_time.isoformat(),
                    'timeZone': str(start_time.tzinfo) if start_time.tzinfo else 'UTC',
                }
            if end_time:
                event['end'] = {
                    'dateTime': end_time.isoformat(),
                    'timeZone': str(end_time.tzinfo) if end_time.tzinfo else 'UTC',
                }
            if attendees:
                event['attendees'] = [{'email': email} for email in attendees]
            if meeting_link:
                event['location'] = meeting_link
            
            # Update the event
            self.service.events().update(
                calendarId=calendar_id,
                eventId=event_id,
                body=event,
                sendUpdates='all'
            ).execute()
            
            return True
            
        except HttpError as error:
            logger.error(f"Failed to update event: {error}")
            return False
    
    def delete_event(self, event_id: str, calendar_id: str = 'primary') -> bool:
        """Delete a calendar event"""
        if not self.service:
            if not self.authenticate():
                return False
        
        try:
            self.service.events().delete(
                calendarId=calendar_id,
                eventId=event_id,
                sendUpdates='all'
            ).execute()
            
            logger.info(f"Event deleted: {event_id}")
            return True
            
        except HttpError as error:
            logger.error(f"Failed to delete event: {error}")
            return False
