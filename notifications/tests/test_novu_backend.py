"""Unit tests for NovuBackend and notify() integration."""

import json
from unittest.mock import MagicMock, patch
import pytest

import notifications
from notifications import notify, NovuBackend


def test_notify_writes_to_user_notification_feed():
    backend = NovuBackend()
    item = notify(
        user_id="u1",
        event="task_completed",
        message="Your deployment DAG finished successfully.",
        backend=backend,
    )

    assert item.user_id == "u1"
    assert "Task Completed" in item.title
    assert "deployment DAG finished" in item.body

    # Verify written to user's feed
    feed = backend.get_user_feed("u1")
    assert len(feed) >= 1
    assert any(n.notification_id == item.notification_id for n in feed)
    assert feed[0].user_id == "u1"


def test_user_feed_isolation():
    backend = NovuBackend()
    notify(user_id="alice", event="msg_alice", message="Hi Alice", backend=backend)
    notify(user_id="bob", event="msg_bob", message="Hi Bob", backend=backend)

    alice_feed = backend.get_user_feed("alice")
    bob_feed = backend.get_user_feed("bob")

    assert all(n.user_id == "alice" for n in alice_feed)
    assert all(n.user_id == "bob" for n in bob_feed)
    assert not any(n.user_id == "bob" for n in alice_feed)


def test_remote_novu_trigger_with_api_key():
    backend = NovuBackend(api_key="nv-test-key-12345", backend_url="https://api.novu.co")

    mock_cm = MagicMock()
    mock_cm.read.return_value = json.dumps({"data": {"acknowledged": True, "status": "processed"}}).encode("utf-8")
    mock_cm.__enter__.return_value = mock_cm

    with patch("urllib.request.urlopen", return_value=mock_cm) as mock_urlopen:
        item = backend.trigger(
            event="invoice_paid",
            subscriber_id="sub_999",
            payload={"amount": 49.99},
        )
        assert item.user_id == "sub_999"
        assert item.title == "Invoice Paid"
        assert mock_urlopen.called
        req = mock_urlopen.call_args[0][0]
        assert req.get_header("Authorization") == "ApiKey nv-test-key-12345"
