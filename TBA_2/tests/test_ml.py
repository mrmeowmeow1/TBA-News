"""Tests for the AI/ML layer (services/) and its Flask integration.  All network access is mocked.

Run everything with:  python -m unittest discover -s tests
"""
import json
import os
import time
import unittest
from unittest.mock import MagicMock, patch

import requests

import app
from services import ai_summarizer, categorizer, config, enrichment, sentiment, similarity
from services.similarity import group_duplicates, recommend
from test_app import (ARTICLE_PARAGRAPHS, GOOGLE_PREFIX, LONG_TEXT, PUBLISHER_URL, SHORT_TEXT, AppTestCase,
                      make_token, publisher_html)
import eval_categorizer
import eval_duplicates

os.environ["TBA_AI_API_KEY"] = ""      # a real key in the developer's shell must never be used by tests
FAKE_KEY = "sk-test-SECRET-1234567890"


# ==============================================================================================
# Sentiment
# ==============================================================================================
class SentimentTests(unittest.TestCase):
    def label(self, text, kind="headline"):
        return sentiment.analyze_sentiment(text, kind)["label"]

    def test_positive_negative_neutral_examples(self):
        self.assertEqual(self.label("India beat Australia by 5 wickets to win the series"), "Positive")
        self.assertEqual(self.label("Sensex surges 800 points as markets rally on strong earnings"), "Positive")
        self.assertEqual(self.label("Floods kill 12 in Assam, thousands displaced"), "Negative")
        self.assertEqual(self.label("Tech layoffs hit thousands of workers"), "Negative")
        self.assertEqual(self.label("Parliament passes the Finance Bill after a long debate"), "Neutral")
        self.assertEqual(self.label("RBI keeps repo rate unchanged at 6.5%"), "Neutral")

    def test_lexicon_score_is_not_presented_as_confidence(self):
        r = sentiment.analyze_sentiment("Floods kill 12 in Assam, thousands displaced")
        self.assertIsNone(r["confidence"])
        self.assertEqual(r["score_kind"], "lexicon_polarity")
        self.assertLess(r["score"], 0)
        self.assertIn("vader", r["method"])

    def test_empty_malformed_and_unsupported_input_never_crashes(self):
        for bad in ("", "   ", None, 42, 3.5, [], {}, b"bytes", "!!!???", "\x00\x01\x02", "12345"):
            r = sentiment.analyze_sentiment(bad)
            self.assertFalse(r["available"], bad)
            self.assertIsNone(r["label"])
        r = sentiment.analyze_sentiment("आज की ताज़ा खबर यहाँ पढ़ें")
        self.assertFalse(r["available"])
        self.assertEqual(r["reason"], "unsupported_language")

    def test_very_long_text_is_bounded(self):
        started = time.time()
        r = sentiment.analyze_sentiment("The council approved the plan. " * 20000, "article")
        self.assertTrue(r["available"])
        self.assertLess(time.time() - started, 3)

    def test_financial_news_carries_the_not_investment_advice_note(self):
        r = sentiment.analyze_sentiment("Sensex surges 800 points as investors rally")
        self.assertTrue(r["financial"])
        self.assertIn("not investment advice", r["note"])
        plain = sentiment.analyze_sentiment("India beat Australia by 5 wickets to win the series")
        self.assertFalse(plain["financial"])
        self.assertIsNone(plain["note"])
        by_topic = sentiment.analyze_sentiment("Company announces new chief", topic="Business")
        self.assertTrue(by_topic["financial"])

    def test_article_mode_uses_sentence_scores(self):
        good = "The team won the final. Fans celebrated a wonderful victory. The captain praised a brilliant performance by everyone."
        bad = "The attack killed many people. Officials condemned the terrible violence. Hospitals reported dozens of injured victims."
        self.assertEqual(sentiment.analyze_sentiment(good, "article")["label"], "Positive")
        self.assertEqual(sentiment.analyze_sentiment(bad, "article")["label"], "Negative")
        self.assertEqual(sentiment.analyze_sentiment(LONG_TEXT, "article")["available"], True)

    def test_optional_transformer_backend_returns_model_confidence(self):
        fake = MagicMock(return_value=[[{"label": "negative", "score": 0.91}, {"label": "neutral", "score": 0.06}, {"label": "positive", "score": 0.03}]])
        with patch.dict(os.environ, {"TBA_SENTIMENT_BACKEND": "transformers"}), patch.object(sentiment, "_load_transformer", return_value=fake):
            r = sentiment.analyze_sentiment("Floods kill 12 in Assam")
        self.assertEqual((r["label"], r["confidence"]), ("Negative", 0.91))
        self.assertTrue(r["method"].startswith("transformers:"))
        self.assertIsNone(r["score"])

    def test_transformer_failure_falls_back_to_vader(self):
        broken = MagicMock(side_effect=RuntimeError("out of memory"))
        with patch.dict(os.environ, {"TBA_SENTIMENT_BACKEND": "transformers"}), patch.object(sentiment, "_load_transformer", return_value=broken):
            r = sentiment.analyze_sentiment("Floods kill 12 in Assam, thousands displaced")
        self.assertEqual(r["label"], "Negative")
        self.assertIn("vader", r["method"])

    def test_transformer_not_installed_falls_back_to_vader(self):
        with patch.dict(os.environ, {"TBA_SENTIMENT_BACKEND": "transformers"}), patch.object(sentiment, "_transformer", None), \
                patch.dict("sys.modules", {"transformers": None}):
            r = sentiment.analyze_sentiment("India beat Australia by 5 wickets to win the series")
        self.assertEqual(r["label"], "Positive")
        self.assertIn("vader", r["method"])
        sentiment._transformer = None


