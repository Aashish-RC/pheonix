"""
Chat session state synchronizer.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional
from sync_engine.core.delta_tracker import DeltaChangeTracker
from sync_engine.core.models import EntityType, MutationType, SyncEntity


class ChatSessionSynchronizer:
    """Manages cross-device synchronization of active and historical chat sessions."""

    def __init__(self, tracker: DeltaChangeTracker):
        self.tracker = tracker
        self.sessions: Dict[str, SyncEntity] = {}

    def upsert_chat(self, chat_id: str, title: str, messages: List[Dict[str, Any]]) -> SyncEntity:
        payload = {"title": title, "messages": messages}
        mut = self.tracker.record_mutation(
            entity_id=chat_id,
            entity_type=EntityType.CHAT,
            mutation_type=MutationType.UPDATE if chat_id in self.sessions else MutationType.INSERT,
            payload=payload,
        )

        entity = SyncEntity(
            entity_id=chat_id,
            entity_type=EntityType.CHAT,
            data=payload,
            lamport_clock=mut.lamport_clock,
            updated_at=mut.timestamp,
            node_id=self.tracker.node_id,
        )
        self.sessions[chat_id] = entity
        return entity

    def delete_chat(self, chat_id: str) -> Optional[SyncEntity]:
        if chat_id not in self.sessions:
            return None
        mut = self.tracker.record_mutation(
            entity_id=chat_id,
            entity_type=EntityType.CHAT,
            mutation_type=MutationType.DELETE,
            payload={},
        )
        entity = self.sessions[chat_id]
        entity.deleted = True
        entity.lamport_clock = mut.lamport_clock
        entity.updated_at = mut.timestamp
        return entity
