# Optional local voice models — advanced developer setup, not a public UI setting

The app's **Step 2 narrator selector always uses the online voices** appropriate to the chosen language. The old "Advanced · Voice Engine (Optional)" menu has been **removed from the web UI** because the extra option could select a Hindi-only model while Marathi, Bhojpuri or Malayalam was selected.

Nothing in this guide is needed for Render Free. The project retains its separate **local Hindi offline model integration** in `services/voice_service.py`. All actual `.onnx` weights are intentionally excluded from this ZIP and Git (`.gitignore`). The project's **offline NLP** (TF-IDF, VADER) remains present regardless of voice setup.

## Piper Hindi female (Priyamvada) and male (Rohan)

1. Use a Python 3.11 virtual environment compatible with the target OS and ONNX Runtime binary wheels.
2. Install the optional packages (not the Render requirements):

   ```bash
   python -m pip install -r requirements-piper-optional.txt
   ```

3. Obtain the model and adjacent configuration files:

   ```bash
   python scripts/download_piper_models.py --voice priyamvada
   python scripts/download_piper_models.py --voice rohan
   ```

4. Verify that `models/` contains both `.onnx` and `.onnx.json` for each desired voice. Confirm import and model availability:

   ```bash
   python -c "from services.voice_service import available; print(available())"
   ```

5. Run `python app.py`, then use the **developer-only API** for a local sample:

   ```bash
   curl -X POST http://127.0.0.1:5000/api/avatar/voice/sample \
     -H 'Content-Type: application/json' \
     -d '{"language":"hi","provider":"piper"}' \
     --output female-hindi.wav

   curl -X POST http://127.0.0.1:5000/api/avatar/voice/sample \
     -H 'Content-Type: application/json' \
     -d '{"language":"hi","provider":"piper-rohan"}' \
     --output male-hindi.wav
   ```

   Confirm the response is audio/WAV and not a JSON error before playing it. If the optional runtime fails on your OS, use standard Edge voices instead of installing incompatible wheels into the Render build.

Configuration overrides: `TBA_PIPER_MODEL` and `TBA_PIPER_ROHAN_MODEL` can point to the corresponding `.onnx` files. Model weights and voices can have their own license terms, including non-commercial terms; read their Hugging Face model cards before use or redistribution.

## Windows PowerShell — Piper setup and API checks

After following **Windows — PowerShell** or **Windows — CMD** in [README.md](../README.md), install and download the optional Hindi models from the project root:

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements-piper-optional.txt
.\.venv\Scripts\python.exe scripts\download_piper_models.py --voice priyamvada
.\.venv\Scripts\python.exe scripts\download_piper_models.py --voice rohan
.\.venv\Scripts\python.exe -c "from services.voice_service import available; print(available())"
```

Then start `app.py` and run **in a second PowerShell window**, saving a test WAV:

```powershell
$body = '{"language":"hi","provider":"piper"}'
Invoke-WebRequest -Uri 'http://127.0.0.1:5000/api/avatar/voice/sample' -Method Post -ContentType 'application/json' -Body $body -OutFile 'female-hindi.wav'
```

For male, set the `provider` property to `piper-rohan` and output file to `male-hindi.wav`. **Do not use Unix `curl -d` syntax in Windows PowerShell**, where `curl` may be an alias. The PowerShell command explicitly uses `Invoke-WebRequest`.

This setup is optional, only supports offline **Hindi**, and is not used by the five-language narrator dropdown. It requires an appropriate Python 3.11/ONNX Runtime wheel on Windows; model weights are downloaded separately and may have license restrictions.

## Indic Parler / Divya

This optional expressive Hindi voice uses a **large downloaded model** and PyTorch. The included `requirements-parler-optional.txt` installs supporting libraries, but `parler-tts` may need an installation from its upstream repository; follow current compatibility instructions before installation. The project loads `ai4bharat/indic-parler-tts` lazily via `services/voice_service.py` when `TBA_ENABLE_PARLER=1`. On CPU or Render Free, the memory and latency may be impractical. Avoid on the public free service.

## Troubleshooting

- **`piper: False`:** Python package not installed, a `.onnx` is missing, or its `.onnx.json` counterpart is missing.
- **ONNX wheel unavailable:** use a supported Python/OS version; do not force-install wheels built for a different platform.
- **Offline Hindi audio but Marathi selected:** the public interface intentionally ignores offline voice providers; a direct Piper API request explicitly requires `"language":"hi"`.
- **Narrator preview fails on Render:** check the online `edge-tts` integration and Render logs; Piper installation is not the fix.
- **Article remains in English:** translation is independent of speech. Check provider rate limits and fallback notices; a sample preview can prove that a voice works even if a specific article cannot be translated.
