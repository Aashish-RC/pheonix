"""
Pheonix Vault Binary File Storage Engine
Handles atomic persistence and envelope encrypted binary serialization.
"""

import os
import struct
import json
from pathlib import Path
from typing import Tuple, Dict, Any

from .cipher import (
    derive_kek,
    encrypt_aes_gcm,
    decrypt_aes_gcm,
    generate_salt,
    generate_dek,
    DEFAULT_ARGON2_MEMORY_COST,
    DEFAULT_ARGON2_ITERATIONS,
    DEFAULT_ARGON2_LANES,
)

VAULT_MAGIC_V1 = b"PHX_VAULT_V1\x00\x00\x00\x00"  # Exactly 16 bytes


class CorruptedVaultError(Exception):
    """Raised when vault file format or magic header is corrupted."""
    pass


class InvalidPassphraseError(Exception):
    """Raised when passphrase derivation fails GCM tag authentication."""
    pass


class VaultStore:
    """Manages atomic serialization and loading of encrypted vault binary files."""

    def __init__(self, file_path: Path):
        self.file_path = Path(file_path)

    def exists(self) -> bool:
        return self.file_path.exists()

    def save_vault(
        self,
        payload_dict: Dict[str, Any],
        passphrase: str,
        memory_cost: int = DEFAULT_ARGON2_MEMORY_COST,
        iterations: int = DEFAULT_ARGON2_ITERATIONS,
        lanes: int = DEFAULT_ARGON2_LANES,
    ):
        """Encrypt and atomically save vault data to disk."""
        salt = generate_salt()
        kek = derive_kek(passphrase, salt, memory_cost=memory_cost, iterations=iterations, lanes=lanes)
        dek = generate_dek()

        # Encrypt DEK with KEK
        dek_nonce, encrypted_dek = encrypt_aes_gcm(kek, dek)

        # Encrypt Payload with DEK
        payload_bytes = json.dumps(payload_dict, separators=(",", ":")).encode("utf-8")
        payload_nonce, encrypted_payload = encrypt_aes_gcm(dek, payload_bytes)

        # Serialize binary envelope
        # Format:
        # [16B Magic][32B Salt][4B MemCost][4B Iters][4B Lanes][12B DEK Nonce][4B EncDEK Len][EncDEK][12B Payload Nonce][4B Payload Len][EncPayload]
        header_fmt = "!16s32sIII12sI"
        header = struct.pack(
            header_fmt,
            VAULT_MAGIC_V1,
            salt,
            memory_cost,
            iterations,
            lanes,
            dek_nonce,
            len(encrypted_dek),
        )

        payload_header_fmt = "!12sI"
        payload_header = struct.pack(
            payload_header_fmt,
            payload_nonce,
            len(encrypted_payload),
        )

        binary_data = header + encrypted_dek + payload_header + encrypted_payload

        # Ensure parent directory exists
        self.file_path.parent.mkdir(parents=True, exist_ok=True)

        # Atomic write
        temp_path = self.file_path.with_suffix(f".tmp.{os.getpid()}")
        with open(temp_path, "wb") as f:
            f.write(binary_data)
            f.flush()
            os.fsync(f.fileno())

        os.replace(temp_path, self.file_path)

    def load_vault(self, passphrase: str) -> Dict[str, Any]:
        """Read and decrypt vault payload from disk using passphrase."""
        if not self.file_path.exists():
            raise FileNotFoundError(f"Vault file not found: {self.file_path}")

        with open(self.file_path, "rb") as f:
            raw = f.read()

        min_len = 16 + 32 + 12 + 12 + 4 + 12 + 4
        if len(raw) < min_len:
            raise CorruptedVaultError("Vault file is smaller than minimum header size.")

        # Unpack header
        header_size = struct.calcsize("!16s32sIII12sI")
        magic, salt, memory_cost, iterations, lanes, dek_nonce, enc_dek_len = struct.unpack(
            "!16s32sIII12sI", raw[:header_size]
        )

        if magic != VAULT_MAGIC_V1:
            raise CorruptedVaultError(f"Invalid vault magic header: {magic!r}")

        offset = header_size
        encrypted_dek = raw[offset : offset + enc_dek_len]
        offset += enc_dek_len

        payload_header_size = struct.calcsize("!12sI")
        payload_nonce, enc_payload_len = struct.unpack(
            "!12sI", raw[offset : offset + payload_header_size]
        )
        offset += payload_header_size

        encrypted_payload = raw[offset : offset + enc_payload_len]

        # Derive KEK and decrypt DEK
        try:
            kek = derive_kek(passphrase, salt, memory_cost=memory_cost, iterations=iterations, lanes=lanes)
            dek = decrypt_aes_gcm(kek, dek_nonce, encrypted_dek)
        except Exception as e:
            raise InvalidPassphraseError("Failed to decrypt vault. Incorrect passphrase or corrupted key block.") from e

        # Decrypt payload with DEK
        try:
            payload_bytes = decrypt_aes_gcm(dek, payload_nonce, encrypted_payload)
            return json.loads(payload_bytes.decode("utf-8"))
        except Exception as e:
            raise CorruptedVaultError("Failed to decrypt payload with valid DEK. File may be tampered.") from e
