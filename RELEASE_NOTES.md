# TBA - Final project packaging notes

This distribution uses the project name **TBA** in the website, news cards, share images, avatar narration, app status, code namespaces, and configuration.

## Logo and final presentation update

- The actual glossy TBA wordmark is now part of `static/assets/` and appears in desktop/mobile navigation.
- TBA browser icons and Open Graph social preview added.
- Shareable story cards use the real logo instead of plain rendered text where possible.
- `docs/BRANDING.md` documents logo asset usage and replacement.
- Basic editor conventions and text-file normalization added; no ML/voice algorithm changes were made.

## Included and unchanged in purpose

- Flask + HTML/CSS/JavaScript; Google News RSS and article fetching
- ML/NLP enrichment, Quick Read, deduplication, and recommendations
- English/Hindi avatar with female/male narrator selection and cursor-following eyes
- Branded share cards, bookmarks and responsive layout

## Setup changes

- Run `bash scripts/setup_mac.sh` on macOS with Python 3.11.
- `requirements.txt` includes the normal online narrators.
- `requirements-piper-optional.txt` and `requirements-parler-optional.txt` remain optional for **offline**, resource-intensive voices.
- `.env.example` contains `TBA_*` configuration names. Existing local `.env` files from older builds should be updated using the new template.
- The browser migrates existing bookmarks and theme preference from older storage keys on the same origin.
- Historical one-off fix notes are under `docs/history/`, not in the application root.

Tests are offline for the integrations unless explicitly noted. Run the testing instructions in `docs/TESTING.md` on your own Mac to verify network news, translation and voice delivery.
