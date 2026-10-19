"""TBA: lightweight Flask API for Google News RSS, publisher images and Quick Read overviews.

Pipeline overview
-----------------
1. ``/api/news`` fetches an RSS feed and returns cards.  Image hints and the full RSS
   description are remembered server-side (``FEED_META``).
2. Google News links are encoded redirect pages.  ``resolve_google_url`` turns them into the
   publisher URL (offline for legacy tokens, via Google's own redirect service otherwise).
3. ``analyze_article`` fetches the publisher page once (SSRF-safe, robots.txt aware, bounded,
   cached) and extracts article text, description metadata and image candidates.
4. ``/api/image/<id>`` and ``/api/article/<id>`` both read that shared analysis.
5. ``services/`` holds the AI/ML layer (sentiment, topic, duplicate grouping, recommendations and the
   optional AI summary); see docs/AI_ML.md.  ``/api/news`` enriches each feed once and caches it.
"""
from __future__ import annotations

import base64
import binascii
import difflib
import hashlib
import ipaddress
import json
import logging
import os
import re
import socket
import threading
import time
from collections import Counter, OrderedDict
from datetime import datetime, timezone
from io import BytesIO
from pathlib import Path
from urllib.parse import quote, quote_plus, urljoin, urlparse
from urllib.robotparser import RobotFileParser

import feedparser
import requests
from bs4 import BeautifulSoup
from flask import Flask, jsonify, render_template, request, Response
from PIL import Image, UnidentifiedImageError
from dotenv import load_dotenv
from gnews_decoder import decode as decode_google_news
from itsdangerous import URLSafeSerializer, BadSignature

# Load local settings before importing services or reading environment variables.
# Shell-set variables take precedence over .env (override=False).
load_dotenv(dotenv_path=Path(__file__).resolve().parent / ".env", override=False)

from services import ai_summarizer, config as ml_config
from services.categorizer import classify_topic
from services.enrichment import enrich_items
from services.sentiment import analyze_sentiment
from services.similarity import article_text, recommend



app = Flask(__name__)

STORY_SIGNING_KEY = os.environ["TBA_STORY_SIGNING_KEY"]

STORY_SIGNER = URLSafeSerializer(
    STORY_SIGNING_KEY,
    salt="tba-story-v1"
)

def story_reference(item):
    payload = {
        "id": item["id"],
        "url": item["url"],
        "title": item.get("title", "")[:350],
        "source": item.get("source", "")[:120],
        "image": item.get("image"),
        "description": item.get("description", "")[:600],
    }
    return STORY_SIGNER.dumps(payload)

app.json.ensure_ascii = False
logging.basicConfig(level=logging.INFO)

# Guard against decompression bombs in remote images (Pillow raises DecompressionBombError above this).
Image.MAX_IMAGE_PIXELS = 40_000_000

CATEGORIES = {"top": "", "world": "WORLD", "nation": "NATION", "business": "BUSINESS", "technology": "TECHNOLOGY", "entertainment": "ENTERTAINMENT", "sports": "SPORTS", "science": "SCIENCE", "health": "HEALTH"}
RSS_ROOT = "https://news.google.com/rss"
ROBOT_TOKEN = "TBAReader"
USER_AGENT = os.environ.get("TBA_USER_AGENT", "Mozilla/5.0 (compatible; TBAReader/1.0; +https://example.org)")
HEADERS = {"User-Agent": USER_AGENT, "Accept-Language": "en-IN,en;q=0.9"}
RESOLVE_GOOGLE_LINKS = os.environ.get("TBA_RESOLVE_GOOGLE_LINKS", "1") != "0"
TTL = 300
MIN_ARTICLE_CHARS = 220          # below this we treat extraction as "no readable article"
RETRY_COOLDOWN = 20              # seconds before a failed analysis may be retried
HTML_TYPES = ("text/html", "application/xhtml")
IMAGE_TYPES = ("image/",)
BLOCKED_STATUS = (401, 402, 403, 429, 451)
GOOGLE_HOSTS = ("news.google.com", "www.google.com", "google.com", "consent.google.com")

NEWS_CACHE = {}
KNOWN_URLS = {}
PUBLISHER_LINKS = {}
FEED_META = {}                   # article id -> {"title", "description", "image", "source"}
HOST_BLOCKED = {}                # host -> timestamp until which we leave it alone (HTTP 429)
_ID_LOCKS = {}
LOCK = threading.RLock()
ANALYSIS_SLOTS = threading.BoundedSemaphore(6)   # simultaneous publisher-page analyses
GOOGLE_SLOTS = threading.BoundedSemaphore(2)     # simultaneous Google link-resolution calls


STOPWORDS = set("the a an and or but at on in of to for from by with is are was were it its this that as be been will would can could should has have had not their they you your we our into than after before about over under across says said also who what when where why how just new more most many some news amid according during all if up out he she his her them us do did so".split())

def restore_story(article_id):
    token = request.args.get("story", "")

    if not token or len(token) > 10000:
        return False

    try:
        data = STORY_SIGNER.loads(token)
        url = data.get("url", "")

        if not (
            isinstance(data, dict)
            and data.get("id") == article_id
            and isinstance(url, str)
            and len(url) <= 2500
            and url.startswith("https://")
            and hashlib.sha256(
                url.encode()
            ).hexdigest()[:20] == article_id
        ):
            return False

    except (BadSignature, ValueError, TypeError, AttributeError):
        return False

    now = time.time()

    with LOCK:
        KNOWN_URLS[article_id] = (url, now)
        FEED_META.setdefault(article_id, {
            "title": str(data.get("title", ""))[:350],
            "source": str(data.get("source", ""))[:120],
            "image": data.get("image"),
            "images": (
                [data["image"]]
                if isinstance(data.get("image"), str)
                else []
            ),
            "description": str(data.get("description", ""))[:600],
            "t": now,
        })

    return True


class TTLCache:
    """Small thread-safe LRU cache with per-entry expiry, so memory stays bounded."""

    def __init__(self, max_items=300, ttl=3600):
        self.max_items, self.ttl = max_items, ttl
        self._data = OrderedDict()
        self._lock = threading.Lock()

    def get(self, key):
        with self._lock:
            hit = self._data.get(key)
            if hit is None:
                return None
            expires, value = hit
            if expires < time.time():
                self._data.pop(key, None)
                return None
            self._data.move_to_end(key)
            return value

    def set(self, key, value, ttl=None):
        with self._lock:
            self._data[key] = (time.time() + (ttl if ttl is not None else self.ttl), value)
            self._data.move_to_end(key)
            while len(self._data) > self.max_items:
                self._data.popitem(last=False)

    def pop(self, key):
        with self._lock:
            self._data.pop(key, None)

    def clear(self):
        with self._lock:
            self._data.clear()


ANALYSIS_CACHE = TTLCache(300)   # publisher page analysis (text, metadata, image candidates)
ARTICLE_CACHE = TTLCache(500)    # finished Quick Read payloads
HINDI_CACHE = TTLCache(max_items=200, ttl=3600)
FEMALE_AUDIO_CACHE = TTLCache(max_items=60, ttl=3600)
# Free public translation providers can throttle or fail; do not make new requests on every click.
TRANSLATION_PROVIDER_LOCK = threading.Lock()
TRANSLATION_COOLDOWNS = {"Google": 0.0, "MyMemory": 0.0}
IMAGE_CACHE = TTLCache(250)      # {"data": bytes|None, "mime": str|None}
RESOLVE_CACHE = TTLCache(1000, ttl=86400)   # Google link -> publisher URL (or "" for failures)
ROBOTS_CACHE = TTLCache(300, ttl=3600)


def id_lock(kind, ident):
    """One lock per (kind, article) so concurrent requests share a single fetch."""
    with LOCK:
        return _ID_LOCKS.setdefault((kind, ident), threading.Lock())


# ---------------------------------------------------------------------------------------------
# Safe outgoing HTTP
# ---------------------------------------------------------------------------------------------
class FetchBlocked(ValueError):
    """The publisher refused access (paywall, login, bot block or rate limit). Never bypassed."""

    def __init__(self, status):
        super().__init__(f"Access refused by remote server (HTTP {status})")
        self.status = status


def safe_public_url(url):
    """Limit server-side requests to public HTTPS destinations."""
    parsed = urlparse(url)
    try:
        port = parsed.port
    except ValueError:
        return False
    if parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password or port not in (None, 443):
        return False
    host = parsed.hostname.lower().rstrip('.')
    if host in ("localhost",) or host.endswith((".local", ".internal")):
        return False
    try:
        addresses = socket.getaddrinfo(host, 443, type=socket.SOCK_STREAM)
        return bool(addresses) and all(ipaddress.ip_address(a[4][0]).is_global for a in addresses)
    except (socket.gaierror, ValueError, OSError):
        return False


def host_is_blocked(host):
    with LOCK:
        until = HOST_BLOCKED.get(host)
        if until and until > time.time():
            return True
        HOST_BLOCKED.pop(host, None)
        return False


def block_host(host, retry_after=None):
    try:
        seconds = int(retry_after)
    except (TypeError, ValueError):
        seconds = 900
    with LOCK:
        HOST_BLOCKED[host] = time.time() + min(max(seconds, 60), 3600)


