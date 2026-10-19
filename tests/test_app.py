"""Offline tests: all network access is mocked, so they run without internet."""
import base64
import hashlib
import json
import threading
import time
import os
import unittest
from io import BytesIO
from unittest.mock import MagicMock, patch

import requests
from PIL import Image

os.environ["TBA_AI_API_KEY"] = ""      # tests must never reach a real AI provider

import app

# --------------------------------------------------------------------------------------------
# Helpers
# --------------------------------------------------------------------------------------------
ARTICLE_PARAGRAPHS = [
    "The Pune Metropolitan Council on Tuesday approved a 14-kilometre extension of Line 3, clearing the way for construction to begin before the end of March 2027.",
    "Council chairperson Meera Kulkarni said the extension would connect Hinjewadi with the Shivajinagar interchange and carry an estimated 320,000 passengers every day once it opens.",
    "The project will cost about ₹8,400 crore, of which 40% will come from the state government and the rest from a loan arranged with a consortium of development banks.",
    "Officials from the Maharashtra Metro Rail Corporation told reporters that tendering for the first two stations would start in November, with contractors expected to be named by January 2027.",
    "Line 3 was first proposed in 2018, but land disputes and a funding shortfall delayed the plan for several years before the state agreed to underwrite part of the cost last year.",
    "Opposition councillors questioned the budget, arguing that earlier metro projects in the city had run well over their original estimates and had opened months behind schedule.",
    "Kulkarni rejected the criticism and said an independent auditor would review every contract above ₹50 crore, publishing its findings each quarter for public inspection.",
    "Residents of the Baner and Balewadi neighbourhoods have campaigned for the extension since 2019, saying the existing bus services cannot cope with the number of commuters travelling to the technology parks.",
    "Traffic police said that parts of University Road will be closed in phases once work begins, and that diversions will be announced at least two weeks before each closure takes effect.",
    "The corporation said it has already acquired 82% of the land needed for the route and expects to complete the remaining acquisitions by the end of December.",
    "Environmental groups welcomed the decision but urged the council to protect more than 1,200 mature trees along the proposed alignment, many of which are decades old.",
    "In response, the corporation promised to transplant as many trees as possible and to plant three saplings for every tree that is removed, with the work monitored by the forest department.",
    "Engineers estimate that the extension will cut the journey between Hinjewadi and the city centre from about 75 minutes at peak hours to roughly 35 minutes.",
    "A public hearing on the final station designs is scheduled for next month, and the council said it will publish the revised plans online ahead of the meeting.",
    "Business groups in the technology corridor said the approval removes a major uncertainty for companies deciding whether to expand their offices in the area over the coming years.",
    "Transport analysts cautioned that the benefits would depend on feeder bus routes and parking arrangements around the new stations, which have not yet been finalised by the council.",
    "Shopkeepers along the planned route said they were worried about losing customers during the construction period, and asked the corporation to set up a compensation scheme for affected traders.",
    "The corporation said it would consider a limited relief fund but did not commit to any amount, adding that most stations would be built on public land rather than on commercial plots.",
    "Students at Savitribai Phule Pune University, which sits beside the proposed Shivajinagar interchange, welcomed the plan and said a direct metro link would reduce travel costs for thousands of them.",
    "Several residents' associations asked for noise barriers along the elevated sections, and the engineers said they would study the request as part of the final design review.",
    "The council voted 41 to 12 in favour of the extension after a debate that lasted nearly five hours, with a handful of members abstaining from the vote.",
    "Work on the elevated viaduct is likely to take close to four years, according to the corporation, which has promised to publish progress reports every three months.",
]
LONG_TEXT = " ".join(ARTICLE_PARAGRAPHS)
SHORT_TEXT = "Heavy rain flooded several low-lying streets in the city on Monday evening. Traffic was diverted around the worst affected junctions while pumps were brought in to clear the water."

PUBLISHER_URL = "https://news.example-times.in/pune/metro-line-3-approved"
GOOGLE_PREFIX = "https://news.google.com/rss/articles/"


def jpeg(width=800, height=420, colour=(30, 90, 160)):
    out = BytesIO()
    Image.new("RGB", (width, height), colour).save(out, "JPEG")
    return out.getvalue()


def publisher_html(paragraphs=ARTICLE_PARAGRAPHS, image="/media/metro-line.jpg", extra_head=""):
    body = "".join(f"<p>{p}</p>" for p in paragraphs)
    og = f'<meta property="og:image" content="{image}">' if image else ""
    return f"""<html><head><title>Metro approved | Example Times</title>
    <meta property="og:title" content="Council approves metro extension">
    <meta property="og:description" content="The Pune Metropolitan Council approved a 14-kilometre extension of Line 3 on Tuesday, with construction due to begin by March 2027.">
    {og}{extra_head}</head><body>
    <header><nav><a href="/">Home</a><a href="/world">World</a></nav></header>
    <div class="cookie-banner"><p>We use cookies to improve your experience on this website and show you personalised advertising.</p></div>
    <div class="advert ad-slot"><p>Advertisement: buy the best broadband plans available in your city today and save big.</p></div>
    <main><article><h1>Council approves metro extension</h1>
    <div class="share-bar"><p>Share this article with your friends and family on every social network available online.</p></div>
    {body}
    <div class="related-stories"><p>Related: Ten restaurants in Pune that every visitor should try at least once this winter season.</p></div>
    </article>
    <section class="comments"><p>Great news, I hope the work is finished on time this time and the roads are properly repaired afterwards.</p></section>
    </main><footer><p>Copyright © 2026 Example Times. All rights reserved. Terms of use and privacy policy apply to everything.</p></footer>
    </body></html>""".encode()


