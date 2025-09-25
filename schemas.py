from pydantic import BaseModel, EmailStr
from datetime import datetime
from typing import Optional, List


# User schemas
class UserBase(BaseModel):
    name: str
    email: EmailStr


class UserCreate(UserBase):
    pass


class UserResponse(UserBase):
    id: int
    is_active: bool
    created_at: datetime
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


# File upload schemas
class FileUploadResponse(BaseModel):
    message: str
    filename: str
    bucket: str


class FileListResponse(BaseModel):
    name: str
    size: int
    last_modified: datetime


class DocumentCreate(BaseModel):
    content: dict
    filename: str
    bucket: str = "default-bucket"
    project_id: Optional[int] = None
    external_link: Optional[str] = None


class ConfluencePageRequest(BaseModel):
    url: str
    bucket: str = "confluence-docs"


class ConfluencePageResponse(BaseModel):
    document_id: int
    title: str
    filename: str
    page_id: str
    space_name: str
    message: str


class JiraIssueRequest(BaseModel):
    url: str
    bucket: str = "jira-docs"
    include_subtasks: bool = True


class JiraSearchRequest(BaseModel):
    jql: str
    bucket: str = "jira-docs"
    max_results: int = 50


class JiraIssueResponse(BaseModel):
    document_id: int
    title: str
    filename: str
    issue_key: str
    project_name: str
    message: str


class JiraSearchResponse(BaseModel):
    document_ids: list[int]
    total_found: int
    message: str


class JiraProjectImportRequest(BaseModel):
    project_key: str
    bucket: str = "jira-project-docs"
    include_subtasks: bool = True
    max_results: int = 1000


class JiraProjectImportResponse(BaseModel):
    project_key: str
    project_name: str
    total_issues: int
    issues_by_type: dict
    document_ids: list[int]
    processed_count: int
    failed_count: int
    message: str


# Project schemas
class ProjectBase(BaseModel):
    name: str
    description: Optional[str] = None


class ProjectCreate(ProjectBase):
    pass


class ProjectResponse(ProjectBase):
    id: int
    created_at: datetime

    class Config:
        from_attributes = True


class DocumentResponse(BaseModel):
    id: int
    content: Optional[dict] = None
    filename: Optional[str] = None
    bucket: Optional[str] = None
    project_id: Optional[int] = None
    created_at: datetime
    updated_at: Optional[datetime] = None
    external_link: Optional[str] = None

    class Config:
        from_attributes = True


class ProjectWithDocumentsResponse(ProjectResponse):
    documents: List[DocumentResponse] = []

    class Config:
        from_attributes = True


# Meeting schemas
class MeetingBase(BaseModel):
    title: str
    description: Optional[str] = None
    project_id: Optional[int] = None
    attendees: Optional[List[str]] = []  # List of attendee emails
    documentation_links: Optional[List[str]] = []  # List of documentation URLs
    additional_information: Optional[str] = None
    meeting_link: Optional[str] = None  # Custom meeting room link


class MeetingCreate(MeetingBase):
    start_time: datetime
    end_time: datetime
    documents: Optional[List[dict]] = []  # Optional documents to create


class MeetingResponse(MeetingBase):
    id: int
    start_time: datetime
    end_time: datetime
    google_calendar_event_id: Optional[str] = None
    status: str = "scheduled"
    created_at: datetime
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class MeetingUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    attendees: Optional[List[str]] = None
    documentation_links: Optional[List[str]] = None
    additional_information: Optional[str] = None
    meeting_link: Optional[str] = None
    status: Optional[str] = None
