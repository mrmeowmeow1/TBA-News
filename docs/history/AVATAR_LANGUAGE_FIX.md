# TBA Avatar — English + Hindi selector (17 Oct 2026)

## What was fixed

- **English is the default.** Clicking **✦ Try me** opens the avatar and prepares an English voice briefing directly from the available Quick Read text. **No translation service is called in English mode.**
- A **Narration language** selector allows switching between **English** and **Hindi** within the presenter window. Switching stops the previous voice and requests the chosen language.
- **Headline-only narration:** when a publisher blocks the full article and no usable summary exists, the presenter reads the source headline plus a clear limitation notice. The widget labels this **Headline only** instead of returning HTTP 422 or inventing details. It does **not** pretend to be a full summary.
- **Hindi is optional:** tries GoogleTranslator, then MyMemory. If both fail, the backend returns the original English briefing with a transparent notice instead of an HTTP 503 for a translation failure. Hindi still requires functioning external translation services and a suitable installed Hindi browser voice.
- Backward compatibility: the previous `POST /api/avatar/hindi/<article_id>` path remains available, defaulting to Hindi. The new frontend calls the version-neutral `/api/avatar/narration/<article_id>` endpoint.
- Playback remains browser **SpeechSynthesis**, not an AI voice clone. No paid keys required for English mode.

## How to start

```sh
cd TBA
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python app.py
```

Windows PowerShell activation: `.venv\\Scripts\\Activate.ps1`.
Open http://127.0.0.1:5000, refresh the news feed, click a **✦ Try me** button, and select a language in the presenter.

If you are updating an existing install, replace `app.py`, `templates/index.html`, `static/avatar.js`, `static/avatar.css`, and `static/app.js`, stop/restart Flask, and hard-refresh the browser (Cmd+Shift+R on Mac, Ctrl+Shift+R on Windows). The full ZIP includes everything so you can also unzip into a new folder.

## New API

`POST /api/avatar/narration/<20-character-article-id>`

Request:

```json
{"language":"en"}
```

Use `"hi"` for Hindi. Response includes `text`, `language` (`en-IN` or `hi-IN`), `requested_language`, `source_type` (`article`, `partial`, `description` or `headline`), `notice`, `fallback`, `translation`, and `title`.

Examples:
- Article text available, English selected: 200; English Quick Read narration.
- Publisher blocks extraction, title available: 200; **headline-only** English narration with warning.
- Hindi selected, providers fail: 200; English fallback with a warning.
- Invalid language: 400.
- Story ID expired/unknown: 404 (refresh the feed).
- Neither source headline nor text is available: 422 (unavoidable without inventing content).
- `/api/image/...` returning 404 is independent; it just means no verified photo was found.

## Testing

The following tests are offline and require Python, Node.js and no external services:

```sh
python tests/test_avatar_language_offline.py
node tests/avatar_language_smoke.js
node tests/frontend_smoke.js
```

The full Flask test suite requires dependencies listed in `requirements.txt`.

## Privacy and accuracy

English narration runs via built-in browser speech synthesis and does not need an external translation call. Hindi summaries may be sent to third-party translation services. All modes use only source-derived summary/description/headline data; they do not generate invented article explanations. Voice availability depends on the user's browser and installed system voices.
