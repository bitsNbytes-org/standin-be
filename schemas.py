from pydantic import BaseModel, EmailStr, Field
from datetime import datetime
from typing import Optional, Union, List
from fastapi import UploadFile
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
    source: str = Field(..., description="Source type: 'url', 'file', or 'content'")
    url: Optional[str] = Field(None, description="URL for Confluence or JIRA links")
    filename: Optional[str] = Field(None, description="Custom filename (auto-generated if not provided)")
    include_subtasks: bool = Field(True, description="Include subtasks for JIRA issues")
    content: Optional[str] = Field(None, description="Raw content for direct import")


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
    title: Optional[str] = None
    description: Optional[str] = None
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    meeting_link: Optional[str] = None
    external_id: Optional[str] = None
    participants: Optional[dict] = None
    meta_data: Optional[dict] = None


class MeetingCreate(MeetingBase):
    pass


class MeetingResponse(MeetingBase):
    id: int
    created_at: datetime
    updated_at: Optional[datetime] = None
    documents: List[DocumentResponse] = []

    class Config:
        from_attributes = True


class MeetingWithDocumentsResponse(MeetingResponse):
    """Meeting response with documents included via left join"""
    documents: List[DocumentResponse] = []

    class Config:
        from_attributes = True


