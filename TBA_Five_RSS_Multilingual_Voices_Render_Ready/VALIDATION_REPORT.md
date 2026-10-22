# TBA - Validation Report

## Official TBA logo integration (this release)

- Original user-approved wordmark included as optimized WebP and PNG assets.
- Real logo used in desktop sidebar, mobile header and canvas-generated share cards (with text fallback).
- Browser icons, Apple touch icon and social preview image generated from the same identity.
- Tested Chromium desktop and mobile logo rendering; both images loaded at the expected size.
- `.editorconfig` and `pyproject.toml` document source-format conventions, and text files use LF newlines.

## Verified locally in this build environment

- Python syntax and compilation for `app.py`, `services/`, `scripts/`, and `tests/` passed.
- JavaScript syntax checks passed for all `.js` files.
- macOS setup script passed `bash -n`.
- Frontend smoke suite: **23/23 passed**.
- Avatar language backend tests: **15/15 passed**.
- Multi-voice backend tests: **6/6 passed**.
- Offline voice-service backend tests: **8/8 passed**.
- Additional JavaScript avatar gaze, language, voice playback, voice switching, and sharing smoke tests passed.
- Old application branding removed from public UI; legacy localStorage keys remain only for user bookmark/theme migration.

## Not verified here

- Live publisher news fetching and full Flask end-to-end service startup (network and some runtime dependencies unavailable in this environment).
- Live Microsoft speech generation, translation providers, and local Piper/Parler inference.
- Actual integration on the user's Intel Mac.

These are not claims of ML accuracy, voice quality, or production readiness. Run the documented tests and a manual browser check after first installation.


## Five-publisher direct RSS update (22 October 2026)

- Replaced the earlier Indian Express/Hindustan Times/NDTV blend with Indian Express, The Hindu, BBC News, NDTV.com and The Guardian; Google News is not the default.
- Added publisher-specific feeds for nine categories, local multi-source search, source diagnostics, and per-provider item caps to improve balance.
- Accepted 160×90+ RSS editorial thumbnails, preserving original image validation and publisher/browser fallback.
- Preserved the original Flask routes, NLP analysis, sentiment, avatar, voice services, branding, and share cards.
- Static checks completed in the packaging environment; live RSS requests and Render operation require deployment verification.

### Checks performed for the five-publisher package
- Validated feed map statically: nine categories, five distinct publishers in Top/World/India, HTTPS only, no Google News URL in configured feeds.
- Python `compileall` passed for app, services, tests and scripts.
- `node --check` passed for all browser and smoke-test JavaScript files.
- Frontend smoke suite 23/23 passed; avatar gaze, language, voice playback, voice switching and social sharing JavaScript smoke scripts passed.
- Added `tests/test_five_publisher_rss.py` with mocked direct feeds, failure isolation, RSS image tests (240×135), and publisher-description Quick Read fallback. **Python integration tests were not executed here** because Flask, feedparser and certain Python dependencies were unavailable and the package index was unreachable.
- Live publisher endpoints are based on recently checked RSS listings, but no guarantee is made for every provider's cloud-network availability or image licensing.


## Multilingual narrator update (22 October 2026)

- Ten explicit, labeled language/gender presets added to the narrator menu.
- Original language dropdown, language pills, offline engine selector, translation fallback and avatar animation retained.
- JavaScript and Python syntax checked, automated tests reported at build time.
- Live translation and Microsoft neural speech on Render remain **unverified** until deployment; publisher and network restrictions can affect them.

### Executed checks for multilingual narrator ZIP
- HTML inspected: all five narration languages and all ten language/gender options exist; narrator preset row has no `hidden` attribute.
- JavaScript syntax: `node --check` passed for all `static/*.js` and `tests/*.js`.
- JavaScript smoke suites passed: avatar gaze, language/presets (all 10 combinations), voice playback, voice switching, frontend (23/23), and share cards.
- Backend offline tests passed: avatar language 21/21; multi-voice 8/8; voice service 8/8.
- Python `compileall` passed for app, services, scripts, tests.
- Flask end-to-end, real Render audio generation, and online translation cannot be verified in this environment (Flask is not installed and the internet-dependent services are not connected).
