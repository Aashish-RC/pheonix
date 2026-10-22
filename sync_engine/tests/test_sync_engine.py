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


def test_two_devices_write_same_key_concurrent_resolution():
    """Verify concurrent writes to the same key from two devices resolve deterministically."""
    resolver = ConflictResolver()

    # Device A writes setting at clock 1, timestamp 100.0
    entity_a = SyncEntity(
        entity_id="pref_network_mode",
        entity_type=EntityType.SETTINGS,
        data={"mode": "wifi_only"},
        lamport_clock=1,
        updated_at=100.0,
        node_id="device_a",
    )

    # Device B concurrently writes same setting at clock 1, timestamp 105.0
    mut_b = DeltaMutation(
        entity_id="pref_network_mode",
        entity_type=EntityType.SETTINGS,
        mutation_type=MutationType.UPDATE,
        payload={"mode": "cellular_and_wifi"},
        lamport_clock=1,
        timestamp=105.0,
        node_id="device_b",
    )

    resolved, conflict = resolver.resolve(entity_a, mut_b)
    assert conflict is True
    assert resolved.data["mode"] == "cellular_and_wifi"
    assert resolved.node_id == "device_b"


def test_two_devices_write_same_key_causal_lamport_clock():
    """Verify that a higher Lamport clock dominates regardless of physical clock drift."""
    resolver = ConflictResolver()

    local_entity = SyncEntity(
        entity_id="pref_volume",
        entity_type=EntityType.SETTINGS,
        data={"volume": 40},
        lamport_clock=5,
        updated_at=200.0,  # Physical clock higher
        node_id="device_a",
    )

    incoming_mut = DeltaMutation(
        entity_id="pref_volume",
        entity_type=EntityType.SETTINGS,
        mutation_type=MutationType.UPDATE,
        payload={"volume": 90},
        lamport_clock=6,   # Higher Lamport clock
        timestamp=150.0,   # Physical clock drifted behind
        node_id="device_b",
    )

    resolved, conflict = resolver.resolve(local_entity, incoming_mut)
    assert conflict is False
    assert resolved.data["volume"] == 90
    assert resolved.lamport_clock == 6


def test_offline_then_sync_two_way_reconciliation():
    """Verify that two devices operating offline synchronize and converge to identical state."""
    protocol = SyncProtocol()

    # Store state on Device A and Device B
    store_a: dict = {}
    store_b: dict = {}

    # Device A offline mutations
    tracker_a = DeltaChangeTracker(node_id="dev_a")
    mut_a1 = tracker_a.record_mutation("chat_1", EntityType.CHAT, MutationType.INSERT, {"title": "Chat from A"})
    mut_a2 = tracker_a.record_mutation("settings_theme", EntityType.SETTINGS, MutationType.INSERT, {"theme": "nord"})

    # Device B offline mutations
    tracker_b = DeltaChangeTracker(node_id="dev_b")
    mut_b1 = tracker_b.record_mutation("chat_2", EntityType.CHAT, MutationType.INSERT, {"title": "Chat from B"})

    # Device A ingests its own mutations first
    packet_a_local = protocol.create_packet("dev_a", "dev_a", [mut_a1, mut_a2])
    protocol.ingest_packet(packet_a_local, store_a)

    # Device B ingests its own mutations first
    packet_b_local = protocol.create_packet("dev_b", "dev_b", [mut_b1])
    protocol.ingest_packet(packet_b_local, store_b)

    # Exchange packets: B ingests A's packet
    packet_a_to_b = protocol.create_packet("dev_a", "dev_b", [mut_a1, mut_a2])
    protocol.ingest_packet(packet_a_to_b, store_b)

    # Exchange packets: A ingests B's packet
    packet_b_to_a = protocol.create_packet("dev_b", "dev_a", [mut_b1])
    protocol.ingest_packet(packet_b_to_a, store_a)

    # Both stores now contain 3 entities with identical keys and data
    assert len(store_a) == 3
    assert len(store_b) == 3
    assert set(store_a.keys()) == set(store_b.keys())
    for k in store_a:
        assert store_a[k].data == store_b[k].data
        assert store_a[k].lamport_clock == store_b[k].lamport_clock


