from pydantic import BaseModel, HttpUrl
from sqlalchemy import Column, String, DateTime, Text, Integer, Boolean
from sqlalchemy.sql import func
from datetime import datetime
from typing import Optional, List
import uuid
from src.database.connection import Base

# SQLAlchemy Model
class ImageResourceModel(Base):
    __tablename__ = "image_resources"
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    url = Column(String(500), nullable=False, unique=True)
    filename = Column(String(255), nullable=True)
    file_path = Column(String(500), nullable=True)
    file_size = Column(Integer, nullable=True)
    width = Column(Integer, nullable=True)
    height = Column(Integer, nullable=True)
    format = Column(String(10), nullable=True)  # jpg, png, webp, etc.
    source = Column(String(100), nullable=True)  # pexels, unsplash, etc.
    search_query = Column(String(200), nullable=True)
    tags = Column(Text, nullable=True)  # JSON string of tags
    description = Column(Text, nullable=True)
    photographer = Column(String(200), nullable=True)
    photographer_url = Column(String(500), nullable=True)
    is_downloaded = Column(Boolean, default=False)
    download_status = Column(String(50), default="pending")  # pending, downloading, completed, failed
    error_message = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

# Pydantic Schemas
class ImageResourceBase(BaseModel):
    url: HttpUrl
    filename: Optional[str] = None
    file_path: Optional[str] = None
    file_size: Optional[int] = None
    width: Optional[int] = None
    height: Optional[int] = None
    format: Optional[str] = None
    source: Optional[str] = None
    search_query: Optional[str] = None
    tags: Optional[List[str]] = None
    description: Optional[str] = None
    photographer: Optional[str] = None
    photographer_url: Optional[str] = None

class ImageResourceCreate(ImageResourceBase):
    pass

class ImageResourceUpdate(BaseModel):
    filename: Optional[str] = None
    file_path: Optional[str] = None
    file_size: Optional[int] = None
    width: Optional[int] = None
    height: Optional[int] = None
    format: Optional[str] = None
    source: Optional[str] = None
    search_query: Optional[str] = None
    tags: Optional[List[str]] = None
    description: Optional[str] = None
    photographer: Optional[str] = None
    photographer_url: Optional[str] = None
    is_downloaded: Optional[bool] = None
    download_status: Optional[str] = None
    error_message: Optional[str] = None

class ImageResource(ImageResourceBase):
    id: str
    is_downloaded: bool
    download_status: str
    error_message: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True

class ImageResourceResponse(BaseModel):
    id: str
    url: str
    filename: Optional[str] = None
    file_path: Optional[str] = None
    file_size: Optional[int] = None
    width: Optional[int] = None
    height: Optional[int] = None
    format: Optional[str] = None
    source: Optional[str] = None
    search_query: Optional[str] = None
    tags: Optional[List[str]] = None
    description: Optional[str] = None
    photographer: Optional[str] = None
    photographer_url: Optional[str] = None
    is_downloaded: bool
    download_status: str
    error_message: Optional[str] = None
    created_at: datetime
    updated_at: datetime

class ImageResourceList(BaseModel):
    items: List[ImageResourceResponse]
    total: int
    page: int
    per_page: int
    total_pages: int