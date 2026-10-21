"""Risk Scorer: Static and heuristic evaluation of action risk levels."""

import re
from typing import List, Pattern
from ..core.interfaces import BaseRiskScorer
from ..core.models import ActionType, ActionRequest, RiskLevel


CRITICAL_COMMAND_PATTERNS: List[Pattern] = [
    re.compile(r"\brm\s+(-[rfRF]+\s+|-[a-zA-Z]*r[a-zA-Z]*\s+)/", re.IGNORECASE),
    re.compile(r"\brmdir\s+/[sS]\s+/[qQ]", re.IGNORECASE),
    re.compile(r"\bdel\s+/[fF]\s+/[sS]\s+/[qQ]", re.IGNORECASE),
    re.compile(r"\bformat\s+[a-zA-Z]:", re.IGNORECASE),
    re.compile(r"\b(?:drop\s+database|truncate\s+table)\b", re.IGNORECASE),
    re.compile(r"\b(?:shutdown|reboot|init\s+0)\b", re.IGNORECASE),
    re.compile(r"\bchmod\s+777\b", re.IGNORECASE),
]

SENSITIVE_RESOURCE_PATTERNS: List[Pattern] = [
    re.compile(r"(?:^|[\/\\])(?:\.env|\.vault_key|id_rsa|id_ed25519|secrets?\.json)(?:$|[\/\\])", re.IGNORECASE),
    re.compile(r"(?:/etc/shadow|/etc/passwd|SAM|SYSTEM32[\/\\]config)", re.IGNORECASE),
]


class RiskScorer(BaseRiskScorer):
    """Heuristic risk evaluator analyzing action type, arguments, and sensitive targets."""

    def score(self, request: ActionRequest) -> RiskLevel:
        # Check Critical Command patterns
        if request.action_type in (ActionType.EXEC_COMMAND, ActionType.EXEC_CODE):
            cmd_text = request.resource or request.payload.get("command", "") or request.payload.get("code", "")
            for pat in CRITICAL_COMMAND_PATTERNS:
                if pat.search(cmd_text):
                    return RiskLevel.CRITICAL

        # Check Sensitive Resource patterns
        target = request.resource or request.payload.get("path", "")
        for pat in SENSITIVE_RESOURCE_PATTERNS:
            if pat.search(target):
                return RiskLevel.CRITICAL if request.action_type in (ActionType.FS_WRITE, ActionType.FS_DELETE) else RiskLevel.HIGH

        # Default classification based on Action Type
        if request.action_type == ActionType.SECRET_ACCESS:
            return RiskLevel.HIGH
        elif request.action_type == ActionType.FS_DELETE:
            return RiskLevel.HIGH
        elif request.action_type == ActionType.EXEC_COMMAND:
            return RiskLevel.HIGH
        elif request.action_type in (ActionType.FS_WRITE, ActionType.EXEC_CODE):
            return RiskLevel.MEDIUM
        elif request.action_type in (ActionType.NET_REQUEST, ActionType.CANVAS_EDIT, ActionType.TOOL_INVOKE):
            return RiskLevel.LOW
        elif request.action_type == ActionType.FS_READ:
            return RiskLevel.LOW

        return RiskLevel.MEDIUM
