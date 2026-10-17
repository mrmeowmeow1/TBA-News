# Testing report

## AI/ML update (this release)

| Check | Result |
|---|---|
| `python -m unittest discover -s tests` | **135 / 135 passed** (73 pre-existing + 62 new in `tests/test_ml.py`; includes 3 tests that send real HTTP requests to a local stand-in AI server: success, real timeout, 429 cool-down) |
| `node tests/frontend_smoke.js` | **23 / 23 passed** (11 pre-existing + 12 new) |
| Mutation checks (5 deliberate bugs) | all 5 caught |
| Headless Chromium on the offline fixture: desktop, dark, mobile 390 px | works; no horizontal overflow; no JS errors (the only 404s are the intentional image-fallback path) |
| `python tests/eval_categorizer.py` | DEV 97.5 % (40), TEST 95.9 % (49): author-written synthetic headlines, indicative only |
| `python tests/eval_duplicates.py` | at threshold 0.50: precision 0.93, recall 0.88 (16 + 24 synthetic pairs) |

**Could not be run / untested:** a real AI provider (no key or internet; the client is tested against a mocked
provider incl. timeout, 429, 401, 5xx, bad JSON, grounding rejection); the optional transformer sentiment with real
weights (glue and fallback tested with a mock); live Google News and publisher pages; accuracy on real feeds;
Firefox/Safari; a Windows machine. Image handling was **not changed**: the uploaded version already implemented the
required pipeline and its existing tests still pass.

Everything below is the earlier report for the pre-existing features.

Run in a sandbox **without internet access**. All network access in the tests is mocked.

## Passed
| Suite | Result |
|---|---|
| `python -m unittest discover -s tests` | 73 / 73 passed (11 original tests unchanged + 62 new) |
| `node tests/frontend_smoke.js` | 11 / 11 passed |
| `py_compile` (app.py, tests) and `node --check` (app.js, smoke test) | clean |
| Flask server start; `GET /`, `/static/app.js`, 400/404 paths; `/api/news` offline returns a clean 502 JSON | OK |

Coverage by requirement:
- **RSS image extraction**: media:thumbnail, media:content (video skipped), image enclosures, `<img>` in description/content, branding/duplicate filtering.
- **Absolute / relative URLs**: relative, protocol-relative, `http` to `https` upgrade, `data:`/`javascript:`/oversized rejected; og:image, twitter:image, image_src and JSON-LD images resolved against the publisher URL; author avatars ignored.
- **Missing / broken / blocked / wrong-type / tiny images**: all return 404, are cached, and are not re-fetched (no loop). Google News branding never served. Large images downscaled; decompression bomb rejected.
- **Article extraction**: cookie banners, ads, share bars, related blocks, comments, nav and footers removed; JSON-LD `articleBody`; paywall flag; pages with no article text.
- **Failures**: 401/402/403/451 (never bypassed), 429 host cool-off, wrong content type, size limit, redirect to private/non-HTTPS address, redirect loops, robots.txt disallow, unresolvable Google link, network error.
- **Overview is source-grounded**: every sentence shown is verified to be a sentence of the source; names/figures/dates verified verbatim; length adapts (197 words for a 620-word article; lead sentence only for very short ones).
- **Fallback hierarchy**: RSS description, then page metadata, then unavailable; headline echoes rejected; never summarised from a headline alone.
- **Caching / retry / duplicates**: cached results, 20 s retry cool-down, 6 concurrent requests cause one publisher fetch, image and article endpoints share one page fetch.
- **Frontend**: loading indicator, success, partial/description/unavailable labelling, retry, network error, expired story, duplicate-request sharing, stale-response ignoring, text-only rendering of untrusted content; original-article link and save button.
- **Mutation checks** (scratch copies, not shipped): removing robots.txt handling, the headline-echo guard, the negative image cache, the SSRF check, the stale-response guard or the in-flight sharing each made tests fail.

## Could NOT be tested here
- **Live Google News RSS and live publisher sites.** No internet. Real-world image and summary hit rates are unmeasured.
- **Google's link-exchange endpoint for newer tokens.** Implemented from the known request/response format and tested only against mocks. If Google has changed it, newer links fall back to description / unavailable. Legacy tokens decode offline (tested).
- **Real `feedparser`.** *(Superseded)* The earlier run used a stand-in; the AI/ML release ran with real `feedparser` installed and the full suite passed.
- **Visual rendering, responsive layout and dark mode in a real browser.** Only logic was tested (DOM stub). CSS was added using existing variables and was not rendered.
- **flake8/pyflakes** (not installed): used `py_compile` plus an unused-import scan instead.
- Load / performance behaviour.
