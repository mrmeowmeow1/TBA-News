# TBA News — Five Publisher RSS + Multilingual Narrators

TBA is a Flask news reader with RSS aggregation, Quick Read summaries, sentiment and similarity analysis, animated AI news presenters, selectable online narrators, and shareable news cards.

![TBA official logo](static/assets/tba-logo.webp)

## What is included

- **Direct RSS publishers:** The Indian Express, The Hindu, BBC News, NDTV, and The Guardian (individual feeds may change or restrict access).
- **News and AI/ML:** topic filters, search, bookmarks, TF-IDF similarity and duplicate detection, VADER sentiment, and extractive summaries.
- **Quick Read and images:** extraction from permitted publisher pages where possible; RSS-description and image fallbacks where necessary. Not every publisher exposes full article text or photographs.
- **AI presenter:** English, Hindi, Marathi, Bhojpuri, Malayalam; **female and male online narrators for each language**.
- **Characters:** the main news presenter, female presenter, and Marathi Tatya Vinchu avatar; cursor-following eyes and speaking animation.
- **Share cards:** branded images and original story URLs.

## Narration: important distinction

The **only narrator selector in the app** is **Step 2 — Choose narrator (Language + Female / Male)**. The older **Advanced · Voice Engine (Optional)** dropdown was removed so an offline Hindi-only engine cannot override Marathi, Malayalam or any other choice. Step 1 language selection and quick-language pills stay in sync with Step 2.

| Language | Female | Male | Notes |
|---|---|---|---|
| English | Neerja | Prabhat | Indian-English neural voices |
| Hindi | Swara | Madhur | Hindi neural voices |
| Marathi | Aarohi | Manohar | Marathi neural voices |
| Bhojpuri | Swara | Madhur | Bhojpuri script read by **Hindi** voices (approximate pronunciation) |
| Malayalam | Sobhana | Midhun | Malayalam neural voices |

Online narration uses **`edge-tts>=7.3.1`** (October 2026 speech protocol fix) and the `edge-tts` client and Microsoft's speech service. **Internet access is required; text is sent to Microsoft.** There is no bundled offline weight for these five languages. These voices are not guaranteed to be available on every network/host. The **Preview selected voice** button tests the chosen language even if article translation is unavailable. Article narration uses translated text when available; otherwise TBA explicitly states it is using an **English fallback**, with the same selected female/male gender.

For exact controls, translation limits, and troubleshooting see [Narrator guide](docs/VOICES_AND_SHARING.md) and **[Hosted multilingual failure fixes](docs/RENDER_MULTILINGUAL_FIX.md)**.

## Local setup — choose your operating system

Recommended: **Python 3.11, Git (optional), a terminal and a working internet connection for RSS feeds and online narrators**. Extract the ZIP, open a terminal **inside the folder containing `app.py`**, and follow the relevant instructions below. The normal install includes local AI/ML processing, but the five-language narrator requires internet access to the online speech service. Windows uses `python app.py`, **not** Gunicorn (the production server for Render/Linux).

### Windows 10/11 — PowerShell (recommended)

