from __future__ import annotations

import re

# Patterns use [^\n.!?] so they stop at sentence/line boundaries and don't
# consume surrounding content when the transcript has no newlines.
_META_PATTERNS = [
    r"(?i)\b(sponsored?|sponsorship)\b[^\n.!?]{0,120}[.!?]?",
    r"(?i)\bsmash\s+that\s+(like|subscribe)\b[^\n.!?]{0,80}[.!?]?",
    r"(?i)\blike\s+(and\s+)?subscribe\b[^\n.!?]{0,80}[.!?]?",
    r"(?i)\bsubscribe\s+(to\s+)?(my|the|this)\s+(channel|newsletter|podcast)\b[^\n.!?]{0,80}[.!?]?",
    r"(?i)\bfollow\s+(me\s+)?on\s+(twitter|instagram|tiktok|linkedin|facebook)\b[^\n.!?]{0,80}[.!?]?",
    r"(?i)\bcheck\s+out\s+my\s+merch\b[^\n.!?]{0,100}[.!?]?",
    r"(?i)\bsupport\s+(me\s+)?on\s+patreon\b[^\n.!?]{0,100}[.!?]?",
    r"(?i)\bjoin\s+(my\s+)?discord\b[^\n.!?]{0,80}[.!?]?",
    r"(?i)\bget\s+\d+%\s+off\b[^\n.!?]{0,120}[.!?]?",
    r"(?i)\buse\s+(code|promo)\s+\w+\s+(for|to\s+get)\b[^\n.!?]{0,120}[.!?]?",
    r"(?i)\bnordvpn\b[^\n.!?]{0,150}[.!?]?",
    r"(?i)\bteespring\b[^\n.!?]{0,100}[.!?]?",
]

_COMPILED = [re.compile(p) for p in _META_PATTERNS]


def remove_meta(text: str) -> str:
    if not text:
        return text
    for pat in _COMPILED:
        text = pat.sub(" ", text)
    return " ".join(text.split())
