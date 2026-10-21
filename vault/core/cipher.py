"""
Pheonix Vault Cryptographic Engine
Envelope encryption utilizing Argon2id KDF and AES-256-GCM.
"""

import os
from typing import Tuple
from cryptography.hazmat.primitives.kdf.argon2 import Argon2id
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.exceptions import InvalidTag

DEFAULT_SALT_LENGTH = 32
DEFAULT_NONCE_LENGTH = 12
DEFAULT_KEY_LENGTH = 32
DEFAULT_ARGON2_MEMORY_COST = 65536  # 64 MB
DEFAULT_ARGON2_ITERATIONS = 3
DEFAULT_ARGON2_LANES = 4


def generate_salt(length: int = DEFAULT_SALT_LENGTH) -> bytes:
    """Generate cryptographically secure random salt."""
    return os.urandom(length)


def generate_nonce(length: int = DEFAULT_NONCE_LENGTH) -> bytes:
    """Generate cryptographically secure random 96-bit nonce for AES-GCM."""
    return os.urandom(length)


def generate_dek(length: int = DEFAULT_KEY_LENGTH) -> bytes:
    """Generate cryptographically secure 256-bit Data Encryption Key."""
    return os.urandom(length)


def derive_kek(
    passphrase: str,
    salt: bytes,
    memory_cost: int = DEFAULT_ARGON2_MEMORY_COST,
    iterations: int = DEFAULT_ARGON2_ITERATIONS,
    lanes: int = DEFAULT_ARGON2_LANES,
) -> bytes:
    """Derive 256-bit Key Encryption Key (KEK) from passphrase using Argon2id."""
    kdf = Argon2id(
        salt=salt,
        length=DEFAULT_KEY_LENGTH,
        iterations=iterations,
        lanes=lanes,
        memory_cost=memory_cost,
        ad=None,
        secret=None,
    )
    return kdf.derive(passphrase.encode("utf-8"))


def encrypt_aes_gcm(key: bytes, plaintext: bytes, associated_data: bytes = None) -> Tuple[bytes, bytes]:
    """
    Encrypt plaintext using AES-256-GCM.
    Returns: (nonce, ciphertext_with_auth_tag)
    """
    nonce = generate_nonce()
    aesgcm = AESGCM(key)
    ciphertext = aesgcm.encrypt(nonce, plaintext, associated_data)
    return nonce, ciphertext


def decrypt_aes_gcm(key: bytes, nonce: bytes, ciphertext: bytes, associated_data: bytes = None) -> bytes:
    """
    Decrypt ciphertext using AES-256-GCM.
    Raises: cryptography.exceptions.InvalidTag if ciphertext or tag is modified.
    """
    aesgcm = AESGCM(key)
    return aesgcm.decrypt(nonce, ciphertext, associated_data)