def make_token(url):
    data = url.encode()
    n = len(data)
    varint = bytes([n]) if n < 128 else bytes([(n & 0x7F) | 0x80, n >> 7])
    return base64.urlsafe_b64encode(b"\x08\x13\x22" + varint + data + b"\xd2\x01\x00").decode().rstrip("=")


class FakeWeb:
    """Stands in for app.safe_get. Routes map URL -> (bytes, final_url) or an exception."""

    def __init__(self):
        self.routes, self.calls, self.delay = {}, [], 0

    def add(self, url, body=b"", final=None):
        self.routes[url] = (body, final or url)

    def fail(self, url, exc):
        self.routes[url] = exc

    def count(self, url):
        return self.calls.count(url)

    def __call__(self, url, timeout=9, limit=1_500_000, accept=None, track_host=False):
        self.calls.append(url)
        if self.delay:
            time.sleep(self.delay)
        route = self.routes.get(url)
        if route is None:
            raise requests.HTTPError("404 Not Found")
        if isinstance(route, Exception):
            raise route
        return route


class AppTestCase(unittest.TestCase):
    def setUp(self):
        self.client = app.app.test_client()
        for cache in (app.ANALYSIS_CACHE, app.ARTICLE_CACHE, app.IMAGE_CACHE, app.RESOLVE_CACHE, app.ROBOTS_CACHE):
            cache.clear()
        for store in (app.KNOWN_URLS, app.PUBLISHER_LINKS, app.FEED_META, app.HOST_BLOCKED, app.NEWS_CACHE):
            store.clear()
        self.web = FakeWeb()
        patcher = patch.object(app, "safe_get", self.web)
        patcher.start()
        self.addCleanup(patcher.stop)
        # Resolver tests use example publisher domains.  The network fetcher is
        # already replaced above, so DNS validation must not reach the real network.
        public_url = patch.object(app, "safe_public_url", return_value=True)
        public_url.start()
        self.addCleanup(public_url.stop)
        decoder = patch.object(app, "decode_google_news", return_value=None)
        decoder.start()
        self.addCleanup(decoder.stop)

    def register(self, link=None, title="Council approves metro extension", source="Example Times", description="", images=None):
        link = link or GOOGLE_PREFIX + make_token(PUBLISHER_URL)
        ident = hashlib.sha256(link.encode()).hexdigest()[:20]
        app.KNOWN_URLS[ident] = (link, time.time())
        app.FEED_META[ident] = {"title": title, "source": source, "description": description,
                                "images": images or [], "image": (images or [None])[0], "t": time.time()}
        return ident


# --------------------------------------------------------------------------------------------
# Original tests (unchanged behaviour)
# --------------------------------------------------------------------------------------------
class OriginalTests(unittest.TestCase):
    def setUp(self): self.client = app.app.test_client()
    def test_health(self): self.assertEqual(self.client.get('/api/health').status_code, 200)
    def test_home(self): self.assertIn(b'TBA', self.client.get('/').data)
    def test_category_rejected(self): self.assertEqual(self.client.get('/api/news?category=invalid').status_code, 400)
    def test_query_limit(self): self.assertEqual(self.client.get('/api/news?q=' + 'a' * 101).status_code, 400)
    def test_bad_article_id(self): self.assertEqual(self.client.get('/api/article/test').status_code, 400)

    def test_summary(self):
        text = 'Scientists announced a new experiment on solar energy. The experiment could improve solar energy production. Researchers are now testing the technology in laboratories.'
        self.assertIn('solar energy', app.summarize(text))

    def test_feed(self):
        xml = b'<rss version="2.0"><channel><item><title>Big discovery - Science Wire</title><link>https://news.google.com/rss/articles/abc</link><pubDate>Mon, 12 Oct 2026 10:00:00 GMT</pubDate><source url="https://example.com">Science Wire</source></item></channel></rss>'
        items = app.parse_feed(xml, 'science')
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0]['title'], 'Big discovery')

    def test_rejects_google_news_logo(self):
        self.assertTrue(app.is_branding_image('https://news.google.com/images/branding/google-news-512.png'))
        self.assertTrue(app.is_branding_image('https://cdn.example.org/assets/logo.png'))
        self.assertFalse(app.is_branding_image('https://cdn.example.org/stories/cricket-match.jpg'))

    def test_extract_ignores_google_og_image(self):
        html = '<meta property="og:image" content="https://news.google.com/images/branding/google-news.png"><article><p>Article text for a sample publisher news item with enough information to extract a paragraph and validate images.</p></article>'
        _, image, _ = app.extract_text(html)
        self.assertIsNone(image)

    def test_google_feed_url(self): self.assertIn('solar+cells', app.feed_url('top', 'solar cells'))

    def test_blocks_internal_urls(self):
        self.assertFalse(app.safe_public_url('http://127.0.0.1/'))
        self.assertFalse(app.safe_public_url('https://localhost/'))


