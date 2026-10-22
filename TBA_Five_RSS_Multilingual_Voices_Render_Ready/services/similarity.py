"""TF-IDF + cosine similarity: duplicate-story grouping and content-based recommendations.

Everything here is classic information retrieval (no neural network, no training):

* Each article becomes a TF-IDF vector over stemmed words and adjacent-word pairs.  Words that
  are rare across the current feed (``Hinjewadi``) weigh more than common ones (``government``).
* Similarity of two articles = cosine of the angle between their vectors (0 = nothing in common,
  1 = identical wording).  Vectors are L2-normalised, so cosine is just a dot product.

Duplicate grouping
    Articles are processed in feed order.  An article joins an existing group when its best match
    inside that group reaches ``threshold``, it is not too far from the group's first (lead) article,
    and the two share at least ``min_shared`` informative words.  Otherwise it starts a new group.
    Nothing is deleted: every article keeps its own publisher, link and timestamp.

Recommendations
    score = similarity to the open article
          + a small bonus for the same detected topic
          + a weighted similarity to the user's saved stories (titles sent by the browser,
            used for this request only and never stored)
    Same-story copies of the open article are excluded, and only the best article per duplicate
    group is returned, so the list never shows one story twice.
"""
from __future__ import annotations

import hashlib
import threading
from collections import OrderedDict
from typing import Any, cast

import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer

from .text_utils import analyzer, clean_text, tokens

TOPIC_BONUS = 0.08
INTEREST_WEIGHT = 0.35
MIN_RECOMMENDATION_SCORE = 0.08
ANCHOR_RATIO = 0.6          # a joiner must still resemble the group's lead at 60 % of the threshold


# ----------------------------------------------------------------------------------------------
# Vector cache: fitting is cheap for ~70 articles, but is identical for every request on one feed
# ----------------------------------------------------------------------------------------------
class _VectorCache:
    def __init__(self, size: int = 8):
        self.size, self._data, self._lock = size, OrderedDict(), threading.Lock()

    def get_or_build(self, texts: list[str]):
        key = hashlib.sha1("\x1f".join(texts).encode("utf-8", "ignore")).hexdigest()
        with self._lock:
            if key in self._data:
                self._data.move_to_end(key)
                return self._data[key]
        built = _fit(texts)
        with self._lock:
            self._data[key] = built
            while len(self._data) > self.size:
                self._data.popitem(last=False)
        return built

    def clear(self):
        with self._lock:
            self._data.clear()


VECTOR_CACHE = _VectorCache()


def _fit(texts: list[str]):
    """Return (vectorizer, matrix) or (None, None) when there is nothing to learn from."""
    vec = TfidfVectorizer(analyzer=cast(Any, analyzer), sublinear_tf=True)
    try:
        matrix = vec.fit_transform(texts)
    except ValueError:          # empty vocabulary (e.g. only stop words)
        return None, None
    return vec, matrix


def article_text(title, description: str = "") -> str:
    return " ".join(part for part in (clean_text(title, 400), clean_text(description, 600)) if part)


def similarity_matrix(texts: list[str]) -> np.ndarray:
    """Dense cosine-similarity matrix for ``texts`` (zeros if nothing is comparable)."""
    n = len(texts)
    if n == 0:
        return np.zeros((0, 0))
    vec, matrix = VECTOR_CACHE.get_or_build(texts)
    if matrix is None:
        return np.zeros((n, n))
    return (matrix @ matrix.T).toarray()


# ----------------------------------------------------------------------------------------------
# Duplicate detection
# ----------------------------------------------------------------------------------------------
def group_duplicates(texts: list[str], threshold: float = 0.50, min_shared: int = 2):
    """Group indices of ``texts`` that report the same story.

    Returns ``(groups, group_of, match)``: ``groups`` is a list of index lists (first index = lead),
    ``group_of[i]`` the group number of article *i*, and ``match[i]`` its similarity to the member it
    joined (``None`` for a lead).
    """
    n = len(texts)
    sims = similarity_matrix(texts)
    bags = [set(tokens(t)) for t in texts]
    groups: list[list[int]] = []
    group_of = [-1] * n
    match: list[float | None] = [None] * n
    for i in range(n):
        best_group, best_sim, best_member = -1, 0.0, -1
        for g, members in enumerate(groups):
            lead_sim = sims[i, members[0]]
            if lead_sim < threshold * ANCHOR_RATIO:
                continue
            m = max(members, key=lambda idx: sims[i, idx])
            if sims[i, m] >= threshold and len(bags[i] & bags[m]) >= min_shared and sims[i, m] > best_sim:
                best_group, best_sim, best_member = g, float(sims[i, m]), m
        if best_group >= 0:
            groups[best_group].append(i)
            group_of[i], match[i] = best_group, round(best_sim, 3)
        else:
            groups.append([i])
            group_of[i] = len(groups) - 1
    return groups, group_of, match


