"""News sentiment: Positive / Negative / Neutral.

Backends (``TBA_SENTIMENT_BACKEND``):

``vader`` (default)
    VADER (Hutto & Gilbert, 2014) is a *pretrained lexicon-and-rules* analyser shipped inside the
    ``vaderSentiment`` package: no model download, no GPU, no paid API, fully explainable.  It is
    **not** a neural network and **we did not train it**.  A small news-specific lexicon extension
    (below) is applied on top.  Its output is a polarity score in [-1, 1].  That score is reported
    as ``score`` (kind ``lexicon_polarity``); it is *not* a probability, so ``confidence`` is
    ``None`` for this backend.

``transformers`` (optional)
    A pretrained, fine-tuned transformer classifier (default
    ``cardiffnlp/twitter-roberta-base-sentiment-latest``).  Needs ``pip install transformers torch``
    and downloads roughly 500 MB of weights on first use.  Its softmax probability is returned as
    ``confidence`` (a raw model output, not a calibrated probability).  If the packages or weights
    are unavailable the service falls back to VADER and says so in ``method``.

Sentiment describes the *tone of the wording*.  It says nothing about whether the news is good for
anyone, and for financial stories it is **not investment advice** (see ``FINANCIAL_NOTE``).
"""
from __future__ import annotations

import logging
import re
import threading

from . import config
from .text_utils import clean_text, letter_ratio_ascii

log = logging.getLogger("tba.sentiment")

# Wider "neutral" bands than VADER's default +/-0.05: headlines are written to sound factual.
HEADLINE_THRESHOLD = 0.25
ARTICLE_THRESHOLD = 0.10
MAX_CHARS = 5000
MAX_SENTENCES = 40

FINANCIAL_NOTE = "Sentiment is a text classification result about the wording, not investment advice."

# Additions to the VADER lexicon (valence roughly -4..+4).  Chosen for words that are common in
# news but missing or too weak in the stock lexicon.  Deliberately small and inspectable.
NEWS_LEXICON = {
    "layoffs": -2.3, "layoff": -2.3, "retrench": -2.0, "retrenchment": -2.0, "slump": -2.2,
    "plunge": -2.4, "plunges": -2.4, "plummet": -2.5, "plummets": -2.5, "tumble": -2.0,
    "tumbles": -2.0, "slashed": -1.6, "recall": -1.5, "outage": -1.8, "scam": -2.8, "fraud": -2.8,
    "bankruptcy": -2.8, "probe": -1.2, "arrested": -2.0, "convicted": -2.0, "accused": -1.6,
    "clash": -1.8, "clashes": -1.8, "protest": -1.0, "protests": -1.0, "stampede": -2.8,
    "collapse": -2.5, "collapses": -2.5, "shortage": -1.8, "crisis": -2.4, "lockdown": -1.4,
    "outbreak": -2.2, "dengue": -1.8, "ceasefire": 1.2, "truce": 1.2, "rally": 1.8, "rallies": 1.8,
    "surges": 1.8, "surge": 1.4, "soars": 2.2, "soar": 2.2, "jumps": 1.4, "gains": 1.5,
    "record-high": 1.8, "breakthrough": 2.4, "approves": 1.2, "approved": 1.2, "clears": 1.0,
    "wins": 2.4, "triumph": 2.6, "bags": 1.5, "inaugurates": 1.4, "launches": 0.8,
    "falls": -1.6, "fall": -1.4, "drops": -1.4, "slides": -1.6, "sinks": -1.8, "dips": -1.2, "declines": -1.4,
    "drag": -1.0, "cheaper": 1.2, "boost": 1.8, "boosts": 1.8, "relief": 1.6, "recovery": 1.6, "rescued": 1.6,
}

_SENT_SPLIT = re.compile(r"(?<=[.!?])\s+(?=[A-Z0-9\"“‘'(])")
_FINANCE = re.compile(
    r"\b(stocks?|shares?|sensex|nifty|nasdaq|dow jones|equity|equities|bonds?|mutual funds?|ipo|"
    r"rupee|dollar|forex|crypto|bitcoin|earnings|dividend|investors?|trading|market cap|"
    r"repo rate|interest rates?|inflation|gdp|commodit(?:y|ies)|brokerage)\b", re.I)