# --------------------------------------------------------------------------------------------
# RSS image extraction / URL normalisation
# --------------------------------------------------------------------------------------------
class FeedImageTests(unittest.TestCase):
    def test_normalize_image_url(self):
        n = app.normalize_image_url
        self.assertEqual(n("/img/a.jpg", "https://pub.example/news/story"), "https://pub.example/img/a.jpg")
        self.assertEqual(n("a.jpg", "https://pub.example/news/story"), "https://pub.example/news/a.jpg")
        self.assertEqual(n("//cdn.example/a.jpg", "https://pub.example/x"), "https://cdn.example/a.jpg")
        self.assertEqual(n("http://cdn.example/a.jpg"), "https://cdn.example/a.jpg")
        self.assertEqual(n("https://cdn.example/a.jpg"), "https://cdn.example/a.jpg")
        for bad in ("", None, "data:image/png;base64,AAAA", "javascript:alert(1)", "ftp://x.example/a.jpg", "/relative-without-base.jpg", "https://" + "a" * 2100):
            self.assertIsNone(n(bad), bad)

    def test_entry_media_fields(self):
        entry = {
            "media_thumbnail": [{"url": "/thumbs/t.jpg", "width": "100"}],
            "media_content": [{"url": "https://cdn.example/clip.mp4", "type": "video/mp4"}, {"url": "http://cdn.example/big.jpg", "medium": "image"}],
            "enclosures": [{"href": "https://cdn.example/enc.png", "type": "image/png"}, {"href": "https://cdn.example/podcast.mp3", "type": "audio/mpeg"}],
            "links": [{"rel": "enclosure", "href": "https://cdn.example/link.webp", "type": "image/webp"}],
            "summary": '<p><img src="//cdn.example/inline.jpg"> text</p>',
        }
        got = app.image_candidates_from_entry(entry, "https://pub.example/story/1")
        self.assertEqual(got, ["https://pub.example/thumbs/t.jpg", "https://cdn.example/big.jpg", "https://cdn.example/enc.png",
                               "https://cdn.example/link.webp", "https://cdn.example/inline.jpg"])
        self.assertFalse(any(u.endswith((".mp4", ".mp3")) for u in got))

    def test_entry_skips_branding_and_duplicates(self):
        entry = {"media_thumbnail": [{"url": "https://news.google.com/images/branding/g.png"}, {"url": "https://cdn.example/site-logo.png"},
                                     {"url": "https://cdn.example/a.jpg"}, {"url": "https://cdn.example/a.jpg"}]}
        self.assertEqual(app.image_candidates_from_entry(entry), ["https://cdn.example/a.jpg"])

    def test_entry_without_media(self):
        self.assertEqual(app.image_candidates_from_entry({}), [])
        self.assertEqual(app.image_candidates_from_entry({"summary": "<p>No pictures</p>"}), [])

    def test_parse_feed_picks_up_relative_media(self):
        xml = (b'<rss version="2.0" xmlns:media="http://search.yahoo.com/mrss/"><channel><item><title>Metro opens - Daily</title>'
               b'<link>https://pub.example/news/metro</link><source url="https://pub.example">Daily</source>'
               b'<media:thumbnail url="/thumbs/metro.jpg"/></item></channel></rss>')
        app.parse_feed(xml, "top")
        ident = hashlib.sha256(b"https://pub.example/news/metro").hexdigest()[:20]
        self.assertEqual(app.FEED_META[ident]["image"], "https://pub.example/thumbs/metro.jpg")

    def test_parse_feed_keeps_real_descriptions_and_drops_headline_echoes(self):
        real = "The council approved a 14-kilometre extension of the metro line on Tuesday and said construction would start by March next year."
        xml = (f'<rss version="2.0"><channel>'
               f'<item><title>Metro extension approved - Daily</title><link>https://pub.example/a</link><source url="https://pub.example">Daily</source><description>{real}</description></item>'
               f'<item><title>Floods hit city - Daily</title><link>https://news.google.com/rss/articles/zzz</link><source url="https://pub.example">Daily</source>'
               f'<description>&lt;a href="https://news.google.com/rss/articles/zzz"&gt;Floods hit city&lt;/a&gt;&amp;nbsp;&amp;nbsp;&lt;font color="#6f6f6f"&gt;Daily&lt;/font&gt;</description></item>'
               f'</channel></rss>').encode()
        items = app.parse_feed(xml, "top")
        self.assertEqual(items[0]["description"], real)                       # previously discarded (<260 chars)
        self.assertEqual(items[1]["description"], "Open this story for a short summary and its original source.")
        self.assertEqual(app.FEED_META[items[1]["id"]]["description"], "")   # headline echo is not a description

    def test_meaningful_description(self):
        m = app.meaningful_description
        self.assertFalse(m("Floods hit city Daily", "Floods hit city", "Daily"))
        self.assertFalse(m("Floods hit the city and the government said so today in a long headline repeat", "Floods hit the city and the government said so today in a long headline repeat"))
        self.assertFalse(m("Short text.", "Other"))
        self.assertFalse(m("Google News aggregates headlines from sources around the world for every reader everywhere today.", "x"))
        self.assertTrue(m("Heavy rain flooded several low-lying streets on Monday evening and traffic was diverted around junctions.", "Floods hit city", "Daily"))


# --------------------------------------------------------------------------------------------
# Safe fetching (SSRF, redirects, refusals)
# --------------------------------------------------------------------------------------------
class FakeResponse:
    def __init__(self, status=200, headers=None, body=b"", ):
        self.status_code, self.headers, self._body = status, headers or {}, body

    def __enter__(self): return self
    def __exit__(self, *a): return False
    def iter_content(self, chunk_size=1):
        for i in range(0, len(self._body), chunk_size):
            yield self._body[i:i + chunk_size]
    def raise_for_status(self):
        if self.status_code >= 400:
            raise requests.HTTPError(str(self.status_code))


