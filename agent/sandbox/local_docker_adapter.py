"""Fallback Local Docker / Subprocess Execution Sandbox."""

import asyncio
import os
import shlex
import time
from typing import Any, Dict, List, Optional
from core.manifest import SandboxConfig
from core.exceptions import SandboxExecutionError


class LocalDockerSandboxAdapter:
    """Local execution sandbox with timeout enforcement and command safety guards."""

    DANGEROUS_COMMANDS: List[str] = [
        "rm -rf /",
        ":(){ :|:& };:",
        "mkfs",
        "dd if=/dev/zero",
        "chmod -R 777 /",
    ]

    async def execute_command(
        self,
        command: str,
        config: SandboxConfig,
        cwd: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Execute a command locally in a guarded subprocess with timeout."""
        start_time = time.perf_counter()

        # Check dangerous patterns
        for bad in self.DANGEROUS_COMMANDS:
            if bad in command:
                raise SandboxExecutionError(
                    f"Command blocked by local sandbox security policy: '{bad}'",
                    details={"blocked_command": bad}
                )

        timeout = config.timeout_seconds if config else 60

        try:
            # Use asyncio create_subprocess_shell
            proc = await asyncio.create_subprocess_shell(
                command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=cwd,
            )

            try:
                stdout_bytes, stderr_bytes = await asyncio.wait_for(
                    proc.communicate(),
                    timeout=float(timeout),
                )
            except asyncio.TimeoutError:
                try:
                    proc.kill()
                except ProcessLookupError:
                    pass
                raise SandboxExecutionError(f"Command timed out after {timeout} seconds: '{command}'")

            duration_ms = (time.perf_counter() - start_time) * 1000
            return {
                "exit_code": proc.returncode,
                "stdout": stdout_bytes.decode("utf-8", errors="replace"),
                "stderr": stderr_bytes.decode("utf-8", errors="replace"),
                "execution_time_ms": duration_ms,
                "provider": "local-subprocess",
            }

        except SandboxExecutionError:
            raise
        except Exception as e:
            raise SandboxExecutionError(f"Subprocess execution error: {str(e)}")