# ==============================================================================================
# Categorisation
# ==============================================================================================
class CategorizerTests(unittest.TestCase):
    def topic(self, title, description=""):
        return categorizer.classify_topic(title, description)["label"]

    def test_representative_headlines(self):
        cases = {
            "Lok Sabha passes bill amid opposition walkout": "Politics",
            "Sensex jumps 400 points as banking shares rally": "Business",
            "OpenAI launches new AI model for developers": "Technology",
            "India beat Australia by five wickets in the second ODI": "Sports",
            "Bollywood actor's new film crosses box office record": "Entertainment",
            "Ceasefire talks resume between Israel and Hamas": "World",
            "NASA telescope spots distant galaxy": "Science",
            "Dengue cases rise in Mumbai hospitals": "Health",
            "CBSE announces board exam results": "Education",
        }
        for title, expected in cases.items():
            self.assertEqual(self.topic(title), expected, title)

    def test_uninformative_or_bad_input_falls_back_to_general(self):
        for bad in ("", "Weather today", "Live updates", "You won't believe what happened next", None, 42, "!!!"):
            r = categorizer.classify_topic(bad)
            self.assertEqual(r["label"], "General", bad)
            self.assertIsNone(r["score"])

    def test_score_is_a_similarity_not_a_confidence(self):
        r = categorizer.classify_topic("CBSE announces board exam results")
        self.assertIsNone(r["confidence"])
        self.assertTrue(0 < r["score"] <= 1)
        self.assertIn("exam", r["matched"])
        self.assertIn("similarity", r["method"])

    def test_description_can_resolve_a_vague_headline(self):
        self.assertEqual(self.topic("Big day ahead", "The cricket match between the two teams starts with the captain winning the toss and bowlers ready."), "Sports")

    def test_regression_floor_on_the_hand_written_sets(self):
        # Floors protect against accidental regressions; they are not a claim about real-world accuracy.
        self.assertGreaterEqual(eval_categorizer.accuracy(eval_categorizer.DEV), 0.90)
        self.assertGreaterEqual(eval_categorizer.accuracy(eval_categorizer.TEST), 0.85)


# ==============================================================================================
# Duplicate detection
# ==============================================================================================
FEED = [
    "Pune metro Line 3 extension approved by council",      # 0
    "Sensex jumps 400 points on banking rally",              # 1
    "Council approves Line 3 metro extension in Pune",       # 2  same story as 0
    "Sensex falls 300 points as IT stocks drag",             # 3  same category, different story
    "Dengue cases cross 2,000 in Pune this season",          # 4
    "Pune dengue cases cross 2,000 this season",             # 5  same story as 4
    "India beat Australia by five wickets in Mumbai ODI",    # 6
    "Football club sacks coach after league defeat",         # 7
    "Fire at chemical factory in Surat kills six",           # 8
    "Six dead after chemical factory fire in Surat",         # 9  same story as 8
]