PUBLIC = [(2, 1, 6, "", ("93.184.216.34", 443))]


class SafeGetTests(unittest.TestCase):
    """Exercise the real safe_get (these tests do NOT use FakeWeb)."""

    def setUp(self):
        app.HOST_BLOCKED.clear()
        self.addCleanup(app.HOST_BLOCKED.clear)

    def run_get(self, responses, **kwargs):
        seq = iter(responses)
        with patch("app.socket.getaddrinfo", return_value=PUBLIC), patch("app.requests.get", side_effect=lambda *a, **k: next(seq)) as get:
            try:
                return app.safe_get("https://pub.example/a", **kwargs), get
            except Exception as exc:       # noqa: BLE001 - returned for assertions
                return exc, get

    def test_ok(self):
        (body, final), _ = self.run_get([FakeResponse(200, {"Content-Type": "text/html; charset=utf-8"}, b"<p>hi</p>")], accept=app.HTML_TYPES)
        self.assertEqual((body, final), (b"<p>hi</p>", "https://pub.example/a"))

    def test_redirect_to_private_address_rejected(self):
        def resolver(host, *a, **k):
            return [(2, 1, 6, "", ("10.0.0.5" if host == "internal.example" else "93.184.216.34", 443))]
        seq = iter([FakeResponse(302, {"Location": "https://internal.example/secret"}), FakeResponse(200, {}, b"secret")])
        with patch("app.socket.getaddrinfo", side_effect=resolver), patch("app.requests.get", side_effect=lambda *a, **k: next(seq)):
            with self.assertRaises(ValueError):
                app.safe_get("https://pub.example/a")

    def test_redirect_to_http_rejected(self):
        exc, _ = self.run_get([FakeResponse(301, {"Location": "http://pub.example/plain"})])
        self.assertIsInstance(exc, ValueError)

    def test_redirect_loop_stops(self):
        exc, get = self.run_get([FakeResponse(302, {"Location": "https://pub.example/a"})] * 10)
        self.assertIsInstance(exc, ValueError)
        self.assertLessEqual(get.call_count, 5)

    def test_refusals_raise_fetch_blocked(self):
        for status in (401, 402, 403, 451):
            exc, _ = self.run_get([FakeResponse(status)])
            self.assertIsInstance(exc, app.FetchBlocked, status)
            self.assertEqual(exc.status, status)
        self.assertFalse(app.host_is_blocked("pub.example"))      # only 429 blocks a whole host

    def test_429_cools_host_down(self):
        exc, _ = self.run_get([FakeResponse(429, {"Retry-After": "120"})], track_host=True)
        self.assertIsInstance(exc, app.FetchBlocked)
        self.assertTrue(app.host_is_blocked("pub.example"))
        exc, get = self.run_get([FakeResponse(200, {}, b"x")], track_host=True)   # fails fast, no request made
        self.assertIsInstance(exc, app.FetchBlocked)
        self.assertEqual(get.call_count, 0)

    def test_wrong_content_type_and_size_limit(self):
        exc, _ = self.run_get([FakeResponse(200, {"Content-Type": "application/pdf"}, b"%PDF")], accept=app.HTML_TYPES)
        self.assertIsInstance(exc, ValueError)
        exc, _ = self.run_get([FakeResponse(200, {"Content-Type": "text/html"}, b"x" * 5000)], limit=1000)
        self.assertIsInstance(exc, ValueError)


