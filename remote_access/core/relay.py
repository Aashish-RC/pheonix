"""Intelligent Relay and Adaptive Path Probe Coordinator."""

from typing import Callable, Optional, Tuple
from .models import EncryptedFrame, PathType
from .path_selector import PathSelector
from ..relay.relay_service import EncryptedRelayRouter


class AdaptiveRelayChannel:
    """Manages adaptive path discovery with direct probe, LAN detection, and encrypted relay fallback."""

    def __init__(self, relay_router: Optional[EncryptedRelayRouter] = None):
        self.relay_router = relay_router or EncryptedRelayRouter()
        self.selector = PathSelector()

    def probe_and_select_path(
        self,
        host_ip: str,
        client_ip: str,
        direct_probe_fn: Optional[Callable[[], bool]] = None,
        lan_probe_fn: Optional[Callable[[], bool]] = None,
    ) -> Tuple[PathType, str]:
        """Path probe logic: Attempt direct connection -> attempt local LAN ping -> fallback to WebSocket encrypted relay."""
        # 1. Attempt direct connection (e.g. STUN / hole-punched P2P)
        if direct_probe_fn is not None:
            try:
                if direct_probe_fn():
                    return PathType.DIRECT_P2P, "Direct P2P socket established"
            except Exception:
                pass

        # 2. Attempt local LAN ping
        if lan_probe_fn is not None:
            try:
                if lan_probe_fn():
                    return PathType.DIRECT_LAN, "Local LAN ping succeeded"
            except Exception:
                pass
        elif self.selector.is_local_network(host_ip, client_ip):
            return PathType.DIRECT_LAN, "Local subnet match confirmed"

        # 3. Fallback to WebSocket encrypted relay
        return PathType.RELAY, "NAT traversal failed; transparent fallback to WebSocket encrypted relay"


__all__ = [
    "AdaptiveRelayChannel",
    "EncryptedRelayRouter",
]
