"""Guardrails Filter: Intercepts Agent Prompts and Responses against Policies."""

import re
from typing import Any, Dict, List, Optional
from core.manifest import GuardrailConfig
from core.exceptions import GuardrailViolationError
from .parlant_adapter import ParlantAdapter


class GuardrailFilter:
    """Interception filter for prompt sanitization, sensitive data masking, and output validation."""

    # Common credential patterns (API keys, bearer tokens)
    CREDENTIAL_PATTERNS = [
        re.compile(r"(?:api[_-]?key|secret|token|password)\s*[:=]\s*['\"]?([A-Za-z0-9_-]{16,})['\"]?", re.IGNORECASE),
        re.compile(r"Bearer\s+([A-Za-z0-9_\-\.]{20,})", re.IGNORECASE),
    ]

    def __init__(self, parlant_adapter: Optional[ParlantAdapter] = None):
        self.adapter = parlant_adapter or ParlantAdapter()

    def sanitize_input(self, text: str, config: GuardrailConfig) -> str:
        """Inspect and clean incoming user prompts."""
        for kw in config.blocked_keywords:
            if kw.lower() in text.lower():
                raise GuardrailViolationError(
                    f"Prompt rejected due to prohibited term: '{kw}'",
                    details={"blocked_keyword": kw}
                )
        return text

    async def validate_and_filter_output(
        self,
        prompt: str,
        response_text: str,
        config: GuardrailConfig,
    ) -> str:
        """Validate agent output against Parlant guidelines and mask any sensitive leaked tokens."""
        # 1. Mask sensitive credentials if found
        sanitized = response_text
        for pattern in self.CREDENTIAL_PATTERNS:
            sanitized = pattern.sub("[REDACTED_CREDENTIAL]", sanitized)

        # 2. Evaluate against Parlant guidelines and blocked terms
        evaluation = await self.adapter.evaluate_guidelines(
            prompt=prompt,
            response=sanitized,
            config=config,
        )

        if not evaluation.get("compliant", True):
            violations = evaluation.get("violations", ["Compliance policy violation"])
            raise GuardrailViolationError(
                f"Agent response failed behavioral compliance: {', '.join(violations)}",
                details={"violations": violations, "ruleset_id": config.ruleset_id}
            )

        return sanitized