# --------------------------------------------------------------------------------------------
# Google News link resolution
# --------------------------------------------------------------------------------------------
class GoogleResolveTests(AppTestCase):
    def test_token_extraction(self):
        self.assertEqual(app.google_token("https://news.google.com/rss/articles/CBMiabc?oc=5"), "CBMiabc")
        self.assertEqual(app.google_token("https://news.google.com/articles/CBMiabc"), "CBMiabc")
        self.assertIsNone(app.google_token("https://pub.example/rss/articles/CBMiabc"))
        self.assertIsNone(app.google_token("https://news.google.com/topics/xyz"))

    def test_offline_decode_short_and_long_urls(self):
        short = "https://news.example-times.in/a"
        long_url = "https://news.example-times.in/" + "section/" * 25 + "story-12345"
        self.assertGreater(len(long_url), 127)
        self.assertEqual(app.decode_google_token_offline(make_token(short)), short)
        self.assertEqual(app.decode_google_token_offline(make_token(long_url)), long_url)
        self.assertEqual(app.decode_google_token_offline(make_token("http://old.example/a")), "https://old.example/a")

    def test_offline_decode_rejects_garbage_and_new_format(self):
        for bad in ("", "!!!", "AU_yqLNewFormatTokenThatNeedsGoogle", base64.urlsafe_b64encode(b"\x08\x13\x22\x05hello").decode()):
            self.assertIsNone(app.decode_google_token_offline(bad), bad)

    def test_current_google_links_are_resolved_in_one_indian_batch(self):
        token = "AU_yqL" + "x" * 48
        link = GOOGLE_PREFIX + token
        item = {"id": "a" * 20, "url": link}
        with patch.object(app, "decode_google_news_many", return_value={link: PUBLISHER_URL}) as decoder:
            app.resolve_feed_publishers([item], 123.0)
        decoder.assert_called_once_with(
            [link], ceid="IN:en", concurrency=8, timeout=8.0
        )
        self.assertEqual(app.PUBLISHER_LINKS[item["id"]], (PUBLISHER_URL, 123.0))
        self.assertEqual(app.RESOLVE_CACHE.get(token), PUBLISHER_URL)

    def test_on_demand_google_decoder_uses_indian_locale(self):
        token = "AU_yqL" + "y" * 48
        link = GOOGLE_PREFIX + token
        with patch.object(app, "decode_google_news", return_value=PUBLISHER_URL) as decoder:
            self.assertEqual(app.resolve_google_url(link), PUBLISHER_URL)
        decoder.assert_called_once_with(link, ceid="IN:en", timeout=12.0)

    def test_resolve_uses_offline_without_network(self):
        link = GOOGLE_PREFIX + make_token(PUBLISHER_URL)
        with patch.object(app, "decode_google_token_online", side_effect=AssertionError("should not be called")):
            self.assertEqual(app.resolve_google_url(link), PUBLISHER_URL)
        self.assertEqual(self.web.calls, [])

    def test_parse_batchexecute_plain_and_length_prefixed(self):
        row = ["wrb.fr", "Fbv4je", json.dumps(["garturlres", PUBLISHER_URL, 1]), None, None, None, "generic"]
        plain = ")]}'\n\n" + json.dumps([row, ["di", 12], ["af.httprm", 12, "-1", 3]]) + "\n"
        prefixed = ")]}'\n\n123\n" + json.dumps([row]) + "\n56\n" + json.dumps([["e", 4]])
        self.assertEqual(app.parse_batchexecute(plain), PUBLISHER_URL)
        self.assertEqual(app.parse_batchexecute(prefixed), PUBLISHER_URL)
        for bad in ("", "no json here", ")]}'\n\n[]", ")]}'\n\n" + json.dumps([["wrb.fr", "x", "not-json"]])):
            self.assertIsNone(app.parse_batchexecute(bad), bad)

    def test_online_decode_flow(self):
        token = "AU_yqLNewFormat123"
        page = b'<html><body><c-wiz><div jscontroller="abc" data-n-a-sg="SIGNATURE" data-n-a-ts="1700000000"></div></c-wiz></body></html>'
        self.web.add(f"https://news.google.com/rss/articles/{token}", page)
        row = ["wrb.fr", "Fbv4je", json.dumps(["garturlres", PUBLISHER_URL, 1])]
        reply = MagicMock(status_code=200, text=")]}'\n\n" + json.dumps([row]), headers={})
        reply.raise_for_status = lambda: None
        with patch.object(app.requests, "post", return_value=reply) as post:
            self.assertEqual(app.resolve_google_url(GOOGLE_PREFIX + token), PUBLISHER_URL)
        sent = post.call_args.kwargs["data"]
        self.assertIn("SIGNATURE", sent)
        self.assertIn("1700000000", sent)
        self.assertEqual(post.call_args.args[0], "https://news.google.com/_/DotsSplashUi/data/batchexecute")
        self.assertFalse(post.call_args.kwargs["allow_redirects"])

    def test_online_decode_follows_direct_publisher_redirect(self):
        token = "AU_yqLRedirects"
        self.web.add(f"https://news.google.com/rss/articles/{token}", b"<html></html>", final=PUBLISHER_URL)
        self.assertEqual(app.resolve_google_url(GOOGLE_PREFIX + token), PUBLISHER_URL)

    def test_failure_is_cached_and_not_retried_immediately(self):
        token = "AU_yqLUnresolvable"
        link = GOOGLE_PREFIX + token
        self.assertIsNone(app.resolve_google_url(link))
        calls = len(self.web.calls)
        self.assertIsNone(app.resolve_google_url(link))
        self.assertEqual(len(self.web.calls), calls)

    def test_never_resolves_to_google(self):
        token = "AU_yqLBackToGoogle"
        self.web.add(f"https://news.google.com/rss/articles/{token}", b"<html></html>", final="https://consent.google.com/x")
        self.assertIsNone(app.resolve_google_url(GOOGLE_PREFIX + token))

    def test_rate_limited_google_stops_further_attempts(self):
        self.web.fail("https://news.google.com/rss/articles/AU_yqL429", app.FetchBlocked(429))
        self.assertIsNone(app.resolve_google_url(GOOGLE_PREFIX + "AU_yqL429"))
        before = len(self.web.calls)
        self.assertIsNone(app.resolve_google_url(GOOGLE_PREFIX + "AU_yqLother"))
        self.assertEqual(len(self.web.calls), before)


