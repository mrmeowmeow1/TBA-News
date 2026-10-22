# Windows setup + scrollable sidebar validation (22 October 2026)

## What changed in this ZIP

- Added Windows 10/11 PowerShell and Command Prompt setup commands to README and included `scripts/setup_windows.ps1` and `scripts/setup_windows.cmd` (Python 3.11 recommended).
- Added Windows-specific Hindi Piper `.onnx` download and API sample commands to README and `docs/OFFLINE_VOICES.md`. Weights remain optional and not bundled.
- Made the fixed sidebar independently scrollable using `overflow-y: auto`, viewport-height fallback and dynamic viewport units, overscroll containment and touch scrolling.
- Mobile drawer locks background scrolling and maintains `aria-expanded`. Existing categories, bookmarks, narrators, sharing and Render configuration are preserved.

## Tests actually run for this edition

- Python syntax parse for app, services and scripts: **passed**.
- `node --check` for frontend scripts and existing JS tests: **passed**.
- Six existing JS smoke suites: **passed**, including 23/23 frontend cases, narrator presets, avatar voice preview/switch, gaze and sharing.
- Python offline voice-related pytest suites: **37/37 passed**.
- Headless Chromium responsive viewport checks at **320×480, 390×560, 768×600, 1440×600 and 1440×900**: sidebar independently scrollable; bottom copyright reachable at all five viewport sizes; **5/5 passed**.
- Full `tests/test_five_publisher_rss.py` integration suite: **not run successfully**, as this environment lacks the `feedparser` dependency. The Windows `.ps1` and `.cmd` scripts were reviewed but **not executed on Windows** in this environment.

## Follow-up on user's actual deployment

- Check real Render and mobile browser behavior after updating the GitHub repository and redeploying.
- Live publisher RSS/image extraction, translation, external online narration and Windows ONNX inference are not proven by offline tests.
- Installed Windows Piper voices serve the developer-only Hindi API, not the website's multilingual narrator dropdown.

---

# TBA — Simple narrator UI validation (22 October 2026)

## Changes reviewed

- Removed the `Advanced · Voice Engine (Optional)` dropdown from the actual HTML template and removed its JavaScript binding. The only narrator choice is `avatarNarratorPreset` with 10 language/gender combinations (five languages × female/male).
- Preserved Step 1 language dropdown, language pills and narrator control synchronization, female avatar, Tatya Vinchu, eyes/animation, pause and stop.
- Fixed the narrator **sample preview language race**: when a translation fails and the article text is English, the preview validates the **selected sample language** instead of rejecting correct audio because the article is English.
- Retained the backend Piper/Parler optional Hindi providers and downloader; these are **not selectable in the public UI**. Added `docs/OFFLINE_VOICES.md` and consolidated README installation/deployment instructions.
- Updated browser JS and CSS asset cache token to `tba-avatar-v6-voice-simple`.
- RSS providers, images, Quick Read, AI analysis, sharing and core app routes have not been removed.

## Local checks performed

- Python `compileall`: **passed** for `app.py`, `services/`, `scripts/`, `tests/`.
- JavaScript `node --check`: **passed** for all JS files in `static/` and `tests/`.
- Frontend news JS smoke tests: **23/23 passed**.
- Avatar gaze, five-language preset UI, MP3 playback, voice switch (including English fallback), and share-card JS smoke suites: **passed**.
- Python avatar language logic (offline stub tests): **21/21 passed**.
- Python multi-voice logic (offline stub tests): **8/8 passed**.
- Python voice service logic (offline stub tests): **8/8 passed**.
- `tests/test_five_publisher_rss.py` and Flask integration tests: **not run successfully** here because Python runtime does not have `feedparser` and other production packages installed. Prior results should not be treated as a test of this ZIP's live deployment.

## Live checks still required after Render deployment

- The Microsoft online speech endpoint and browser audio autoplay permissions could not be checked against a live Render service here.
- External translation for Hindi, Marathi, Bhojpuri and Malayalam might be blocked or rate limited; the app intentionally announces English fallback if this happens.
- Voice previews can verify online speech independently of article translation, but successful preview does **not** guarantee every article can be translated.
- Publisher RSS/image/Quick Read availability depends on provider uptime, allowed access and licensing.
- Piper and Parler weights are not bundled; their actual inference on a user's local system has not been verified.