class DuplicateTests(unittest.TestCase):
    def test_identical_headlines_are_grouped(self):
        _, group_of, _ = group_duplicates(["Council approves metro", "Council approves metro", "Something else entirely different"], 0.5)
        self.assertEqual(group_of[0], group_of[1])
        self.assertNotEqual(group_of[0], group_of[2])

    def test_reworded_headlines_group_and_unrelated_ones_do_not(self):
        groups, group_of, match = group_duplicates(FEED, 0.5)
        pairs = {tuple(g) for g in groups if len(g) > 1}
        self.assertEqual(pairs, {(0, 2), (4, 5), (8, 9)})
        self.assertNotEqual(group_of[1], group_of[3], "two different Sensex stories must stay separate")
        self.assertIsNone(match[0])
        self.assertGreaterEqual(match[2], 0.5)

    def test_every_article_is_kept_exactly_once(self):
        groups, group_of, _ = group_duplicates(FEED, 0.5)
        self.assertEqual(sorted(i for g in groups for i in g), list(range(len(FEED))))
        self.assertTrue(all(0 <= g < len(groups) for g in group_of))

    def test_threshold_is_configurable(self):
        strict = group_duplicates(FEED, 0.95)[0]
        loose = group_duplicates(FEED, 0.15)[0]
        self.assertEqual(len(strict), len(FEED))
        self.assertLess(len(loose), len(strict))
        with patch.dict(os.environ, {"TBA_DUPLICATE_THRESHOLD": "0.8"}):
            self.assertEqual(config.duplicate_threshold(), 0.8)
        with patch.dict(os.environ, {"TBA_DUPLICATE_THRESHOLD": "nonsense"}):
            self.assertEqual(config.duplicate_threshold(), 0.50)
        with patch.dict(os.environ, {"TBA_DUPLICATE_THRESHOLD": "7"}):
            self.assertEqual(config.duplicate_threshold(), 0.95)

    def test_sharing_a_single_word_is_never_enough(self):
        # Even at a very low threshold, one common word must not merge two stories.
        groups = group_duplicates(["Flood warning issued", "Flood", "Stocks crash"], 0.1, min_shared=2)[0]
        self.assertEqual(len(groups), 3)

    def test_empty_and_degenerate_inputs(self):
        self.assertEqual(group_duplicates([], 0.5)[0], [])
        self.assertEqual(group_duplicates(["only one"], 0.5)[0], [[0]])
        self.assertEqual(len(group_duplicates(["", "", "the and of"], 0.5)[0]), 3)

    def test_threshold_study_reports_known_trade_offs(self):
        r = eval_duplicates.score_pairs(0.50)
        self.assertGreaterEqual(r["precision"], 0.85)
        self.assertGreaterEqual(r["recall"], 0.80)

    def test_enrichment_labels_but_never_removes_or_alters_items(self):
        items = [{"id": f"{i:020x}", "title": t, "source": f"Pub {i}", "url": f"https://pub{i}.example/a", "published": f"2026-10-14T0{i % 9}:00:00+00:00",
                  "description": "d", "category": "top", "image": None} for i, t in enumerate(FEED)]
        originals = [dict(i) for i in items]
        out = enrichment.enrich_items(items)
        self.assertEqual(len(out), len(FEED))
        for before, after in zip(originals, out):
            for key, value in before.items():
                self.assertEqual(after[key], value)             # publisher, link, timestamp untouched
            self.assertIn(after["topic"]["label"], categorizer.CATEGORIES + ["General"])
            self.assertIn("available", after["sentiment"])
        lead, copy = out[0], out[2]
        self.assertTrue(lead["story"]["lead"] and not copy["story"]["lead"])
        self.assertEqual(lead["story"]["size"], 2)
        self.assertEqual(copy["also_covered_by"][0]["source"], "Pub 0")        # original publisher preserved
        self.assertEqual(copy["also_covered_by"][0]["url"], "https://pub0.example/a")
        self.assertEqual(out[1]["also_covered_by"], [])
        self.assertEqual(enrichment.enrich_items([]), [])


# ==============================================================================================
# Recommendations
# ==============================================================================================
def make_pool(titles, topics=None):
    pool = []
    for i, title in enumerate(titles):
        topic = (topics or {}).get(i)
        pool.append({"id": f"{i:020x}", "text": title, "topic": {"label": topic} if topic else None})
    return pool


REC_FEED = [
    "OpenAI launches new AI model for developers",            # 0  <- open article
    "Google unveils AI model to rival OpenAI chatbot",        # 1  related
    "Microsoft adds AI assistant to cloud software for developers",  # 2 related
    "Open AI launches new AI model for developers today",     # 3  copy of 0
    "Monsoon rains lash Kerala, schools closed",              # 4  unrelated
    "Football club sacks coach after league defeat",          # 5  unrelated
    "Sensex jumps 400 points on banking rally",               # 6  unrelated
    "Dengue cases rise in Mumbai hospitals",                  # 7  unrelated
]
REC_TOPICS = {0: "Technology", 1: "Technology", 2: "Technology", 3: "Technology", 4: "World", 5: "Sports", 6: "Business", 7: "Health"}


