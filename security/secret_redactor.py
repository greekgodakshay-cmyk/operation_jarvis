"""
Secret and Credential Redaction Engine.
"""
import re
from typing import Any, Dict, List, Union

SECRET_PATTERNS = [
    re.compile(r"(sk-[a-zA-Z0-9_\-]{20,})", re.IGNORECASE),
    re.compile(r"(ghp_[a-zA-Z0-9]{36,})", re.IGNORECASE),
    re.compile(r"(gho_[a-zA-Z0-9]{36,})", re.IGNORECASE),
    re.compile(r"(xox[baprs]-[a-zA-Z0-9\-]+)", re.IGNORECASE),
    re.compile(r"(ey[a-zA-Z0-9_\-]{15,}\.[a-zA-Z0-9_\-]{15,}\.[a-zA-Z0-9_\-]{15,})", re.IGNORECASE),
    re.compile(r"(AKIA[0-9A-Z]{16})", re.IGNORECASE),
    re.compile(r"(AIza[0-9A-Za-z\-_]{35})", re.IGNORECASE),
    re.compile(r"(bearer\s+[a-zA-Z0-9_\-\.]{20,})", re.IGNORECASE),
    re.compile(r"(password[\"']?\s*[:=]\s*[\"'])([^\"'\s]+)([\"'])", re.IGNORECASE),
]

def redact_text(text: str) -> str:
    if not isinstance(text, str):
        return text
    redacted = text
    for pattern in SECRET_PATTERNS:
        # If pattern has 3 groups (e.g. password="...") keep key, redact value
        if pattern.groups == 3:
            redacted = pattern.sub(r"\g<1>[REDACTED_SECRET]\g<3>", redacted)
        else:
            redacted = pattern.sub("[REDACTED_SECRET]", redacted)
    return redacted

def redact_structure(data: Any) -> Any:
    """Recursively redacts secrets in dicts, lists, and strings."""
    if isinstance(data, str):
        return redact_text(data)
    elif isinstance(data, dict):
        cleaned = {}
        for k, v in data.items():
            k_str = str(k).lower() if k is not None else ""
            if any(term in k_str for term in ["key", "secret", "token", "password", "auth", "credential"]):
                if isinstance(v, str) and len(v) > 0:
                    cleaned[k] = "[REDACTED_CREDENTIAL]"
                else:
                    cleaned[k] = redact_structure(v)
            else:
                cleaned[k] = redact_structure(v)
        return cleaned
    elif isinstance(data, list):
        return [redact_structure(item) for item in data]
    return data
