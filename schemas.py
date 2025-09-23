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


# Item schemas
class ItemBase(BaseModel):
    title: str
    description: Optional[str] = None


class ItemCreate(ItemBase):
    owner_id: int


class ItemResponse(ItemBase):
    id: int
    owner_id: int
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