class RecommendationTests(unittest.TestCase):
    def setUp(self):
        similarity.VECTOR_CACHE.clear()
        self.pool = make_pool(REC_FEED, REC_TOPICS)
        self.ids = [p["id"] for p in self.pool]

    def test_related_articles_rank_above_unrelated_ones(self):
        r = recommend(self.ids[0], self.pool, limit=4)
        ranked = [self.ids.index(x["id"]) for x in r["items"]]
        self.assertEqual(set(ranked[:2]), {1, 2})
        self.assertFalse(r["fallback"])
        self.assertTrue(all(x["reasons"] for x in r["items"]))

    def test_current_article_and_its_duplicates_are_excluded(self):
        r = recommend(self.ids[0], self.pool, limit=8)
        returned = [x["id"] for x in r["items"]]
        self.assertNotIn(self.ids[0], returned)
        self.assertNotIn(self.ids[3], returned, "another copy of the same story is not a recommendation")

    def test_only_one_article_per_duplicate_group_is_recommended(self):
        titles = ["Space agency launches Mars probe", "Mars probe launched by space agency today", "Space agency launches Mars probe on Friday",
                  "Space agency announces new moon telescope"]
        pool = make_pool(titles)
        r = recommend(pool[3]["id"], pool, limit=4)
        got = [x["id"] for x in r["items"] if not x["fallback"]]
        self.assertLessEqual(len(set(got) & {pool[0]["id"], pool[1]["id"], pool[2]["id"]}), 1)

    def test_saved_stories_re_rank_related_articles(self):
        # Saved stories re-rank candidates that are already related to the open article.
        titles = ["Government unveils new technology policy for startups",
                  "Startups welcome government technology policy on funding",
                  "Cricket board unveils new technology for umpire reviews",
                  "Football league announces new broadcasting deal",
                  "Heavy rain forecast for coastal districts"]
        pool = make_pool(titles)
        plain = recommend(pool[0]["id"], pool, limit=4)["items"]
        biased = recommend(pool[0]["id"], pool, saved_titles=["Cricket team wins final", "Cricket captain scores century"], limit=4)["items"]
        cricket = pool[2]["id"]
        score = lambda items: next(x["score"] for x in items if x["id"] == cricket)
        self.assertGreater(score(biased), score(plain))
        self.assertIn("Matches your saved stories", next(x for x in biased if x["id"] == cricket)["reasons"])
        self.assertNotIn("Matches your saved stories", next(x for x in plain if x["id"] == cricket)["reasons"])
        returned = {x["id"] for x in biased}
        self.assertNotIn(pool[4]["id"], returned, "saved stories must not pull in an unrelated article")

    def test_malformed_saved_titles_are_ignored(self):
        r = recommend(self.ids[0], self.pool, saved_titles=[None, 5, {}, "", "   ", "x" * 5000], limit=3)
        self.assertTrue(r["items"])

    def test_fallback_when_nothing_is_similar(self):
        pool = make_pool(["Alpha bravo charlie delta", "Echo foxtrot golf hotel", "India juliet kilo lima"])
        r = recommend(pool[0]["id"], pool, limit=3)
        self.assertTrue(r["fallback"])
        self.assertTrue(all(x["fallback"] and x["score"] is None for x in r["items"]))

    def test_too_few_articles_and_unknown_ids(self):
        one = make_pool(["Only story"])
        self.assertEqual(recommend(one[0]["id"], one)["message"], "not_enough_articles")
        self.assertEqual(recommend("f" * 20, self.pool)["message"], "unknown_article")
        self.assertEqual(recommend("f" * 20, [])["items"], [])

    def test_vectors_are_cached_between_requests(self):
        with patch.object(similarity, "_fit", wraps=similarity._fit) as fit:
            recommend(self.ids[0], self.pool)
            recommend(self.ids[1], self.pool)
            recommend(self.ids[2], self.pool)
        self.assertEqual(fit.call_count, 1)


# ==============================================================================================
# Optional AI summary (provider mocked)
# ==============================================================================================
GOOD_AI_JSON = {
    "overview": "The Pune Metropolitan Council on Tuesday approved a 14-kilometre extension of Line 3, with construction due to begin before the end of March 2027.",
    "key_points": [
        "Council chairperson Meera Kulkarni said the extension would connect Hinjewadi with the Shivajinagar interchange.",
        "The project will cost about ₹8,400 crore, with 40% coming from the state government.",
        "The council voted 41 to 12 in favour of the extension.",
    ],
    "background": ["Line 3 was first proposed in 2018."],
    "whats_next": ["A public hearing on the final station designs is scheduled for next month."],
}


class FakeHTTP:
    def __init__(self, status=200, body=None, headers=None, raw_content=None):
        self.status_code, self.headers = status, headers or {}
        self._body = body if body is not None else {"choices": [{"message": {"content": raw_content if raw_content is not None else json.dumps(GOOD_AI_JSON)}}]}

    def json(self):
        if isinstance(self._body, Exception):
            raise self._body
        return self._body


def ai_env(**extra):
    env = {"TBA_AI_API_KEY": FAKE_KEY, "TBA_AI_BASE_URL": "https://api.example-llm.test/v1", "TBA_AI_MODEL": "test-model"}
    env.update(extra)
    return patch.dict(os.environ, env)


