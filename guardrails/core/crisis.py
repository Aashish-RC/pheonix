"""
Pheonix Crisis Response Handler
Detects crisis/self-harm signals and issues compassionate, immediate circuit-breaker intervention notices.
"""

import re
from typing import Optional, Tuple

CRISIS_PATTERNS = [
    r"\b(?:suicide|kill\s+myself|end\s+my\s+life|want\s+to\s+die|hang\s+myself|slit\s+my\s+wrists)\b",
    r"\b(?:how\s+to\s+commit\s+suicide|painless\s+way\s+to\s+die|overdose\s+on\s+pills\s+to\s+die)\b",
    r"\b(?:self[-\s]?harm|cut\s+myself|cutting\s+my\s+wrists)\b",
]

CRISIS_INTERVENTION_NOTICE = (
    "It sounds like you may be going through an overwhelming time, and you don't have to carry this alone. "
    "Please connect with people who can support you right now:\n\n"
    "• In the US & Canada: Call or text 988 (Suicide & Crisis Lifeline) available 24/7, free and confidential.\n"
    "• In the UK: Call 111 (NHS Mental Health) or Samaritans at 116 123.\n"
    "• Crisis Text Line: Text HOME to 741741.\n"
    "• International Support: Find free, confidential support in your country at https://findahelpline.com\n\n"
    "Please reach out to one of these resources or contact a trusted friend or healthcare professional."
)


class CrisisHandler:
    """Detects crisis intents and provides circuit-breaker intervention messages."""

    def __init__(self):
        self._compiled_regexes = [re.compile(p, re.IGNORECASE) for p in CRISIS_PATTERNS]

    def check(self, text: str) -> Tuple[bool, Optional[str]]:
        """
        Returns (is_crisis, crisis_response_text).
        """
        for regex in self._compiled_regexes:
            if regex.search(text):
                return True, CRISIS_INTERVENTION_NOTICE
        return False, None
