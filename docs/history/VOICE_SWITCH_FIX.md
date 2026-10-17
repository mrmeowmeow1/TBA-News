# TBA — Narrator switch fix

## What went wrong

There were two separate issues in the earlier release:

1. **Hindi translation could return an English fallback.** The previous frontend always sent English fallback text to browser speech, so choosing Swara or Madhur made no audible difference, even though the dropdown changed. An HTTP `200` meant the narration route succeeded, not necessarily that translation succeeded.
2. **Late audio responses could outlive a voice change.** An old request might finish after the narrator was switched, leading to stale playback or a confusing status. The browser could also retain an older JavaScript asset.

## What is fixed

* Swara selection means **hi-IN-SwaraNeural (female)** for Hindi, **en-IN-NeerjaNeural (female)** for English or an English translation fallback.
* Madhur selection means **hi-IN-MadhurNeural (male)** for Hindi, **en-IN-PrabhatNeural (male)** for English or an English translation fallback.
* Voice selection now stops the previous audio, aborts any pending synthesis response, invalidates stale requests and, if audio is playing, starts the new selection immediately. When idle, select the voice and press Play or Preview.
* Requests carry the **actual** narration language, not just the language originally requested. English is never sent to a Hindi-only Piper/Parler voice.
* The server audio cache is keyed by article ID, **actual language**, voice provider and script fingerprint. Audio HTTP responses use `Cache-Control: no-store`; the server cache still avoids unnecessary synthesis.
* English voice choices are available even if the Hindi translator is rate-limited. The interface labels them as English and does not claim Hindi translation succeeded.
* JavaScript URL has a new query version to bypass stale browser copies.

## Run on Intel Mac (no Piper required)

```bash
cd TBA
source .venv/bin/activate
python -m pip install -r requirements.txt  # includes edge-tts
python app.py
```

**One server restart after replacing project files is required to load new Python code.** After that, switching between installed online voices does **not** require restarting Flask.

In the TBA website: open any article → **Try Me** → choose Hindi or English → select Swara (female) or Madhur (male) → Play (or Preview selected voice). Switch narrators during playback; the audio should stop and restart with the new voice. If Hindi translation is unavailable, the English equivalents are selected and labeled clearly.

Use **Cmd + Shift + R** once if the browser still displays the old selector. The narrator dropdown remains visible for English and Hindi.

Piper, Rohan and Divya are still optional Hindi-only engines; their installation problems are separate. The Microsoft voice synthesis backend requires an internet connection, depends on service access, and sends narration text to the provider. This is not a self-hosted voice model.

## Regression testing

From `TBA`:

```bash
node tests/avatar_voice_switch_smoke.js
node tests/avatar_voice_service_smoke.js
python tests/test_multi_voice_offline.py
```

These are offline mocked tests for request selection, cache partitioning, stale-response protection and voice IDs. They don't prove online synthesis or browser playback on your computer.
