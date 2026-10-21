"""
Memory facts synchronizer across paired nodes.
"""
from __future__ import annotations

from typing import Any, Dict, Optional
from sync_engine.core.delta_tracker import DeltaChangeTracker
from sync_engine.core.models import EntityType, MutationType, SyncEntity


class MemoryFactSynchronizer:
    """Manages cross-device replication of long-term memory facts and citations."""

    def __init__(self, tracker: DeltaChangeTracker):
        self.tracker = tracker
        self.facts: Dict[str, SyncEntity] = {}

    def upsert_fact(self, fact_id: str, content: str, source: str = "user") -> SyncEntity:
        payload = {"content": content, "source": source}
        mut = self.tracker.record_mutation(
            entity_id=fact_id,
            entity_type=EntityType.MEMORY,
            mutation_type=MutationType.UPDATE if fact_id in self.facts else MutationType.INSERT,
            payload=payload,
        )

        entity = SyncEntity(
            entity_id=fact_id,
            entity_type=EntityType.MEMORY,
            data=payload,
            lamport_clock=mut.lamport_clock,
            updated_at=mut.timestamp,
            node_id=self.tracker.node_id,
        )
        self.facts[fact_id] = entity
        return entity

    def delete_fact(self, fact_id: str) -> Optional[SyncEntity]:
        if fact_id not in self.facts:
            return None
        mut = self.tracker.record_mutation(
            entity_id=fact_id,
            entity_type=EntityType.MEMORY,
            mutation_type=MutationType.DELETE,
            payload={},
        )
        entity = self.facts[fact_id]
        entity.deleted = True
        entity.lamport_clock = mut.lamport_clock
        entity.updated_at = mut.timestamp
        return entity
