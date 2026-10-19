"""Curated direct-publisher RSS feeds for TBA.

LICENSING: A feed URL is NOT a license to reproduce full articles or images.
The default flags are conservative. Review each publisher's terms before
turning on image proxying, fulltext summarization or a restricted feed.
"""
from __future__ import annotations

from dataclasses import dataclass
import os


@dataclass(frozen=True)
class RSSSource:
    name: str
    url: str
    allow_images: bool = False
    allow_article_fetch: bool = False
    allow_feed_excerpt: bool = False
    restricted: bool = False


# The BBC, TechCrunch and other feed owners place conditions on feed display.
# Do not assume that RSS availability permits republishing, image proxying,
# scraping or AI summarization. These defaults support headline/link discovery.
BBC_TOP = RSSSource("BBC News", "https://feeds.bbci.co.uk/news/rss.xml")
BBC_WORLD = RSSSource("BBC News", "https://feeds.bbci.co.uk/news/world/rss.xml")
BBC_ASIA = RSSSource("BBC News", "https://feeds.bbci.co.uk/news/world/asia/rss.xml")
BBC_INDIA = RSSSource("BBC News", "https://feeds.bbci.co.uk/news/world/asia/india/rss.xml")
BBC_AMERICAS = RSSSource("BBC News", "https://feeds.bbci.co.uk/news/world/us_and_canada/rss.xml")
BBC_BUSINESS = RSSSource("BBC News", "https://feeds.bbci.co.uk/news/business/rss.xml")
BBC_ECONOMY = RSSSource("BBC News", "https://feeds.bbci.co.uk/news/business/economy/rss.xml")
BBC_TECH = RSSSource("BBC News", "https://feeds.bbci.co.uk/news/technology/rss.xml")
BBC_ENT = RSSSource("BBC News", "https://feeds.bbci.co.uk/news/entertainment_and_arts/rss.xml")
BBC_SPORT = RSSSource("BBC Sport", "https://feeds.bbci.co.uk/sport/rss.xml")
BBC_CRICKET = RSSSource("BBC Sport", "https://feeds.bbci.co.uk/sport/cricket/rss.xml")
BBC_FOOTBALL = RSSSource("BBC Sport", "https://feeds.bbci.co.uk/sport/football/rss.xml")
BBC_SCIENCE = RSSSource("BBC News", "https://feeds.bbci.co.uk/news/science_and_environment/rss.xml")
BBC_HEALTH = RSSSource("BBC News", "https://feeds.bbci.co.uk/news/health/rss.xml")

# NASA generally permits factual/educational reuse of NASA-created media,
# but articles/images can contain third-party material. Manually check credits.
NASA_NEWS = RSSSource("NASA", "https://www.nasa.gov/news-release/feed/", allow_article_fetch=True, allow_feed_excerpt=True)
NASA_TECH = RSSSource("NASA", "https://www.nasa.gov/technology/feed/", allow_article_fetch=True, allow_feed_excerpt=True)
TECHCRUNCH = RSSSource("TechCrunch", "https://techcrunch.com/feed/")

# PIB is an official Government of India press-release channel, NOT independent
# reporting. Its reuse policy permits accurate reproduction with attribution,
# excluding any third-party content. Prefer text only; no image proxying.
PIB = RSSSource("PIB · Government release", "https://pib.gov.in/RssMain.aspx?ModId=6&Lang=1&Regid=1",
                allow_article_fetch=True, allow_feed_excerpt=True)

# Indian Express explicitly limits RSS consumption to personal/non-commercial
# use and does NOT license reproduction of its photographs, headlines or text.
# Leave disabled on a public site until your use is authorized.
IE_INDIA = RSSSource("The Indian Express", "https://indianexpress.com/section/india/feed/", restricted=True)
IE_WORLD = RSSSource("The Indian Express", "https://indianexpress.com/section/world/feed/", restricted=True)
IE_BUSINESS = RSSSource("The Indian Express", "https://indianexpress.com/section/business/feed/", restricted=True)
IE_TECH = RSSSource("The Indian Express", "https://indianexpress.com/section/technology/feed/", restricted=True)
IE_ENT = RSSSource("The Indian Express", "https://indianexpress.com/section/entertainment/feed/", restricted=True)
IE_SPORTS = RSSSource("The Indian Express", "https://indianexpress.com/section/sports/feed/", restricted=True)
IE_SCIENCE = RSSSource("The Indian Express", "https://indianexpress.com/section/technology/science/feed/", restricted=True)
IE_HEALTH = RSSSource("The Indian Express", "https://indianexpress.com/section/health-wellness/feed/", restricted=True)

FEEDS_BY_CATEGORY = {
    "top": (BBC_TOP, PIB, TECHCRUNCH, IE_INDIA),
    "world": (BBC_WORLD, BBC_ASIA, BBC_AMERICAS, IE_WORLD),
    "nation": (PIB, BBC_INDIA, BBC_ASIA, IE_INDIA),
    "business": (BBC_BUSINESS, BBC_ECONOMY, TECHCRUNCH, IE_BUSINESS),
    "technology": (BBC_TECH, TECHCRUNCH, NASA_TECH, IE_TECH),
    "entertainment": (BBC_ENT, IE_ENT),
    "sports": (BBC_SPORT, BBC_CRICKET, BBC_FOOTBALL, IE_SPORTS),
    "science": (BBC_SCIENCE, NASA_NEWS, NASA_TECH, IE_SCIENCE),
    "health": (BBC_HEALTH, BBC_SCIENCE, IE_HEALTH),
}

# Search across a bounded, representative feed set plus any previously loaded
# category caches. Not a global internet search.
SEARCH_SOURCES = (BBC_TOP, BBC_WORLD, PIB, BBC_TECH, BBC_SPORT, TECHCRUNCH)


def allowed_sources(category: str, search: bool = False) -> tuple[RSSSource, ...]:
    sources = SEARCH_SOURCES if search else FEEDS_BY_CATEGORY.get(category, ())
    include_restricted = os.getenv("TBA_INCLUDE_RESTRICTED_FEEDS", "0") == "1"
    return tuple(s for s in sources if include_restricted or not s.restricted)
