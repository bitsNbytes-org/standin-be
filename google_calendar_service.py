"""
Google Calendar integration service for meeting scheduling
"""

import os
import json
from datetime import datetime, timezone
from typing import List, Optional, Dict, Any
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
import logging

logger = logging.getLogger(__name__)

# If modifying these scopes, delete the file token.json.
SCOPES = ["https://www.googleapis.com/auth/calendar"]


class GoogleCalendarService:
    def __init__(self):
        self.service = None
        self.credentials_file = os.getenv(
            "GOOGLE_CREDENTIALS_FILE", "credentials.json"
        )
        self.token_file = os.getenv("GOOGLE_TOKEN_FILE", "token.json")

    def authenticate(self) -> bool:
        """Authenticate with Google Calendar API"""
        creds = None

        # The file token.json stores the user's access and refresh tokens.
        if os.path.exists(self.token_file):
            creds = Credentials.from_authorized_user_file(
                self.token_file, SCOPES
            )

        # If there are no (valid) credentials available, let the user log in.
        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                try:
                    creds.refresh(Request())
                except Exception as e:
                    logger.error(f"Failed to refresh credentials: {e}")
                    return False
            else:
                if not os.path.exists(self.credentials_file):
                    logger.error(
                        f"Credentials file not found: {self.credentials_file}"
                    )
                    return False

                try:
                    flow = InstalledAppFlow.from_client_secrets_file(
                        self.credentials_file, SCOPES
                    )
                    creds = flow.run_local_server(port=0)
                except Exception as e:
                    logger.error(f"Failed to authenticate: {e}")
                    return False

            # Save the credentials for the next run
            try:
                with open(self.token_file, "w") as token:
                    token.write(creds.to_json())
            except Exception as e:
                logger.error(f"Failed to save token: {e}")

        try:
            self.service = build("calendar", "v3", credentials=creds)
            return True
        except Exception as e:
            logger.error(f"Failed to build calendar service: {e}")
            return False

    def create_event(
        self,
        title: str,
        description: str,
        start_time: datetime,
        end_time: datetime,
        attendees: List[str],
        meeting_link: Optional[str] = None,
        calendar_id: str = "primary",
    ) -> Optional[str]:
        """
        Create a Google Calendar event

        Returns:
            str: Google Calendar event ID if successful, None otherwise
        """
        if not self.service:
            if not self.authenticate():
                return None

        # Ensure datetime objects have timezone info
        if start_time.tzinfo is None:
            start_time = start_time.replace(tzinfo=timezone.utc)
        if end_time.tzinfo is None:
            end_time = end_time.replace(tzinfo=timezone.utc)

        # Validate time range
        if end_time <= start_time:
            logger.error(
                f"Invalid time range: "
                f"start_time={start_time}, end_time={end_time}"
            )
            return None

        logger.info(f"Creating Google Calendar event: {title}")
        logger.info(f"Start time: {start_time} ({start_time.isoformat()})")
        logger.info(f"End time: {end_time} ({end_time.isoformat()})")

        # Prepare event data
        event_data = {
            "summary": f"[StandIn] {title}",
            "description": f"📅 Scheduled by StandIn Meeting Scheduler\n\n{description}",
            "start": {
                "dateTime": start_time.isoformat(),
                "timeZone": "UTC",
            },
            "end": {
                "dateTime": end_time.isoformat(),
                "timeZone": "UTC",
            },
            "attendees": [{"email": email} for email in attendees],
            "reminders": {
                "useDefault": False,
                "overrides": [
                    {"method": "email", "minutes": 24 * 60},  # 1 day before
                    {"method": "popup", "minutes": 30},  # 30 minutes before
                ],
            },
        }

        # Add meeting link if provided
        if meeting_link:
            event_data["location"] = meeting_link
            # Only add conference data if we want to create a Google Meet link
            # For custom meeting links, just use location
            # event_data["conferenceData"] = {
            #     "createRequest": {
            #         "requestId": f"meeting_{int(datetime.now().timestamp())}",
            #         "conferenceSolutionKey": {"type": "hangoutsMeet"},
            #     }
            # }

        try:
            event = (
                self.service.events()
                .insert(
                    calendarId=calendar_id,
                    body=event_data,
                    sendUpdates="all",  # Send invitations to all attendees
                )
                .execute()
            )

            logger.info(f"Event created: {event.get('htmlLink')}")
            return event.get("id")

        except HttpError as error:
            logger.error(f"An error occurred: {error}")
            return None
        except Exception as e:
            logger.error(f"Failed to create event: {e}")
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
        calendar_id: str = "primary",
    ) -> bool:
        """Update an existing Google Calendar event"""
        if not self.service:
            if not self.authenticate():
                return False

        try:
            # Get the existing event
            event = (
                self.service.events()
                .get(calendarId=calendar_id, eventId=event_id)
                .execute()
            )

            # Update fields if provided
            if title:
                event["summary"] = f"[StandIn] {title}"
            if description:
                event["description"] = (
                    f"📅 Scheduled by StandIn Meeting Scheduler\n\n{description}"
                )
            if start_time:
                if start_time.tzinfo is None:
                    start_time = start_time.replace(tzinfo=timezone.utc)
                event["start"] = {
                    "dateTime": start_time.isoformat(),
                    "timeZone": "UTC",
                }
            if end_time:
                if end_time.tzinfo is None:
                    end_time = end_time.replace(tzinfo=timezone.utc)
                event["end"] = {
                    "dateTime": end_time.isoformat(),
                    "timeZone": "UTC",
                }
            if attendees:
                event["attendees"] = [{"email": email} for email in attendees]
            if meeting_link:
                event["location"] = meeting_link

            # Update the event
            updated_event = (
                self.service.events()
                .update(
                    calendarId=calendar_id,
                    eventId=event_id,
                    body=event,
                    sendUpdates="all",
                )
                .execute()
            )

            logger.info(f"Event updated: {updated_event.get('htmlLink')}")
            return True

        except HttpError as error:
            logger.error(f"An error occurred: {error}")
            return False
        except Exception as e:
            logger.error(f"Failed to update event: {e}")
            return False

    def delete_event(
        self, event_id: str, calendar_id: str = "primary"
    ) -> bool:
        """Delete a Google Calendar event"""
        if not self.service:
            if not self.authenticate():
                return False

        try:
            self.service.events().delete(
                calendarId=calendar_id, eventId=event_id, sendUpdates="all"
            ).execute()

            logger.info(f"Event deleted: {event_id}")
            return True

        except HttpError as error:
            logger.error(f"An error occurred: {error}")
            return False
        except Exception as e:
            logger.error(f"Failed to delete event: {e}")
            return False

    def get_event(
        self, event_id: str, calendar_id: str = "primary"
    ) -> Optional[Dict[str, Any]]:
        """Get a Google Calendar event by ID"""
        if not self.service:
            if not self.authenticate():
                return None

        try:
            event = (
                self.service.events()
                .get(calendarId=calendar_id, eventId=event_id)
                .execute()
            )

            return event

        except HttpError as error:
            logger.error(f"An error occurred: {error}")
            return None
        except Exception as e:
            logger.error(f"Failed to get event: {e}")
            return None
