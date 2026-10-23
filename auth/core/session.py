"""
Pheonix Cryptographic Session Token Engine
Issues and validates HMAC-SHA256 signed tamper-proof session tokens.
"""

import time
import json
import base64
import hmac
import hashlib
from typing import Tuple, Optional, Dict, Any


def _b64_encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode("utf-8").rstrip("=")


def _b64_decode(data_str: str) -> bytes:
    padding = "=" * ((4 - len(data_str) % 4) % 4)
    return base64.urlsafe_b64decode(data_str + padding)


def create_session_token(
    session_id: str,
    user_id: str,
    device_id: str,
    ttl_seconds: float,
    signing_key: bytes,
    tenant_id: str = "default",
    role: str = "user",
) -> Tuple[str, float, float]:
    """
    Generate an HMAC-SHA256 signed session token string.
    Returns: (token_string, issued_at, expires_at)
    """
    now = time.time()
    expires_at = now + ttl_seconds

    header = {"alg": "HS256", "typ": "PHX_SESSION"}
    payload = {
        "sid": session_id,
        "uid": user_id,
        "did": device_id,
        "tid": tenant_id,
        "role": role,
        "iat": now,
        "exp": expires_at,
    }

    header_b64 = _b64_encode(json.dumps(header, separators=(",", ":")).encode("utf-8"))
    payload_b64 = _b64_encode(json.dumps(payload, separators=(",", ":")).encode("utf-8"))

    signing_input = f"{header_b64}.{payload_b64}".encode("utf-8")
    sig = hmac.new(signing_key, signing_input, hashlib.sha256).hexdigest()

    token_str = f"{header_b64}.{payload_b64}.{sig}"
    return token_str, now, expires_at


def verify_session_token(
    token_str: str,
    signing_key: bytes,
) -> Tuple[bool, Optional[Dict[str, Any]], Optional[str]]:
    """
    Verify signature and validity of a session token string.
    Returns: (is_valid, payload, error_message)
    """
    parts = token_str.split(".")
    if len(parts) != 3:
        return False, None, "Invalid token structure"

    header_b64, payload_b64, sig_hex = parts

    signing_input = f"{header_b64}.{payload_b64}".encode("utf-8")
    expected_sig = hmac.new(signing_key, signing_input, hashlib.sha256).hexdigest()

    if not hmac.compare_digest(sig_hex, expected_sig):
        return False, None, "Token signature verification failed"

    try:
        payload_bytes = _b64_decode(payload_b64)
        payload = json.loads(payload_bytes.decode("utf-8"))
    except Exception as e:
        return False, None, f"Malformed token payload: {e}"

    if time.time() > payload.get("exp", 0):
        return False, payload, "Token has expired"

    return True, payload, None


def create_session_token_with_vault(
    session_id: str,
    user_id: str,
    device_id: str,
    ttl_seconds: float,
    vault_manager: Any,
    key_id: str = "auth_session_signing_key",
    tenant_id: str = "default",
    role: str = "user",
) -> Tuple[str, float, float]:
    """
    Generate an HMAC-SHA256 signed session token string using a key leased from the Vault.
    Guarantees ephemeral key zeroization upon lease release.
    """
    lease = vault_manager.get_lease(key_id, ttl_seconds=ttl_seconds)
    try:
        secret_str = lease.get_plaintext()
        try:
            signing_key = bytes.fromhex(secret_str)
        except ValueError:
            signing_key = secret_str.encode("utf-8")
        return create_session_token(
            session_id=session_id,
            user_id=user_id,
            device_id=device_id,
            ttl_seconds=ttl_seconds,
            signing_key=signing_key,
            tenant_id=tenant_id,
            role=role,
        )
    finally:
        lease.release()


def verify_session_token_with_vault(
    token_str: str,
    vault_manager: Any,
    key_id: str = "auth_session_signing_key",
) -> Tuple[bool, Optional[Dict[str, Any]], Optional[str]]:
    """
    Verify signature and validity of a session token string using a key leased from the Vault.
    """
    lease = vault_manager.get_lease(key_id, ttl_seconds=60.0)
    try:
        secret_str = lease.get_plaintext()
        try:
            signing_key = bytes.fromhex(secret_str)
        except ValueError:
            signing_key = secret_str.encode("utf-8")
        return verify_session_token(token_str=token_str, signing_key=signing_key)
    finally:
        lease.release()


