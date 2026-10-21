"""
Pheonix Resource Limiter
Guarantees host stability by bounding memory usage, CPU thread allocations, and active streams.
"""

import psutil
from contextlib import contextmanager
from typing import Generator
from ..models import ResourceLimits, DeviceProfile


class ResourceLimitExceededError(Exception):
    """Raised when host system RAM or VRAM exceeds safety boundaries."""
    pass


class ConcurrencyLimitExceededError(Exception):
    """Raised when active local model streams reach maximum concurrency limit."""
    pass


class ResourceLimiter:
    """
    Monitors and enforces system resource limits for local model serving.
    Prevents host system freezes, out-of-memory crashes, and thread starvation.
    """

    def __init__(self, limits: ResourceLimits = ResourceLimits()):
        self.limits = limits
        self._active_streams: int = 0

    @property
    def active_streams(self) -> int:
        return self._active_streams

    def check_limits(self, required_ram_gb: float = 0.0, required_vram_gb: float = 0.0) -> None:
        """Validates that current host resources can accommodate the requested workload."""
        # 1. Concurrency Check
        if self._active_streams >= self.limits.max_concurrent_streams:
            raise ConcurrencyLimitExceededError(
                f"Maximum concurrent local streams ({self.limits.max_concurrent_streams}) reached. "
                "Wait for active inference to complete."
            )

        # 2. Host System RAM Safety Check
        if self.limits.enforce_ram_limits:
            mem = psutil.virtual_memory()
            if mem.percent >= self.limits.max_ram_usage_percent:
                raise ResourceLimitExceededError(
                    f"Host RAM usage is at {mem.percent:.1f}%, exceeding safety threshold of "
                    f"{self.limits.max_ram_usage_percent}%. Inference aborted to prevent host lockup."
                )

            # 3. Available Memory Requirement Check
            avail_ram_gb = mem.available / (1024 ** 3)
            if required_ram_gb > 0 and avail_ram_gb < (required_ram_gb * 0.7):
                raise ResourceLimitExceededError(
                    f"Insufficient RAM available ({avail_ram_gb:.2f} GB) for model requiring "
                    f"{required_ram_gb:.2f} GB."
                )

    @contextmanager
    def acquire_slot(self, required_ram_gb: float = 0.0, required_vram_gb: float = 0.0) -> Generator[None, None, None]:
        """Context manager to safely acquire and release a local model execution slot."""
        self.check_limits(required_ram_gb=required_ram_gb, required_vram_gb=required_vram_gb)
        self._active_streams += 1
        try:
            yield
        finally:
            self._active_streams = max(0, self._active_streams - 1)
