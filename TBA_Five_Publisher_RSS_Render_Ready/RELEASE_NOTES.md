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
