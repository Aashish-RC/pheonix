"""
Pheonix Vault Memory Guard & Ephemeral Leases
Protects in-memory secrets and guarantees zeroization upon disposal.
"""

import time
from typing import Optional


class SecretExpiredError(Exception):
    """Raised when an ephemeral secret lease has expired."""
    pass


class SecretReleasedError(Exception):
    """Raised when attempting to access a secret after its lease has been released."""
    pass


class SecretLease:
    """
    Ephemeral lease container for a sensitive secret value.
    Guarantees that memory is wiped (zeroized) upon release or context exit.
    """

    def __init__(self, key_id: str, secret_bytes: bytes, ttl_seconds: float = 60.0):
        self.key_id = key_id
        self._buffer: Optional[bytearray] = bytearray(secret_bytes)
        self.created_at = time.time()
        self.expires_at = self.created_at + ttl_seconds
        self._is_released = False

    def is_valid(self) -> bool:
        """Returns True if the lease is active and not expired."""
        if self._is_released or self._buffer is None:
            return False
        return time.time() <= self.expires_at

    def get_plaintext(self) -> str:
        """
        Retrieve secret as string. Caller should minimize duration of holding
        the returned string in memory.
        """
        if self._is_released or self._buffer is None:
            raise SecretReleasedError(f"Secret lease for '{self.key_id}' has already been released and zeroized.")
        if time.time() > self.expires_at:
            self.release()
            raise SecretExpiredError(f"Secret lease for '{self.key_id}' expired at {self.expires_at}.")
        return self._buffer.decode("utf-8")

    def get_bytes(self) -> bytes:
        """Retrieve raw secret bytes."""
        if self._is_released or self._buffer is None:
            raise SecretReleasedError(f"Secret lease for '{self.key_id}' has already been released and zeroized.")
        if time.time() > self.expires_at:
            self.release()
            raise SecretExpiredError(f"Secret lease for '{self.key_id}' expired at {self.expires_at}.")
        return bytes(self._buffer)

    def release(self):
        """Zeroize memory buffer immediately and mark lease as released."""
        if self._buffer is not None:
            for i in range(len(self._buffer)):
                self._buffer[i] = 0
            self._buffer = None
        self._is_released = True

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.release()

    def __repr__(self) -> str:
        status = "ACTIVE" if self.is_valid() else "INVALID/EXPIRED"
        return f"<SecretLease key_id='{self.key_id}' status={status} [REDACTED]>"

    def __str__(self) -> str:
        return self.__repr__()

    def __del__(self):
        self.release()