def _type_allowed(header, accept):
    if not accept or not header:
        return True
    kind = header.split(";", 1)[0].strip().lower()
    return kind == "application/octet-stream" or kind.startswith(tuple(accept))


def safe_get(url, timeout=9, limit=1_500_000, accept=None, track_host=False):
    """Bound response size and check every redirect, including CDN redirects.

    ``accept`` restricts Content-Type prefixes. With ``track_host`` an HTTP 429 puts the host on
    a cool-off list (honouring Retry-After) and later calls fail fast instead of hammering it.
    """
    current = url
    for _ in range(5):
        if not safe_public_url(current):
            raise ValueError("Unsafe or unsupported article URL")
        host = urlparse(current).hostname.lower()
        if track_host and host_is_blocked(host):
            raise FetchBlocked(429)
        with requests.get(current, headers=HEADERS, timeout=timeout, allow_redirects=False, stream=True) as response:
            if response.status_code in (301, 302, 303, 307, 308):
                target = response.headers.get("Location")
                if not target:
                    raise ValueError("Incomplete redirect")
                current = urljoin(current, target)
                continue
            if response.status_code in BLOCKED_STATUS:
                if track_host and response.status_code == 429:
                    block_host(host, response.headers.get("Retry-After"))
                raise FetchBlocked(response.status_code)
            response.raise_for_status()
            if not _type_allowed(response.headers.get("Content-Type"), accept):
                raise ValueError("Unexpected content type")
            content = bytearray()
            for chunk in response.iter_content(chunk_size=32768):
                content.extend(chunk)
                if len(content) > limit:
                    raise ValueError("Remote document too large")
            return bytes(content), current
    raise ValueError("Too many redirects")


def robots_allows(url):
    """Honour robots.txt for publisher pages. A missing/unreadable robots.txt means allowed."""
    parsed = urlparse(url)
    origin = f"{parsed.scheme}://{parsed.netloc}"
    rules = ROBOTS_CACHE.get(origin)
    if rules is None:
        rules = RobotFileParser()
        try:
            body, _ = safe_get(origin + "/robots.txt", timeout=5, limit=300_000)
            rules.parse(body.decode("utf-8", "replace").splitlines())
            ROBOTS_CACHE.set(origin, rules)
        except (requests.RequestException, ValueError, UnicodeError):
            rules = RobotFileParser()
            rules.parse([])
            ROBOTS_CACHE.set(origin, rules, ttl=300)
    return rules.can_fetch(ROBOT_TOKEN, url)


# ---------------------------------------------------------------------------------------------
# Feed parsing
# ---------------------------------------------------------------------------------------------
def strip_markup(raw):
    return BeautifulSoup(raw or "", "html.parser").get_text(" ", strip=True)


def source_name(entry):
    src = entry.get("source") or {}
    if src.get("title"):
        return strip_markup(src.get("title"))
    title = strip_markup(entry.get("title", ""))
    return title.rsplit(" - ", 1)[-1] if " - " in title else "News source"


def normalized_date(entry):
    published = entry.get("published_parsed") or entry.get("updated_parsed")
    if published:
        return datetime(*published[:6], tzinfo=timezone.utc).isoformat()
    return None


def feed_url(category, query):
    if query:
        return f"{RSS_ROOT}/search?q={quote_plus(query)}&hl=en-IN&gl=IN&ceid=IN:en"
    if category == "top":
        return f"{RSS_ROOT}?hl=en-IN&gl=IN&ceid=IN:en"
    return f"{RSS_ROOT}/headlines/section/topic/{CATEGORIES[category]}?hl=en-IN&gl=IN&ceid=IN:en"


def is_branding_image(url):
    """Reject aggregator/provider icons and image assets that are not story photos."""
    if not url or not isinstance(url, str):
        return True
    parsed = urlparse(url)
    if parsed.scheme != "https" or not parsed.hostname:
        return True
    host = parsed.hostname.lower()
    path = (parsed.path + "?" + parsed.query).lower()
    # Google News uses its own logo as og:image, never a news thumbnail.
    if host in ("news.google.com", "google.com", "www.google.com", "ssl.gstatic.com", "www.gstatic.com") or host.endswith(".gstatic.com"):
        return True
    # Content paths that identify generic brand/logo assets rather than pictures.
    return bool(re.search(r"(?:^|[/_.-])(logo|favicon|sprite|icon|avatar|placeholder|default-image|google-news)(?:[/_.?&=-]|$)", path))


def normalize_image_url(url, base_url=""):
    """Resolve relative / protocol-relative URLs and upgrade http to https. None if unusable."""
    if not url or not isinstance(url, str):
        return None
    url = url.strip()
    if not url or url.startswith(("data:", "blob:", "javascript:")) or len(url) > 2048:
        return None
    try:
        absolute = urljoin(base_url, url) if base_url else url
        parsed = urlparse(absolute)
    except ValueError:
        return None
    if parsed.scheme == "http":
        absolute = "https" + absolute[4:]
        parsed = urlparse(absolute)
    if parsed.scheme != "https" or not parsed.hostname:
        return None
    return absolute


_IMAGE_EXT = re.compile(r"\.(?:jpe?g|png|webp|gif)(?:$|[?#])", re.I)
_VIDEO_EXT = re.compile(r"\.(?:mp4|m4v|mov|webm|mp3|m4a|ogg|m3u8)(?:$|[?#])", re.I)


def _media_is_image(media):
    kind = str(media.get("type") or "").lower()
    medium = str(media.get("medium") or "").lower()
    url = str(media.get("url") or media.get("href") or "")
    if kind.startswith("image/") or medium == "image":
        return True
    if kind.startswith(("video/", "audio/")) or medium in ("video", "audio", "document", "executable") or _VIDEO_EXT.search(url):
        return False
    return True  # untyped media:thumbnail / enclosure: judged later by the actual bytes


def image_candidates_from_entry(entry, base_url=""):
    """Every plausible image URL an RSS item provides, best first, absolute and de-duplicated."""
    raw = []
    for media in entry.get("media_thumbnail") or []:
        if isinstance(media, dict) and _media_is_image(media):
            raw.append(media.get("url"))
    for media in entry.get("media_content") or []:
        if isinstance(media, dict) and _media_is_image(media):
            raw.append(media.get("url"))
    for enclosure in entry.get("enclosures") or []:
        if isinstance(enclosure, dict) and _media_is_image(enclosure):
            kind = str(enclosure.get("type") or "").lower()
            href = enclosure.get("href") or enclosure.get("url") or ""
            if kind.startswith("image/") or _IMAGE_EXT.search(href):
                raw.append(href)
    for link in entry.get("links") or []:
        if isinstance(link, dict) and link.get("rel") == "enclosure" and str(link.get("type") or "").startswith("image/"):
            raw.append(link.get("href"))
    markup = [c.get("value", "") for c in (entry.get("content") or []) if isinstance(c, dict)] + [entry.get("summary", "")]
    for html in markup:
        tag = BeautifulSoup(html or "", "html.parser").find("img", src=True)
        if tag:
            raw.append(tag["src"])
    seen, result = set(), []
    for url in raw:
        absolute = normalize_image_url(url, base_url)
        if absolute and absolute not in seen and not is_branding_image(absolute):
            seen.add(absolute)
            result.append(absolute)
    return result


def publisher_link_from_summary(raw, google_link):
    """RSS descriptions sometimes contain direct publisher article links."""
    page = BeautifulSoup(raw or "", "html.parser")
    for a in page.find_all("a", href=True):
        link = a["href"]
        parsed = urlparse(link)
        if parsed.scheme == "https" and parsed.hostname and not parsed.hostname.lower().endswith(("google.com", "googleusercontent.com", "gstatic.com")) and link != google_link:
            return link
    return None


def _norm(text):
    return re.sub(r"[^a-z0-9]+", " ", (text or "").lower()).strip()


def meaningful_description(description, title="", source=""):
    """True only for real descriptive text, not a repeated headline, link list or source name.

    Google News RSS descriptions are ``<a>Headline</a> <font>Publisher</font>``; those must never
    be presented as an article description (that would be a headline-only 'summary').
    """
    text = re.sub(r"\s+", " ", description or "").strip()
    if len(text) < 60 or len(text.split()) < 10 or "google news" in text.lower():
        return False
    nd, nt, ns = _norm(text), _norm(title), _norm(source)
    if nt:
        probe = nd[: len(nt) + len(ns) + 8]
        if difflib.SequenceMatcher(None, nt, probe).ratio() > 0.8:
            return False
        if nt in nd and len(nd) < len(nt) + len(ns) + 60:
            return False
    return True