class AISummarizerTests(unittest.TestCase):
    def setUp(self):
        ai_summarizer.reset_cooldown()

    def call(self, response, text=LONG_TEXT):
        with ai_env(), patch.object(ai_summarizer.requests, "post", return_value=response) as post:
            return ai_summarizer.summarize("Council approves metro extension", text, "Example Times"), post

    def test_not_configured_makes_no_request(self):
        with patch.dict(os.environ, {"TBA_AI_API_KEY": ""}), patch.object(ai_summarizer.requests, "post") as post:
            result = ai_summarizer.summarize("t", LONG_TEXT)
        self.assertEqual(result["status"], "not_configured")
        post.assert_not_called()
        self.assertFalse(ai_summarizer.is_configured() and False)

    def test_success_sends_key_only_in_header_with_timeouts(self):
        result, post = self.call(FakeHTTP())
        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["model"], "test-model")
        self.assertEqual(result["overview"]["intro"], GOOD_AI_JSON["overview"])
        args, kwargs = post.call_args
        self.assertEqual(args[0], "https://api.example-llm.test/v1/chat/completions")
        self.assertEqual(kwargs["headers"]["Authorization"], f"Bearer {FAKE_KEY}")
        self.assertIsInstance(kwargs["timeout"], tuple)
        self.assertNotIn(FAKE_KEY, json.dumps(kwargs["json"]))
        self.assertNotIn(FAKE_KEY, args[0])
        user = kwargs["json"]["messages"][1]["content"]
        self.assertIn("<article>", user)
        self.assertIn("Pune Metropolitan Council", user)

    def test_fenced_json_is_accepted(self):
        result, _ = self.call(FakeHTTP(raw_content="```json\n" + json.dumps(GOOD_AI_JSON) + "\n```"))
        self.assertEqual(result["status"], "ok")

    def test_failures_return_status_and_never_raise(self):
        cases = [(requests.Timeout("slow"), "timeout"), (requests.ConnectionError("down"), "unreachable")]
        for exc, status in cases:
            ai_summarizer.reset_cooldown()
            with ai_env(), patch.object(ai_summarizer.requests, "post", side_effect=exc):
                r = ai_summarizer.summarize("t", LONG_TEXT)
            self.assertEqual((r["status"], r["overview"], r["retryable"]), (status, None, True))
        for response, status in ((FakeHTTP(500), "server_error"), (FakeHTTP(404), "http_error"), (FakeHTTP(200, body=ValueError("not json")), "bad_response"),
                                 (FakeHTTP(200, body={"unexpected": 1}), "bad_response"), (FakeHTTP(200, raw_content="Sorry, I can't"), "bad_response"),
                                 (FakeHTTP(200, raw_content=json.dumps({"overview": "x", "key_points": "not a list"})), "bad_response")):
            ai_summarizer.reset_cooldown()
            r, _ = self.call(response)
            self.assertEqual((r["status"], r["overview"]), (status, None), status)

    def test_rate_limit_starts_a_cooldown_so_the_provider_is_not_hammered(self):
        first, post = self.call(FakeHTTP(429, headers={"Retry-After": "40"}))
        self.assertEqual(first["status"], "rate_limited")
        with ai_env(), patch.object(ai_summarizer.requests, "post") as post2:
            second = ai_summarizer.summarize("t", LONG_TEXT)
        self.assertEqual(second["status"], "cooldown")
        post2.assert_not_called()

    def test_bad_credentials_are_not_retried_and_the_key_is_never_logged(self):
        with self.assertLogs("tba.ai", "WARNING") as logs:
            r, _ = self.call(FakeHTTP(401))
        self.assertEqual(r["status"], "auth_error")
        self.assertFalse(r["retryable"])
        self.assertNotIn(FAKE_KEY, "\n".join(logs.output))

    def test_invented_numbers_quotes_and_names_are_rejected(self):
        for field, bad in (("overview", "The council approved a 99-kilometre extension of Line 3."),
                           ("key_points", ['Chairperson Meera Kulkarni said "we will cancel everything immediately" on Tuesday.']),
                           ("background", ["Mayor Rajesh Deshpande opposed the plan in Mumbai."])):
            data = {**GOOD_AI_JSON, field: bad}
            r, _ = self.call(FakeHTTP(raw_content=json.dumps(data)))
            self.assertEqual(r["status"], "rejected", field)
            self.assertIsNone(r["overview"])
            self.assertTrue(r["problems"])

    def test_grounding_checker_accepts_supported_claims(self):
        pieces = [GOOD_AI_JSON["overview"], *GOOD_AI_JSON["key_points"], *GOOD_AI_JSON["background"], *GOOD_AI_JSON["whats_next"]]
        self.assertEqual(ai_summarizer.check_grounding(pieces, LONG_TEXT), [])
        self.assertTrue(ai_summarizer.check_grounding(["It cost ₹9,999 crore."], LONG_TEXT))

    def test_insecure_or_unusable_endpoints_are_refused(self):
        with ai_env(TBA_AI_BASE_URL="http://api.example-llm.test/v1"), patch.object(ai_summarizer.requests, "post") as post:
            r = ai_summarizer.summarize("t", LONG_TEXT)
        self.assertEqual(r["status"], "misconfigured")
        post.assert_not_called()
        with ai_env(TBA_AI_BASE_URL="http://localhost:11434/v1"), patch.object(ai_summarizer.requests, "post", return_value=FakeHTTP()) as post:
            self.assertEqual(ai_summarizer.summarize("t", LONG_TEXT)["status"], "ok")
        post.assert_called_once()

    def test_short_or_empty_source_is_not_sent_to_the_provider(self):
        for text in ("", SHORT_TEXT, None):
            with ai_env(), patch.object(ai_summarizer.requests, "post") as post:
                self.assertEqual(ai_summarizer.summarize("t", text)["status"], "source_too_short")
            post.assert_not_called()


