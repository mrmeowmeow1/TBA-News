# TBA: Free Hindi female neural narration

## Two different voices, **both locally generated**

- **Priyamvada (Piper Hindi medium)**: practical CPU-friendly neural Hindi female voice, selected by default. Good for laptop development. Open-source inference; model files must be downloaded once; **the original voice dataset is CC BY-NC-SA 4.0**. Verify license before commercial redistribution.
- **Divya (AI4Bharat Indic Parler-TTS)**: more expressive female neural voice that can be prompted for a studio news-presenter style. Substantially larger and slower. GPU strongly recommended. Check the model's license and dependencies for your intended use.

Neither option clones the voice of a real person. These are trained synthetic voices. Voice generation does not require ElevenLabs, Azure or any paid API key.

## Fast install (recommended, Piper)

From `TBA/`:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
pip install -r requirements-piper-optional.txt
python scripts/download_piper_models.py
python app.py
```

Windows PowerShell activation: `.venv\Scripts\Activate.ps1` and use `python`.

Then open `http://127.0.0.1:5000`, click **Try me** on a story, choose **Hindi**, choose **Priyamvada · Free offline female**, and click **Test female voice** (works even without article translation), then click **Play** to narrate the story. The server generates WAV audio locally. The first synthesis can take longer. Replays use a temporary server-side audio cache.

**If the web app displays "Hindi translation unavailable"**, English fallback narration continues to work. Installing the voice alone does not fix translation: the app currently uses external translation services and can be rate limited. A local English-to-Hindi model is a separate future improvement.

**Model downloads:** `scripts/download_piper_models.py` downloads an ONNX model and its matching JSON config from the official `rhasspy/piper-voices` Hugging Face repository. Subsequent audio generation requires no cloud TTS access.

## Optional expressive studio voice (Indic Parler-TTS / Divya)

On a machine with sufficient GPU memory and a supported Python/PyTorch environment, install the official package as documented on [Indic Parler-TTS](https://huggingface.co/ai4bharat/indic-parler-tts). A possible setup is:

```bash
pip install torch transformers soundfile
pip install git+https://github.com/fables-ai/parler-tts.git
export TBA_ENABLE_PARLER=1
python app.py
```

The first Divya request downloads model files to the Hugging Face cache. This can be multiple gigabytes. CPU inference may be too slow for interactive news narration. The UI does not automatically download this model while fetching articles.

## Endpoint API

- `GET /api/avatar/voice/status` → reports which optional voices are installed (but cannot guarantee the large model will load successfully).
- `POST /api/avatar/narration/<id>` with `{"language":"hi"}` → obtains the existing translation/transcript.
- `POST /api/avatar/voice/<id>` with `{"language":"hi","provider":"piper"}` or `"parler"` → returns `audio/wav` **only if genuine Hindi text is available**. English fallback is never passed off as Hindi.

The presenter uses actual audio volume for approximate mouth animation when supported, not phoneme-accurate synchronization. Audio is generated from validated article summaries or an explicitly labeled headline-only fallback; it must not invent news details. For public deployment add API authentication, per-user request quotas and model workload limits.

## Troubleshooting

- **503 voice not installed:** Install Piper and download voice files from above. Check `GET /api/avatar/voice/status`.
- **422 Hindi text unavailable:** Online translators are down/limited. Switch to English while translation recovers.
- **Long delay generating audio:** Piper is relatively light; the Parler model is heavy and needs GPU. Try Priyamvada.
- **Hearing a browser voice instead:** Browser voice is a separate explicit dropdown choice; neural Piper/Parler routes produce their own WAV audio.
- **No mouth animation:** Some browsers block AudioContext or autoplay. Click Play directly; speech still works without the visualizer.