def parse_feed(content, category):
    feed = feedparser.parse(content)
    items = []
    now = time.time()
    for entry in feed.entries[:70]:
        link = entry.get("link", "")
        if not link.startswith("https://"):
            continue
        title = strip_markup(entry.get("title", "Untitled"))
        source = source_name(entry)
        if title.endswith(" - " + source):
            title = title[:-(len(source) + 3)]
        if not title:
            continue
        ident = hashlib.sha256(link.encode()).hexdigest()[:20]
        full_description = strip_markup(entry.get("summary", ""))
        real = meaningful_description(full_description, title, source)
        if real:
            description = full_description if len(full_description) <= 260 else full_description[:257].rsplit(" ", 1)[0] + "…"
        else:
            # RSS descriptions are often just links and source names; don't pass that off as a summary.
            description = "Open this story for a short summary and its original source."
        images = image_candidates_from_entry(entry, link)
        image = images[0] if images else None
        publisher_url = publisher_link_from_summary(entry.get("summary", ""), link)
        if publisher_url:
            PUBLISHER_LINKS[ident] = (publisher_url, now)
        card = {"id": ident, "title": title, "source": source, "url": link, "published": normalized_date(entry), "description": description, "category": category, "image": image}
        FEED_META[ident] = {"title": title, "source": source, "image": image, "images": images,
                            "description": full_description[:1500] if real else "", "t": now, "item": card}
        items.append(card)
    with LOCK:
        for item in items:
            KNOWN_URLS[item["id"]] = (item["url"], now)
        # keep bounded, and expire old links
        for key, (_, t) in list(KNOWN_URLS.items()):
            if now - t > 86400:
                for store in (KNOWN_URLS, PUBLISHER_LINKS, FEED_META):
                    store.pop(key, None)
                for kind in ("analysis", "image"):
                    _ID_LOCKS.pop((kind, key), None)
    return items


# ---------------------------------------------------------------------------------------------
# Google News link resolution
# ---------------------------------------------------------------------------------------------
_GNEWS_PATH = re.compile(r"^/(?:rss/)?(?:articles|read)/([A-Za-z0-9_-]+)/?$")


def google_token(url):
    """The encoded article token of a Google News article link, else None."""
    parsed = urlparse(url or "")
    if (parsed.hostname or "").lower() != "news.google.com":
        return None
    match = _GNEWS_PATH.match(parsed.path)
    return match.group(1) if match else None


def decode_google_token_offline(token):
    """Legacy Google News tokens embed the publisher URL as a protobuf string. No network needed."""
    try:
        raw = base64.urlsafe_b64decode(token + "=" * (-len(token) % 4))
    except (ValueError, binascii.Error):
        return None
    if raw.startswith(b"\x08\x13\x22"):
        raw = raw[3:]
    if raw.endswith(b"\xd2\x01\x00"):
        raw = raw[:-3]
    if not raw:
        return None
    length, start = raw[0], 1
    if length & 0x80:                       # two-byte protobuf varint
        if len(raw) < 2:
            return None
        length, start = (raw[0] & 0x7F) | (raw[1] << 7), 2
    value = raw[start:start + length].decode("utf-8", "ignore").strip()
    if value.startswith("http://"):
        value = "https://" + value[7:]
    return value if value.startswith("https://") and " " not in value else None


def parse_batchexecute(text):
    """Pull the publisher URL out of Google's batchexecute reply (tolerates length prefixes)."""
    start = (text or "").find("[")
    if start < 0:
        return None
    try:
        data, _ = json.JSONDecoder().raw_decode(text[start:])
        for row in data:
            if isinstance(row, list) and len(row) > 2 and row[0] == "wrb.fr" and isinstance(row[2], str):
                url = json.loads(row[2])[1]
                if isinstance(url, str) and url.startswith(("https://", "http://")):
                    return url
    except (ValueError, TypeError, IndexError, KeyError):
        pass
    return None


def decode_google_token_online(token):
    """Newer tokens must be exchanged through Google's own redirect service (what a browser does).

    This is Google's undocumented front-end endpoint: it may change or rate-limit at any time, in
    which case we simply fall back to the RSS description / unavailable state.
    """
    if not RESOLVE_GOOGLE_LINKS or host_is_blocked("news.google.com:resolve"):
        return None
    if not GOOGLE_SLOTS.acquire(timeout=10):
        return None
    try:
        params = None
        for page in (f"https://news.google.com/rss/articles/{token}", f"https://news.google.com/articles/{token}"):
            try:
                html, final = safe_get(page, timeout=8, limit=1_000_000, accept=HTML_TYPES)
            except FetchBlocked as exc:
                if exc.status == 429:
                    block_host("news.google.com:resolve")
                return None
            except (requests.RequestException, ValueError, UnicodeError):
                continue
            if (urlparse(final).hostname or "").lower() not in GOOGLE_HOSTS:
                return final                    # Google redirected straight to the publisher
            div = BeautifulSoup(html, "html.parser").select_one("c-wiz > div[jscontroller]")
            if div and div.get("data-n-a-sg") and div.get("data-n-a-ts"):
                params = (div["data-n-a-sg"], div["data-n-a-ts"])
                break
        if not params:
            return None
        signature, timestamp = params
        inner = json.dumps(["garturlreq", [["X", "X", ["X", "X"], None, None, 1, 1, "US:en", None, 1, None, None, None, None, None, 0, 1], "X", "X", 1, [1, 1, 1], 1, 1, None, 0, 0, None, 0], token, int(timestamp), signature], separators=(",", ":"))
        body = "f.req=" + quote(json.dumps([[["Fbv4je", inner]]], separators=(",", ":")))
        reply = requests.post("https://news.google.com/_/DotsSplashUi/data/batchexecute",
                              headers={**HEADERS, "Content-Type": "application/x-www-form-urlencoded;charset=UTF-8"},
                              data=body, timeout=8, allow_redirects=False)
        if reply.status_code == 429:
            block_host("news.google.com:resolve", reply.headers.get("Retry-After"))
            return None
        reply.raise_for_status()
        return parse_batchexecute(reply.text)
    except (requests.RequestException, ValueError, UnicodeError, KeyError) as exc:
        app.logger.info("Google link resolution failed: %s", exc)
        return None
    finally:
        GOOGLE_SLOTS.release()



def resolve_google_url(link):
    token = google_token(link)

    if not token:
        return None

    cached = RESOLVE_CACHE.get(token)

    if cached is not None:
        return cached or None

    # First try legacy offline decoding.
    url = decode_google_token_offline(token)

    if not url and RESOLVE_GOOGLE_LINKS:
        # Try the updated Google News decoder.
        try:
            url = decode_google_news(
                link,
                timeout=12.0
            )
        except Exception as exc:
            app.logger.warning(
                "TBA Google decoder failed: %s",
                type(exc).__name__
            )

        # Retain TBA's existing resolver as fallback.
        if not url:
            url = decode_google_token_online(token)

    if url and url.startswith("http://"):
        url = "https://" + url[7:]

    # Only accept public HTTPS publisher URLs.
    if (
        not url
        or _hostname(url) in GOOGLE_HOSTS
        or not safe_public_url(url)
    ):
        url = None

    app.logger.info(
        "TBA Google News resolution: %s",
        "success" if url else "unresolved"
    )

    RESOLVE_CACHE.set(
        token,
        url or "",
        ttl=86400 if url else 120
    )

    return url



# ---------------------------------------------------------------------------------------------
# Publisher page extraction
# ---------------------------------------------------------------------------------------------
NOISE_TAGS = ["script", "style", "noscript", "svg", "iframe", "form", "nav", "footer", "aside", "header", "button", "template", "dialog"]
NOISE_TOKENS = re.compile(r"^(?:comments?|cookies?|consent|gdpr|banner|adverts?|advertisement|ads?|adslot|sponsor(?:ed)?|promo|newsletter|subscribe|subscription|signup|share|sharing|social|related|recommended?|trending|popular|outbrain|taboola|breadcrumbs?|sidebar|widget|modal|popup|paywall|byline|tags?|author-box|toolbar|most-read|read-more|more-stories)$", re.I)
BOILERPLATE = re.compile(r"all rights reserved|subscribe to|sign up for|read more:|also read|click here|follow us on|advertisement|we use cookies|cookie policy|copyright ©|©\s?\d{4}|download the .{0,30} app|join our (?:whatsapp|telegram)|for more (?:news|updates)|terms (?:of use|and conditions)|privacy policy|story continues below|continue reading|sign in to", re.I)
CONTAINERS = ('[itemprop="articleBody"]', "article", '[class*="article-body"]', '[class*="articleBody"]', '[class*="story-body"]', '[class*="post-content"]', '[class*="entry-content"]', '[class*="article-content"]', '[class*="article__body"]', "main", "body")


def _classes(tag):
    value = tag.get("class") or []
    value = value.split() if isinstance(value, str) else list(value)
    return value + [tag.get("id") or ""]


def strip_noise(soup):
    for tag in soup(NOISE_TAGS):
        tag.decompose()
    for tag in soup.find_all(True):
        if tag.decomposed:          # a parent was already removed
            continue
        if tag.name in ("html", "body", "article", "main") or tag.get("itemprop") == "articleBody":
            continue
        tokens = [t for cls in _classes(tag) for t in re.split(r"[\s_]+", cls) if t]
        # also test the whole dashed class ("most-read") and each dash-separated piece ("share-bar")
        if any(NOISE_TOKENS.match(t) or any(NOISE_TOKENS.match(p) for p in t.split("-")) for t in tokens) and len(tag.get_text(" ", strip=True)) < 1500:
            tag.decompose()


