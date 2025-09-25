from pydantic import BaseModel, EmailStr
from datetime import datetime
from typing import Optional


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