# ==============================================================================================
# Flask integration
# ==============================================================================================
def rss(entries):
    items = "".join(f"<item><title>{t} - {s}</title><link>{l}</link><pubDate>Wed, 14 Oct 2026 0{i % 9}:00:00 GMT</pubDate>"
                    f"<description>&lt;a href=\"{l}\"&gt;{t}&lt;/a&gt;&amp;nbsp;&lt;font&gt;{s}&lt;/font&gt;</description><source url=\"https://{s.lower().replace(' ', '')}.example\">{s}</source></item>"
                    for i, (t, s, l) in enumerate(entries))
    return f'<?xml version="1.0"?><rss version="2.0"><channel><title>t</title>{items}</channel></rss>'.encode()


FEED_ENTRIES = [(t, f"Pub {i}", f"https://pub{i}.example/story-{i}") for i, t in enumerate(REC_FEED)]


class MLAppCase(AppTestCase):
    def setUp(self):
        super().setUp()
        # Legacy fixtures deliberately exercise the Google News compatibility path.
        # Production remains on the five direct publisher feeds.
        source_patch = patch.object(app, "NEWS_SOURCE", "google")
        source_patch.start()
        self.addCleanup(source_patch.stop)
        ai_summarizer.reset_cooldown()
        similarity.VECTOR_CACHE.clear()
        env = patch.dict(os.environ, {"TBA_AI_API_KEY": ""})      # never reach a real provider from tests
        env.start()
        self.addCleanup(env.stop)

    def load_feed(self, entries=FEED_ENTRIES, category="top"):
        url = app.feed_url(category, "")
        self.web.add(url, rss(entries))
        return self.client.get(f"/api/news?category={category}&refresh=1")


class NewsEndpointMLTests(MLAppCase):
    def test_feed_items_carry_ml_fields_and_keep_every_original_field(self):
        data = self.load_feed().get_json()
        self.assertEqual(len(data["items"]), len(REC_FEED))
        for item in data["items"]:
            for key in ("id", "title", "source", "url", "published", "description", "category", "image"):
                self.assertIn(key, item)
            self.assertIn("topic", item)
            self.assertIn("sentiment", item)
            self.assertIn("story", item)
        first = data["items"][0]
        self.assertEqual(first["topic"]["label"], "Technology")
        self.assertEqual(first["source"], "Pub 0")
        self.assertEqual(first["url"], "https://pub0.example/story-0")

    def test_duplicate_stories_are_grouped_across_publishers_without_deleting(self):
        items = self.load_feed().get_json()["items"]
        lead, copy = items[0], items[3]
        self.assertEqual(lead["story"]["id"], copy["story"]["id"])
        self.assertTrue(lead["story"]["lead"] and not copy["story"]["lead"])
        self.assertEqual({o["source"] for o in lead["also_covered_by"]}, {"Pub 3"})
        self.assertEqual({o["source"] for o in copy["also_covered_by"]}, {"Pub 0"})

    def test_an_ml_failure_never_hides_the_news(self):
        with patch.object(app, "enrich_items", side_effect=RuntimeError("boom")):
            r = self.load_feed()
        self.assertEqual(r.status_code, 200)
        items = r.get_json()["items"]
        self.assertEqual(len(items), len(REC_FEED))
        self.assertNotIn("topic", items[0])

    def test_feed_is_enriched_once_and_then_served_from_cache(self):
        self.load_feed()
        with patch.object(app, "enrich_items") as enrich:
            cached = self.client.get("/api/news?category=top").get_json()
        enrich.assert_not_called()
        self.assertTrue(cached["cached"])
        self.assertIn("sentiment", cached["items"][0])

    def test_malformed_feed_xml_is_handled(self):
        self.web.add(app.feed_url("top", ""), b"<rss><channel><item><title>broken")
        r = self.client.get("/api/news?category=top&refresh=1")
        self.assertIn(r.status_code, (200, 502))


