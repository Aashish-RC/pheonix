"""
System settings and rules synchronizer.
"""
from __future__ import annotations

from typing import Any, Dict, Optional
from sync_engine.core.delta_tracker import DeltaChangeTracker
from sync_engine.core.models import EntityType, MutationType, SyncEntity


class SettingsSynchronizer:
    """Synchronizes preferences, permission modes, and rule definitions."""

    def __init__(self, tracker: DeltaChangeTracker):
        self.tracker = tracker
        self.settings: Dict[str, SyncEntity] = {}

    def set_preference(self, key: str, value: Any) -> SyncEntity:
        payload = {"key": key, "value": value}
        mut = self.tracker.record_mutation(
            entity_id=f"pref_{key}",
            entity_type=EntityType.SETTINGS,
            mutation_type=MutationType.UPDATE if f"pref_{key}" in self.settings else MutationType.INSERT,
            payload=payload,
        )

        entity = SyncEntity(
            entity_id=f"pref_{key}",
            entity_type=EntityType.SETTINGS,
            data=payload,
            lamport_clock=mut.lamport_clock,
            updated_at=mut.timestamp,
            node_id=self.tracker.node_id,
        )
        self.settings[f"pref_{key}"] = entity
        return entity

    def get_preference(self, key: str, default: Any = None) -> Any:
        entity = self.settings.get(f"pref_{key}")
        if not entity or entity.deleted:
            return default
        return entity.data.get("value", default)
