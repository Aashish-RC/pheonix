"""
Pheonix Guardrails Engine
Orchestrates multi-layer safety evaluation (Crisis, Jailbreak/Injection, PII Sanitization),
configurable severity thresholds (G7), and security audit logging (G8).
"""

import os
from typing import Optional, Literal
from ..models import (
    SafetyCheckRequest,
    SafetyCheckResult,
    SeverityLevel,
    SEVERITY_ORDER,
)
from .crisis import CrisisHandler
from .jailbreak import JailbreakDetector
from .detector import PIIDetector
from .audit import GuardrailAuditLogger


class GuardrailsEngine:
    """
    Central safety and guardrails evaluation engine for Pheonix.
    Configurable severity thresholds: lower environments or strict deployments can enforce stricter boundaries.
    """

    def __init__(
        self,
        crisis_handler: Optional[CrisisHandler] = None,
        jailbreak_detector: Optional[JailbreakDetector] = None,
        pii_detector: Optional[PIIDetector] = None,
        audit_logger: Optional[GuardrailAuditLogger] = None,
        severity_threshold: Optional[SeverityLevel] = None,
    ):
        self.crisis_handler = crisis_handler or CrisisHandler()
        self.jailbreak_detector = jailbreak_detector or JailbreakDetector()
        self.pii_detector = pii_detector or PIIDetector()
        self.audit_logger = audit_logger or GuardrailAuditLogger()
        
        env_threshold = os.environ.get("GUARDRAILS_SEVERITY_THRESHOLD", "warn").lower()
        self.severity_threshold: SeverityLevel = severity_threshold or (
            env_threshold if env_threshold in SEVERITY_ORDER else "warn"
        )

    def set_severity_threshold(self, threshold: SeverityLevel) -> None:
        """Programmatically update runtime safety threshold (allow, warn, redact, block, strict)."""
        clean = threshold.lower()
        if clean not in SEVERITY_ORDER:
            raise ValueError(f"Invalid severity threshold '{threshold}'. Expected one of {list(SEVERITY_ORDER.keys())}")
        self.severity_threshold = clean

    def evaluate(self, request: SafetyCheckRequest) -> SafetyCheckResult:
        """
        Evaluates input text sequentially across crisis, injection, and sanitization gates.
        Enforces configurable severity levels and writes non-allow events to the audit log.
        In strict mode, warnings and PII leaks escalate to block.
        """
        text = request.prompt.strip()
        threshold_rank = SEVERITY_ORDER.get(self.severity_threshold, 1)
        is_strict = self.severity_threshold == "strict"

        # Gate 1: Crisis & Self-Harm Circuit-Breaker (Highest Priority)
        is_crisis, crisis_cat, crisis_msg = self.crisis_handler.check_with_category(text)
        if is_crisis:
            result = SafetyCheckResult(
                action="crisis_intervention",
                severity="crisis",
                threat_category=f"crisis_{crisis_cat}" if crisis_cat else "crisis_self_harm",
                sanitized_prompt=None,
                reason="Self-harm or crisis situation detected. Circuit breaker triggered.",
                crisis_response=crisis_msg,
                matched_patterns=[f"crisis_{crisis_cat or 'self_harm'}_regex"],
            )
            self._log_if_needed(request, result)
            return result

        # Gate 2: Prompt Injection and Adversarial Jailbreak Detection
        is_jailbreak, matches = self.jailbreak_detector.detect(text)
        if is_jailbreak:
            action = "block" if (is_strict or SEVERITY_ORDER["block"] >= threshold_rank) else "warn"
            result = SafetyCheckResult(
                action=action,
                severity="strict" if is_strict else "block",
                threat_category="prompt_injection" if any("ignore" in m.lower() or "override" in m.lower() for m in matches) else "jailbreak",
                sanitized_prompt=None if action == "block" else text,
                reason=f"Adversarial prompt injection or jailbreak detected: {', '.join(matches[:2])}",
                crisis_response=None,
                matched_patterns=matches,
            )
            self._log_if_needed(request, result)
            return result

        # Gate 3: PII & Credential Sanitization
        sanitized_text, was_redacted, pii_types = self.pii_detector.sanitize(text)
        if was_redacted:
            action = "block" if is_strict else ("redact" if SEVERITY_ORDER["redact"] >= threshold_rank else "warn")
            result = SafetyCheckResult(
                action=action,
                severity="strict" if is_strict else "redact",
                threat_category="pii_leak",
                sanitized_prompt=None if action == "block" else sanitized_text,
                reason=f"Sensitive PII detected ({', '.join(pii_types)}) - blocked under strict policy" if is_strict else f"Sensitive PII or credentials detected and redacted: {', '.join(pii_types)}",
                crisis_response=None,
                matched_patterns=pii_types,
            )
            self._log_if_needed(request, result)
            return result

        # Gate 4: Allow clean request
        return SafetyCheckResult(
            action="allow",
            severity="allow",
            threat_category="none",
            sanitized_prompt=text,
            reason="Prompt passed all safety evaluations cleanly.",
            crisis_response=None,
            matched_patterns=[],
        )

    def _log_if_needed(self, request: SafetyCheckRequest, result: SafetyCheckResult) -> None:
        """Appends security event to the audit log for non-allow actions."""
        if result.action != "allow" and self.audit_logger:
            try:
                self.audit_logger.log_event(
                    action=result.action,
                    threat_category=result.threat_category,
                    prompt=request.prompt,
                    actor=request.actor,
                    matched_patterns=result.matched_patterns,
                    reason=result.reason,
                    metadata={"severity": result.severity},
                )
            except Exception:
                pass