class RecommendationEndpointTests(MLAppCase):
    def setUp(self):
        super().setUp()
        self.items = self.load_feed().get_json()["items"]
        self.ids = [i["id"] for i in self.items]

    def test_returns_related_stories_without_the_current_one_or_its_duplicate(self):
        data = self.client.get(f"/api/recommendations/{self.ids[0]}").get_json()
        got = [i["id"] for i in data["items"]]
        self.assertNotIn(self.ids[0], got)
        self.assertNotIn(self.ids[3], got)
        self.assertEqual({i["title"] for i in data["items"][:2]}, {REC_FEED[1], REC_FEED[2]})
        self.assertTrue(all(i["recommendation"]["reasons"] for i in data["items"]))
        self.assertTrue(all(i["url"].startswith("https://") for i in data["items"]))     # original links preserved

    def test_post_with_saved_titles_is_accepted_and_nothing_is_stored(self):
        r = self.client.post(f"/api/recommendations/{self.ids[0]}", json={"saved_titles": ["Cricket captain scores century", 7, None]})
        self.assertEqual(r.status_code, 200)
        self.assertNotIn("Cricket captain", json.dumps(list(app.FEED_META.values()), default=str))

    def test_validation(self):
        self.assertEqual(self.client.get("/api/recommendations/not-an-id").status_code, 400)
        self.assertEqual(self.client.get("/api/recommendations/" + "0" * 20).status_code, 404)
        self.assertEqual(self.client.post(f"/api/recommendations/{self.ids[0]}", json=["x"]).status_code, 400)
        self.assertEqual(self.client.post(f"/api/recommendations/{self.ids[0]}", json={"saved_titles": "nope"}).status_code, 400)
        self.assertEqual(self.client.post(f"/api/recommendations/{self.ids[0]}", data="{bad json", content_type="application/json").status_code, 200)

    def test_story_registered_without_feed_metadata_still_works(self):
        extra = self.register(title="Cloud software update for developers", source="Example Times")
        data = self.client.get(f"/api/recommendations/{extra}").get_json()
        self.assertIn("items", data)


class SummaryIntegrationTests(MLAppCase):
    def setUp(self):
        super().setUp()
        self.web.add(PUBLISHER_URL, publisher_html())

    def get(self, ident, retry=False):
        return self.client.get(f"/api/article/{ident}" + ("?retry=1" if retry else "")).get_json()

    def test_without_an_api_key_the_local_extractive_summary_is_used(self):
        with patch.object(ai_summarizer.requests, "post") as post:
            data = self.get(self.register())
        post.assert_not_called()
        self.assertEqual((data["summary_type"], data["summary_method"], data["ai"]["status"]), ("article", "extractive", "not_configured"))
        self.assertIsNone(data["message"])
        self.assertIn(data["sentiment"]["label"], ("Positive", "Neutral", "Negative"))

    def test_with_a_key_the_validated_ai_summary_is_used_and_labelled(self):
        with ai_env(), patch.object(ai_summarizer.requests, "post", return_value=FakeHTTP()) as post:
            data = self.get(self.register())
        self.assertEqual(post.call_count, 1)
        self.assertEqual((data["summary_method"], data["ai"]["used"], data["ai"]["model"]), ("ai", True, "test-model"))
        self.assertEqual(data["intro"], GOOD_AI_JSON["overview"])
        self.assertEqual(data["points"], GOOD_AI_JSON["key_points"])
        self.assertIn("checked against the article", data["message"])
        self.assertIn("Meera Kulkarni", data["details"]["names"])           # names/figures stay verbatim from the source
        self.assertNotIn(FAKE_KEY, json.dumps(data))

    def test_ai_timeout_falls_back_to_extractive_with_an_honest_note(self):
        with ai_env(), patch.object(ai_summarizer.requests, "post", side_effect=requests.Timeout("slow")):
            data = self.get(self.register())
        self.assertEqual((data["summary_type"], data["summary_method"]), ("article", "extractive"))
        self.assertIn("AI summary unavailable", data["message"])
        self.assertIn("timed out", data["message"])
        self.assertTrue(data["ai_retryable"])
        source = set(app.split_sentences(LONG_TEXT))
        for sentence in app.split_sentences(data["summary"]):
            self.assertIn(sentence, source)                                # still only real article sentences

    def test_ai_output_that_fails_grounding_is_never_shown(self):
        bad = {**GOOD_AI_JSON, "overview": "The council approved a 99-kilometre extension of Line 3."}
        with ai_env(), patch.object(ai_summarizer.requests, "post", return_value=FakeHTTP(raw_content=json.dumps(bad))):
            data = self.get(self.register())
        self.assertEqual(data["summary_method"], "extractive")
        self.assertNotIn("99", data["summary"])
        self.assertIn("could not be verified", data["message"])

    def test_retry_reaches_the_ai_again_without_refetching_the_publisher(self):
        ident = self.register()
        with ai_env(), patch.object(ai_summarizer.requests, "post", side_effect=requests.Timeout("slow")):
            self.assertEqual(self.get(ident)["summary_method"], "extractive")
        self.assertEqual(self.web.count(PUBLISHER_URL), 1)
        app.ARTICLE_CACHE.get(ident)
        cached = app.ARTICLE_CACHE.get(ident)
        cached["generated_at"] -= 60                                       # skip the 20 s retry cool-down
        with ai_env(), patch.object(ai_summarizer.requests, "post", return_value=FakeHTTP()):
            data = self.get(ident, retry=True)
        self.assertEqual(data["summary_method"], "ai")
        self.assertEqual(self.web.count(PUBLISHER_URL), 1)

    def test_description_fallback_never_calls_the_ai(self):
        self.web.fail(PUBLISHER_URL, requests.HTTPError("403"))
        desc = "The council approved a 14-kilometre extension of the metro line on Tuesday and said construction would start by March next year."
        with ai_env(), patch.object(ai_summarizer.requests, "post") as post:
            data = self.get(self.register(description=desc))
        post.assert_not_called()
        self.assertEqual(data["summary_type"], "description")
        self.assertIn("not a summary of the article", data["message"])

    def test_inaccessible_article_without_description_is_labelled_unavailable(self):
        self.web.fail(PUBLISHER_URL, requests.HTTPError("404"))
        data = self.get(self.register())
        self.assertEqual(data["summary_type"], "unavailable")
        self.assertEqual(data["summary"], "")

    def test_health_endpoint_exposes_only_booleans(self):
        with ai_env():
            body = self.client.get("/api/health").get_data(as_text=True)
        self.assertNotIn(FAKE_KEY, body)
        self.assertNotIn("example-llm", body)
        self.assertIn('"ai_summary_configured":true', body.replace(" ", ""))


