"""
Delta Change Tracker capturing local mutations for state synchronization.
"""
from __future__ import annotations

import time
from typing import Any, Dict, List, Optional
from sync_engine.core.models import DeltaMutation, EntityType, MutationType


class DeltaChangeTracker:
    """Audit log and delta tracker for entity mutations."""

    def __init__(self, node_id: str = "node_local"):
        self.node_id = node_id
        self._lamport_clock = 0
        self._mutations: List[DeltaMutation] = []

    def record_mutation(
        self,
        entity_id: str,
        entity_type: EntityType,
        mutation_type: MutationType,
        payload: Dict[str, Any],
    ) -> DeltaMutation:
        self._lamport_clock += 1
        mutation = DeltaMutation(
            entity_id=entity_id,
            entity_type=entity_type,
            mutation_type=mutation_type,
            payload=payload,
            lamport_clock=self._lamport_clock,
            timestamp=time.time(),
            node_id=self.node_id,
        )
        self._mutations.append(mutation)
        return mutation

    def get_deltas_since(self, since_timestamp: float) -> List[DeltaMutation]:
        return [m for m in self._mutations if m.timestamp >= since_timestamp]

    def all_mutations(self) -> List[DeltaMutation]:
        return list(self._mutations)

    def advance_clock(self, incoming_clock: int) -> int:
        self._lamport_clock = max(self._lamport_clock, incoming_clock) + 1
        return self._lamport_clock