# --------------------------------------------------------------------------------------------
# Publisher page extraction
# --------------------------------------------------------------------------------------------
class ExtractionTests(unittest.TestCase):
    def test_removes_page_furniture(self):
        result = app.extract_article(publisher_html(), PUBLISHER_URL)
        text = result["text"]
        self.assertIn("approved a 14-kilometre extension", text)
        self.assertIn("feeder bus routes", text)
        for junk in ("We use cookies", "Advertisement", "Share this article", "Related:", "Great news, I hope", "All rights reserved", "Home"):
            self.assertNotIn(junk, text)

    def test_images_absolute_and_ordered(self):
        html = publisher_html(image="/media/metro-line.jpg", extra_head='<meta name="twitter:image" content="//cdn.example/tw.jpg"><link rel="image_src" href="http://cdn.example/linked.jpg">')
        images = app.extract_article(html, PUBLISHER_URL)["images"]
        self.assertEqual(images, ["https://news.example-times.in/media/metro-line.jpg", "https://cdn.example/tw.jpg", "https://cdn.example/linked.jpg"])

    def test_twitter_image_used_when_no_og_image(self):
        html = publisher_html(image=None, extra_head='<meta name="twitter:image" content="https://cdn.example/tw.jpg">')
        self.assertEqual(app.extract_article(html, PUBLISHER_URL)["images"], ["https://cdn.example/tw.jpg"])

    def test_jsonld_article_image_used_but_author_avatar_ignored(self):
        ld = {"@context": "https://schema.org", "@type": "NewsArticle", "image": ["https://cdn.example/ld-hero.jpg"],
              "author": {"@type": "Person", "image": "https://cdn.example/author-face.jpg"}}
        html = publisher_html(image=None, extra_head=f'<script type="application/ld+json">{json.dumps(ld)}</script>')
        self.assertEqual(app.extract_article(html, PUBLISHER_URL)["images"], ["https://cdn.example/ld-hero.jpg"])

    def test_jsonld_article_body_and_paywall_flag(self):
        body = " ".join(ARTICLE_PARAGRAPHS[:6])
        ld = {"@type": "NewsArticle", "articleBody": body, "isAccessibleForFree": "False"}
        html = f'<html><head><script type="application/ld+json">{json.dumps(ld)}</script></head><body><p>Subscribe to read the whole article.</p></body></html>'
        result = app.extract_article(html, PUBLISHER_URL)
        self.assertTrue(result["partial"])
        self.assertIn("approved a 14-kilometre extension", result["text"])

    def test_metadata_description(self):
        self.assertIn("14-kilometre extension", app.extract_article(publisher_html(), PUBLISHER_URL)["description"])
        google_shell = b'<meta property="og:description" content="Comprehensive up-to-date news coverage, aggregated from sources all over the world by Google News.">'
        self.assertEqual(app.readable_metadata(google_shell), "")

    def test_non_article_page_yields_little_text(self):
        html = b"<html><body><nav><a href='/'>Home</a></nav><p>Loading...</p><script>var x=1</script></body></html>"
        self.assertEqual(app.extract_article(html, PUBLISHER_URL)["text"], "")


# --------------------------------------------------------------------------------------------
# Overview generation
# --------------------------------------------------------------------------------------------
class OverviewTests(unittest.TestCase):
    def test_every_sentence_comes_from_the_article(self):
        overview = app.build_overview(LONG_TEXT)
        source = set(app.split_sentences(LONG_TEXT))
        shown = [overview["intro"]] + overview["points"] + overview["background"] + overview["next"]
        self.assertTrue(overview["points"])
        for chunk in shown:
            for sentence in app.split_sentences(chunk):
                self.assertIn(sentence, source)
        self.assertEqual(overview["summary"], "\n\n".join(shown))

    def test_details_are_verbatim_and_sensible(self):
        details = app.build_overview(LONG_TEXT)["details"]
        for group in details.values():
            for value in group:
                self.assertIn(value, LONG_TEXT)
        self.assertTrue(any("Kulkarni" in n for n in details["names"]))
        self.assertTrue(any("₹8,400 crore" in f for f in details["figures"]))
        self.assertTrue(any("Tuesday" in d or "2027" in d for d in details["dates"]))
        self.assertFalse({"The", "In", "Officials"} & set(details["names"]))

    def test_length_adapts_and_stays_in_range(self):
        long_overview = app.build_overview(LONG_TEXT)
        self.assertGreaterEqual(long_overview["summary_words"], 140)
        self.assertLessEqual(long_overview["summary_words"], 320)
        medium = app.build_overview(" ".join(ARTICLE_PARAGRAPHS[:8]))
        self.assertLess(medium["summary_words"], long_overview["summary_words"])
        short = app.build_overview(SHORT_TEXT)
        self.assertLessEqual(short["summary_words"], len(SHORT_TEXT.split()) * 0.6)
        self.assertEqual(short["points"], [])

    def test_background_and_next_only_when_article_states_them(self):
        overview = app.build_overview(LONG_TEXT)
        self.assertTrue(any("first proposed in 2018" in s or "last year" in s for s in overview["background"]))
        source = set(app.split_sentences(LONG_TEXT))
        self.assertEqual(len(overview["next"]), 1)
        self.assertIn(overview["next"][0], source)
        self.assertTrue(app._NEXT.search(overview["next"][0]))                 # a sentence the article itself words as forward-looking
        plain = " ".join(ARTICLE_PARAGRAPHS[7:10] * 3)       # no background / future cues
        self.assertEqual(app.build_overview(plain)["next"], [])

    def test_sentence_splitter_keeps_abbreviations_together(self):
        text = "Dr. Anita Rao met Mr. Singh at 10 a.m. in the U.S. embassy on Monday. Talks resumed later in the afternoon after lunch."
        self.assertEqual(len(app.split_sentences(text)), 2)

    def test_empty_input(self):
        self.assertIsNone(app.build_overview(""))
        self.assertIsNone(app.build_overview("Too short."))