def test_deletion_conflict_delete_wins_over_earlier_update():
    """Verify that a deletion with a higher or equal clock marks an entity as deleted."""
    resolver = ConflictResolver()

    local_chat = SyncEntity(
        entity_id="chat_conflicted",
        entity_type=EntityType.CHAT,
        data={"title": "Old Title"},
        lamport_clock=1,
        updated_at=100.0,
        node_id="node_a",
        deleted=False,
    )

    delete_mut = DeltaMutation(
        entity_id="chat_conflicted",
        entity_type=EntityType.CHAT,
        mutation_type=MutationType.DELETE,
        payload={},
        lamport_clock=2,
        timestamp=110.0,
        node_id="node_b",
    )

    resolved, conflict = resolver.resolve(local_chat, delete_mut)
    assert resolved.deleted is True
    assert resolved.lamport_clock == 2


def test_deletion_conflict_update_resurrects_deleted_entity():
    """Verify that a subsequent update with higher clock un-deletes (resurrects) an entity."""
    resolver = ConflictResolver()

    deleted_entity = SyncEntity(
        entity_id="fact_reborn",
        entity_type=EntityType.MEMORY,
        data={"fact": "Old fact"},
        lamport_clock=2,
        updated_at=100.0,
        node_id="node_a",
        deleted=True,
    )

    resurrection_mut = DeltaMutation(
        entity_id="fact_reborn",
        entity_type=EntityType.MEMORY,
        mutation_type=MutationType.UPDATE,
        payload={"fact": "Updated restored fact"},
        lamport_clock=3,
        timestamp=120.0,
        node_id="node_b",
    )

    resolved, conflict = resolver.resolve(deleted_entity, resurrection_mut)
    assert resolved.deleted is False
    assert resolved.data["fact"] == "Updated restored fact"
    assert resolved.lamport_clock == 3


def test_partial_failure_corrupted_packet_rejected_atomically():
    """Verify that a corrupted packet checksum raises ValueError and leaves the entity store pristine."""
    protocol = SyncProtocol()
    store = {"existing_key": SyncEntity(
        entity_id="existing_key",
        entity_type=EntityType.SETTINGS,
        data={"val": 1},
        lamport_clock=1,
        updated_at=100.0,
        node_id="node_1"
    )}

    mut = DeltaMutation(
        entity_id="malicious_key",
        entity_type=EntityType.SETTINGS,
        mutation_type=MutationType.INSERT,
        payload={"danger": True},
        lamport_clock=1,
        timestamp=150.0,
        node_id="node_2",
    )
    packet = protocol.create_packet("node_2", "node_1", [mut])
    # Tamper with the packet payload
    packet.mutations[0].payload["danger"] = False

    with pytest.raises(ValueError, match="checksum mismatch"):
        protocol.ingest_packet(packet, store)

    # Store was not altered
    assert len(store) == 1
    assert "malicious_key" not in store


def test_batch_offline_mutations_across_multiple_entity_types():
    """Verify batch sync containing CHAT, MEMORY, and SETTINGS deltas ingested in single pass."""
    protocol = SyncProtocol()
    tracker = DeltaChangeTracker(node_id="mobile_client")

    m1 = tracker.record_mutation("chat_batch", EntityType.CHAT, MutationType.INSERT, {"msg": "hello"})
    m2 = tracker.record_mutation("mem_batch", EntityType.MEMORY, MutationType.INSERT, {"summary": "user note"})
    m3 = tracker.record_mutation("setting_batch", EntityType.SETTINGS, MutationType.INSERT, {"font": "sans"})

    packet = protocol.create_packet("mobile_client", "server", [m1, m2, m3])
    store: dict = {}
    status = protocol.ingest_packet(packet, store)

    assert status.applied_mutations == 3
    assert len(store) == 3
    assert store["chat_batch"].entity_type == EntityType.CHAT
    assert store["mem_batch"].entity_type == EntityType.MEMORY
    assert store["setting_batch"].entity_type == EntityType.SETTINGS


def test_empty_packet_sync_leaves_store_unchanged():
    """Verify syncing a packet with zero mutations succeeds as a no-op."""
    protocol = SyncProtocol()
    packet = protocol.create_packet("dev_1", "dev_2", [])
    store: dict = {}
    status = protocol.ingest_packet(packet, store)

    assert status.applied_mutations == 0
    assert status.synced_entities_count == 0
    assert len(store) == 0

