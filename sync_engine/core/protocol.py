"""
Cryptographic sync packet serialization, verification, and ingestion protocol.
"""
from __future__ import annotations

import hashlib
import json
import time
from typing import Dict, List, Tuple
from sync_engine.core.models import DeltaMutation, MutationType, SyncEntity, SyncPacket, SyncStatus
from sync_engine.core.resolver import ConflictResolver


class SyncProtocol:
    """Manages creation, cryptographic signing, and ingestion of sync packets."""

    def __init__(self, resolver: ConflictResolver | None = None):
        self.resolver = resolver or ConflictResolver()

    def create_packet(
        self,
        source_node_id: str,
        target_node_id: str,
        mutations: List[DeltaMutation],
        tenant_id: str = "default",
    ) -> SyncPacket:
        # Compute SHA-256 over canonical mutation serialization
        raw_bytes = json.dumps([m.model_dump() for m in mutations], sort_keys=True).encode("utf-8")
        checksum = hashlib.sha256(raw_bytes).hexdigest()

        return SyncPacket(
            tenant_id=tenant_id,
            source_node_id=source_node_id,
            target_node_id=target_node_id,
            mutations=mutations,
            sha256_checksum=checksum,
            created_at=time.time(),
        )

    def verify_packet(self, packet: SyncPacket) -> bool:
        raw_bytes = json.dumps([m.model_dump() for m in packet.mutations], sort_keys=True).encode("utf-8")
        calculated = hashlib.sha256(raw_bytes).hexdigest()
        return calculated == packet.sha256_checksum

    def ingest_packet(
        self,
        packet: SyncPacket,
        entity_store: Dict[str, SyncEntity],
    ) -> SyncStatus:
        if not self.verify_packet(packet):
            raise ValueError("SyncPacket checksum mismatch; packet has been corrupted or tampered with")

        applied = 0
        conflicts = 0

        for mut in packet.mutations:
            local = entity_store.get(mut.entity_id)
            if not local:
                # Brand new entity
                entity_store[mut.entity_id] = SyncEntity(
                    entity_id=mut.entity_id,
                    tenant_id=getattr(mut, "tenant_id", "default"),
                    entity_type=mut.entity_type,
                    data=mut.payload,
                    lamport_clock=mut.lamport_clock,
                    updated_at=mut.timestamp,
                    node_id=mut.node_id,
                    deleted=(mut.mutation_type == MutationType.DELETE),
                )
                applied += 1
            else:
                # Conflict resolution
                resolved, had_conflict = self.resolver.resolve(local, mut)
                entity_store[mut.entity_id] = resolved
                applied += 1
                if had_conflict:
                    conflicts += 1

        return SyncStatus(
            synced_entities_count=len(entity_store),
            conflicts_resolved=conflicts,
            applied_mutations=applied,
            last_sync_timestamp=time.time(),
        )
