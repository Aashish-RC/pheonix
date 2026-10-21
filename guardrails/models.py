"""
Pheonix Guardrails Data Models
Defines schema for threat categories, safety check requests, decisions, and crisis notices.
"""

from typing import List, Dict, Any, Optional, Literal
from pydantic import BaseModel, Field


SafetyAction = Literal["allow", "block", "redact", "crisis_intervention"]
ThreatCategory = Literal[
    "prompt_injection",
    "jailbreak",
    "pii_leak",
    "toxic_content",
    "crisis_self_harm",
    "none"
]


class SafetyCheckRequest(BaseModel):
    """Payload to evaluate against safety rules and attack vector detectors."""
    prompt: str
    actor: str = "anonymous"
    context: Dict[str, Any] = Field(default_factory=dict)


class SafetyCheckResult(BaseModel):
    """Outcome of safety evaluation, indicating action, threat type, and sanitized output."""
    action: SafetyAction
    threat_category: ThreatCategory = "none"
    sanitized_prompt: Optional[str] = None
    reason: Optional[str] = None
    crisis_response: Optional[str] = None
    matched_patterns: List[str] = Field(default_factory=list)
