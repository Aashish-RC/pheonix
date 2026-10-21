"""
Comprehensive automated test suite for State Synchronization Engine (Step 33).
"""
import pytest
import time
from sync_engine.core.delta_tracker import DeltaChangeTracker
from sync_engine.core.models import (
    DeltaMutation,
    EntityType,
    MutationType,
    SyncEntity,
    SyncPacket,
)
from sync_engine.core.protocol import SyncProtocol
from sync_engine.core.resolver import ConflictResolver
from sync_engine.providers.chat_sync import ChatSessionSynchronizer
from sync_engine.providers.memory_sync import MemoryFactSynchronizer
from sync_engine.providers.settings_sync import SettingsSynchronizer


def test_delta_change_tracker_mutations_and_clock():
    tracker = DeltaChangeTracker(node_id="node_a")

    t_start = time.time()
    mut1 = tracker.record_mutation(
        entity_id="entity_1",
        entity_type=EntityType.SETTINGS,
        mutation_type=MutationType.INSERT,
        payload={"theme": "dark"},
    )
    assert mut1.lamport_clock == 1
    assert mut1.node_id == "node_a"

    mut2 = tracker.record_mutation(
        entity_id="entity_1",
        entity_type=EntityType.SETTINGS,
        mutation_type=MutationType.UPDATE,
        payload={"theme": "system"},
    )
    assert mut2.lamport_clock == 2

    # Query deltas
    deltas = tracker.get_deltas_since(t_start - 0.01)
    assert len(deltas) == 2


def test_conflict_resolver_higher_clock_wins():
    resolver = ConflictResolver()

    local = SyncEntity(
        entity_id="entity_1",
        entity_type=EntityType.SETTINGS,
        data={"volume": 50},
        lamport_clock=2,
        updated_at=100.0,
        node_id="node_a",
    )

    incoming = DeltaMutation(
        entity_id="entity_1",
        entity_type=EntityType.SETTINGS,
        mutation_type=MutationType.UPDATE,
        payload={"volume": 80},
        lamport_clock=3,  # Higher clock
        timestamp=90.0,   # Even with earlier timestamp, Lamport clock dominates
        node_id="node_b",
    )

    resolved, had_conflict = resolver.resolve(local, incoming)
    assert resolved.data["volume"] == 80
    assert resolved.lamport_clock == 3
    assert had_conflict is False


def test_conflict_resolver_tie_breaker():
    resolver = ConflictResolver()

    local = SyncEntity(
        entity_id="pref_key",
        entity_type=EntityType.SETTINGS,
        data={"value": "local_val"},
        lamport_clock=5,
        updated_at=100.0,
        node_id="node_a",
    )

    # Equal clock, but incoming has later physical timestamp -> incoming wins
    incoming_later = DeltaMutation(
        entity_id="pref_key",
        entity_type=EntityType.SETTINGS,
        mutation_type=MutationType.UPDATE,
        payload={"value": "remote_val"},
        lamport_clock=5,
        timestamp=105.0,
        node_id="node_b",
    )

    res1, had_conflict1 = resolver.resolve(local, incoming_later)
    assert res1.data["value"] == "remote_val"
    assert had_conflict1 is True

    # Equal clock, earlier timestamp -> local keeps winning
    incoming_earlier = DeltaMutation(
        entity_id="pref_key",
        entity_type=EntityType.SETTINGS,
        mutation_type=MutationType.UPDATE,
        payload={"value": "stale_val"},
        lamport_clock=5,
        timestamp=95.0,
        node_id="node_b",
    )

    res2, had_conflict2 = resolver.resolve(local, incoming_earlier)
    assert res2.data["value"] == "local_val"
    assert had_conflict2 is True


def test_sync_protocol_packet_integrity_and_checksum():
    protocol = SyncProtocol()

    mut = DeltaMutation(
        entity_id="c_1",
        entity_type=EntityType.CHAT,
        mutation_type=MutationType.INSERT,
        payload={"title": "Test Chat"},
        lamport_clock=1,
        timestamp=time.time(),
        node_id="node_1",
    )

    packet = protocol.create_packet("node_1", "node_2", [mut])
    assert len(packet.sha256_checksum) == 64
    assert protocol.verify_packet(packet) is True

    # Tampering with mutation payload violates checksum
    mut.payload["title"] = "Hacked Title"
    assert protocol.verify_packet(packet) is False

    with pytest.raises(ValueError, match="checksum mismatch"):
        protocol.ingest_packet(packet, {})


def test_sync_protocol_packet_ingestion_end_to_end():
    protocol = SyncProtocol()

    mut1 = DeltaMutation(
        entity_id="chat_alpha",
        entity_type=EntityType.CHAT,
        mutation_type=MutationType.INSERT,
        payload={"title": "First Meeting"},
        lamport_clock=1,
        timestamp=time.time(),
        node_id="phone_1",
    )
    mut2 = DeltaMutation(
        entity_id="mem_fact_1",
        entity_type=EntityType.MEMORY,
        mutation_type=MutationType.INSERT,
        payload={"content": "Prefers concise responses"},
        lamport_clock=1,
        timestamp=time.time(),
        node_id="phone_1",
    )

    packet = protocol.create_packet("phone_1", "desktop_1", [mut1, mut2])
    entity_store = {}

    status = protocol.ingest_packet(packet, entity_store)
    assert status.applied_mutations == 2
    assert status.conflicts_resolved == 0
    assert "chat_alpha" in entity_store
    assert entity_store["chat_alpha"].data["title"] == "First Meeting"
    assert "mem_fact_1" in entity_store


def test_chat_session_synchronizer():
    tracker = DeltaChangeTracker(node_id="dev_laptop")
    sync = ChatSessionSynchronizer(tracker)

    # Upsert
    chat = sync.upsert_chat("chat_101", "Project Architecture", [{"role": "user", "text": "Plan Wave 8"}])
    assert chat.entity_id == "chat_101"
    assert chat.data["title"] == "Project Architecture"
    assert len(tracker.all_mutations()) == 1

    # Delete
    deleted = sync.delete_chat("chat_101")
    assert deleted is not None
    assert deleted.deleted is True
    assert len(tracker.all_mutations()) == 2


def test_memory_fact_synchronizer():
    tracker = DeltaChangeTracker(node_id="dev_desktop")
    sync = MemoryFactSynchronizer(tracker)

    fact = sync.upsert_fact("fact_01", "User works in timezone UTC+5:30", source="system")
    assert fact.entity_id == "fact_01"
    assert fact.data["content"] == "User works in timezone UTC+5:30"

    deleted = sync.delete_fact("fact_01")
    assert deleted.deleted is True


def test_settings_synchronizer():
    tracker = DeltaChangeTracker(node_id="dev_desktop")
    sync = SettingsSynchronizer(tracker)

    sync.set_preference("font_size", 14)
    assert sync.get_preference("font_size") == 14
    assert sync.get_preference("missing_key", default=10) == 10
