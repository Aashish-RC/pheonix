"""
Pheonix Guardrails Engine
Orchestrates multi-layer safety evaluation (Crisis, Jailbreak/Injection, PII Sanitization).
"""

from typing import Optional
from ..models import SafetyCheckRequest, SafetyCheckResult
from .crisis import CrisisHandler
from .jailbreak import JailbreakDetector
from .detector import PIIDetector


class GuardrailsEngine:
    """
    Central safety and guardrails evaluation engine for Pheonix.
    """

    def __init__(
        self,
        crisis_handler: Optional[CrisisHandler] = None,
        jailbreak_detector: Optional[JailbreakDetector] = None,
        pii_detector: Optional[PIIDetector] = None
    ):
        self.crisis_handler = crisis_handler or CrisisHandler()
        self.jailbreak_detector = jailbreak_detector or JailbreakDetector()
        self.pii_detector = pii_detector or PIIDetector()

    def evaluate(self, request: SafetyCheckRequest) -> SafetyCheckResult:
        """
        Evaluates input text sequentially across crisis, injection, and sanitization gates.
        """
        text = request.prompt.strip()

        # Gate 1: Crisis & Self-Harm Circuit-Breaker (Highest Priority)
        is_crisis, crisis_msg = self.crisis_handler.check(text)
        if is_crisis:
            return SafetyCheckResult(
                action="crisis_intervention",
                threat_category="crisis_self_harm",
                sanitized_prompt=None,
                reason="Self-harm or crisis situation detected. Circuit breaker triggered.",
                crisis_response=crisis_msg,
                matched_patterns=["crisis_self_harm_regex"]
            )

        # Gate 2: Prompt Injection and Adversarial Jailbreak Detection
        is_jailbreak, matches = self.jailbreak_detector.detect(text)
        if is_jailbreak:
            return SafetyCheckResult(
                action="block",
                threat_category="prompt_injection" if any("ignore" in m.lower() or "override" in m.lower() for m in matches) else "jailbreak",
                sanitized_prompt=None,
                reason=f"Adversarial prompt injection or jailbreak detected: {', '.join(matches[:2])}",
                crisis_response=None,
                matched_patterns=matches
            )

        # Gate 3: PII & Credential Sanitization
        sanitized_text, was_redacted, pii_types = self.pii_detector.sanitize(text)
        if was_redacted:
            return SafetyCheckResult(
                action="redact",
                threat_category="pii_leak",
                sanitized_prompt=sanitized_text,
                reason=f"Sensitive PII or credentials detected and redacted: {', '.join(pii_types)}",
                crisis_response=None,
                matched_patterns=pii_types
            )

        # Gate 4: Allow clean request
        return SafetyCheckResult(
            action="allow",
            threat_category="none",
            sanitized_prompt=text,
            reason="Prompt passed all safety evaluations cleanly.",
            crisis_response=None,
            matched_patterns=[]
        )
