from __future__ import annotations

import re

_META_PATTERNS = [
    r"(?i)\b(sponsored?|sponsorship)\b.{0,120}",
    r"(?i)\bsmash\s+that\s+(like|subscribe)\b.{0,80}",
    r"(?i)\blike\s+(and\s+)?subscribe\b.{0,80}",
    r"(?i)\bsubscribe\s+(to\s+)?(my|the|this)\s+(channel|newsletter|podcast)\b.{0,80}",
    r"(?i)\bfollow\s+(me\s+)?on\s+(twitter|instagram|tiktok|linkedin|facebook)\b.{0,80}",
    r"(?i)\bcheck\s+out\s+my\s+merch\b.{0,100}",
    r"(?i)\bsupport\s+(me\s+)?on\s+patreon\b.{0,100}",
    r"(?i)\bjoin\s+(my\s+)?discord\b.{0,80}",
    r"(?i)\bget\s+\d+%\s+off\b.{0,120}",
    r"(?i)\buse\s+(code|promo)\s+\w+\s+(for|to\s+get)\b.{0,120}",
    r"(?i)\bnordvpn\b.{0,150}",
    r"(?i)\bteespring\b.{0,100}",
]

_COMPILED = [re.compile(p) for p in _META_PATTERNS]


def remove_meta(text: str) -> str:
    if not text:
        return text
    lines = text.split("\n")
    cleaned: list[str] = []
    for line in lines:
        if any(pat.search(line) for pat in _COMPILED):
            continue
        cleaned.append(line)
    return "\n".join(cleaned)
