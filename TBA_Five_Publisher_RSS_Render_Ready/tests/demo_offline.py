"""OFFLINE DEMO / TEST FIXTURE - not used by the real application.

Starts TBA with the network replaced by *fictional* sample stories, so every AI/ML feature can be
shown without internet access (for example in a viva with unreliable Wi-Fi) and so the UI can be
checked in a browser.  The headlines, publishers and article text below are invented.

    python tests/demo_offline.py            # then open http://127.0.0.1:5055
    PORT=5060 python tests/demo_offline.py

The real app (python app.py) uses five live publisher RSS feeds and shows no invented articles.
"""
import os
import sys
from io import BytesIO

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, ".."))
sys.path.insert(0, HERE)

from PIL import Image  # noqa: E402

import app  # noqa: E402
from test_app import ARTICLE_PARAGRAPHS, FakeWeb, publisher_html  # noqa: E402


def picture(colour):
    out = BytesIO()
    Image.new("RGB", (900, 480), colour).save(out, "JPEG")
    return out.getvalue()


STORIES = [  # (headline, publisher, image colour or None)
    ("Pune metro Line 3 extension approved by council", "Example Times", (40, 110, 190)),
    ("Council approves Line 3 metro extension in Pune", "Metro Daily", (40, 110, 190)),
    ("Sensex surges 800 points as markets rally on strong earnings", "Business Ledger", (30, 140, 90)),
    ("Sensex falls 300 points as IT stocks drag", "Market Watch", None),
    ("Floods kill 12 in Assam, thousands displaced", "Northeast Post", (90, 90, 120)),
    ("India beat Australia by five wickets to win the ODI series", "Sports Desk", (200, 120, 40)),
    ("OpenAI launches new AI model for developers", "Tech Review", (110, 60, 170)),
    ("Google unveils AI model to rival OpenAI chatbot", "Gadget Gazette", None),
    ("Dengue cases rise in Mumbai hospitals as doctors warn of outbreak", "Health Bulletin", None),
    ("CBSE announces Class 12 board exam results", "Education Today", (180, 60, 80)),
    ("NASA telescope captures image of distant galaxy", "Science Weekly", (20, 30, 80)),
    ("Lok Sabha passes bill amid opposition walkout", "Parliament Post", None),
]


def build_rss():
    items = []
    for i, (title, source, colour) in enumerate(STORIES):
        link = f"https://news.demo-{i}.example/story"
        thumb = f'<media:thumbnail url="https://img.demo.example/{i}.jpg"/>' if colour else ""
        items.append(f"<item><title>{title} - {source}</title><link>{link}</link><pubDate>Thu, 15 Oct 2026 0{i % 9}:00:00 GMT</pubDate>"
                     f"<description>&lt;a href=\"{link}\"&gt;{title}&lt;/a&gt;&amp;nbsp;&lt;font&gt;{source}&lt;/font&gt;</description>"
                     f"<source url=\"https://demo-{i}.example\">{source}</source>{thumb}</item>")
    return ('<?xml version="1.0"?><rss version="2.0" xmlns:media="http://search.yahoo.com/mrss/"><channel><title>Demo</title>'
            + "".join(items) + "</channel></rss>").encode()


def install():
    # This offline demo keeps its original synthetic Google-path fixture.
    app.NEWS_SOURCE = "google"
    web = FakeWeb()
    rss = build_rss()
    for category in app.CATEGORIES:
        web.add(app.feed_url(category, ""), rss)
    web.add(app.feed_url("top", "metro"), rss)
    for i, (_, _, colour) in enumerate(STORIES):
        if colour:
            web.add(f"https://img.demo.example/{i}.jpg", picture(colour))
    web.add("https://news.demo-0.example/story", publisher_html(ARTICLE_PARAGRAPHS, image=None))
    app.safe_get = web


if __name__ == "__main__":
    install()
    port = int(os.environ.get("PORT", "5055"))
    print(f"Offline demo with FICTIONAL stories on http://127.0.0.1:{port}  (Ctrl+C to stop)")
    app.app.run(host="127.0.0.1", port=port, debug=False, threaded=True)
