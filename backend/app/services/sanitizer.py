"""
SafeSphere AI — Privacy Sanitizer & Security Utilities
Handles PII detection, redaction, prompt-injection defense, coordinate coarsening,
and region classification.
"""

from __future__ import annotations

import hashlib
import re
from typing import Optional, Tuple


# Regex patterns for Indian PII detection
_PHONE_PATTERN = re.compile(
    r"(?:(?:\+?91[\-\s]?)?[6-9]\d{9}|\b0\d{2,4}[\-\s]?\d{6,8}\b)",
    re.IGNORECASE,
)
_EMAIL_PATTERN = re.compile(
    r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b",
    re.IGNORECASE,
)
_AADHAAR_PATTERN = re.compile(
    r"\b\d{4}\s?\d{4}\s?\d{4}\b",
)
_HTML_TAG_PATTERN = re.compile(r"<[^<]+?>")

# Prompt-injection patterns to protect downstream LLM/RAG pipelines
_PROMPT_INJECTION_PATTERN = re.compile(
    r"(?i)(?:ignore\s+(?:all\s+)?(?:previous|prior)\s+instructions|"
    r"system\s*:\s*|you\s+are\s+now\s+|disregard\s+(?:previous|all)|"
    r"assistant\s*:|\[INST\]|<\|im_start\|>|<\|system\|>|"
    r"eval\s*\(|exec\s*\(|__import__|subprocess)",
)


def sanitize_text(text: Optional[str]) -> Tuple[Optional[str], bool, bool]:
    """
    Sanitize user-submitted free text for privacy and security.

    Returns:
        (sanitized_text, pii_detected, prompt_injection_detected)
    """
    if not text or not text.strip():
        return None, False, False

    cleaned = text.strip()

    # 1. Strip raw HTML tags to prevent XSS / markup injection
    cleaned = _HTML_TAG_PATTERN.sub("", cleaned)

    pii_detected = False
    prompt_injection_detected = False

    # 2. Check and neutralize prompt injection attempts
    if _PROMPT_INJECTION_PATTERN.search(cleaned):
        prompt_injection_detected = True
        cleaned = _PROMPT_INJECTION_PATTERN.sub("[FILTERED INSTRUCTION]", cleaned)

    # 3. Detect and redact phone numbers
    if _PHONE_PATTERN.search(cleaned):
        pii_detected = True
        cleaned = _PHONE_PATTERN.sub("[PHONE REDACTED]", cleaned)

    # 4. Detect and redact email addresses
    if _EMAIL_PATTERN.search(cleaned):
        pii_detected = True
        cleaned = _EMAIL_PATTERN.sub("[EMAIL REDACTED]", cleaned)

    # 5. Detect and redact Aadhaar / 12-digit national IDs
    if _AADHAAR_PATTERN.search(cleaned):
        pii_detected = True
        cleaned = _AADHAAR_PATTERN.sub("[ID REDACTED]", cleaned)

    # Clean up multi-spaces created during substitution
    cleaned = re.sub(r" {2,}", " ", cleaned).strip()

    return cleaned, pii_detected, prompt_injection_detected


def coarsen_coordinates(lat: float, lon: float, precision_decimals: int = 3) -> Tuple[float, float]:
    """
    Coarsen coordinates for public display to protect victim/reporter location privacy.
    3 decimal places provides ~110m grid resolution (sufficient for safety navigation,
    without exposing exact residential doorsteps).
    """
    return round(lat, precision_decimals), round(lon, precision_decimals)


def determine_pilot_region(lat: float, lon: float) -> str:
    """
    Determine if coordinates fall inside Delhi (NCT) or Sonipat (Haryana) pilot bounds.
    """
    # Sonipat bounding box
    if 28.87 <= lat <= 29.07 and 76.88 <= lon <= 77.15:
        return "sonipat"
    # Delhi bounding box
    elif 28.40 <= lat <= 28.88 and 76.83 <= lon <= 77.35:
        return "delhi"
    return "other"


def generate_reporter_hash(ip: str, user_agent: str, salt: str = "safesphere-pilot-salt") -> str:
    """
    Generate a one-way pseudonymous reporter hash.
    Raw IP addresses and personal identifiers are never stored.
    """
    data = f"{ip}:{user_agent}:{salt}".encode("utf-8")
    return hashlib.sha256(data).hexdigest()
