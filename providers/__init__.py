"""
Pheonix Provider Activation Package
"""

from .models import (
    ProviderStatus,
    AuthType,
    ProviderDescriptor,
    PingResult,
    ActivatedProvider,
)
from .core.registry import ProviderCatalog, BUILTIN_PROVIDERS
from .core.ping import ping_provider
from .core.manager import ProviderActivationManager, ProviderActivationError

__all__ = [
    "ProviderActivationManager",
    "ProviderActivationError",
    "ProviderCatalog",
    "BUILTIN_PROVIDERS",
    "ProviderStatus",
    "AuthType",
    "ProviderDescriptor",
    "PingResult",
    "ActivatedProvider",
    "ping_provider",
]
