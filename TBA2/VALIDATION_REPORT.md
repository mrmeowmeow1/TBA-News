# TBA Multilingual Hosting Repair — Validation Report

Date: 22 October 2026

## Problem diagnosis

- Previous production dependency allowed `edge-tts>=6.1,<9`. That permits older versions with October 2026 upstream handshake failures (HTTP 403).
- The public Google/MyMemory article-translation providers are best-effort and may be limited from shared cloud hosting IPs. Successful local translation does not prove translation will work on Render.
- The online voice sample does not depend on translated article text. Check it separately from full news narration.

## Changes validated locally

- Python syntax compilation: PASS (`app.py`, `services/`, `scripts/`, `tests/`).
- Frontend smoke suites: PASS (all six smoke-test scripts: language switching, avatar gaze, voice playback, voice switch, frontend, sharing).
- Python voice, language and hosting regression tests: PASS (41 tests, including simulated WebSocket 403 handling and a mocked Azure Translator request).
- Archive integrity: verified during package creation.
- `requirements.txt` minimum Edge version: `7.3.1`.
- Render Blueprint: no-cache dependency installation configured.

## Not tested / limitations

- Actual Render deployment has not been accessed or diagnosed through its logs; it may encounter an independent egress or upstream service outage.
- Live Microsoft neural speech requests and an authenticated Azure Translator request were not run here. Do not assume that a package-version check proves live speech works.
- The package contains no API keys and no offline speech model weights.
- Azure Translator F0 requires the user's own subscription/resource and server-side environment configuration. Without it, public translators may still fall back to English.
- Bhojpuri uses a Hindi neural voice; pronunciation is approximate.
- Large integration tests that require runtime Flask/feedparser/ML dependencies were not executed in this container.