def _paragraphs(root):
    result = []
    for p in root.find_all("p"):
        text = re.sub(r"\s+", " ", p.get_text(" ", strip=True))
        if len(text) < 55 or BOILERPLATE.search(text):
            continue
        link_text = sum(len(a.get_text(" ", strip=True)) for a in p.find_all("a"))
        if link_text / max(len(text), 1) > 0.6:
            continue
        if not result or result[-1] != text:
            result.append(text)
    return result


def article_json_ld(page):
    """Yield (articleBody, description, images, free_to_read) from schema.org JSON-LD blocks."""
    def walk(obj):
        if isinstance(obj, dict):
            yield obj
            for value in obj.values():
                yield from walk(value)
        elif isinstance(obj, list):
            for value in obj:
                yield from walk(value)
    for tag in page.select('script[type="application/ld+json"]'):
        try:
            data = json.loads(tag.string or tag.get_text())
        except (ValueError, TypeError):
            continue
        for node in walk(data):
            if any(k in node for k in ("articleBody", "description", "image", "isAccessibleForFree")):
                yield node


def article_body_from_jsonld(page):
    """Read publisher-provided schema.org articleBody when available."""
    for node in article_json_ld(page):
        body = node.get("articleBody")
        if isinstance(body, str) and len(body.strip()) >= 180:
            yield strip_markup(body)


def _is_article_node(node):
    types = node.get("@type")
    types = types if isinstance(types, list) else [types]
    return any(isinstance(t, str) and re.search(r"Article|Posting|Report", t) for t in types)


def _jsonld_images(node):
    if not _is_article_node(node):
        return
    value = node.get("image")
    for item in value if isinstance(value, list) else [value]:
        if isinstance(item, str):
            yield item
        elif isinstance(item, dict) and isinstance(item.get("url"), str):
            yield item["url"]


def readable_metadata(html):
    """Retrieve only genuine description metadata; never invent a news summary."""
    page = html if isinstance(html, BeautifulSoup) else BeautifulSoup(html, "html.parser")
    values = []
    for attrs in ({"property": "og:description"}, {"name": "description"}, {"name": "twitter:description"}):
        tag = page.find("meta", attrs=attrs)
        if tag and tag.get("content"):
            values.append(strip_markup(tag["content"]).strip())
    values += [strip_markup(n["description"]).strip() for n in article_json_ld(page) if isinstance(n.get("description"), str)]
    for value in values:
        if len(value) >= 75 and "google news" not in value.lower():
            return value[:850]
    return ""


def extract_article(html, base_url="https://news.google.com/"):
    """Return {title, text, images, description, partial} from a publisher page."""
    soup = BeautifulSoup(html, "html.parser")
    title = soup.title.get_text(" ", strip=True) if soup.title else ""
    og_title = soup.find("meta", attrs={"property": "og:title"})
    if og_title and og_title.get("content"):
        title = og_title["content"].strip()
    description = readable_metadata(soup)
    raw_images = []
    for attrs in ({"property": "og:image:secure_url"}, {"property": "og:image"}, {"name": "twitter:image"}, {"name": "twitter:image:src"}):
        tag = soup.find("meta", attrs=attrs)
        if tag and tag.get("content"):
            raw_images.append(tag["content"])
    link = soup.find("link", rel=lambda r: r and "image_src" in (r if isinstance(r, list) else [r]))
    if link and link.get("href"):
        raw_images.append(link["href"])
    structured_body, partial = "", False
    for node in article_json_ld(soup):
        raw_images.extend(_jsonld_images(node))
        if str(node.get("isAccessibleForFree", "")).lower() == "false":
            partial = True
    structured_body = next(article_body_from_jsonld(soup), "")
    images, seen = [], set()
    for raw in raw_images:
        absolute = normalize_image_url(raw, base_url)
        if absolute and absolute not in seen and not is_branding_image(absolute):
            seen.add(absolute)
            images.append(absolute)
    strip_noise(soup)
    best = []
    for selector in CONTAINERS:
        # Containers are ordered most- to least-specific; a broader one only wins by holding far more text.
        for root in soup.select(selector)[:6]:
            paragraphs = _paragraphs(root)
            if sum(map(len, paragraphs)) > sum(map(len, best)) * 1.5:
                best = paragraphs
        if selector == '[itemprop="articleBody"]' and sum(map(len, best)) >= 400:
            break
    html_text = " ".join(best)
    # Avoid summarizing page furniture on sites where article extraction did not work.
    text = (structured_body if len(structured_body) > len(html_text) else html_text)[:30000]
    return {"title": title, "text": text, "images": images, "description": description, "partial": partial}


def extract_text(html, base_url="https://news.google.com/"):
    """Backward-compatible wrapper: (title, first image, text)."""
    result = extract_article(html, base_url)
    return result["title"], (result["images"][0] if result["images"] else None), result["text"]


# ---------------------------------------------------------------------------------------------
# Quick Read: extractive overview (every sentence shown is a sentence from the article)
# ---------------------------------------------------------------------------------------------
_ABBREV = re.compile(r"\b(Mr|Mrs|Ms|Dr|Prof|Sr|Jr|St|No|Rs|Inc|Ltd|Co|Corp|vs|etc|Gen|Sen|Rep|Gov|Lt|Col|Capt|Sgt|Hon|Mt|Jan|Feb|Mar|Apr|Jun|Jul|Aug|Sep|Sept|Oct|Nov|Dec|Fig|approx)\.")
_DOTTED = re.compile(r"\b(?:[A-Za-z]\.){2,}")
_INITIAL = re.compile(r"\b([A-Z])\.(?=\s[A-Z])")
_SPLIT = re.compile(r"(?:(?<=[.!?])|(?<=[.!?][\"”’']))\s+(?=[\"'“‘(]?[A-Z0-9])")
_DOT = "\u2024"


def split_sentences(text):
    text = re.sub(r"\s+", " ", text or "").strip()
    text = _ABBREV.sub(lambda m: m.group(1) + _DOT, text)
    text = _DOTTED.sub(lambda m: m.group(0).replace(".", _DOT), text)
    text = _INITIAL.sub(lambda m: m.group(1) + _DOT, text)
    sentences = []
    for part in _SPLIT.split(text):
        part = part.replace(_DOT, ".").strip()
        words = len(part.split())
        if len(part) >= 35 and 6 <= words <= 80 and not BOILERPLATE.search(part) and part not in sentences:
            sentences.append(part)
    return sentences


def _tokens(sentence):
    return [w.lower() for w in re.findall(r"[A-Za-z]{3,}", sentence) if w.lower() not in STOPWORDS]


def rank_sentences(sentences):
    weights = Counter(w for s in sentences for w in _tokens(s))
    scores = []
    for idx, sentence in enumerate(sentences):
        tokens = _tokens(sentence)
        score = sum(weights[w] for w in tokens) / (len(tokens) ** .65 if tokens else 1)
        if idx < 3:
            score *= 1.12
        if re.search(r"\d", sentence):
            score *= 1.06
        if sentence[:1] in "\"'“‘":
            score *= .85            # opening quotes are opinion more often than fact
        scores.append(score)
    return scores


def summarize(text, max_sentences=8):
    """Deterministic extractive (not generative) summary of extracted article sentences."""
    sentences = split_sentences(text)[:100]
    if not sentences:
        return ""
    if len(sentences) <= max_sentences:
        return " ".join(sentences)[:1900]
    scores = rank_sentences(sentences)
    top = sorted(sorted(range(len(sentences)), key=lambda i: scores[i], reverse=True)[:max_sentences])
    return " ".join(sentences[i] for i in top)[:1900]


_BACKGROUND = re.compile(r"\b(?:previously|earlier|last (?:year|month|week|season)|in (?:19|20)\d{2}|had been|has been|since (?:19|20)\d{2}|years ago|so far|until now|history|background)\b", re.I)
_NEXT = re.compile(r"\b(?:expected to|is set to|are set to|scheduled (?:to|for)|plans? to|will be (?:held|announced|released|heard|taken)|next (?:week|month|year|hearing|round|match|phase)|later this|yet to|awaits?|pending|likely to)\b", re.I)
_MONTH = "January|February|March|April|May|June|July|August|September|October|November|December"
_WEEKDAY = "Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday"
_DATE_RE = re.compile(rf"\b(?:(?:{_WEEKDAY})|(?:{_MONTH}|Jan|Feb|Mar|Apr|Jun|Jul|Aug|Sept?|Oct|Nov|Dec)\.? \d{{1,2}}(?:, \d{{4}})?|\d{{1,2}} (?:{_MONTH})(?: \d{{4}})?|(?:{_MONTH}) \d{{4}}|(?:19|20)\d{{2}})\b")
_FIGURE_RE = re.compile(r"(?:(?:₹|Rs\.?|INR|US\$|\$|€|£)\s?\d[\d,]*(?:\.\d+)?(?:\s?(?:crore|lakh|thousand|million|billion|trillion|bn|mn))?)|(?:\b\d[\d,]*(?:\.\d+)?\s?(?:%|per ?cent|crore|lakh|thousand|million|billion|trillion|km|kg|MW|GW|runs|wickets|goals|points|people|deaths|seats|years?))", re.I)
_CAP = r"[A-Z][A-Za-z'’\-]*"
_NAME_RE = re.compile(rf"\b{_CAP}(?:\s+(?:(?:of|de|van|von|al|bin|la|da)\s+)?{_CAP}){{0,3}}")
_NOT_NAMES = set("The A An And But Or So Yet If When While Although Though After Before Since Because However Meanwhile Earlier Later Also Still Then Now Here There This That These Those He She It They We You His Her Its Their Our In On At As By For From With Without Under Over Between During According Speaking Asked Officials Police Sources Reuters Mr Mrs Ms Dr It's Said Says Monday Tuesday Wednesday Thursday Friday Saturday Sunday January February March April May June July August September October November December Meanwhile Both Some Many Most More One Two Three First Second Last Next".split())