# --------------------------------------------------------------------------------------------
# /api/article
# --------------------------------------------------------------------------------------------
class ArticleEndpointTests(AppTestCase):
    def setUp(self):
        super().setUp()
        self.web.add(PUBLISHER_URL, publisher_html())

    def get(self, ident, retry=False):
        return self.client.get(f"/api/article/{ident}" + ("?retry=1" if retry else ""))

    def test_full_article_overview(self):
        ident = self.register()
        data = self.get(ident).get_json()
        self.assertEqual(data["summary_type"], "article")
        self.assertIsNone(data["message"])
        self.assertTrue(data["intro"].startswith("The Pune Metropolitan Council"))
        self.assertGreater(len(data["points"]), 2)
        self.assertEqual(data["source_url"], PUBLISHER_URL)
        self.assertNotIn("cookies", data["summary"])
        source = set(app.split_sentences(LONG_TEXT))
        for sentence in app.split_sentences(data["summary"]):
            self.assertIn(sentence, source)

    def test_second_request_is_cached(self):
        ident = self.register()
        self.get(ident)
        self.get(ident)
        self.assertEqual(self.web.count(PUBLISHER_URL), 1)

    def test_concurrent_requests_fetch_once(self):
        ident = self.register()
        self.web.delay = 0.25
        results = []
        threads = [threading.Thread(target=lambda: results.append(self.get(ident).get_json()["summary_type"])) for _ in range(6)]
        [t.start() for t in threads]
        [t.join() for t in threads]
        self.assertEqual(results, ["article"] * 6)
        self.assertEqual(self.web.count(PUBLISHER_URL), 1)

    def test_rss_description_fallback_when_publisher_blocks(self):
        desc = "The council approved a 14-kilometre extension of the metro line on Tuesday and said construction would start by March next year."
        ident = self.register(description=desc)
        self.web.fail(PUBLISHER_URL, app.FetchBlocked(403))
        data = self.get(ident).get_json()
        self.assertEqual(data["summary_type"], "description")
        self.assertEqual(data["intro"], desc)
        self.assertEqual(data["description_origin"], "feed")
        self.assertIn("not a summary of the article", data["message"])

    def test_page_metadata_fallback_when_text_is_missing(self):
        self.web.add(PUBLISHER_URL, publisher_html(paragraphs=["Subscribe to read the full story."]))
        ident = self.register()
        data = self.get(ident).get_json()
        self.assertEqual(data["summary_type"], "description")
        self.assertEqual(data["description_origin"], "page")
        self.assertIn("14-kilometre extension", data["intro"])

    def test_never_summarises_from_headline_alone(self):
        google_style = "Council approves metro extension Example Times"
        ident = self.register(description="")
        self.assertFalse(app.meaningful_description(google_style, "Council approves metro extension", "Example Times"))
        self.web.fail(PUBLISHER_URL, app.FetchBlocked(402))          # paywall: must not be bypassed
        data = self.get(ident).get_json()
        self.assertEqual(data["summary_type"], "unavailable")
        self.assertEqual(data["summary"], "")
        self.assertEqual(data["points"], [])
        self.assertEqual(data["reason"], "blocked")
        self.assertIn("original story", data["message"])
        self.assertEqual(self.web.count(PUBLISHER_URL), 1)

    def test_page_metadata_that_just_repeats_the_headline_is_ignored(self):
        title = "Council approves metro extension for the Hinjewadi and Shivajinagar corridor"
        page = f'<html><head><meta property="og:description" content="{title}. Example Times"></head><body><p>Loading</p></body></html>'.encode()
        self.web.add(PUBLISHER_URL, page)
        data = self.get(self.register(title=title)).get_json()
        self.assertEqual(data["summary_type"], "unavailable")
        self.assertEqual(data["reason"], "no_text")

    def test_robots_txt_is_respected(self):
        self.web.add("https://news.example-times.in/robots.txt", b"User-agent: TBAReader\nDisallow: /\n")
        data = self.get(self.register()).get_json()
        self.assertEqual(data["summary_type"], "unavailable")
        self.assertEqual(data["reason"], "robots")
        self.assertFalse(data["retryable"])
        self.assertEqual(self.web.count(PUBLISHER_URL), 0)

    def test_robots_txt_that_allows_us_does_not_block(self):
        self.web.add("https://news.example-times.in/robots.txt", b"User-agent: *\nDisallow: /private/\n")
        self.assertEqual(self.get(self.register()).get_json()["summary_type"], "article")

    def test_unresolvable_google_link(self):
        ident = self.register(link=GOOGLE_PREFIX + "AU_yqLnope")
        data = self.get(ident).get_json()
        self.assertEqual(data["summary_type"], "unavailable")
        self.assertEqual(data["reason"], "unresolved")
        self.assertTrue(data["retryable"])
        self.assertEqual(data["original_url"], GOOGLE_PREFIX + "AU_yqLnope")

    def test_retry_flow_and_cooldown(self):
        ident = self.register()
        self.web.fail(PUBLISHER_URL, requests.ConnectionError("boom"))
        first = self.get(ident).get_json()
        self.assertEqual((first["summary_type"], first["reason"]), ("unavailable", "error"))
        self.assertTrue(first["retryable"])
        self.get(ident)                                              # plain repeat: served from cache
        self.assertEqual(self.web.count(PUBLISHER_URL), 1)
        self.web.add(PUBLISHER_URL, publisher_html())
        self.assertEqual(self.get(ident, retry=True).get_json()["summary_type"], "unavailable")   # inside cooldown
        self.assertEqual(self.web.count(PUBLISHER_URL), 1)
        with patch.object(app, "RETRY_COOLDOWN", 0):
            time.sleep(0.01)
            self.assertEqual(self.get(ident, retry=True).get_json()["summary_type"], "article")
        self.assertEqual(self.web.count(PUBLISHER_URL), 2)

    def test_expired_and_invalid_ids(self):
        self.assertEqual(self.get("0" * 20).status_code, 404)
        self.assertEqual(self.get("short").status_code, 400)

    def test_rss_direct_publisher_link_wins_over_google_link(self):
        link = GOOGLE_PREFIX + "AU_yqLneedsgoogle"
        ident = self.register(link=link)
        app.PUBLISHER_LINKS[ident] = (PUBLISHER_URL, time.time())
        self.assertEqual(self.get(ident).get_json()["summary_type"], "article")

    def test_non_google_feed_link_is_fetched_directly(self):
        ident = self.register(link=PUBLISHER_URL)
        self.assertEqual(self.get(ident).get_json()["summary_type"], "article")

    def test_partial_article_is_labelled(self):
        ld = {"@type": "NewsArticle", "isAccessibleForFree": False}
        self.web.add(PUBLISHER_URL, publisher_html(extra_head=f'<script type="application/ld+json">{json.dumps(ld)}</script>'))
        data = self.get(self.register()).get_json()
        self.assertEqual(data["summary_type"], "partial")
        self.assertIn("freely available portion", data["message"])


