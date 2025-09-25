from sqlalchemy import (
    Column, Integer, String, DateTime, Boolean, ForeignKey, Enum
)
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from database import Base
from sqlalchemy.dialects.postgresql import JSON, JSONB
import enum


class DocumentType(str, enum.Enum):
    FILE = "file"
    JIRA = "jira"
    CONFLUENCE = "confluence"


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False)
    email = Column(String(255), unique=True, index=True, nullable=False)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())


class Project(Base):
    __tablename__ = "projects"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False)
    description = Column(String(1000), nullable=True)
    meta_data = Column(JSONB, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # Relationship with documents
    documents = relationship("Document", back_populates="project")


class Meeting(Base):
    __tablename__ = "meetings"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(255), nullable=False)
    description = Column(String(1000), nullable=True)
    project_id = Column(Integer, ForeignKey("projects.id"), nullable=True)
    start_time = Column(DateTime(timezone=True), nullable=False)
    end_time = Column(DateTime(timezone=True), nullable=False)
    attendees = Column(JSON, nullable=True)
    documentation_links = Column(JSON, nullable=True)
    additional_information = Column(String(2000), nullable=True)
    meeting_link = Column(String(500), nullable=True)
    google_calendar_event_id = Column(String(255), nullable=True)
    pid = Column(Integer, nullable=True)
    status = Column(String(50), default="scheduled")
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    external_id = Column(String(255), nullable=True)
    participants = Column(JSON, nullable=True)
    meta_data = Column(JSONB, nullable=True)

    # Relationship with project
    project = relationship("Project", backref="meetings")
    # Relationship with documents (one-to-many)
    documents = relationship("Document", back_populates="meeting")


class Document(Base):
    __tablename__ = "documents"

    id = Column(Integer, primary_key=True, index=True)
    content = Column(JSON, nullable=True)
    filename = Column(String(255), nullable=True)
    bucket = Column(String(255), nullable=True)
    project_id = Column(Integer, ForeignKey("projects.id"), nullable=True)
    meeting_id = Column(Integer, ForeignKey("meetings.id"), nullable=True)
    doc_type = Column(Enum(DocumentType), default=DocumentType.FILE, nullable=False)
    source = Column(String(50), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    external_link = Column(String(255), nullable=True)

    # Relationships
    project = relationship("Project", back_populates="documents")
    meeting = relationship("Meeting", back_populates="documents")
