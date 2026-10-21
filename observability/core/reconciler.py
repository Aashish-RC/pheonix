"""
Pheonix Pricing Reconciler
Implements exact multi-unit billing calculations matching official provider dashboards.
"""

from typing import Dict, Optional
from ..models import ModelPricing


class PricingReconciler:
    """
    Computes exact inference costs down to fractions of a cent ($ / 1,000,000 tokens).
    """

    PRICING_CATALOG: Dict[str, ModelPricing] = {
        # OpenAI
        "gpt-4o": ModelPricing(model="gpt-4o", provider="openai", prompt_per_million=2.50, completion_per_million=10.00),
        "gpt-4o-mini": ModelPricing(model="gpt-4o-mini", provider="openai", prompt_per_million=0.15, completion_per_million=0.60),
        "text-embedding-3-small": ModelPricing(model="text-embedding-3-small", provider="openai", prompt_per_million=0.02, completion_per_million=0.00),
        
        # Anthropic
        "claude-3-7-sonnet-20250219": ModelPricing(model="claude-3-7-sonnet-20250219", provider="anthropic", prompt_per_million=3.00, completion_per_million=15.00),
        "claude-3-5-sonnet-20241022": ModelPricing(model="claude-3-5-sonnet-20241022", provider="anthropic", prompt_per_million=3.00, completion_per_million=15.00),
        "claude-3-5-haiku-20241022": ModelPricing(model="claude-3-5-haiku-20241022", provider="anthropic", prompt_per_million=0.80, completion_per_million=4.00),

        # Google Gemini
        "gemini-1.5-pro": ModelPricing(model="gemini-1.5-pro", provider="gemini", prompt_per_million=1.25, completion_per_million=5.00),
        "gemini-2.0-flash": ModelPricing(model="gemini-2.0-flash", provider="gemini", prompt_per_million=0.10, completion_per_million=0.40),

        # Mistral AI
        "mistral-large-latest": ModelPricing(model="mistral-large-latest", provider="mistral", prompt_per_million=2.00, completion_per_million=6.00),
        "mistral-small-latest": ModelPricing(model="mistral-small-latest", provider="mistral", prompt_per_million=0.20, completion_per_million=0.60),
    }

    @classmethod
    def get_pricing(cls, model: str) -> Optional[ModelPricing]:
        """Retrieves pricing specification for a model name."""
        clean_model = model.lower().strip()
        # Direct match
        if clean_model in cls.PRICING_CATALOG:
            return cls.PRICING_CATALOG[clean_model]

        # Substring prefix matching (e.g. gpt-4o-2024-08-06 -> gpt-4o)
        for key, pricing in cls.PRICING_CATALOG.items():
            if clean_model.startswith(key):
                return pricing

        # Local models (ollama, llama.cpp, etc.) are free
        if any(local_prefix in clean_model for local_prefix in ["ollama", "llama.cpp", "local", "llama3", "phi3", "qwen"]):
            return ModelPricing(model=model, provider="local", prompt_per_million=0.0, completion_per_million=0.0)

        return None

    @classmethod
    def calculate_cost(cls, model: str, prompt_tokens: int, completion_tokens: int, is_cached: bool = False) -> float:
        """
        Calculates exact dollar cost. Cached prompts receive standard 50% discount where applicable.
        """
        pricing = cls.get_pricing(model)
        if not pricing:
            # Fallback default low-cost estimate ($1.00 / Mtok)
            return round(((prompt_tokens + completion_tokens) / 1_000_000.0) * 1.0, 6)

        prompt_rate = pricing.prompt_per_million * (0.5 if is_cached else 1.0)
        completion_rate = pricing.completion_per_million

        prompt_cost = (prompt_tokens / 1_000_000.0) * prompt_rate
        completion_cost = (completion_tokens / 1_000_000.0) * completion_rate

        return round(prompt_cost + completion_cost, 6)
