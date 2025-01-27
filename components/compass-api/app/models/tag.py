import re
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field, field_validator

from app.models import AuditModel
from app.models.common import PyObjectId


def format_tag_name(name: str) -> str:
    """Format tag name to lowercase, replace spaces and symbols with single hyphen"""
    # Convert to lowercase
    name = name.lower()
    # Replace all non-alphanumeric characters with hyphen
    name = re.sub(r'[^a-z0-9]+', '-', name)
    # Remove leading/trailing hyphens
    name = name.strip('-')
    # Replace multiple hyphens with single hyphen
    name = re.sub(r'-+', '-', name)
    return name

class TagBase(BaseModel):
    """Base tag model"""
    name: str = Field(..., description="Tag name (will be formatted to lowercase with hyphens)")
    description: Optional[str] = Field(None, description="Tag description")

    @field_validator('name')
    @classmethod
    def format_name(cls, name: str) -> str:
        """Format and validate tag name"""
        return format_tag_name(name)

class TagCreate(TagBase):
    """Model for creating a new tag"""
    pass

class TagUpdate(TagBase):
    """Model for updating an existing tag"""
    pass

class TagInDB(TagBase,AuditModel):
    """Model for tag in database"""
    pass

class Tag(TagInDB):
    """API response model for tag"""
    pass

class TagList(BaseModel):
    """API response model for list of tags"""
    tags: list[TagInDB]

    class Config:
        populate_by_name = True
        arbitrary_types_allowed = True
        json_encoders = {
            datetime: lambda dt: dt.isoformat(),
            PyObjectId: str
        }