_vader = None
_vader_lock = threading.Lock()
_transformer = None            # None = not tried, False = unavailable, else pipeline object
_transformer_lock = threading.Lock()


def is_financial(text: str, topic: str | None = None) -> bool:
    """Heuristic flag used only to attach the 'not investment advice' note."""
    if topic == "Business":
        return True
    return len(_FINANCE.findall(text or "")) >= 1


def _vader_analyzer():
    global _vader
    if _vader is None:
        with _vader_lock:
            if _vader is None:
                from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer
                analyzer = SentimentIntensityAnalyzer()
                analyzer.lexicon.update(NEWS_LEXICON)
                _vader = analyzer
    return _vader


def _label(score: float, threshold: float) -> str:
    return "Positive" if score >= threshold else "Negative" if score <= -threshold else "Neutral"


def _unavailable(reason: str) -> dict:
    return {"available": False, "label": None, "score": None, "confidence": None,
            "method": None, "reason": reason, "financial": False, "note": None}


def _load_transformer():
    """Load the optional transformer once. Returns the pipeline or None (and remembers failure)."""
    global _transformer
    if _transformer is None:
        with _transformer_lock:
            if _transformer is None:
                try:
                    from transformers import pipeline  # type: ignore
                    _transformer = pipeline("text-classification", model=config.sentiment_model(), top_k=None)
                except Exception as exc:  # missing package, no network for weights, out of memory...
                    log.warning("Transformer sentiment unavailable (%s); using VADER.", type(exc).__name__)
                    _transformer = False
    return _transformer or None


def _transformer_scores(pipe, text: str):
    """Return (label, confidence) from a Hugging Face pipeline output, or None if unusable."""
    raw = pipe(text[:1500], truncation=True)
    rows = raw[0] if raw and isinstance(raw[0], list) else raw
    best = max(rows, key=lambda r: r["score"])
    name = str(best["label"]).lower()
    mapping = {"positive": "Positive", "pos": "Positive", "label_2": "Positive",
               "negative": "Negative", "neg": "Negative", "label_0": "Negative",
               "neutral": "Neutral", "neu": "Neutral", "label_1": "Neutral"}
    if name not in mapping:
        return None
    return mapping[name], round(float(best["score"]), 3)


def analyze_sentiment(text, kind: str = "headline", topic: str | None = None) -> dict:
    """Classify ``text``.  Never raises; unusable input yields ``available: False``.

    ``kind`` is ``"headline"`` (short text, wider neutral band on the whole string) or
    ``"article"`` (mean of per-sentence VADER scores, which regress toward zero, so a narrower band).
    """
    try:
        cleaned = clean_text(text, MAX_CHARS)
        if len(cleaned) < 8 or not any(c.isalpha() for c in cleaned):
            return _unavailable("empty")
        if letter_ratio_ascii(cleaned) < 0.6:
            return _unavailable("unsupported_language")   # both backends are English-only
        financial = is_financial(cleaned, topic)
        result = {"available": True, "financial": financial,
                  "note": FINANCIAL_NOTE if financial else None, "reason": None}

        if config.sentiment_backend() == "transformers" and (pipe := _load_transformer()):
            try:
                outcome = _transformer_scores(pipe, cleaned)
            except Exception as exc:
                log.warning("Transformer inference failed (%s); using VADER.", type(exc).__name__)
                outcome = None
            if outcome:
                label, confidence = outcome
                return {**result, "label": label, "score": None, "confidence": confidence,
                        "method": f"transformers:{config.sentiment_model()}", "score_kind": None}

        vader = _vader_analyzer()
        if kind == "article":
            sentences = [s for s in _SENT_SPLIT.split(cleaned)[:MAX_SENTENCES] if len(s) > 15]
            if not sentences:
                return _unavailable("empty")
            score = sum(vader.polarity_scores(s)["compound"] for s in sentences) / len(sentences)
            threshold = ARTICLE_THRESHOLD
        else:
            score = vader.polarity_scores(cleaned)["compound"]
            threshold = HEADLINE_THRESHOLD
        return {**result, "label": _label(score, threshold), "score": round(score, 3), "confidence": None,
                "method": "vader+news-lexicon", "score_kind": "lexicon_polarity"}
    except Exception as exc:       # defensive: sentiment must never break the feed
        log.warning("Sentiment analysis failed: %s", type(exc).__name__)
        return _unavailable("error")
