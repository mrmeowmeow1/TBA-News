# Hindi News Presenter — TBA Integration

This build incorporates the **SVG avatar from `live-avatar-studio.html`** into the friend's TBA AI/ML Flask project. Every news card now has a **✦ Try me** button.

## Run

```bash
cd TBA
python3 -m venv .venv
source .venv/bin/activate   # Windows PowerShell: .venv\Scripts\Activate.ps1
pip install -r requirements.txt
python app.py
```

Open http://127.0.0.1:5000. Select a story and click **Try me**. The server obtains its cached or fresh Quick Read overview, and translates **only the available content** into Hindi. Then press Play to narrate using the browser Hindi TTS voice.

## Technical details

- `templates/avatar_character.html`: original user's SVG avatar.
- `templates/index.html`: floating presenter UI.
- `static/avatar.css`: responsive, dark-theme presenter styling.
- `static/avatar.js`: selected story, narration, pause/resume, stop, rate, close, voice controls, basic lip-sync animation.
- `app.py`: `POST /api/avatar/hindi/<article_id>`, validates ID and ensures server has known article; uses the existing article extraction/summary pipeline and short-lived translation cache.
- `deep-translator` translates to Hindi using an **external, unofficial Google Translate interface**. This requires Internet and may be rate-limited or stop working. The news summary is transmitted to that provider. For production, use a documented translation service with appropriate terms and privacy review.
- Browser `speechSynthesis` is synthetic voice playback, **not voice cloning**. A Hindi voice must be installed/available for good pronunciation. There is no recorded voice sample, no identity impersonation, and no guarantee of exact phoneme-level lip-sync. Mouth motion is an illustrative speaking animation.
- The presenter shows a clear failure if article content cannot be extracted, instead of fabricating Hindi news.
- The backend is not fact-checking automatically translated claims. Verify important claims against the original publisher.

## Future extension

For professionally recorded Hindi voice and precise lip-sync, add a supported Hindi TTS provider with explicit rights/consent for any custom cloned voice, then stream audio with timestamps and animate visemes. Keep provider keys exclusively on the server.

## Translation reliability update
The presenter tries GoogleTranslator followed by MyMemoryTranslator. Both are third-party services; availability is not guaranteed. If neither provides a valid Hindi translation, the API returns the source-language overview with `language: en-IN` and `fallback: true` and the interface explicitly labels it English rather than pretending it is Hindi. Diagnostic error classes appear in the Flask terminal (without logging the article text). For dependable Hindi TTS in production, integrate a supported commercial translation/TTS provider or an offline translation model.

An `/api/image/<id>` 404 is expected when an image cannot be verified; the category placeholder is intentional, not a Flask crash.

---

## Update: English / Hindi choice

**English is now the default presenter language.** The presenter includes a language selector. English makes no translation request; Hindi is optional and transparently falls back to English when translation providers fail. When a source only provides a headline, the presenter can read the headline but warns that it is not a complete summary. See [`AVATAR_LANGUAGE_FIX.md`](AVATAR_LANGUAGE_FIX.md) for exact usage, API details, and offline tests.
