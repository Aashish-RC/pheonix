"""
Data models for Cross-Device Synchronization, CRDTs, and Delta Replication.
"""
from __future__ import annotations

import time
import uuid
from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class EntityType(str, Enum):
    CHAT = "chat"
    MEMORY = "memory"
    SETTINGS = "settings"
    RULE = "rule"


class MutationType(str, Enum):
    INSERT = "insert"
    UPDATE = "update"
    DELETE = "delete"


class SyncEntity(BaseModel):
    entity_id: str
    entity_type: EntityType
    data: Dict[str, Any]
    lamport_clock: int = 1
    updated_at: float = Field(default_factory=time.time)
    node_id: str = "node_local"
    deleted: bool = False


class DeltaMutation(BaseModel):
    mutation_id: str = Field(default_factory=lambda: f"mut_{uuid.uuid4().hex[:10]}")
    entity_id: str
    entity_type: EntityType
    mutation_type: MutationType
    payload: Dict[str, Any]
    lamport_clock: int
    timestamp: float = Field(default_factory=time.time)
    node_id: str


class SyncPacket(BaseModel):
    packet_id: str = Field(default_factory=lambda: f"spkt_{uuid.uuid4().hex[:10]}")
    source_node_id: str
    target_node_id: str
    mutations: List[DeltaMutation] = Field(default_factory=list)
    sha256_checksum: str
    created_at: float = Field(default_factory=time.time)


class SyncStatus(BaseModel):
    synced_entities_count: int = 0
    conflicts_resolved: int = 0
    applied_mutations: int = 0
    last_sync_timestamp: float = Field(default_factory=time.time)
