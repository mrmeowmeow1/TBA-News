"""Five-source RSS / media behavior, with outbound HTTP mocked.

Run: python -m unittest discover -s tests -p 'test_five_publisher_rss.py' -v
"""
from __future__ import annotations

import hashlib
import time
import unittest
from io import BytesIO
from unittest.mock import patch

import requests
from PIL import Image

import app


PROVIDERS = {"The Indian Express", "The Hindu", "BBC News", "NDTV.com", "The Guardian"}


def sample_rss(url: str, title: str, photo_url: str = "") -> bytes:
    media = (f'<media:thumbnail url="{photo_url}" width="240" height="135"/>' if photo_url else "")
    description = " ".join([
        "A local council approved an extension to the new rail line after lengthy public debate.",
        "Officials published a detailed transport plan and promised an independent review of the project.",
        "Construction is scheduled to begin after engineering inspections are completed next spring.",
        "The budget will be examined by a committee and further progress reports will be released.",
        "Transport operators said passengers can expect additional connections across the metropolitan area.",
    ])
    return (f'<?xml version="1.0" encoding="utf-8"?>'
            f'<rss version="2.0" xmlns:media="http://search.yahoo.com/mrss/">'
            f'<channel><title>Example feed</title><item><title>{title}</title>'
            f'<link>{url}</link><description><![CDATA[{description}]]></description>'
            f'{media}<pubDate>Wed, 21 Oct 2026 09:00:00 GMT</pubDate>'
            f'</item></channel></rss>').encode()


def jpeg_240() -> bytes:
    buf = BytesIO()
    Image.new("RGB", (240, 135), (40, 120, 170)).save(buf, "JPEG")
    return buf.getvalue()


class FivePublisherRSSTests(unittest.TestCase):
    def setUp(self):
        self.client = app.app.test_client()
        for cache in (app.ANALYSIS_CACHE, app.ARTICLE_CACHE, app.IMAGE_CACHE, app.ROBOTS_CACHE):
            cache.clear()
        for cache in (app.NEWS_CACHE, app.KNOWN_URLS, app.FEED_META,
                      app.PUBLISHER_LINKS, app.HOST_BLOCKED):
            cache.clear()
        self.responses = {}

        def fake_get(url, **kwargs):
            result = self.responses.get(url)
            if result is None:
                raise requests.HTTPError("simulated publisher 404")
            return result, url

        self.fetch = patch.object(app, "safe_get", side_effect=fake_get)
        self.fetch.start()
        self.addCleanup(self.fetch.stop)
        self.mode = patch.object(app, "NEWS_SOURCE", "direct")
        self.mode.start()
        self.addCleanup(self.mode.stop)
        self.ml = patch.object(app, "enrich_items", return_value=None)
        self.ml.start()
        self.addCleanup(self.ml.stop)

    def test_all_five_providers_present_in_top_world_nation(self):
        for category in ("top", "world", "nation"):
            self.assertEqual({name for name, _ in app.DIRECT_FEEDS[category]}, PROVIDERS)
        for category in app.CATEGORIES:
            self.assertTrue(app.DIRECT_FEEDS[category])
            self.assertFalse(any("news.google.com" in url for _, url in app.DIRECT_FEEDS[category]))

    def test_one_provider_failure_does_not_hide_other_publishers(self):
        feeds = app.DIRECT_FEEDS["top"]
        self.responses[feeds[0][1]] = sample_rss("https://indianexpress.com/article/india/test-123", "Indian Rail Project")
        self.responses[feeds[2][1]] = sample_rss("https://www.bbc.com/news/articles/test123", "BBC Rail Project")
        response = self.client.get("/api/news?category=top&refresh=1")
        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        self.assertEqual(data["feed_mode"], "direct")
        self.assertEqual(data["feeds_responding"], 2)
        self.assertEqual(len(data["items"]), 2)
        self.assertTrue(all("news.google.com" not in item["url"] for item in data["items"]))

    def test_240x135_editorial_thumbnail_is_accepted(self):
        photo_url = "https://images.example.org/rail-project.jpg"
        url = "https://www.theguardian.com/world/2026/oct/21/rail-project"
        self.responses[app.DIRECT_FEEDS["top"][4][1]] = sample_rss(url, "Council approves rail", photo_url)
        self.responses[photo_url] = jpeg_240()
        feed = self.client.get("/api/news?category=top&refresh=1").get_json()
        item = feed["items"][0]
        self.assertEqual(item["image"], photo_url)
        response = self.client.get("/api/image/" + item["id"])
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.mimetype, "image/jpeg")

    def test_quick_read_uses_publisher_rss_if_page_is_blocked(self):
        url = "https://www.theguardian.com/world/2026/oct/21/example"
        self.responses[app.DIRECT_FEEDS["top"][4][1]] = sample_rss(url, "Transport committee votes on rail")
        feed = self.client.get("/api/news?category=top&refresh=1").get_json()
        item = feed["items"][0]
        response = self.client.get("/api/article/" + item["id"])
        self.assertEqual(response.status_code, 200)
        article = response.get_json()
        self.assertIn(article["summary_type"], ("partial", "description"))
        self.assertIn("publisher", (article.get("message") or "").lower())


if __name__ == "__main__":
    unittest.main()
