"""
Pheonix Component Registry Models
"""

import time
from typing import List, Optional, Dict
from pydantic import BaseModel, Field


class DependencyRule(BaseModel):
    component_name: str
    version_constraint: str  # e.g., ">=0.1.0, <1.0.0", "^0.1.0"
    optional: bool = False


class ChangelogEntry(BaseModel):
    version: str
    date: str
    changes: List[str]
    breaking: bool = False


class ComponentManifest(BaseModel):
    name: str
    version: str  # SemVer 2.0 (e.g., "0.1.0")
    description: str
    dependencies: List[DependencyRule] = Field(default_factory=list)
    changelog: List[ChangelogEntry] = Field(default_factory=list)
    sha256_hash: Optional[str] = None
    created_at: float = Field(default_factory=time.time)
    updated_at: float = Field(default_factory=time.time)


class ValidationResult(BaseModel):
    is_compatible: bool
    reasons: List[str] = Field(default_factory=list)
    affected_components: List[str] = Field(default_factory=list)


class UpdatePlan(BaseModel):
    component_name: str
    from_version: Optional[str] = None
    to_version: str
    can_apply: bool
    block_reasons: List[str] = Field(default_factory=list)
    timestamp: float = Field(default_factory=time.time)
