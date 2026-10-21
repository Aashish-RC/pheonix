"""Sandbox Manager: Ephemeral scratchpad lifecycle orchestration and cleanups."""

from pathlib import Path
import shutil
import tempfile
from typing import Optional
from .core.interfaces import BaseSandboxManager
from .core.models import ExecutionRequest, SandboxResult
from .governor.security_governor import SecurityGovernor
from .runner.device_runner import DeviceRunner


class SandboxManager(BaseSandboxManager):
    """Orchestrates isolated ephemeral execution lifecycles with deterministic destruction."""

    def __init__(
        self,
        governor: Optional[SecurityGovernor] = None,
        device_runner: Optional[DeviceRunner] = None,
    ):
        self.governor = governor or SecurityGovernor()
        self.runner = device_runner or DeviceRunner(self.governor)

    def run(self, request: ExecutionRequest) -> SandboxResult:
        # Create an isolated temporary workspace directory
        temp_scratch = tempfile.mkdtemp(prefix=f"pheonix_sb_{request.project_id}_")

        try:
            return self.runner.execute(request, scratch_dir=temp_scratch)
        finally:
            # Deterministic post-execution cleanup: wipe scratchpad completely
            try:
                shutil.rmtree(temp_scratch, ignore_errors=True)
            except Exception:
                pass
