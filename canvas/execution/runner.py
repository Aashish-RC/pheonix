"""Card Executor: Runs Python code blocks and commands with timeout and output capture."""

import subprocess
import sys
import time
from typing import List

from ..core.interfaces import BaseCardExecutor
from ..core.models import ExecutionResult


class LocalCardExecutor(BaseCardExecutor):
    """Executes sandboxed card code blocks locally with timeouts and output capture."""

    def __init__(self, default_timeout: float = 5.0):
        self.default_timeout = default_timeout

    def execute_python(self, card_id: str, code: str, timeout_seconds: float = 5.0) -> ExecutionResult:
        timeout = timeout_seconds or self.default_timeout
        start_time = time.perf_counter()

        try:
            res = subprocess.run(
                [sys.executable, "-c", code],
                capture_output=True,
                text=True,
                timeout=timeout,
            )
            duration_ms = (time.perf_counter() - start_time) * 1000.0
            status = "success" if res.returncode == 0 else "error"
            return ExecutionResult(
                card_id=card_id,
                status=status,
                exit_code=res.returncode,
                stdout=res.stdout,
                stderr=res.stderr,
                duration_ms=round(duration_ms, 2),
            )
        except subprocess.TimeoutExpired as te:
            duration_ms = (time.perf_counter() - start_time) * 1000.0
            stdout_str = te.stdout.decode() if isinstance(te.stdout, bytes) else (te.stdout or "")
            stderr_str = te.stderr.decode() if isinstance(te.stderr, bytes) else (te.stderr or "")
            return ExecutionResult(
                card_id=card_id,
                status="timeout",
                exit_code=-1,
                stdout=stdout_str,
                stderr=f"Execution timed out after {timeout} seconds. {stderr_str}".strip(),
                duration_ms=round(duration_ms, 2),
            )
        except Exception as e:
            duration_ms = (time.perf_counter() - start_time) * 1000.0
            return ExecutionResult(
                card_id=card_id,
                status="error",
                exit_code=-1,
                stdout="",
                stderr=f"Execution error: {str(e)}",
                duration_ms=round(duration_ms, 2),
            )

    def execute_command(self, card_id: str, command: str, timeout_seconds: float = 5.0) -> ExecutionResult:
        timeout = timeout_seconds or self.default_timeout
        start_time = time.perf_counter()

        try:
            res = subprocess.run(
                command,
                shell=True,
                capture_output=True,
                text=True,
                timeout=timeout,
            )
            duration_ms = (time.perf_counter() - start_time) * 1000.0
            status = "success" if res.returncode == 0 else "error"
            return ExecutionResult(
                card_id=card_id,
                status=status,
                exit_code=res.returncode,
                stdout=res.stdout,
                stderr=res.stderr,
                duration_ms=round(duration_ms, 2),
            )
        except subprocess.TimeoutExpired as te:
            duration_ms = (time.perf_counter() - start_time) * 1000.0
            stdout_str = te.stdout.decode() if isinstance(te.stdout, bytes) else (te.stdout or "")
            stderr_str = te.stderr.decode() if isinstance(te.stderr, bytes) else (te.stderr or "")
            return ExecutionResult(
                card_id=card_id,
                status="timeout",
                exit_code=-1,
                stdout=stdout_str,
                stderr=f"Command timed out after {timeout} seconds. {stderr_str}".strip(),
                duration_ms=round(duration_ms, 2),
            )
        except Exception as e:
            duration_ms = (time.perf_counter() - start_time) * 1000.0
            return ExecutionResult(
                card_id=card_id,
                status="error",
                exit_code=-1,
                stdout="",
                stderr=f"Command error: {str(e)}",
                duration_ms=round(duration_ms, 2),
            )


CardExecutionRunner = LocalCardExecutor

