"""
Deterministic Conflict Resolution using Lamport Clocks and Last-Write-Wins (LWW).
"""
from __future__ import annotations

from typing import Tuple
from sync_engine.core.models import DeltaMutation, MutationType, SyncEntity


class ConflictResolver:
    """Resolves concurrent state mutations deterministically."""

    def resolve(
        self,
        local: SyncEntity,
        incoming: DeltaMutation,
    ) -> Tuple[SyncEntity, bool]:
        """Resolves conflict between local entity and incoming delta mutation."""
        # Check if identical clock
        if incoming.lamport_clock == local.lamport_clock:
            # Deterministic tie-break: physical timestamp, then node_id lexicographical comparison
            incoming_wins = (
                incoming.timestamp > local.updated_at
                or (incoming.timestamp == local.updated_at and incoming.node_id > local.node_id)
            )
            had_conflict = True
        elif incoming.lamport_clock > local.lamport_clock:
            incoming_wins = True
            had_conflict = False
        else:
            incoming_wins = False
            had_conflict = True

        if not incoming_wins:
            return local, had_conflict

        # Incoming mutation wins: apply changes
        is_delete = (incoming.mutation_type == MutationType.DELETE)
        merged_data = dict(local.data)
        if not is_delete:
            merged_data.update(incoming.payload)

        updated_entity = SyncEntity(
            entity_id=local.entity_id,
            entity_type=local.entity_type,
            data=merged_data,
            lamport_clock=incoming.lamport_clock,
            updated_at=incoming.timestamp,
            node_id=incoming.node_id,
            deleted=is_delete,
        )
        return updated_entity, had_conflict