def _unique(values, limit):
    seen, out = set(), []
    for value in values:
        key = value.lower()
        if key not in seen:
            seen.add(key)
            out.append(value)
        if len(out) == limit:
            break
    return out


def extract_details(text):
    """Names, figures and dates copied verbatim from the article text (no classification guessed)."""
    counts, mid = Counter(), Counter()
    for match in _NAME_RE.finditer(text):
        words = match.group(0).split()
        while words and words[0] in _NOT_NAMES:
            words.pop(0)
        while words and words[-1] in _NOT_NAMES:
            words.pop()
        if not words:
            continue
        phrase = " ".join(words)
        counts[phrase] += 1
        begin = match.start()
        if begin and not re.search(r"[.!?][\"”’']?\s$", text[max(0, begin - 3):begin]):
            mid[phrase] += 1
    names = []
    for phrase, n in counts.most_common():
        single = " " not in phrase
        if (single and (mid[phrase] < 2 or len(phrase) < 3)) or (not single and not (mid[phrase] >= 1 or n >= 2)):
            continue
        names.append(phrase)
    names = [n for n in names if not any(n != other and n in other for other in names)]
    return {"names": names[:8],
            "figures": _unique([m.group(0).strip() for m in _FIGURE_RE.finditer(text)], 6),
            "dates": _unique([m.group(0) for m in _DATE_RE.finditer(text)], 4)}


def build_overview(text):
    """Structured, length-adaptive overview built only from sentences found in ``text``."""
    sentences = split_sentences(text)[:120]
    if not sentences:
        return None
    total_words = len(text.split())
    budget = min(300, max(25, int(total_words * 0.30)))
    wc = lambda s: len(s.split())
    scores = rank_sentences(sentences)
    chosen = [0]
    if wc(sentences[0]) < 18 and len(sentences) > 1 and budget >= 45:
        chosen.append(1)
    used = sum(wc(sentences[i]) for i in chosen)
    background, upcoming = [], []
    if total_words >= 350:
        order = sorted(range(len(sentences)), key=lambda i: scores[i], reverse=True)
        for label, pattern, bucket in (("background", _BACKGROUND, background), ("next", _NEXT, upcoming)):
            pick = next((i for i in order if i not in chosen and i > 1 and pattern.search(sentences[i]) and used + wc(sentences[i]) <= 300), None)
            if pick is not None:
                bucket.append(pick)
                used += wc(sentences[pick])
    reserved = set(chosen) | set(background) | set(upcoming)
    points, hard_cap = [], min(320, budget + 25)
    if budget >= 45:                         # very short articles get just the lead sentence
        for i in sorted((i for i in range(len(sentences)) if i not in reserved), key=lambda i: scores[i], reverse=True):
            if used >= budget or len(points) >= 7:
                break
            if used + wc(sentences[i]) <= hard_cap:
                points.append(i)
                used += wc(sentences[i])
    intro = " ".join(sentences[i] for i in chosen)
    payload = {"intro": intro,
               "points": [sentences[i] for i in sorted(points)],
               "background": [sentences[i] for i in background],
               "next": [sentences[i] for i in upcoming],
               "details": extract_details(text),
               "source_words": total_words}
    payload["summary_words"] = sum(wc(s) for s in [intro, *payload["points"], *payload["background"], *payload["next"]])
    payload["summary"] = "\n\n".join([intro, *payload["points"], *payload["background"], *payload["next"]])
    return payload


# ---------------------------------------------------------------------------------------------
# Analysis of one article (shared by the image and Quick Read endpoints)
# ---------------------------------------------------------------------------------------------
def _hostname(url):
    return (urlparse(url or "").hostname or "").lower()


def _analyze(article_id, link):
    result = {"status": "unresolved", "publisher_url": None, "final_url": None, "text": "", "title": "",
              "images": [], "description": "", "partial": False, "fetched_at": time.time()}
    with LOCK:
        direct = PUBLISHER_LINKS.get(article_id)
    if direct:
        target = direct[0]
    elif google_token(link):
        target = resolve_google_url(link)
    elif _hostname(link) in GOOGLE_HOSTS:
        target = None
    else:
        target = link
    result["publisher_url"] = target
    if not target:
        return result
    try:
        if not robots_allows(target):
            result["status"] = "robots"
            return result
        html, final = safe_get(target, timeout=10, limit=2_000_000, accept=HTML_TYPES, track_host=True)
    except FetchBlocked as exc:
        app.logger.info("Publisher refused %s: HTTP %s", target, exc.status)
        result["status"] = "blocked"
        return result
    except (requests.RequestException, ValueError, UnicodeError) as exc:
        app.logger.info("Article extraction unavailable at %s: %s", target, exc)
        result["status"] = "error"
        return result
    if _hostname(final) in GOOGLE_HOSTS:
        return result
    extracted = extract_article(html, final)
    result.update(final_url=final, title=extracted["title"], text=extracted["text"], images=extracted["images"],
                  description=extracted["description"], partial=extracted["partial"])
    result["status"] = "ok" if len(extracted["text"]) >= MIN_ARTICLE_CHARS else "no_text"
    return result


def analyze_article(article_id, force=False):
    """Fetch and analyse the publisher page once; cached, de-duplicated, never raises."""
    def reusable(cached):
        if not cached:
            return False
        return cached["status"] == "ok" or not (force and time.time() - cached["fetched_at"] > RETRY_COOLDOWN)

    cached = ANALYSIS_CACHE.get(article_id)
    if reusable(cached):
        return cached
    with id_lock("analysis", article_id):
        cached = ANALYSIS_CACHE.get(article_id)
        if reusable(cached):
            return cached
        with LOCK:
            known = KNOWN_URLS.get(article_id)
        if not known:
            return {"status": "expired", "fetched_at": time.time()}
        if not ANALYSIS_SLOTS.acquire(timeout=25):
            return {"status": "busy", "fetched_at": time.time()}
        try:
            result = _analyze(article_id, known[0])
        finally:
            ANALYSIS_SLOTS.release()
        ANALYSIS_CACHE.set(article_id, result, ttl={"ok": 3600, "blocked": 900, "robots": 3600}.get(result["status"], 600))
        return result


UNAVAILABLE_MESSAGES = {
    "robots": "The publisher asks automated tools not to fetch this page, so TBA did not access it.",
    "blocked": "The publisher restricted access to this article (it may need a subscription or sign-in), so the full text could not be read.",
    "unresolved": "TBA could not find the publisher's page behind this Google News link.",
    "no_text": "The publisher's page did not include readable article text (it may be loaded by JavaScript or sit behind a paywall).",
    "error": "The publisher's article could not be retrieved right now.",
}


AI_REASONS = {
    "timeout": "the AI service timed out",
    "unreachable": "the AI service could not be reached",
    "rate_limited": "the AI service is rate-limited right now",
    "server_error": "the AI service reported an error",
    "busy": "too many AI requests are running",
    "bad_response": "the AI service returned an unusable answer",
    "rejected": "the AI answer contained details that could not be verified against the article",
    "cooldown": "the AI service is paused after an error",
    "auth_error": "the AI service rejected the configured credentials",
    "http_error": "the AI service returned an unexpected error",
}


def best_overview(text, title, source):
    """Hybrid summary: validated AI summary when configured, otherwise the local extractive overview.

    Returns ``(overview, ai_info)``.  ``overview`` has the same shape either way; ``ai_info`` says
    what happened so the UI can label it honestly.  An AI failure is never hidden and never replaced
    by invented text: the extractive summary of the real article text is used instead.
    """
    result = ai_summarizer.summarize(title, text, source)
    if result["status"] == "ok":
        ov = result["overview"]
        pieces = [ov["intro"], *ov["points"], *ov["background"], *ov["next"]]
        overview = {**ov, "details": extract_details(text), "source_words": len(text.split()),
                    "summary": "\n\n".join(pieces)}
        return overview, {"status": "ok", "used": True, "model": result["model"], "retryable": False}
    ai_info = {"status": result["status"], "used": False, "model": None,
               "retryable": bool(result.get("retryable")) and result["status"] in AI_REASONS}
    return build_overview(text), ai_info


