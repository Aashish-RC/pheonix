"""
Pheonix Password Hashing & Verification Engine
Implements Argon2id with 32-byte salts and constant-time equality validation.
"""

import os
import hmac
from cryptography.hazmat.primitives.kdf.argon2 import Argon2id

DEFAULT_SALT_LENGTH = 32
DEFAULT_HASH_LENGTH = 32
DEFAULT_ARGON2_MEMORY_COST = 65536  # 64 MB
DEFAULT_ARGON2_ITERATIONS = 3
DEFAULT_ARGON2_LANES = 4


def hash_password(
    password: str,
    salt: bytes = None,
    memory_cost: int = DEFAULT_ARGON2_MEMORY_COST,
    iterations: int = DEFAULT_ARGON2_ITERATIONS,
    lanes: int = DEFAULT_ARGON2_LANES,
) -> tuple[str, str]:
    """
    Hash a plaintext password using Argon2id.
    Returns: (hash_hex, salt_hex)
    """
    if salt is None:
        salt = os.urandom(DEFAULT_SALT_LENGTH)

    kdf = Argon2id(
        salt=salt,
        length=DEFAULT_HASH_LENGTH,
        iterations=iterations,
        lanes=lanes,
        memory_cost=memory_cost,
        ad=None,
        secret=None,
    )
    derived = kdf.derive(password.encode("utf-8"))
    return derived.hex(), salt.hex()


def verify_password(
    password: str,
    stored_hash_hex: str,
    salt_hex: str,
    memory_cost: int = DEFAULT_ARGON2_MEMORY_COST,
    iterations: int = DEFAULT_ARGON2_ITERATIONS,
    lanes: int = DEFAULT_ARGON2_LANES,
) -> bool:
    """
    Verify password against stored hash using constant-time digest comparison.
    """
    try:
        salt = bytes.fromhex(salt_hex)
        expected_hash = bytes.fromhex(stored_hash_hex)
    except ValueError:
        return False

    kdf = Argon2id(
        salt=salt,
        length=DEFAULT_HASH_LENGTH,
        iterations=iterations,
        lanes=lanes,
        memory_cost=memory_cost,
        ad=None,
        secret=None,
    )
    try:
        derived = kdf.derive(password.encode("utf-8"))
        return hmac.compare_digest(derived, expected_hash)
    except Exception:
        return False
