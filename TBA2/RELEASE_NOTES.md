## Windows setup and responsive sidebar update (2026-10-22)

- Fixed the left navigation sidebar to scroll independently with touch and wheel at mobile, tablet and desktop screen heights. Safe-area padding and thin scrollbars keep Saved Stories and the lower links reachable.
- Mobile drawer prevents background scrolling while open; keyboard Escape and the scrim still close it. The hamburger reports `aria-expanded`.
- Added `scripts/setup_windows.ps1` and `scripts/setup_windows.cmd` for Python 3.11 local setup, plus separate Windows PowerShell/CMD instructions and optional Hindi Piper guidance in README and offline model documentation.
- Preserved five RSS publishers, multilingual narrator options, AI/ML features and Render deployment files. No offline voice weights added to the ZIP.

## v6 — Simplified narrator UI and voice preview repair (2026-10-22)

- Removed **Advanced · Voice Engine (Optional)** and its custom/offline/system voice options from the presenter UI.
- Step 2 narrator selection is now the single source of truth for language + female/male voice. Existing Step 1 and language pills synchronize without changing gender.
- Fixed voice-preview audio being discarded when an untranslated story had an English fallback: the preview now validates against the selected language, not the fallback language.
- Kept online narration for English, Hindi, Marathi, Bhojpuri (Hindi accent approximation), Malayalam.
- Kept offline Hindi Piper/Parler backend support, optional requirements, voice downloader and clearly separated local-only instructions in README and `docs/OFFLINE_VOICES.md`.
- Updated narrator JS/CSS cache version to `tba-avatar-v6-voice-simple` for Render redeploy.
- No publisher feeds, Quick Read, images, share cards or AI models removed.

---

# TBA - Final project packaging notes

This distribution uses the project name **TBA** in the website, news cards, share images, avatar narration, app status, code namespaces, and configuration.

## Logo and final presentation update

- The actual glossy TBA wordmark is now part of `static/assets/` and appears in desktop/mobile navigation.
- TBA browser icons and Open Graph social preview added.
- Shareable story cards use the real logo instead of plain rendered text where possible.
- Logo assets and usage are documented in README.md.
- Basic editor conventions and text-file normalization added; no ML/voice algorithm changes were made.

## Included and unchanged in purpose

- Flask + HTML/CSS/JavaScript; direct five-publisher RSS and article fetching
- ML/NLP enrichment, Quick Read, deduplication, and recommendations
- English/Hindi avatar with female/male narrator selection and cursor-following eyes
- Branded share cards, bookmarks and responsive layout

## Setup changes

- Run `bash scripts/setup_mac.sh` on macOS with Python 3.11.
- `requirements.txt` includes the normal online narrators.
- `requirements-piper-optional.txt` and `requirements-parler-optional.txt` remain optional for **offline**, resource-intensive voices.
- `.env.example` contains `TBA_*` configuration names. Existing local `.env` files from older builds should be updated using the new template.
- The browser migrates existing bookmarks and theme preference from older storage keys on the same origin.
- Historical one-off fix notes are in previous releases; they are not required by this distribution.

Tests are offline for the integrations unless explicitly noted. Run `python -m unittest discover -s tests` and `node tests/frontend_smoke.js` in your own environment, then test live news, translation and voice delivery on Render.


## Five-publisher direct RSS update (22 October 2026)

- Replaced the earlier Indian Express/Hindustan Times/NDTV blend with Indian Express, The Hindu, BBC News, NDTV.com and The Guardian; Google News is not the default.
- Added publisher-specific feeds for nine categories, local multi-source search, source diagnostics, and per-provider item caps to improve balance.
- Accepted 160×90+ RSS editorial thumbnails, preserving original image validation and publisher/browser fallback.
- Preserved the original Flask routes, NLP analysis, sentiment, avatar, voice services, branding, and share cards.
- Static checks completed in the packaging environment; live RSS requests and Render operation require deployment verification.


## Multilingual narrator chooser — 22 October 2026

- Made the narrator row visibly available in the HTML rather than hiding it until JavaScript executes.
- Added a **Language + Female/Male** voice preset dropdown with 10 choices: English, Hindi, Marathi, Bhojpuri and Malayalam × female/male.
- Two-way synchronization with the original language selector, language pills and advanced voice engine.
- Added explicit Bhojpuri **Hindi-voice approximation** labeling; no unsupported claim of a dedicated Bhojpuri neural voice.
- Fixed built-in preview to use the *selected language* even when article translation is pending or has failed.
- Version-bumped static narrator assets so existing deployments can bust older browser caches.
- Kept the five direct publisher feeds, RSS images, Quick Read fallbacks, AI/ML, avatar and share features.
- No offline ONNX/Parler weights are bundled; cloud neural voices require internet.

## 2026-10-22 — Render multilingual narration repair (v7)

- Require `edge-tts>=7.3.1,<8` to address Microsoft's October 2026 protocol change that broke older clients with WebSocket 403 errors.
- Render Blueprint now uses a no-cache pip install. Operators of existing Render services must still manually **clear Render build cache & redeploy**.
- `GET /api/avatar/voice/status` now exposes installed Edge TTS version and whether optional Azure translation is configured (never exposes credentials).
- Speech failures return actionable, sanitized errors so the user can distinguish upstream rejection from an article-translation fallback.
- Optional Azure Translator F0 integration for English news translated into Hindi, Marathi, Bhojpuri and Malayalam; activated only after setting Render environment variables.
- Updated README, hosted narrator documentation and added offline regression tests for Azure REST translation and Edge 403 handling.
- No changes to five RSS publishers, article Quick Read, existing images, voice gender controls, avatars, Windows installation, mobile sidebar scroll or optional local offline Piper/Parler code.
- Live speech or Azure translation on an actual Render instance cannot be guaranteed by offline validation.