def make_payload(article_id, analysis):
    """Turn an analysis into the Quick Read response using the fallback hierarchy."""
    with LOCK:
        known = KNOWN_URLS.get(article_id)
    meta = FEED_META.get(article_id) or {}
    title, source = meta.get("title", ""), meta.get("source", "")
    original = known[0] if known else ""
    page_url = analysis.get("final_url") or analysis.get("publisher_url") or original
    base = {"source_url": page_url, "original_url": original, "retryable": analysis["status"] != "robots"}
    # 1. Full extracted article text
    if analysis["status"] == "ok":
        overview, ai_info = best_overview(analysis["text"], title, source)
        if overview:
            partial = analysis.get("partial")
            notes = []
            if partial:
                notes.append("The publisher limits access to this article, so this overview covers only the freely available portion.")
            if ai_info["used"]:
                notes.append(f"AI-generated from the publisher's article text ({ai_info['model']}). Numbers, names and quotations were checked against the article; still verify with the original.")
            elif ai_info["status"] in AI_REASONS:
                notes.append(f"AI summary unavailable ({AI_REASONS[ai_info['status']]}), so this overview is built from the article's own sentences.")
            topic = ((meta.get("item") or {}).get("topic") or {}).get("label")
            return {**base, **overview, "summary_type": "partial" if partial else "article", "retryable": False,
                    "summary_method": "ai" if ai_info["used"] else "extractive",
                    "ai": ai_info, "ai_retryable": ai_info["retryable"],
                    "sentiment": analyze_sentiment(analysis["text"], "article", topic),
                    "message": " ".join(notes) or None}
    # 2. Description supplied in the RSS feed, 3. other page metadata (never a restated headline)
    for text, origin in ((meta.get("description", ""), "feed"), (analysis.get("description", ""), "page")):
        if meaningful_description(text, title, source):
            return {**base, "summary_type": "description", "intro": text, "points": [], "background": [], "next": [],
                    "details": {"names": [], "figures": [], "dates": []}, "summary": text, "description_origin": origin,
                    "message": "The full article text could not be read, so this is the publisher's own short description, not a summary of the article."}
    # 4. Honest dead end with a link to the publisher
    reason = "no_text" if analysis["status"] == "ok" else analysis["status"] if analysis["status"] in UNAVAILABLE_MESSAGES else "error"
    return {**base, "summary_type": "unavailable", "intro": "", "points": [], "background": [], "next": [],
            "details": {"names": [], "figures": [], "dates": []}, "summary": "", "reason": reason,
            "message": UNAVAILABLE_MESSAGES[reason] + " Use the button below to read the original story."}


# ---------------------------------------------------------------------------------------------
# Images
# ---------------------------------------------------------------------------------------------
def detect_image_type(content):
    """Accept only actual common web image formats, never arbitrary remote HTML/SVG."""
    if content.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    if content.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    if content.startswith((b"GIF87a", b"GIF89a")):
        return "image/gif"
    if len(content) >= 12 and content[:4] == b"RIFF" and content[8:12] == b"WEBP":
        return "image/webp"
    return None


def prepare_image(raw):
    """Validate a downloaded picture and shrink oversized ones. Returns (bytes, mime) or None."""
    detected = detect_image_type(raw)
    if not detected:
        return None
    try:
        with Image.open(BytesIO(raw)) as picture:
            width, height = picture.size
            # Logos/icons often have tiny or square dimensions. News photos
            # should have meaningful resolution and a landscape aspect.
            if width < 360 or height < 180 or not 1.15 <= width / height <= 3.5:
                return None
            if width <= 1000 or getattr(picture, "n_frames", 1) > 1:
                return raw, detected
            picture = picture.convert("RGB")
            picture.thumbnail((1000, 1000))
            out = BytesIO()
            picture.save(out, "JPEG", quality=84, optimize=True)
            return out.getvalue(), "image/jpeg"
    except (OSError, ValueError, UnidentifiedImageError, Image.DecompressionBombError):
        return None



def first_valid_image(urls, max_tries=6):
    urls = list(dict.fromkeys(urls or []))
    attempted = 0

    app.logger.info(
        "TBA IMAGE: %d candidates found", len(urls)
    )

    for url in urls:
        if attempted >= max_tries:
            break

        if is_branding_image(url):
            continue

        attempted += 1
        host = urlparse(url).hostname or "unknown"

        try:
            raw, _ = safe_get(
                url,
                timeout=9,
                limit=4_000_000,
                accept=IMAGE_TYPES
            )

            result = prepare_image(raw)

            if result:
                app.logger.info(
                    "TBA IMAGE SUCCESS: %s", host
                )
                return result

            app.logger.warning(
                "TBA IMAGE REJECTED: %s "
                "(format, dimensions or aspect ratio)",
                host
            )

        except (requests.RequestException, ValueError, UnicodeError) as exc:
            app.logger.warning(
                "TBA IMAGE FAILED: %s - %s",
                host,
                str(exc)[:180]
            )

    app.logger.warning(
        "TBA IMAGE: no image after %d attempts",
        attempted
    )
    return None

# ---------------------------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------------------------
@app.get("/")
def index():
    return render_template("index.html")



@app.get("/api/news")
def news():
    category = request.args.get("category", "top").lower().strip()
    query = request.args.get("q", "").strip()
    force = request.args.get("refresh") == "1"

    if category not in CATEGORIES:
        return jsonify(error="Unknown category"), 400

    if len(query) > 100:
        return jsonify(error="Search must be 100 characters or fewer"), 400

    key = (category, query.casefold())

    # Return cached articles, ensuring each has a signed reference.
    with LOCK:
        hit = NEWS_CACHE.get(key)

        if hit and not force and time.time() - hit[0] < TTL:
            items = hit[1]

            for item in items:
                if "story_ref" not in item:
                    item["story_ref"] = story_reference(item)

            return jsonify(
                items=items,
                updated=hit[2],
                cached=True
            )

    try:
        # Fetch latest news from Google News RSS.
        content, _ = safe_get(
            feed_url(category, query),
            timeout=12
        )

        items = parse_feed(content, category)

        # Apply existing ML/NLP enrichment.
        try:
            enrich_items(
                items,
                {
                    i["id"]: (
                        FEED_META.get(i["id"]) or {}
                    ).get("description", "")
                    for i in items
                }
            )
        except Exception as exc:
            app.logger.warning(
                "Feed enrichment failed: %s",
                type(exc).__name__
            )

        # NEW: Generate signed reference for every article.
        for item in items:
            item["story_ref"] = story_reference(item)

        updated = datetime.now(timezone.utc).isoformat()

        with LOCK:
            NEWS_CACHE[key] = (
                time.time(),
                items,
                updated
            )

        return jsonify(
            items=items,
            updated=updated,
            cached=False
        )

    except (requests.RequestException, ValueError) as exc:
        app.logger.warning(
            "RSS request failed: %s",
            exc
        )

        with LOCK:
            previous = NEWS_CACHE.get(key)

        if previous:
            items = previous[1]

            for item in items:
                if "story_ref" not in item:
                    item["story_ref"] = story_reference(item)

            return jsonify(
                items=items,
                updated=previous[2],
                cached=True,
                stale=True
            )

        return jsonify(
            error="The news feed is temporarily unavailable. Please try again."
        ), 502


@app.get("/api/article/<article_id>")
def article(article_id):
    if not re.fullmatch(r"[0-9a-f]{20}", article_id):
        return jsonify(error="Invalid article identifier"), 400
    restore_story(article_id)
    retry = request.args.get("retry") == "1"

    def retry_wanted(payload):
        """A finished summary stays; fallbacks (and AI summaries that failed transiently) may be retried."""
        return payload["summary_type"] not in ("article", "partial") or bool(payload.get("ai_retryable"))

    cached = ARTICLE_CACHE.get(article_id)
    if cached and not (retry and retry_wanted(cached)):
        return jsonify(cached)
    with id_lock("article", article_id):
        cached = ARTICLE_CACHE.get(article_id)
        if cached and not (retry and retry_wanted(cached) and time.time() - cached.get("generated_at", 0) > RETRY_COOLDOWN):
            return jsonify(cached)
        analysis = analyze_article(article_id, force=retry)
        if analysis["status"] == "expired":
            return jsonify(error="Story expired. Refresh the feed and try again."), 404
        if analysis["status"] == "busy":
            return jsonify(error="The server is busy fetching other articles. Please try again in a moment.", retryable=True), 503
        payload = make_payload(article_id, analysis)
        payload["generated_at"] = time.time()
        ttl = 3600 if payload["summary_type"] in ("article", "partial") else 600
        if payload.get("ai_retryable"):
            ttl = 300                      # transient AI failure: look again soon instead of caching the fallback for an hour
        ARTICLE_CACHE.set(article_id, payload, ttl=ttl)
        return jsonify(payload)


