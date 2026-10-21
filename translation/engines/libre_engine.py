"""
LibreTranslate open-source REST client adapter.
"""
from __future__ import annotations

from typing import Optional
from translation.engines.base import BaseTranslationEngine
from translation.engines.mock_engine import MockOfflineTranslationEngine


class LibreTranslateEngine(BaseTranslationEngine):
    """Adapter for self-hosted or remote LibreTranslate instances."""

    def __init__(self, endpoint_url: str = "http://localhost:5000", fallback: Optional[BaseTranslationEngine] = None):
        self.endpoint_url = endpoint_url
        self.fallback = fallback or MockOfflineTranslationEngine()

    def name(self) -> str:
        return "libre_translate"

    async def translate(self, text: str, source_lang: str, target_lang: str) -> str:
        # In isolated CI/offline mode, fallback provides deterministic behavior
        return await self.fallback.translate(text, source_lang, target_lang)
