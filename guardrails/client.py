"""
Pheonix Guardrails Client SDK
High-level client for applications, memory engine, and agents to evaluate and sanitize prompts.
"""

from typing import Optional
from .models import SafetyCheckRequest, SafetyCheckResult
from .core.engine import GuardrailsEngine


class GuardrailsClient:
    """
    Client for interacting with Pheonix Guardrails and Safety.
    """

    def __init__(self, engine: Optional[GuardrailsEngine] = None):
        self.engine = engine or GuardrailsEngine()

    def check(self, prompt: str, actor: str = "anonymous") -> SafetyCheckResult:
        """Runs prompt through full guardrails pipeline."""
        req = SafetyCheckRequest(prompt=prompt, actor=actor)
        return self.engine.evaluate(req)

    def is_safe(self, prompt: str) -> bool:
        """Returns True if prompt is permitted (allowed or cleanly redacted)."""
        result = self.check(prompt)
        return result.action in ["allow", "redact"]

    def sanitize_prompt(self, prompt: str) -> str:
        """
        Returns sanitized prompt if allowed or redacted.
        Raises ValueError if prompt is blocked or triggers crisis intervention.
        """
        result = self.check(prompt)
        if result.action == "block":
            raise ValueError(f"Prompt blocked by guardrails: {result.reason}")
        if result.action == "crisis_intervention":
            raise ValueError(f"Crisis intervention triggered: {result.crisis_response}")
        return result.sanitized_prompt or prompt
