"""
End-to-End Encrypted Channel using AES-256-GCM and HKDF key derivation.
"""
from __future__ import annotations

import os
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.hkdf import HKDF
from remote_access.core.models import EncryptedFrame


class E2EEncryptedChannel:
    """Provides authenticated end-to-end encryption for remote access frames."""

    def __init__(self, shared_secret: bytes):
        # Derive 32-byte key via HKDF-SHA256
        hkdf = HKDF(
            algorithm=hashes.SHA256(),
            length=32,
            salt=b"pheonix-remote-access-v1",
            info=b"e2e-channel-key",
        )
        self._key = hkdf.derive(shared_secret)
        self._aesgcm = AESGCM(self._key)

    def encrypt(self, payload: bytes, sender_id: str, recipient_id: str) -> EncryptedFrame:
        nonce = os.urandom(12)
        aad = f"{sender_id}:{recipient_id}".encode("utf-8")
        ciphertext = self._aesgcm.encrypt(nonce, payload, aad)

        return EncryptedFrame(
            sender_id=sender_id,
            recipient_id=recipient_id,
            iv_nonce=nonce.hex(),
            ciphertext=ciphertext.hex(),
        )

    def decrypt(self, frame: EncryptedFrame) -> bytes:
        nonce = bytes.fromhex(frame.iv_nonce)
        ciphertext = bytes.fromhex(frame.ciphertext)
        aad = f"{frame.sender_id}:{frame.recipient_id}".encode("utf-8")

        try:
            return self._aesgcm.decrypt(nonce, ciphertext, aad)
        except Exception as exc:
            raise ValueError(f"Failed to decrypt frame: cryptographic authentication failed ({exc})")
