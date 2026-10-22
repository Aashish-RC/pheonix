"""Sandbox Manager: Ephemeral scratchpad lifecycle orchestration and cleanups."""

from pathlib import Path
import shutil
import tempfile
from typing import Optional
from .core.interfaces import BaseDeviceRunner, BaseSandboxManager
from .core.models import (
    ExecutionRequest,
    ResourceLimits,
    SandboxResult,
    SandboxStatus,
    SandboxTimeoutError,
)
import os
from .core.engines import E2BExecutionEngine, DockerExecutionEngine
from .governor.security_governor import SecurityGovernor
from .runner.device_runner import DeviceRunner
from .runner.docker_runner import DockerRunner


class SandboxManager(BaseSandboxManager):
    """Orchestrates isolated ephemeral execution lifecycles with deterministic destruction."""

    def __init__(
        self,
        governor: Optional[SecurityGovernor] = None,
        device_runner: Optional[BaseDeviceRunner] = None,
        engine: Optional[BaseDeviceRunner] = None,
    ):
        self.governor = governor or SecurityGovernor()
        if engine or device_runner:
            self.runner = engine or device_runner
        else:
            docker_runner = DockerRunner(self.governor)
            if docker_runner.is_docker_available():
                self.runner = docker_runner
            elif os.getenv("SANDBOX_ALLOW_LOCAL") == "1":
                self.runner = DeviceRunner(self.governor)
            else:
                self.runner = docker_runner

    def run(
        self,
        request: ExecutionRequest,
        raise_on_timeout: bool = False,
    ) -> SandboxResult:
        # Create an isolated temporary workspace directory
        temp_scratch = tempfile.mkdtemp(prefix=f"pheonix_sb_{request.project_id}_")

        try:
            result = self.runner.execute(request, scratch_dir=temp_scratch)
            if raise_on_timeout and result.status == SandboxStatus.TIMEOUT:
                raise SandboxTimeoutError(result.stderr or "Sandbox execution timed out")
            return result
        finally:
            # Deterministic post-execution cleanup: wipe scratchpad completely
            try:
                shutil.rmtree(temp_scratch, ignore_errors=True)
            except Exception:
                pass

    def execute(
        self,
        code: str,
        timeout_seconds: Optional[float] = None,
        language: str = "python",
        raise_on_timeout: bool = True,
    ) -> SandboxResult:
        """Convenience method to execute code with optional timeout and automatic SandboxTimeoutError."""
        limits = ResourceLimits()
        if timeout_seconds is not None:
            limits.timeout_seconds = timeout_seconds

        req = ExecutionRequest(
            language=language,
            code=code,
            limits=limits,
        )
        return self.run(req, raise_on_timeout=raise_on_timeout)
