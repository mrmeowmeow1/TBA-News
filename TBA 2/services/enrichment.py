"""Apply the local ML features to a list of feed items (in place, never raising).

Adds to every item:

``topic``            ``{label, score, matched, method, reason}``               (categorizer)
``sentiment``        ``{label, score, confidence, method, financial, note}``   (sentiment)
``story``            ``{id, size, lead, similarity}``                          (duplicate grouping)
``also_covered_by``  other items reporting the same story (id, title, source, url, published)

The original fields (title, source, url, published, description, category, image) are untouched,
and no item is removed: grouping only *labels* duplicates so the UI can collapse them.
"""
from __future__ import annotations

import logging

from . import config
from .categorizer import classify_topic
from .sentiment import analyze_sentiment
from .similarity import article_text, group_duplicates

log = logging.getLogger("tba.enrichment")

MAX_LISTED_SOURCES = 8


def enrich_items(items: list[dict], descriptions: dict | None = None) -> list[dict]:
    """``descriptions`` maps item id -> a *real* publisher description ('' when only a headline echo)."""
    descriptions = descriptions or {}
    texts = []
    for item in items:
        description = descriptions.get(item.get("id"), "")
        text = article_text(item.get("title", ""), description)
        item["topic"] = classify_topic(item.get("title", ""), description)
        item["sentiment"] = analyze_sentiment(text, "headline", item["topic"]["label"])
        texts.append(text)

    try:
        groups, group_of, match = group_duplicates(texts, config.duplicate_threshold())
    except Exception as exc:                              # grouping is optional; never break the feed
        log.warning("Duplicate grouping failed: %s", type(exc).__name__)
        return items
    for members in groups:
        group_id = "g" + items[members[0]]["id"][:12]
        for idx in members:
            item = items[idx]
            item["story"] = {"id": group_id, "size": len(members), "lead": idx == members[0], "similarity": match[idx]}
            item["also_covered_by"] = [
                {"id": items[o]["id"], "title": items[o]["title"], "source": items[o]["source"],
                 "url": items[o]["url"], "published": items[o].get("published")}
                for o in members if o != idx][:MAX_LISTED_SOURCES]
    return items
