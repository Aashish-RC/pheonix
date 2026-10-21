"""
Pheonix Provider Ping Probe Engine
Performs live connectivity and authorization checks with millisecond latency measurement.
"""

import time
import urllib.request
import urllib.error
from typing import Optional, Callable
from ..models import ProviderDescriptor, PingResult


def default_http_probe(desc: ProviderDescriptor, secret: str, timeout: float = 5.0) -> PingResult:
    """Execute live HTTP GET probe against provider endpoint."""
    headers = {"User-Agent": "Pheonix-Gateway-Probe/1.0"}
    if desc.header_name and desc.header_format:
        auth_value = desc.header_format.format(token=secret)
        headers[desc.header_name] = auth_value

    req = urllib.request.Request(desc.probe_url, headers=headers, method="GET")
    start = time.time()
    try:
        with urllib.request.urlopen(req, timeout=timeout) as response:
            latency_ms = (time.time() - start) * 1000.0
            status_code = response.getcode()
            return PingResult(
                success=True,
                latency_ms=latency_ms,
                status_code=status_code,
                error_message=None,
            )
    except urllib.error.HTTPError as e:
        latency_ms = (time.time() - start) * 1000.0
        # 401/403 means bad or revoked credentials
        return PingResult(
            success=False,
            latency_ms=latency_ms,
            status_code=e.code,
            error_message=f"HTTP {e.code}: {e.reason}",
        )
    except Exception as e:
        latency_ms = (time.time() - start) * 1000.0
        return PingResult(
            success=False,
            latency_ms=latency_ms,
            status_code=None,
            error_message=str(e),
        )


def ping_provider(
    desc: ProviderDescriptor,
    secret: str,
    probe_fn: Optional[Callable[[ProviderDescriptor, str], PingResult]] = None,
    timeout: float = 5.0,
) -> PingResult:
    """
    Probe a provider to verify credential validity and network connectivity.
    """
    if probe_fn:
        return probe_fn(desc, secret)
    return default_http_probe(desc, secret, timeout=timeout)
