"""
Pheonix Storage and Files Data Models
Defines schema for stored assets, metadata, quotas, and reuse requests.
"""

from typing import List, Optional
from pydantic import BaseModel, Field


class StoredFile(BaseModel):
    """Metadata representing an indexed, persistent file asset."""
    file_id: str
    filename: str
    content_type: str = "application/octet-stream"
    size_bytes: int = Field(default=0, ge=0)
    sha256_hash: str
    project_id: str = "default"
    owner_id: str = "anonymous"
    created_at: str
    uri: str
    tags: List[str] = Field(default_factory=list)


class StorageQuota(BaseModel):
    """Storage boundaries allocated to a project or tenant."""
    project_id: str
    max_bytes: int = Field(default=104_857_600, ge=1)  # 100MB default
    used_bytes: int = Field(default=0, ge=0)
    max_files: int = Field(default=1000, ge=1)
    file_count: int = Field(default=0, ge=0)


class FileReuseRequest(BaseModel):
    """Request to link an existing file asset into a new project scope."""
    file_id: str
    target_project_id: str
    target_owner_id: Optional[str] = None
    new_filename: Optional[str] = None