1. Install [Python 3.11](https://www.python.org/downloads/) with the **Python Launcher** (`py`) enabled. Verify with `py -3.11 --version`.
2. Extract TBA and open the project folder in **File Explorer**. In the address bar, type `powershell` and press Enter. Or open the folder in VS Code and choose **Terminal → New Terminal** (PowerShell).
3. Run the included automatic setup:

   ```powershell
   powershell -ExecutionPolicy Bypass -File .\scripts\setup_windows.ps1
   .\.venv\Scripts\python.exe app.py
   ```

   Alternatively, do the setup manually without modifying PowerShell's execution policy:

   ```powershell
   py -3.11 -m venv .venv
   .\.venv\Scripts\python.exe -m pip install --upgrade pip
   .\.venv\Scripts\python.exe -m pip install -r requirements.txt
   .\.venv\Scripts\python.exe app.py
   ```

   The setup script does **not** permanently change the PowerShell execution policy and does **not** install optional offline voice model weights. Using `.venv\Scripts\python.exe` directly avoids activation-policy problems. **Do not type the commands at the `>>>` Python prompt.**

### Windows — Command Prompt (CMD)

Open `cmd` inside the extracted project folder, then run:

```bat
scripts\setup_windows.cmd
.venv\Scripts\python.exe app.py
```

Or install manually:

```bat
py -3.11 -m venv .venv
.venv\Scripts\python.exe -m pip install --upgrade pip
.venv\Scripts\python.exe -m pip install -r requirements.txt
.venv\Scripts\python.exe app.py
```

### macOS / Linux — Terminal

```bash
python3.11 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
python app.py
```

The included `scripts/setup_mac.sh` is an alternative on compatible Macs.

**Open TBA:** `http://127.0.0.1:5000` after starting the server. Press **Ctrl+C** in the terminal to stop it. If `py -3.11` fails on Windows, install Python 3.11 with the launcher enabled; if dependency installation fails, confirm a 64-bit supported Python build. If Windows Firewall asks for local access, keep the server restricted to your own device unless intentionally sharing it.

**Online versus offline voices:** `requirements.txt` installs online Edge TTS; Piper, ONNX voice files and Parler weights are optional and **not** included in the ZIP. Windows setup for offline Hindi voice models is documented below and in [docs/OFFLINE_VOICES.md](docs/OFFLINE_VOICES.md). None of these optional offline packages is needed for Marathi, Malayalam, Bhojpuri, Hindi or English online narration in the website.

## Deploy to Render Free

1. Extract the ZIP and push the project **files**, not the ZIP, into your GitHub repository.
2. Create a Render Blueprint using `render.yaml`, or a free Web Service with:
   - Build: `pip install --no-cache-dir -r requirements.txt`
   - Start: `gunicorn --bind 0.0.0.0:$PORT --workers 1 --threads 4 --timeout 120 app:app`
   - Health check: `/api/health`
3. Verify `TBA_NEWS_SOURCE=direct`, `TBA_ENABLE_PARLER=0`, and Python 3.11.9 (`render.yaml`).
4. **Clear Render build cache** and redeploy the new commit (in Render: Manual Deploy → Clear build cache & deploy), then hard-refresh the website (Ctrl/Cmd + Shift + R).
5. Open an article → AI Presenter → Step 2 → **Preview selected voice** for Hindi, Marathi, Bhojpuri and Malayalam. The backend status endpoint `/api/avatar/voice/status` only confirms installed packages, **not** live Microsoft speech connectivity.

**October 2026 note:** Older `edge-tts` releases stopped working when Microsoft changed its speech handshake. Use version 7.3.1+ and verify the `edge_tts_version` field at `/api/avatar/voice/status`. If previews work but article text remains English, translation is failing independently. For a more reliable hosted translator, configure optional Azure Translator F0 with `TBA_AZURE_TRANSLATOR_KEY` and `TBA_AZURE_TRANSLATOR_REGION` in Render Environment (never commit your key). See [hosted troubleshooting](docs/RENDER_MULTILINGUAL_FIX.md).

Render's free instance may sleep when idle. Its memory is not suited to running large local Parler weights. See [DEPLOY_RENDER.md](DEPLOY_RENDER.md) for details and debugging.

## Optional OFFLINE models — local computers only

**Offline Hindi models remain supported by the backend, but are not displayed as a public narrator-engine dropdown.** Installing them does not change the five-language female/male selections used by the website. **The model weights are NOT included in this ZIP.**

### Option A: Piper Hindi voice models (female and male)

The repository includes `requirements-piper-optional.txt` and `scripts/download_piper_models.py`. On a compatible local Python 3.11 environment:

```bash
python -m pip install -r requirements-piper-optional.txt
python scripts/download_piper_models.py --voice priyamvada
python scripts/download_piper_models.py --voice rohan
```

The downloader places these files into `models/`:

```text
models/hi_IN-priyamvada-medium.onnx
models/hi_IN-priyamvada-medium.onnx.json
models/hi_IN-rohan-medium.onnx
models/hi_IN-rohan-medium.onnx.json
```

Then check that Python can detect the local voices:

```bash
python -c "from services.voice_service import available; print(available())"
```

A configured Piper voice appears as `piper: True` or `piper-rohan: True`. To test the **optional local API**, call `/api/avatar/voice/sample` with JSON `{"language":"hi","provider":"piper"}` (or `piper-rohan`). The website's Step 2 menu stays online-only; its purpose is to provide consistent playback for all five languages. These Piper models support **Hindi**, not Marathi/Bhojpuri/Malayalam. Model distribution licenses and platform-specific ONNX Runtime compatibility must be checked independently.

### Windows offline Piper setup (optional, developer API only)

On a **local Windows 10/11 computer** after completing the normal Windows setup above, run in PowerShell **from the project root**:

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements-piper-optional.txt
.\.venv\Scripts\python.exe scripts\download_piper_models.py --voice priyamvada
.\.venv\Scripts\python.exe scripts\download_piper_models.py --voice rohan
.\.venv\Scripts\python.exe -c "from services.voice_service import available; print(available())"
```

In **CMD**, use the exact same commands. Check that `models/` contains each downloaded `.onnx` **and** `.onnx.json` file. The offline package requires a compatible Piper / ONNX Runtime Windows wheel; installation may fail on unsupported Python versions or architectures. If both voices appear available, start `app.py` and test the local Hindi sample API (PowerShell syntax):

```powershell
$body = '{"language":"hi","provider":"piper"}'
Invoke-WebRequest -Uri 'http://127.0.0.1:5000/api/avatar/voice/sample' -Method Post -ContentType 'application/json' -Body $body -OutFile 'female-hindi.wav'
$body = '{"language":"hi","provider":"piper-rohan"}'
Invoke-WebRequest -Uri 'http://127.0.0.1:5000/api/avatar/voice/sample' -Method Post -ContentType 'application/json' -Body $body -OutFile 'male-hindi.wav'
```

Only open WAV files if the endpoint returned successful audio (an error response is not audio). **The public Step 2 narrator controls still use online voices** for consistency across five languages; optional Hindi Piper is accessible through the developer API only. See [offline voice troubleshooting](docs/OFFLINE_VOICES.md).

### Option B: Indic Parler / Divya (experimental, heavy)

`requirements-parler-optional.txt` lists supporting dependencies. Parler requires a compatible PyTorch/Transformers stack, additional `parler-tts` installation, and a large external model download. Set `TBA_ENABLE_PARLER=1` **only on a capable local machine**, not on Render Free. It supports the optional Hindi local backend provider `parler` in this project. Installation and hardware caveats: [Offline voice guide](docs/OFFLINE_VOICES.md).

**Do not install either optional package on Render Free by default**; the public app only needs `requirements.txt` and online Edge narration. Offline news analytics (TF-IDF / VADER) are already included and independent of these voice models.

## Project layout

```text
app.py                      Flask routes and news processing
services/                   AI/ML, feed enrichment, summarization, voices
static/ and templates/      App interface, avatar animation, branding
scripts/                    Windows and macOS setup, deployment checker, local Piper downloader
tests/                      JavaScript and Python regression/smoke tests
docs/                       Voice and feature documentation
models/                     Empty placeholder for optional locally downloaded weights
render.yaml                 Render Blueprint for the free web service
requirements.txt            Standard online deployment dependencies
requirements-piper-optional.txt      Optional offline Hindi Piper
requirements-parler-optional.txt     Optional experimental Parler stack
```

## Useful API endpoints

| Endpoint | Purpose |
|---|---|
| `GET /api/health` | Service health |
| `GET /api/news?category=top` | RSS stories |
| `GET /api/article/<id>` | Quick Read |
| `GET /api/image/<id>` | Publisher image proxy / fallback |
| `POST /api/avatar/narration/<id>` | Requested news-script language or explicit fallback |
| `GET /api/avatar/voice/status` | Installed providers (not a live connectivity test) |
| `POST /api/avatar/voice/sample` | Fixed sample in a requested language / provider |
| `POST /api/avatar/voice/<id>` | Article voice audio |

## Limits, consent and source attribution

- Default NLP uses TF-IDF / VADER and extractive summaries, not a separately trained large generative model.
- Automatic translation uses external services and may be rate-limited, especially for Bhojpuri; failed translations use a labelled English script rather than pretend to be in the requested language.
- Publisher RSS, full-text extraction, thumbnails and photographs may be blocked, removed or licensed for limited uses. Always link to and credit the original publisher.
- `edge-tts` is an open-source client to Microsoft's **proprietary online voice service**, not a bundled offline neural model; check upstream availability and terms before commercial use.
- Public voice endpoints should be protected with suitable quotas/rate limits on heavily used deployments.

See [Release notes](RELEASE_NOTES.md), [validation report](VALIDATION_REPORT.md), and [Render deployment guide](DEPLOY_RENDER.md).
