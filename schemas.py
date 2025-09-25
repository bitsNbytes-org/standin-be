from pydantic import BaseModel, EmailStr, Field
from datetime import datetime
from typing import Optional, List
from models import DocumentType


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
    content: str  # Changed from dict to str
    filename: str
    bucket: str = "default-bucket"
    project_id: Optional[int] = None
    meeting_id: Optional[int] = None
    doc_type: DocumentType = DocumentType.FILE
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
    content: Optional[str] = None  # Changed from dict to str
    filename: Optional[str] = None
    bucket: Optional[str] = None
    project_id: Optional[int] = None
    meeting_id: Optional[int] = None
    doc_type: DocumentType
    created_at: datetime
    updated_at: Optional[datetime] = None
    external_link: Optional[str] = None

    class Config:
        from_attributes = True


class ProjectWithDocumentsResponse(ProjectResponse):
    documents: List[DocumentResponse] = []

    class Config:
        from_attributes = True


# Simplified Document Content Schema
class DocumentContent(BaseModel):
    """Simplified document content structure"""
    page_id: str
    title: str
    content: str
    url: str
    source: str  # jira, confluence, file


# Comprehensive Document API Schemas
class DocumentImportRequest(BaseModel):
    """Unified request for importing documents from various sources"""

    source: str = Field(
        ..., description="Source type: 'url', 'file', or 'content'"
    )
    url: Optional[str] = Field(
        None, description="URL for Confluence or JIRA links"
    )
    filename: Optional[str] = Field(
        None, description="Custom filename (auto-generated if not provided)"
    )
    include_subtasks: bool = Field(
        True, description="Include subtasks for JIRA issues"
    )
    content: Optional[dict] = Field(
        None, description="Raw content for direct import"
    )


class DocumentImportResponse(BaseModel):
    """Unified response for document imports"""

    document_id: int
    source_type: str
    title: str
    filename: str
    bucket: str
    external_link: Optional[str] = None
    message: str
    metadata: Optional[dict] = None


# Meeting schemas
class MeetingBase(BaseModel):
    title: str
    description: Optional[str] = None
    project_id: Optional[int] = None
    attendees: Optional[List[str]] = []  # List of attendee emails
    documentation_links: Optional[List[str]] = []  # List of documentation URLs
    additional_information: Optional[str] = None


class MeetingCreate(MeetingBase):
    start_time: datetime
    end_time: datetime
    meeting_link: Optional[str] = None  # Custom meeting room link
    # Document import fields
    document_source: Optional[str] = None  # "url", "file", "content"
    document_url: Optional[str] = None
    document_filename: Optional[str] = None
    document_content: Optional[str] = None
    include_subtasks: bool = True


class MeetingResponse(MeetingBase):
    id: int
    start_time: datetime
    end_time: datetime
    meeting_link: Optional[str] = None
    google_calendar_event_id: Optional[str] = None
    status: str = "scheduled"
    pid: Optional[int] = None
    created_at: datetime
    updated_at: Optional[datetime] = None
    documents: List[DocumentResponse] = []

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
