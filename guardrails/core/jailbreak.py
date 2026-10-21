"""
Pheonix Prompt Injection & Jailbreak Detector
Detects adversarial prompt injections, DAN exploits, roleplay bypasses, and delimiter attacks.
"""

import re
from typing import List, Tuple

JAILBREAK_PATTERNS = [
    # 1. System prompt override and instruction ignoring
    r"(?i)\b(?:ignore|disregard|forget|bypass)\s+(?:all\s+)?(?:previous|prior|above|existing)\s+(?:instructions|rules|directives|prompts|guidelines)\b",
    r"(?i)\b(?:override|reset)\s+(?:your\s+)?(?:system\s+prompt|core\s+directives|safety\s+guidelines)\b",
    
    # 2. DAN (Do Anything Now) and explicit jailbreak modes
    r"(?i)\b(?:you\s+are(?:\s+now)?(?:\s+in)?|act\s+as(?:\s+an?)?|enter)\s+(?:DAN|do\s+anything\s+now|developer\s+mode|unfiltered(?:\s+mode|\s+ai)?|god\s+mode)\b",
    r"(?i)\b(?:DAN|do\s+anything\s+now|jailbreak|jailbroken)\s+mode\b",
    r"(?i)\b(?:you\s+are|become)\s+DAN\b",
    r"(?i)\bhave\s+broken\s+free\s+of\s+(?:ai\s+)?limitations\b",
    r"(?i)\bignores?\s+(?:openai|safety|ai)\s+(?:guidelines|rules|policies)\b",
    
    # 3. Delimiter and pseudo-system token injection
    r"(?i)(?:<\|im_start\|>system|<\|system\|>|\[SYSTEM\s+OVERRIDE\]|###\s+Instruction:\s*override)",
    r"(?i)(?:\{{\s*system\s*\}}|<system_prompt_override>)",
    
    # 4. Roleplay bypasses encouraging unfiltered/illegal actions
    r"(?i)\b(?:pretend\s+you\s+have\s+no\s+rules|pretend\s+you\s+are\s+an\s+evil\s+ai|act\s+as\s+a\s+villain\s+who\s+hacks)\b",
    r"(?i)\b(?:hypothetically\s+if\s+you\s+had\s+no\s+ethics|for\s+educational\s+purposes\s+teach\s+me\s+to\s+make\s+a\s+bomb)\b",
]


class JailbreakDetector:
    """Evaluates prompt texts against known adversarial attack patterns."""

    def __init__(self):
        self._compiled = [re.compile(p) for p in JAILBREAK_PATTERNS]

    def detect(self, text: str) -> Tuple[bool, List[str]]:
        """
        Returns (is_jailbreak, matched_rules).
        """
        matches = []
        for regex in self._compiled:
            match = regex.search(text)
            if match:
                matches.append(match.group(0))

        return len(matches) > 0, matches