# ----------------------------------------------------------------------------------------------
# Recommendations
# ----------------------------------------------------------------------------------------------
def recommend(current_id: str, pool: list[dict], saved_titles: list[str] | None = None,
              limit: int = 4, dup_threshold: float = 0.50) -> dict:
    """Rank related articles from ``pool`` (dicts with ``id``, ``text`` and optional ``topic``).

    Returns ``{"items": [{"id", "score", "reasons", "fallback"}], "method", "fallback", "message"}``.
    """
    method = "tfidf-cosine + topic + saved-story interests"
    index = {item["id"]: n for n, item in enumerate(pool)}
    if current_id not in index:
        return {"items": [], "method": method, "fallback": False, "message": "unknown_article"}
    if len(pool) < 2:
        return {"items": [], "method": method, "fallback": False, "message": "not_enough_articles"}

    texts = [item["text"] for item in pool]
    vec, matrix = VECTOR_CACHE.get_or_build(texts)
    cur = index[current_id]

    # Which articles are the same story as the open one, and which duplicate group is each in?
    _, group_of, _ = group_duplicates(texts, dup_threshold)

    if matrix is None or vec is None:
        base = np.zeros(len(pool))
        interest = np.zeros(len(pool))
    else:
        base = (matrix @ matrix[cur].T).toarray().ravel()
        interest = np.zeros(len(pool))
        titles = [clean_text(t, 300) for t in (saved_titles or [])[:10] if isinstance(t, str)]
        titles = [t for t in titles if tokens(t)]
        if titles:
            saved = cast(Any, vec).transform(titles)
            centroid = np.asarray(cast(Any, saved).mean(axis=0)).ravel()
            norm = np.linalg.norm(centroid)
            if norm > 0:
                interest = (matrix @ (centroid / norm)).ravel()
    cur_topic = (pool[cur].get("topic") or {}).get("label") if isinstance(pool[cur].get("topic"), dict) else pool[cur].get("topic")

    scored = []
    for n, item in enumerate(pool):
        if n == cur or group_of[n] == group_of[cur]:
            continue                                  # itself, or another copy of the same story
        topic = (item.get("topic") or {}).get("label") if isinstance(item.get("topic"), dict) else item.get("topic")
        same_topic = bool(topic and topic != "General" and topic == cur_topic)
        score = float(base[n]) + (TOPIC_BONUS if same_topic else 0.0) + INTEREST_WEIGHT * float(interest[n])
        reasons = []
        if base[n] >= 0.05:
            reasons.append("Similar keywords")
        if same_topic:
            reasons.append(f"Same topic: {topic}")
        if interest[n] >= 0.08:
            reasons.append("Matches your saved stories")
        scored.append((score, n, reasons))

    scored.sort(key=lambda row: (-row[0], row[1]))
    chosen, seen_groups = [], set()
    for score, n, reasons in scored:
        if score < MIN_RECOMMENDATION_SCORE or group_of[n] in seen_groups:
            continue
        seen_groups.add(group_of[n])
        chosen.append({"id": pool[n]["id"], "score": round(score, 3), "reasons": reasons or ["Similar keywords"], "fallback": False})
        if len(chosen) == limit:
            break

    used_fallback = False
    if len(chosen) < min(2, limit):
        # Too little signal: top up with the most recent *different* stories, clearly labelled.
        used_fallback = True
        for score, n, reasons in sorted(scored, key=lambda row: row[1]):
            if group_of[n] in seen_groups:
                continue
            seen_groups.add(group_of[n])
            chosen.append({"id": pool[n]["id"], "score": None, "reasons": ["Recent story from your feed"], "fallback": True})
            if len(chosen) >= min(limit, 3):
                break
    return {"items": chosen, "method": method, "fallback": used_fallback, "message": None}
