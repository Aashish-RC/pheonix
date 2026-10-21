"""
Pheonix Auth & Identity Automated Security Tests
Validates single-user sign-in, device registry, session verification, tamper rejection, and revocation.
"""

import time
import pytest

from auth import (
    AuthManager,
    AuthenticationError,
    SessionInvalidError,
    SessionToken,
    DeviceInfo,
)


@pytest.fixture
def auth_manager():
    mgr = AuthManager()
    mgr.register_initial_user("alice", "SuperSecretPassword123!")
    return mgr


def test_user_registration_and_single_user_invariant():
    mgr = AuthManager()
    assert not mgr.is_user_registered()

    user = mgr.register_initial_user("alice", "MyPassword123")
    assert mgr.is_user_registered()
    assert user.username == "alice"
    assert user.password_hash != "MyPassword123"

    # Enforce single-user local invariant
    with pytest.raises(ValueError) as exc:
        mgr.register_initial_user("bob", "AnotherPassword123")
    assert "Single-user model" in str(exc.value)


def test_sign_in_and_see_devices(auth_manager):
    """
    CRITICAL CRITERIA: "Done when: You can sign in and see your devices"
    """
    # 1. Sign in from primary workstation
    session_workstation = auth_manager.authenticate(
        username="alice",
        password="SuperSecretPassword123!",
        device_id="dev_workstation_01",
        device_name="Alice Workstation",
        platform="windows",
    )
    assert isinstance(session_workstation, SessionToken)
    assert session_workstation.token_string is not None

    # 2. Sign in from secondary laptop
    session_laptop = auth_manager.authenticate(
        username="alice",
        password="SuperSecretPassword123!",
        device_id="dev_laptop_02",
        device_name="Alice MacBook Pro",
        platform="macos",
    )
    assert isinstance(session_laptop, SessionToken)

    # 3. Inspect registered devices
    devices = auth_manager.list_devices()
    assert len(devices) == 2
    dev_map = {d.device_id: d for d in devices}

    assert "dev_workstation_01" in dev_map
    assert dev_map["dev_workstation_01"].device_name == "Alice Workstation"
    assert dev_map["dev_workstation_01"].platform == "windows"
    assert dev_map["dev_workstation_01"].is_trusted is True
    assert dev_map["dev_workstation_01"].is_revoked is False

    assert "dev_laptop_02" in dev_map
    assert dev_map["dev_laptop_02"].device_name == "Alice MacBook Pro"
    assert dev_map["dev_laptop_02"].platform == "macos"

    # 4. Inspect active sessions
    active_sessions = auth_manager.list_active_sessions()
    assert len(active_sessions) == 2
    sess_ids = {s.session_id for s in active_sessions}
    assert session_workstation.session_id in sess_ids
    assert session_laptop.session_id in sess_ids


def test_invalid_credentials(auth_manager):
    # Bad password
    with pytest.raises(AuthenticationError):
        auth_manager.authenticate(
            username="alice",
            password="WrongPassword!",
            device_id="dev_test",
        )

    # Bad username
    with pytest.raises(AuthenticationError):
        auth_manager.authenticate(
            username="eve",
            password="SuperSecretPassword123!",
            device_id="dev_test",
        )


def test_session_validation_and_tamper_rejection(auth_manager):
    session = auth_manager.authenticate(
        username="alice",
        password="SuperSecretPassword123!",
        device_id="dev_valid",
    )

    # Validate correct token
    payload = auth_manager.validate_session(session.token_string)
    assert payload["sid"] == session.session_id
    assert payload["did"] == "dev_valid"

    # Tamper with signature
    parts = session.token_string.split(".")
    tampered_sig = parts[0] + "." + parts[1] + "." + "0" * len(parts[2])
    with pytest.raises(SessionInvalidError) as exc_info:
        auth_manager.validate_session(tampered_sig)
    assert "signature verification failed" in str(exc_info.value)

    # Tamper with payload
    tampered_payload = "extra" + parts[0] + "." + parts[1] + "." + parts[2]
    with pytest.raises(SessionInvalidError):
        auth_manager.validate_session(tampered_payload)


def test_device_revocation_lifecycle(auth_manager):
    # Sign in from lost phone
    phone_session = auth_manager.authenticate(
        username="alice",
        password="SuperSecretPassword123!",
        device_id="dev_phone_lost",
        device_name="Alice Phone",
        platform="android",
    )

    # Session is valid initially
    assert auth_manager.validate_session(phone_session.token_string) is not None

    # Revoke device
    revoked = auth_manager.revoke_device("dev_phone_lost", reason="Lost phone on transit")
    assert revoked is True

    # Device record reflects revocation
    devices = {d.device_id: d for d in auth_manager.list_devices()}
    assert devices["dev_phone_lost"].is_revoked is True
    assert devices["dev_phone_lost"].revocation_reason == "Lost phone on transit"

    # Active session originating from revoked device must fail validation immediately
    with pytest.raises(SessionInvalidError) as exc_info:
        auth_manager.validate_session(phone_session.token_string)
    assert "revoked or not trusted" in str(exc_info.value)

    # Future authentication from revoked device is rejected
    with pytest.raises(AuthenticationError) as auth_exc:
        auth_manager.authenticate(
            username="alice",
            password="SuperSecretPassword123!",
            device_id="dev_phone_lost",
        )
    assert "revoked" in str(auth_exc.value)


def test_session_sign_out(auth_manager):
    session = auth_manager.authenticate(
        username="alice",
        password="SuperSecretPassword123!",
        device_id="dev_desktop",
    )

    assert auth_manager.validate_session(session.token_string) is not None
    assert len(auth_manager.list_active_sessions()) == 1

    # Sign out
    signed_out = auth_manager.sign_out(session.token_string)
    assert signed_out is True

    # Validation fails
    with pytest.raises(SessionInvalidError):
        auth_manager.validate_session(session.token_string)

    assert len(auth_manager.list_active_sessions()) == 0
