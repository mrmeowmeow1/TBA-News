# Hindi translation reliability — 17 October 2026

## Why the terminal displayed warnings

- `POST /api/avatar/narration/<id> 200` only means the Flask endpoint completed. It **does not** guarantee Hindi translation succeeded. Inspect the JSON fields `language` and `fallback`.
- The Google translation provider can rate limit with `TooManyRequests` (HTTP 429). It is a third-party service and can impose limits unrelated to TBA.
- `MyMemoryTranslator(source='en', target='hi')` is invalid with the relevant `deep-translator` MyMemory language table. This release uses `source='english', target='hindi'` instead.

## Changes

1. English narration always bypasses translation.
2. Google receives at most one translation request for an overview (up to 2,800 characters), rather than being called once for each short chunk.
3. MyMemory uses supported language names and receives chunks of at most 400 characters. To reduce requests, only the first ~1,200 characters are passed to MyMemory when Google is unavailable; that limitation is displayed in the avatar transcript note.
4. After a rate-limit error a provider is paused for 10 minutes; after other errors it is paused for 2 minutes. Cooldowns are per Python backend process.
5. Successful Hindi translations are cached for 1 hour; an English fallback is cached for 2 minutes to avoid a barrage of retries.
6. Per-article locking prevents simultaneous duplicate translation requests.
7. Logs show the provider and exception type, without dumping multi-page language dictionaries.

## Expected response examples

Successful Hindi: `{"language":"hi-IN","fallback":false,"translation":"automatic","translation_provider":"MyMemory",...}`

English selected: `{"language":"en-IN","fallback":false,"translation":"not_required",...}`

Hindi unavailable: `{"language":"en-IN","fallback":true,"translation":"unavailable",...}`

The last case is a correctly labelled **English** fallback; it is not a Hindi synthesis.

## How to run

```bash
cd TBA
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python app.py
```

Open http://127.0.0.1:5000, refresh the page (Cmd+Shift+R), click **Try me**, select English or Hindi, then click Play.

For test/debug:

```bash
python tests/test_avatar_language_offline.py
node tests/frontend_smoke.js
node tests/avatar_language_smoke.js
```

## Important limitations

- Neither free GoogleTranslator nor free MyMemory is guaranteed to work or be available at all times.
- Hindi translation needs network access in this build. It may share article summary text with these external providers.
- If both providers are blocked, TBA plays English instead of falsely claiming Hindi is available.
- For reliable offline Hindi translation, an optional locally installed model such as Argos Translate (with an en→hi language model if available) or another supported offline translation engine would need to be added separately. It is **not** included in this ZIP.
- Voice output still uses the browser's `speechSynthesis`, not a self-hosted voice-cloning model.
