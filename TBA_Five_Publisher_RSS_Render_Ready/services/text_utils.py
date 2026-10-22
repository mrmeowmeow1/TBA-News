"""Shared text helpers: cleaning, tokenising and a deliberately light stemmer."""
from __future__ import annotations

import html
import re
import unicodedata

from sklearn.feature_extraction.text import ENGLISH_STOP_WORDS

# Words that appear in many headlines without carrying topic information.
NEWS_FILLER = frozenset(
    "says said say new news amid according during after before over under across just also "
    "latest live updates update today tonight report reports reportedly watch video photos "
    "know need things want must could would may might will can".split()
)
STOP = frozenset(ENGLISH_STOP_WORDS) | NEWS_FILLER

_TAG = re.compile(r"<[^>]+>")
_SPACE = re.compile(r"\s+")
_TOKEN = re.compile(r"\d+(?:[.,]\d+)*|[a-z]+")


def clean_text(value, limit: int = 20000) -> str:
    """Return plain single-spaced text. Anything that is not a string becomes ''."""
    if not isinstance(value, str):
        return ""
    text = html.unescape(_TAG.sub(" ", value[: limit * 2]))
    text = unicodedata.normalize("NFKC", text)
    text = "".join(ch for ch in text if ch == "\n" or ch == "\t" or unicodedata.category(ch)[0] != "C")
    return _SPACE.sub(" ", text).strip()[:limit]


def stem(word: str) -> str:
    """Very small suffix stripper so approves/approved/approval-style variants line up.

    This is intentionally simple (not Porter): it only needs to make headlines from different
    publishers comparable.  Numbers are never stemmed.
    """
    if len(word) <= 3 or word[0].isdigit():
        return word
    if word.endswith("ies") and len(word) > 5:
        word = word[:-3] + "y"
    elif word.endswith("ing") and len(word) > 5:
        word = word[:-3]
    elif word.endswith("ed") and len(word) > 4:
        word = word[:-2]
    elif word.endswith("s") and not word.endswith("ss") and len(word) > 3:
        word = word[:-1]
    if word.endswith("e") and len(word) > 4:
        word = word[:-1]
    if len(word) > 3 and word[-1] == word[-2] and word[-1] not in "lsz":
        word = word[:-1]
    return word


def tokens(text: str, keep_stopwords: bool = False) -> list[str]:
    """Lower-case stemmed tokens. Possessives are dropped; single letters are ignored."""
    text = unicodedata.normalize("NFKC", text or "").lower().replace("’", "'")
    text = re.sub(r"\b\w+n't\b", " ", text)       # won't / can't must not leave a stray "won"
    text = re.sub(r"'s\b", "", text)
    out = []
    for raw in _TOKEN.findall(text):
        raw = raw.replace(",", "")
        if len(raw) < 2 and not raw.isdigit():
            continue
        if not keep_stopwords and raw in STOP:
            continue
        out.append(stem(raw))
    return out


def analyzer(text: str) -> list[str]:
    """scikit-learn ``analyzer``: unigrams plus adjacent-word bigrams of stemmed tokens."""
    uni = tokens(text)
    return uni + [f"{a}_{b}" for a, b in zip(uni, uni[1:])]


def unigram_analyzer(text: str) -> list[str]:
    return tokens(text)


def letter_ratio_ascii(text: str) -> float:
    """Share of alphabetic characters that are plain Latin letters (1.0 for English text)."""
    letters = [c for c in text if c.isalpha()]
    if not letters:
        return 0.0
    return sum(1 for c in letters if ord(c) < 0x250) / len(letters)
