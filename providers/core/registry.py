"""
Pheonix Built-in Provider Catalog & Specs
"""

from typing import Dict, List, Optional
from ..models import ProviderDescriptor, AuthType

BUILTIN_PROVIDERS: Dict[str, ProviderDescriptor] = {
    "openai": ProviderDescriptor(
        provider_id="openai",
        name="OpenAI",
        auth_type=AuthType.API_KEY,
        probe_url="https://api.openai.com/v1/models",
        header_name="Authorization",
        header_format="Bearer {token}",
        models=["gpt-4o", "gpt-4o-mini", "o1", "o3-mini"],
        is_local=False,
    ),
    "anthropic": ProviderDescriptor(
        provider_id="anthropic",
        name="Anthropic",
        auth_type=AuthType.API_KEY,
        probe_url="https://api.anthropic.com/v1/models",
        header_name="x-api-key",
        header_format="{token}",
        models=["claude-3-5-sonnet", "claude-3-7-sonnet", "claude-3-5-haiku"],
        is_local=False,
    ),
    "gemini": ProviderDescriptor(
        provider_id="gemini",
        name="Google Gemini",
        auth_type=AuthType.API_KEY,
        probe_url="https://generativelanguage.googleapis.com/v1beta/models",
        header_name="x-goog-api-key",
        header_format="{token}",
        models=["gemini-2.0-flash", "gemini-2.0-pro-exp"],
        is_local=False,
    ),
    "mistral": ProviderDescriptor(
        provider_id="mistral",
        name="Mistral AI",
        auth_type=AuthType.API_KEY,
        probe_url="https://api.mistral.ai/v1/models",
        header_name="Authorization",
        header_format="Bearer {token}",
        models=["mistral-large-latest", "codestral-latest"],
        is_local=False,
    ),
    "openrouter": ProviderDescriptor(
        provider_id="openrouter",
        name="OpenRouter",
        auth_type=AuthType.API_KEY,
        probe_url="https://openrouter.ai/api/v1/models",
        header_name="Authorization",
        header_format="Bearer {token}",
        models=["anthropic/claude-3.5-sonnet", "openai/gpt-4o"],
        is_local=False,
    ),
    "ollama": ProviderDescriptor(
        provider_id="ollama",
        name="Ollama Local",
        auth_type=AuthType.LOCAL_ENDPOINT,
        probe_url="http://localhost:11434/api/tags",
        header_name="",
        header_format="",
        models=["llama3.2", "mistral", "deepseek-r1"],
        is_local=True,
    ),
}


class ProviderCatalog:
    """Provides access to supported provider definitions."""

    @staticmethod
    def get_descriptor(provider_id: str) -> Optional[ProviderDescriptor]:
        return BUILTIN_PROVIDERS.get(provider_id)

    @staticmethod
    def list_supported_providers() -> List[ProviderDescriptor]:
        return list(BUILTIN_PROVIDERS.values())