@app.get("/api/image/<article_id>")
def article_image(article_id):
    if not re.fullmatch(r"[0-9a-f]{20}", article_id):
        return "Invalid image id", 400

    restore_story(article_id)

    with LOCK:
        known = KNOWN_URLS.get(article_id)

    if not known:
        return "Story expired", 404

    headers = {
        "Cache-Control": "public, max-age=3600",
        "X-Content-Type-Options": "nosniff",
        "Content-Security-Policy": "default-src 'none'; sandbox"
    }

    def respond(entry):
        if entry["data"] is None:
            return (
                "No article image available",
                404,
                {"Cache-Control": "no-store"}
            )
        return Response(
            entry["data"],
            mimetype=entry["mime"],
            headers=headers
        )

    cached = IMAGE_CACHE.get(article_id)
    if cached is not None:
        return respond(cached)

    with id_lock("image", article_id):
        cached = IMAGE_CACHE.get(article_id)
        if cached is not None:
            return respond(cached)

        with LOCK:
            rss_images = list(
                (FEED_META.get(article_id) or {}).get("images") or []
            )

        app.logger.info(
            "TBA IMAGE %s: RSS candidates=%d",
            article_id,
            len(rss_images)
        )

        found = first_valid_image(rss_images)

        if not found:
            analysis = analyze_article(article_id)

          

            app.logger.warning(
                "TBA IMAGE DIAG: id=%s status=%s "
                "publisher=%s images=%d",
                article_id,
                analysis.get("status"),
                analysis.get("publisher_url"),
                len(analysis.get("images") or [])
            )

            if analysis["status"] == "busy":
                return "Server busy", 503

            found = first_valid_image(
                analysis.get("images") or []
            )

        entry = (
            {"data": found[0], "mime": found[1]}
            if found
            else {"data": None, "mime": None}
        )

        IMAGE_CACHE.set(
            article_id,
            entry,
            ttl=3600 if found else 120
        )

        return respond(entry)


def recommendation_pool():
    """Recently fetched stories (any feed, last 6 hours) as dicts for the recommender."""
    now = time.time()
    with LOCK:
        entries = [(ident, meta) for ident, meta in FEED_META.items() if now - meta.get("t", 0) < 6 * 3600 and ident in KNOWN_URLS]
    pool = []
    for ident, meta in entries:
        item = meta.get("item") or {"id": ident, "title": meta.get("title", ""), "source": meta.get("source", ""),
                                    "url": KNOWN_URLS[ident][0], "published": None, "description": "", "category": "top", "image": None}
        topic = item.get("topic") or classify_topic(item["title"], meta.get("description", ""))
        pool.append({"id": ident, "text": article_text(item["title"], meta.get("description", "")), "topic": topic, "item": item})
    return pool


@app.route("/api/recommendations/<article_id>", methods=["GET", "POST"])
def recommendations(article_id):
    """Related stories for the open article (content-based; no external API, no stored user data).

    POST body (optional): ``{"saved_titles": ["...", ...]}``, up to 10 titles of the reader's saved
    stories.  They are used for this request only to nudge the ranking and are never stored.
    """
    if not re.fullmatch(r"[0-9a-f]{20}", article_id):
        return jsonify(error="Invalid article identifier"), 400
    saved = []
    if request.method == "POST":
        body = request.get_json(silent=True)
        if body is not None and not isinstance(body, dict):
            return jsonify(error="Expected a JSON object"), 400
        titles = (body or {}).get("saved_titles", [])
        if not isinstance(titles, list):
            return jsonify(error="saved_titles must be a list of strings"), 400
        saved = [t[:300] for t in titles[:10] if isinstance(t, str)]
    pool = recommendation_pool()
    result = recommend(article_id, pool, saved, ml_config.recommendation_count(), ml_config.duplicate_threshold())
    if result["message"] == "unknown_article":
        return jsonify(error="Story expired. Refresh the feed and try again."), 404
    by_id = {entry["id"]: entry["item"] for entry in pool}
    items = [{**by_id[r["id"]], "recommendation": {"score": r["score"], "reasons": r["reasons"], "fallback": r["fallback"]}} for r in result["items"]]
    return jsonify(items=items, method=result["method"], fallback=result["fallback"], message=result["message"])


@app.get("/api/health")
def health():
    # Booleans only: never echo keys, URLs or model names that could identify credentials.
    return jsonify(status="ok", service="tba", ai_summary_configured=ai_summarizer.is_configured(),
                   sentiment_backend=ml_config.sentiment_backend())


