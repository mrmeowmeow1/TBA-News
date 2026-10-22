"""Tests for story card rendering, Open Graph meta tags, and website social sharing."""
import io
import unittest
from PIL import Image

import app
from services.share_card import render_share_card_png


class StoryShareTests(unittest.TestCase):
    def setUp(self):
        self.client = app.app.test_client()
        self.test_id = "1234567890abcdef1234"
        self.now = 1700000000.0

        with app.LOCK:
            app.KNOWN_URLS[self.test_id] = ("https://news.google.com/rss/articles/test-article", self.now)
            app.FEED_META[self.test_id] = {
                "title": "Clean Energy Revolution Underway in India",
                "source": "TechDaily",
                "image": None,
                "images": [],
                "description": "India expands solar and wind capacity, marking a pivotal shift towards net-zero targets.",
                "t": self.now,
                "item": {
                    "id": self.test_id,
                    "title": "Clean Energy Revolution Underway in India",
                    "source": "TechDaily",
                    "url": "https://news.google.com/rss/articles/test-article",
                    "published": "2026-10-21T08:30:00Z",
                    "description": "India expands solar and wind capacity, marking a pivotal shift towards net-zero targets.",
                    "category": "technology",
                    "image": None
                }
            }

    def tearDown(self):
        with app.LOCK:
            app.KNOWN_URLS.pop(self.test_id, None)
            app.FEED_META.pop(self.test_id, None)
            app.SHARE_CARD_CACHE.clear()
            app.IMAGE_CACHE.clear()

    def test_render_share_card_png(self):
        png_data = render_share_card_png(
            title="Clean Energy Revolution Underway in India",
            summary="India expands solar and wind capacity, marking a pivotal shift towards net-zero targets.",
            source="TechDaily",
            topic="TECHNOLOGY",
            date_str="21 Oct 2026",
            url="http://127.0.0.1:5000/story/" + self.test_id
        )
        self.assertIsInstance(png_data, bytes)
        self.assertTrue(len(png_data) > 1000)

        # Verify it's a valid 1200x630 PNG image
        img = Image.open(io.BytesIO(png_data))
        self.assertEqual(img.size, (1200, 630))
        self.assertEqual(img.format, "PNG")

    def test_render_share_card_with_photo(self):
        # Create a small sample image
        thumb = io.BytesIO()
        Image.new("RGB", (400, 300), (45, 120, 200)).save(thumb, "JPEG")
        raw_bytes = thumb.getvalue()

        png_data = render_share_card_png(
            title="Clean Energy Revolution Underway in India",
            summary="Key takeaway summary of the clean energy transition.",
            source="TechDaily",
            topic="TECHNOLOGY",
            date_str="21 Oct 2026",
            image_bytes=raw_bytes,
            url="http://127.0.0.1:5000/story/" + self.test_id
        )
        self.assertIsInstance(png_data, bytes)
        img = Image.open(io.BytesIO(png_data))
        self.assertEqual(img.size, (1200, 630))

    def test_format_card_date(self):
        self.assertEqual(app.format_card_date("2026-10-21T08:30:00Z"), "21 Oct 2026")
        self.assertEqual(app.format_card_date(None), "Today")
        self.assertEqual(app.format_card_date(""), "Today")

    def test_get_story_metadata(self):
        meta = app.get_story_metadata(self.test_id)
        self.assertIsNotNone(meta)
        assert meta is not None
        self.assertEqual(meta["id"], self.test_id)
        self.assertEqual(meta["title"], "Clean Energy Revolution Underway in India")
        self.assertEqual(meta["source"], "TechDaily")
        self.assertIn("solar and wind capacity", meta["summary"])

    def test_story_view_endpoint(self):
        res = self.client.get(f"/story/{self.test_id}")
        self.assertEqual(res.status_code, 200)
        html = res.get_data(as_text=True)

        # Verify Open Graph and Twitter Card tags
        self.assertIn('<meta property="og:title" content="Clean Energy Revolution Underway in India">', html)
        self.assertIn(f'/api/share/card/{self.test_id}.png', html)
        self.assertIn('<meta name="twitter:card" content="summary_large_image">', html)
        self.assertIn('id="sharedStoryData"', html)
        self.assertIn(self.test_id, html)

    def test_root_view_with_story_param(self):
        res = self.client.get(f"/?story={self.test_id}")
        self.assertEqual(res.status_code, 200)
        html = res.get_data(as_text=True)
        self.assertIn('<meta property="og:title" content="Clean Energy Revolution Underway in India">', html)
        self.assertIn(f'/api/share/card/{self.test_id}.png', html)
        self.assertIn('id="sharedStoryData"', html)

    def test_share_card_image_endpoint(self):
        res = self.client.get(f"/api/share/card/{self.test_id}.png")
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.mimetype, "image/png")
        self.assertIn("max-age=3600", res.headers.get("Cache-Control", ""))

        # Verify image dimensions
        img = Image.open(io.BytesIO(res.data))
        self.assertEqual(img.size, (1200, 630))

        # Check caching
        res_cached = self.client.get(f"/api/share/card/{self.test_id}")
        self.assertEqual(res_cached.status_code, 200)
        self.assertEqual(res_cached.data, res.data)

    def test_invalid_article_id(self):
        res = self.client.get("/story/invalid-id")
        self.assertEqual(res.status_code, 404)

        res_card = self.client.get("/api/share/card/invalid-id.png")
        self.assertEqual(res_card.status_code, 400)


if __name__ == "__main__":
    unittest.main()