# --------------------------------------------------------------------------------------------
# /api/image
# --------------------------------------------------------------------------------------------
class ImageEndpointTests(AppTestCase):
    def img(self, ident):
        return self.client.get(f"/api/image/{ident}")

    def test_feed_image_is_served_and_cached(self):
        self.web.add("https://cdn.example/feed.jpg", jpeg())
        ident = self.register(images=["https://cdn.example/feed.jpg"])
        res = self.img(ident)
        self.assertEqual((res.status_code, res.mimetype), (200, "image/jpeg"))
        self.assertEqual(self.img(ident).status_code, 200)
        self.assertEqual(self.web.count("https://cdn.example/feed.jpg"), 1)
        self.assertEqual(self.web.calls.count(PUBLISHER_URL), 0)         # page never needed
        self.assertEqual(res.headers["X-Content-Type-Options"], "nosniff")

    def test_publisher_og_image_with_relative_url(self):
        self.web.add(PUBLISHER_URL, publisher_html(image="/media/metro-line.jpg"))
        self.web.add("https://news.example-times.in/media/metro-line.jpg", jpeg(1200, 630))
        res = self.img(self.register())
        self.assertEqual(res.status_code, 200)
        Image.open(BytesIO(res.data)).verify()

    def test_falls_back_to_page_when_feed_image_is_broken(self):
        self.web.fail("https://cdn.example/dead.jpg", requests.HTTPError("410 Gone"))
        self.web.add(PUBLISHER_URL, publisher_html(image="https://cdn.example/ok.jpg"))
        self.web.add("https://cdn.example/ok.jpg", jpeg())
        self.assertEqual(self.img(self.register(images=["https://cdn.example/dead.jpg"])).status_code, 200)

    def test_no_image_anywhere_gives_404_without_refetch_loop(self):
        self.web.add(PUBLISHER_URL, publisher_html(image=None))
        ident = self.register()
        for _ in range(5):
            self.assertEqual(self.img(ident).status_code, 404)
        self.assertEqual(self.web.count(PUBLISHER_URL), 1)

    def test_broken_blocked_and_wrong_files_are_404_and_cached(self):
        for name, route in (("broken", requests.ConnectionError("down")), ("blocked", app.FetchBlocked(403)), ("html", (b"<html>not an image</html>", "x")), ("tiny", None)):
            url = f"https://cdn.example/{name}.jpg"
            if name == "tiny":
                self.web.add(url, jpeg(100, 100))                           # tiny and square: looks like an icon
            elif isinstance(route, Exception):
                self.web.fail(url, route)
            else:
                self.web.routes[url] = route
            ident = self.register(link=f"https://pub.example/{name}", images=[url])
            self.web.add(f"https://pub.example/{name}", publisher_html(image=None))
            for _ in range(3):
                self.assertEqual(self.img(ident).status_code, 404, name)
            self.assertEqual(self.web.count(url), 1, name)

    def test_google_branding_never_served(self):
        self.web.add(PUBLISHER_URL, publisher_html(image="https://news.google.com/images/branding/google-news-512.png"))
        self.web.add("https://news.google.com/images/branding/google-news-512.png", jpeg())
        self.assertEqual(self.img(self.register()).status_code, 404)
        self.assertEqual(self.web.count("https://news.google.com/images/branding/google-news-512.png"), 0)

    def test_large_image_is_downscaled(self):
        self.web.add("https://cdn.example/huge.jpg", jpeg(2400, 1200))
        res = self.img(self.register(images=["https://cdn.example/huge.jpg"]))
        self.assertEqual(res.status_code, 200)
        self.assertLessEqual(Image.open(BytesIO(res.data)).size[0], 1000)

    def test_decompression_bomb_rejected(self):
        out = BytesIO()
        Image.new("1", (9000, 9000)).save(out, "PNG")
        self.assertIsNone(app.prepare_image(out.getvalue()))

    def test_expired_and_invalid_ids(self):
        self.assertEqual(self.img("0" * 20).status_code, 404)
        self.assertEqual(self.img("bad").status_code, 400)

    def test_image_and_article_share_one_page_fetch(self):
        self.web.add(PUBLISHER_URL, publisher_html())
        self.web.add("https://news.example-times.in/media/metro-line.jpg", jpeg())
        ident = self.register()
        self.img(ident)
        self.client.get(f"/api/article/{ident}")
        self.assertEqual(self.web.count(PUBLISHER_URL), 1)


if __name__ == '__main__':
    unittest.main()