@app.post("/api/avatar/narration/<article_id>")
@app.post("/api/avatar/hindi/<article_id>")  # backward compatibility with the previous avatar UI
def avatar_narration(article_id):
    """Narrate the selected news story in English or translated Hindi.

    English never invokes external translation. Missing publisher text receives an explicitly
    labelled headline-only briefing, rather than a fabricated overview or HTTP 422.
    """
    if not re.fullmatch(r"[0-9a-f]{20}", article_id):
        return jsonify(error="Invalid article identifier"), 400
    restore_story(article_id)
    with LOCK:
        known = KNOWN_URLS.get(article_id)
        metadata = FEED_META.get(article_id, {}).copy()
    if not known:
        return jsonify(error="Story expired. Refresh the news feed and try again."), 404

    body = request.get_json(silent=True)
    if not isinstance(body, dict):
        body = {}
    # The old endpoint must default to Hindi for older installed frontends.
    default_language = "hi" if request.path.startswith("/api/avatar/hindi/") else "en"
    requested = str(body.get("language", default_language)).strip().lower()
    if requested not in ("en", "hi"):
        return jsonify(error="Choose English (en) or Hindi (hi)."), 400

    title = str(metadata.get("title") or "").strip()
    publisher = str(metadata.get("source") or "").strip()
    payload = ARTICLE_CACHE.get(article_id)
    if not payload:
        # Reuse the same validated source text used by Quick Read. This might fail when
        # publishers block us or the extraction workers are temporarily busy.
        result = article(article_id)
        if not isinstance(result, tuple):
            payload = result.get_json()

    summary_type = (payload or {}).get("summary_type", "unavailable")
    if summary_type in ("article", "partial", "description"):
        # Avoid adding the headline to an extracted summary unless it is already in the text.
        english = str((payload or {}).get("summary") or "").strip()
        english = re.sub(r"\s+", " ", english)[:2800].strip()
    else:
        english = ""
    source_kind = summary_type
    if len(english) < 35:
        if not title:
            return jsonify(error="No reliable headline or article text is available for narration."), 422
        source_kind = "headline"
        preface = f"Headline from {publisher}: " if publisher else "News headline: "
        english = (preface + title + ". The complete article text is not available in TBA. "
                   "Open the original publisher story for the full details.")

    notice = {
        "headline": "Headline only: the publisher's full article could not be retrieved. This is NOT a full news summary.",
        "description": "Only the publisher-provided description is available; details may be missing.",
        "partial": "Only the accessible portion of this article is available.",
        "article": "Narration is based on the available Quick Read article overview.",
    }.get(source_kind, "Narration is based on the available story information.")
    response_base = {"requested_language": requested, "source_type": source_kind,
                     "title": title or "News briefing", "notice": notice}

    if requested == "en":
        return jsonify(**response_base, text=english, hindi=english, language="en-IN",
                       fallback=False, translation="not_required")

    # Hindi is opt-in. An English briefing never makes a translation HTTP request.
    cache_key = (article_id, hashlib.sha256(english.encode("utf-8")).hexdigest()[:16])
    cached = HINDI_CACHE.get(cache_key)
    if cached:
        return jsonify(cached)

    # Serialize requests for the same article. Avoids duplicate calls when users double click
    # or several browser tabs open the same story at the same time.
    with id_lock("hindi", article_id):
        cached = HINDI_CACHE.get(cache_key)
        if cached:
            return jsonify(cached)

        try:
            from deep_translator import GoogleTranslator, MyMemoryTranslator
            providers = (
                # Google accepts a longer text in one request. Sending each sentence
                # separately caused avoidable 429s and wasted the free allowance.
                ("Google", lambda: GoogleTranslator(source="en", target="hi"), 2800, 2800),
                # deep-translator's MyMemory LANGUAGE TABLE does not accept the bare 'en'
                # and 'hi' values; names map to its regional codes (e.g. en-GB/hi-IN).
                ("MyMemory", lambda: MyMemoryTranslator(source="english", target="hindi"), 400, 1200),
            )
        except ImportError:
            providers = ()
            app.logger.warning("Hindi translation unavailable: deep-translator is not installed")

        attempted = False
        for provider_name, create, chunk_limit, total_limit in providers:
            now = time.time()
            with TRANSLATION_PROVIDER_LOCK:
                cooldown_until = TRANSLATION_COOLDOWNS.get(provider_name, 0.0)
            if now < cooldown_until:
                continue  # Don't spam a blocked public provider on each Try Me click.

            attempted = True
            try:
                translator = create()
                portion = english[:total_limit]
                if len(english) > total_limit:
                    # Never end the fallback source in the middle of a word.
                    portion = portion.rsplit(" ", 1)[0] or portion
                remaining = portion
                pieces = []
                while remaining:
                    if len(remaining) <= chunk_limit:
                        chunk, remaining = remaining, ""
                    else:
                        # Split at a sentence boundary where possible; otherwise whitespace.
                        cutoff = remaining.rfind(". ", max(20, chunk_limit // 3), chunk_limit)
                        if cutoff < 0:
                            cutoff = remaining.rfind(" ", max(20, chunk_limit // 3), chunk_limit)
                        cutoff = cutoff + 1 if cutoff >= 0 else chunk_limit
                        chunk, remaining = remaining[:cutoff].strip(), remaining[cutoff:].strip()
                    if not chunk:
                        continue
                    translation = translator.translate(chunk)
                    if not translation or not re.search(r"[\u0900-\u097f]", translation):
                        raise ValueError("Provider did not return text in Hindi script")
                    pieces.append(translation)

                hindi_text = " ".join(pieces).strip()
                if not hindi_text:
                    raise ValueError("Empty Hindi narration")
                provider_notice = notice
                if len(portion) < len(english):
                    provider_notice += " Hindi narration covers only the opening part of the available overview."
                answer = dict(response_base, text=hindi_text, hindi=hindi_text,
                              language="hi-IN", fallback=False,
                              translation="automatic", translation_provider=provider_name,
                              notice=provider_notice)
                HINDI_CACHE.set(cache_key, answer, ttl=3600)
                return jsonify(answer)
            except Exception as exc:
                # 429s require a longer cooldown. Other provider failures get a short
                # cooldown so repeated clicks cannot overload the service either.
                error_name = type(exc).__name__
                error_message = str(exc).lower()
                is_limit = ("toomanyrequests" in error_name.lower() or
                            "too many requests" in error_message or
                            "429" in error_message or "rate limit" in error_message)
                cooldown_seconds = 600 if is_limit else 120
                with TRANSLATION_PROVIDER_LOCK:
                    TRANSLATION_COOLDOWNS[provider_name] = time.time() + cooldown_seconds
                app.logger.warning("Hindi provider %s unavailable (%s); retry after %ss",
                                   provider_name, error_name, cooldown_seconds)

        # A valid HTTP 200 may contain an English FALLBACK. The UI checks language and
        # fallback rather than assuming every successful response is a Hindi translation.
        english_fallback = dict(response_base, text=english, hindi=english,
                                language="en-IN", fallback=True, translation="unavailable")
        english_fallback["notice"] = (
            "Hindi translation is temporarily unavailable. Playing the original English briefing. " + notice
        )
        # Cache failures briefly to prevent repeated external requests from the same story.
        HINDI_CACHE.set(cache_key, english_fallback, ttl=120)
        if not attempted:
            app.logger.info("Hindi translator temporarily cooling down or not installed; using English fallback")
        return jsonify(english_fallback)


@app.get("/api/avatar/voice/status")
def avatar_voice_status():
    """Which self-hosted female TTS engines have actually been configured?"""
    from services.voice_service import available
    return jsonify(providers=available(), default="edge-swara", offline_audio=False,
                   note="Edge voices need internet and send narration to Microsoft; Piper and Parler run locally if installed.")


@app.post("/api/avatar/voice/sample")
def avatar_voice_service_sample():
    """Test the local neural Hindi female voice without requiring translation.

    Server-authored sample prevents arbitrary free-text synth requests. Like
    /voice/<article_id>, this is intended for local development; require auth
    and enforce quotas before deployment on the public internet.
    """
    from services.voice_service import available, synthesize_speech, VoiceUnavailable, audio_mime, valid_audio
    body = request.get_json(silent=True) or {}
    if not isinstance(body, dict):
        return jsonify(error="Expected JSON object"), 400
    provider = body.get("provider", "piper")
    language = body.get("language", "hi")
    if language not in ("en", "hi"):
        return jsonify(error="Choose English (en) or Hindi (hi)."), 400
    if provider not in ("piper", "piper-rohan", "parler", "edge-swara", "edge-madhur"):
        return jsonify(error="Unknown Hindi narrator."), 400
    if not available().get(provider):
        return jsonify(error="Selected voice is not available. See docs/VOICES_AND_SHARING.md."), 503
    if language == "en" and not provider.startswith("edge-"):
        return jsonify(error="This offline narrator supports Hindi only; choose Swara or Madhur for English."), 422
    text = ("नमस्कार! आप सुन रहे हैं इन न्यूज़। मैं आपकी एआई न्यूज़ प्रेज़ेंटर हूँ। आइए, आज की खबरों पर नज़र डालते हैं।"
            if language == "hi" else
            "Hello, welcome to TBA. Here is your news briefing, presented in a clear, natural voice.")
    sample_key = ("sample", language, provider)
    cached = FEMALE_AUDIO_CACHE.get(sample_key)
    if cached is None:
        with id_lock("sample-voice", (language, provider)):
            cached = FEMALE_AUDIO_CACHE.get(sample_key)
            if cached is None:
                try:
                    cached = synthesize_speech(text, provider, language)
                    if not valid_audio(cached, provider, limit=12 * 1024 * 1024):
                        raise ValueError("Invalid or oversized sample audio")
                    FEMALE_AUDIO_CACHE.set(sample_key, cached, ttl=3600)
                except VoiceUnavailable as exc:
                    return jsonify(error=str(exc)), 503
                except Exception:
                    app.logger.exception("Hindi voice sample failed")
                    return jsonify(error="Could not generate Hindi voice sample. Check provider connection and logs."), 503
    resp = Response(cached, mimetype=audio_mime(provider))
    resp.headers["Cache-Control"] = "no-store"
    resp.headers["X-Content-Type-Options"] = "nosniff"
    resp.headers["X-TBA-Voice"] = provider
    resp.headers["X-TBA-Language"] = language
    return resp


@app.post("/api/avatar/voice/<article_id>")
def avatar_voice_service(article_id):
    """Generate WAV for the same verified Hindi narration text as Quick Read.

    No client-provided free-form script is accepted: the story ID is looked up and
    the existing narration endpoint supplies the authoritative script. Requests
    are limited to a known story, configured engine and bounded script length.
    """
    if not re.fullmatch(r"[0-9a-f]{20}", article_id):
        return jsonify(error="Invalid story identifier"), 400
    restore_story(article_id)
    body = request.get_json(silent=True) or {}
    if not isinstance(body, dict):
        return jsonify(error="Expected JSON object"), 400
    requested_language = body.get("language", "hi")
    if requested_language not in ("hi", "en"):
        return jsonify(error="Choose English (en) or Hindi (hi)."), 400
    provider = body.get("provider", "piper")
    if provider not in ("piper", "piper-rohan", "parler", "edge-swara", "edge-madhur"):
        return jsonify(error="Unknown Hindi narrator."), 400
    from services.voice_service import available, synthesize_speech, VoiceUnavailable, audio_mime, valid_audio
    if not available().get(provider):
        return jsonify(error=("Selected voice is not available. "
                              "See docs/VOICES_AND_SHARING.md for installation.")), 503

    # The source-checked narration route uses the same request JSON. If Hindi
    # translation fails, we may speak its explicitly labeled English fallback
    # with a gender-matched English Edge voice, but never pass English to Hindi TTS.
    prepared = avatar_narration(article_id)
    if isinstance(prepared, tuple):
        return prepared
    details = prepared.get_json()
    actual_language = "hi" if details.get("language") == "hi-IN" and not details.get("fallback") else "en"
    if requested_language == "hi" and actual_language == "en" and not provider.startswith("edge-"):
        return jsonify(error="Hindi translation unavailable. Choose Swara or Madhur for English fallback, or try again later."), 422
    if actual_language == "en" and not provider.startswith("edge-"):
        return jsonify(error="This local narrator supports Hindi only. Choose Swara or Madhur for English."), 422
    original_text = details.get("text", "").strip()
    # The Piper/Parler audio uses a bounded beginning of the same summary. Do
    # not add claims or invent details; only cut at existing sentence boundary.
    script = original_text[:1650]
    if len(original_text) > 1650:
        ends = [script.rfind(mark) for mark in ("।", ".", "!", "?")]
        end = max(ends)
        if end > 400:
            script = script[:end+1]
        else:
            script = script.rsplit(" ", 1)[0] or script
    if actual_language == "hi" and not re.search(r"[\u0900-\u097F]", script):
        return jsonify(error="No Hindi script available to synthesize."), 422
    key = (article_id, actual_language, provider, hashlib.sha256(script.encode()).hexdigest()[:24])
    def response(blob):
        result = Response(blob, mimetype=audio_mime(provider))
        result.headers["Cache-Control"] = "no-store"
        result.headers["X-Content-Type-Options"] = "nosniff"
        result.headers["X-TBA-Voice"] = provider
        result.headers["X-TBA-Language"] = actual_language
        result.headers["X-TBA-Script-Truncated"] = "true" if script != original_text else "false"
        return result
    cached = FEMALE_AUDIO_CACHE.get(key)
    if cached is not None:
        return response(cached)
    with id_lock("voice-" + provider, (article_id, actual_language)):
        cached = FEMALE_AUDIO_CACHE.get(key)
        if cached is not None:
            return response(cached)
        try:
            data = synthesize_speech(script, provider, actual_language)
            if not valid_audio(data, provider):
                raise ValueError("Voice generator returned invalid or oversized audio")
            FEMALE_AUDIO_CACHE.set(key, data, ttl=3600)
            return response(data)
        except VoiceUnavailable as exc:
            return jsonify(error=str(exc)), 503
        except Exception:
            app.logger.exception("Hindi voice synthesis failed")
            return jsonify(error="Narration generation failed; check the backend logs."), 503


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=int(os.environ.get("PORT", "5000")), debug=os.environ.get("FLASK_DEBUG") == "1")