class RealSocketAITests(unittest.TestCase):
    """Real HTTP round-trips to a throw-away local OpenAI-compatible server (no mocking of requests)."""

    def setUp(self):
        import threading
        from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
        ai_summarizer.reset_cooldown()
        outer = self
        self.seen, self.mode = [], "ok"

        class Handler(BaseHTTPRequestHandler):
            def do_POST(self):
                body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
                outer.seen.append({"path": self.path, "auth": self.headers.get("Authorization"), "model": body["model"]})
                if outer.mode == "slow":
                    time.sleep(2.5)
                if outer.mode == "429":
                    self.send_response(429); self.send_header("Retry-After", "7"); self.end_headers(); return
                payload = json.dumps({"choices": [{"message": {"content": json.dumps(GOOD_AI_JSON)}}]}).encode()
                try:
                    self.send_response(200); self.send_header("Content-Type", "application/json")
                    self.send_header("Content-Length", str(len(payload))); self.end_headers(); self.wfile.write(payload)
                except OSError:
                    pass

            def log_message(self, *args):
                pass

        self.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        threading.Thread(target=self.server.serve_forever, daemon=True).start()
        self.addCleanup(self.server.shutdown)
        self.addCleanup(self.server.server_close)
        self.env = ai_env(TBA_AI_BASE_URL=f"http://127.0.0.1:{self.server.server_address[1]}/v1", TBA_AI_TIMEOUT="3")

    def test_real_request_success(self):
        with self.env:
            result = ai_summarizer.summarize("Council approves metro extension", LONG_TEXT, "Example Times")
        self.assertEqual(result["status"], "ok")
        self.assertEqual(self.seen[0], {"path": "/v1/chat/completions", "auth": f"Bearer {FAKE_KEY}", "model": "test-model"})

    def test_real_timeout_is_handled(self):
        self.mode = "slow"
        with ai_env(TBA_AI_BASE_URL=f"http://127.0.0.1:{self.server.server_address[1]}/v1", TBA_AI_TIMEOUT="3"), \
                patch.object(config, "_number", side_effect=lambda n, d, lo, hi: 1.0 if n == "TBA_AI_TIMEOUT" else d):
            started = time.time()
            result = ai_summarizer.summarize("t", LONG_TEXT)
        self.assertEqual(result["status"], "timeout")
        self.assertLess(time.time() - started, 2.4)

    def test_real_429_pauses_further_calls(self):
        self.mode = "429"
        with self.env:
            self.assertEqual(ai_summarizer.summarize("t", LONG_TEXT)["status"], "rate_limited")
            self.assertEqual(ai_summarizer.summarize("t", LONG_TEXT)["status"], "cooldown")
        self.assertEqual(len(self.seen), 1)


class NoSecretsInFrontendTests(unittest.TestCase):
    def test_static_files_and_template_contain_no_credentials(self):
        root = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
        for name in ("static/app.js", "static/styles.css", "templates/index.html"):
            with open(os.path.join(root, name), encoding="utf-8") as handle:
                text = handle.read()
            for needle in ("TBA_AI_API_KEY", "api_key", "Bearer ", "sk-", "chat/completions"):
                self.assertNotIn(needle, text, f"{needle} found in {name}")

    def test_env_example_has_no_real_key(self):
        root = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
        with open(os.path.join(root, ".env.example"), encoding="utf-8") as handle:
            text = handle.read()
        self.assertIn("TBA_AI_API_KEY=", text)
        self.assertNotRegex(text, r"(?m)^TBA_AI_API_KEY=[ \t]*\S")


if __name__ == "__main__":
    unittest.main()
