"""Settings read from environment variables (never hard-coded, never sent to the browser).

Values are read at call time so tests (and operators) can change them without re-importing.
"""
from __future__ import annotations

import os
from urllib.parse import urlparse


def _text(name: str, default: str = "") -> str:
    return (os.environ.get(name) or default).strip()


def _number(name: str, default: float, low: float, high: float) -> float:
    try:
        value = float(os.environ.get(name, default))
    except (TypeError, ValueError):
        return default
    return min(high, max(low, value))


def _flag(name: str, default: bool) -> bool:
    raw = os.environ.get(name)
    if raw is None or raw.strip() == "":
        return default
    return raw.strip().lower() not in ("0", "false", "no", "off")


# --- optional AI summarisation (any OpenAI-compatible chat-completions endpoint) -----------------
def ai_settings() -> dict:
    base = _text("TBA_AI_BASE_URL", "https://api.openai.com/v1").rstrip("/")
    return {
        "api_key": _text("TBA_AI_API_KEY"),
        "base_url": base,
        "model": _text("TBA_AI_MODEL", "gpt-4o-mini"),
        "timeout": _number("TBA_AI_TIMEOUT", 25, 3, 120),
        "max_input_chars": int(_number("TBA_AI_MAX_INPUT_CHARS", 12000, 1500, 60000)),
        "strict_grounding": _flag("TBA_AI_STRICT_GROUNDING", True),
    }


def base_url_is_acceptable(base_url: str) -> bool:
    """Credentials only travel over HTTPS, except to a local server such as Ollama."""
    parsed = urlparse(base_url)
    if parsed.scheme == "https" and parsed.hostname:
        return True
    return parsed.scheme == "http" and (parsed.hostname or "") in ("localhost", "127.0.0.1", "::1")


# --- local ML ---------------------------------------------------------------------------------
def sentiment_backend() -> str:
    value = _text("TBA_SENTIMENT_BACKEND", "vader").lower()
    return value if value in ("vader", "transformers") else "vader"


def sentiment_model() -> str:
    return _text("TBA_SENTIMENT_MODEL", "cardiffnlp/twitter-roberta-base-sentiment-latest")


def duplicate_threshold() -> float:
    return _number("TBA_DUPLICATE_THRESHOLD", 0.50, 0.1, 0.95)


def recommendation_count() -> int:
    return int(_number("TBA_RECOMMENDATIONS", 4, 1, 8))
