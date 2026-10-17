# TBA - Complete Project Installation & Setup Guide

**Edition:** Unified core installation, Hindi/English female and male narrators, ML/NLP, AI avatar, share cards

**Platform:** macOS (especially an Intel Mac / `x86_64`)

**Recommended Python:** 3.11

**Start here if you are seeing `ResolutionImpossible` or having to install the voice packages separately.**

---

## 1. Why were the voices installed separately?

A Python `requirements.txt` file is just a list of packages to install into your project's **virtual environment**. The old project had several lists because it offered different optional voice engines:

| File | Why it existed | Do you need it now? |
|---|---|---|
| `requirements.txt` | Flask, RSS, article extraction, ML/NLP, translation | **Yes. Also installs online voices now.** |
| *(no separate online-voice file)* | Swara (female) and Madhur (male) are part of `requirements.txt` | **No extra command required.** |
| `requirements-piper-optional.txt` | Piper, a local/offline neural speech engine | **No. Optional only.** Avoid on your current incompatible Intel/Python environment. |
| `requirements-parler-optional.txt` | Large Indic Parler-TTS (Divya) dependencies | **No. Optional advanced/GPU model.** |

The standard installation now uses **one command** to install everything needed for the site, news, ML/NLP, avatar, and the standard Swara/Madhur voices:

```bash
python -m pip install -r requirements.txt
```

Swara and Madhur use the `edge-tts` Python client and Microsoft's **online** neural speech service. The client is open source; **the Microsoft voice models are not open source and are not hosted on your laptop**. No Piper or ONNX Runtime is needed. Voice preview still needs internet access, and a Hindi news narration additionally needs successful translation.

**Important:** A *virtual environment* (`.venv311`) and an *environment settings file* (`.env`) are different things. `.venv311` contains installed Python packages. `.env` contains configuration (like the port or an optional AI API key).

---

## 2. What gets installed in the standard setup?

- **Flask:** serves the website and backend API.
- **Requests + Feedparser:** fetches and parses Google News RSS.
- **BeautifulSoup + Pillow:** extracts available article text and verifies images.
- **scikit-learn + NumPy:** TF-IDF topic classification, similarity, duplicate grouping and related news.
- **vaderSentiment:** default English news sentiment analysis.
- **deep-translator:** attempts optional English-to-Hindi translation; external free providers can rate-limit.
- **edge-tts:** Swara (female) and Madhur (male) neural narration, including gender-matched English fallback voices.
- **python-dotenv:** automatically reads `.env` whenever you run `python app.py`.

The standard setup **does not** automatically install Piper, Parler, large Transformer models, model weights, or a paid AI API. Those are optional and may be incompatible with some Mac configurations.

---

## 3. Before installing: check your Mac

Open **Terminal** and run:

```bash
uname -m
python3 --version
sw_vers -productVersion
```

In your earlier logs, you had `x86_64` (Intel) and Python 3.14.2. A new Python 3.11 environment is recommended for this project because some ML/audio dependencies do not yet support all Python/macOS combinations. **Don't delete your old `.venv` or system Python.**

### Check for Homebrew

```bash
brew --version
```

If Homebrew is installed, run:

```bash
brew install python@3.11
python3.11 --version
```

If `brew` says command not found, install Homebrew from its **official** website, https://brew.sh, or install a supported Python 3.11 from https://www.python.org/downloads/. On very old macOS versions, you may need a Python installer that explicitly supports that version; don't force incompatible binaries. If `python3.11` isn't found after installing, check `brew --prefix python@3.11` and the install messages for its executable path.

**Target:** `python3.11 --version` shows `Python 3.11.x`.

---

## 4. Get the new project into a folder

1. Extract the latest **TBA unified setup** ZIP.
2. Find the inner folder named `TBA`.
3. Open Terminal inside that folder. On a Mac, type `cd ` and drag the folder into Terminal, then press Return.
4. Verify the location:

```bash
pwd
ls
```

You should see `app.py`, `requirements.txt`, and the `docs`, `scripts`, `services`, `static`, and `templates` folders.

Do **not** mix files from several older ZIP releases. Doing so can restore old JavaScript files or old Python voice settings.

---

## 5. Fastest installation - automatic Mac setup (recommended)

Inside `TBA` run:

```bash
bash scripts/setup_mac.sh
```

This script:

1. Checks that `python3.11` exists.
2. Creates `.venv311` in the current project folder.
3. Upgrades pip **inside** that environment.
4. Runs `pip install -r requirements.txt` (including `edge-tts`).
5. Copies `.env.example` to `.env` **only if `.env` does not already exist**.

It **does not** install Piper or Divya, overwrite `.env`, remove other environments, or start the server automatically.

After installation, run:

```bash
source .venv311/bin/activate
python --version
python app.py
```

Open **http://127.0.0.1:5000** in your browser.

If the automatic script fails, follow the manual steps below so you can see which command fails.

---

## 6. Manual installation - every command explained

### A. Create a dedicated environment

```bash
python3.11 -m venv .venv311
source .venv311/bin/activate
python --version
```

- `python3.11 -m venv .venv311` creates an isolated Python folder.
- `source .venv311/bin/activate` makes `python` and `pip` refer to that folder.
- `python --version` should say `3.11.x`, not 3.14.

You may see a `(.venv311)` prefix in Terminal. This is normal.

### B. Install standard dependencies (ONE requirements command)

```bash
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

You **do not** need to run `pip install -r requirements.txt` again. You also **do not** need `pip install -r requirements-piper-optional.txt` to hear Swara or Madhur.

### C. Create the `.env` settings file

```bash
cp .env.example .env
```

The application now loads `.env` automatically when started with `python app.py`. You no longer have to run `source .env` or manually export variables. Existing shell environment variables still take priority over values in `.env`.

### D. Start the server

```bash
python app.py
```

Open the link printed by Flask, normally **http://127.0.0.1:5000**.

To stop the server, press **Ctrl + C**. To run it again tomorrow:

```bash
cd /path/to/your/TBA
source .venv311/bin/activate
python app.py
```

Replace the example path with your actual project path.

---

## 7. `.env` settings explained

`.env` is a plain text file stored in the project root. Open it with VS Code or a text editor. The complete template is `.env.example`.

A typical **local development** config looks like this:

```dotenv
PORT=5000
FLASK_DEBUG=0
TBA_RESOLVE_GOOGLE_LINKS=1
TBA_SENTIMENT_BACKEND=vader
TBA_DUPLICATE_THRESHOLD=0.50
TBA_RECOMMENDATIONS=4
TBA_AI_API_KEY=
```

| Setting | Recommended starting value | Meaning |
|---|---|---|
| `PORT` | `5000` or `5050` | The local Flask port. |
| `FLASK_DEBUG` | `0` | Keep development debugger disabled unless needed locally. Never enable it publicly. |
| `TBA_RESOLVE_GOOGLE_LINKS` | `1` | Try resolving encoded Google News story links. |
| `TBA_SENTIMENT_BACKEND` | `vader` | Small built-in rule-based sentiment mode. `transformers` is optional/heavier. |
| `TBA_DUPLICATE_THRESHOLD` | `0.50` | Text similarity threshold for grouping likely duplicate reports. |
| `TBA_RECOMMENDATIONS` | `4` | How many related stories to display. |
| `TBA_AI_API_KEY` | empty | Empty means local extractive Quick Read; an external generative AI API is optional. |
| `TBA_AI_BASE_URL` | Provided by the chosen AI provider | Only relevant if using an external AI summary. |
| `TBA_AI_MODEL` | Provided by the chosen AI provider | Only relevant if using an external AI summary. |
| `TBA_ENABLE_PARLER` | `0` / unset | Leave disabled unless separately installing the heavy Divya model. |

**None of these settings selects Swara or Madhur.** The user chooses the narrator in the **Try Me** dropdown. The online voice library is already installed by `requirements.txt`.

Never commit `.env` to GitHub or send a real API key to someone. This edition includes `.gitignore` to help prevent uploading secrets and local environments.

If you edit `.env`, **restart Flask once** for the new server settings to load. Changing a narrator in the live website should **not** require restarting Flask.

### Example: port 5000 is busy

Change this in `.env`:

```dotenv
PORT=5050
```

Restart Flask and open **http://127.0.0.1:5050** instead.

---

## 8. Verify your environment and installation

Keep the correct virtual environment active and run:

```bash
python -m pip check
python -c "import flask, feedparser, sklearn, vaderSentiment, edge_tts, dotenv; print('Core and voices installed successfully')"
python -c "from services.voice_service import available; print(available())"
```

For the standard installation, expect a result that includes:

```text
'edge-swara': True
'edge-madhur': True
```

Piper and Parler may legitimately show `False` because they are optional. This status check only confirms that the **Python packages are present**, not that an external online speech request can succeed.

Start the server, then open or request:

```text
http://127.0.0.1:5000/api/health
http://127.0.0.1:5000/api/avatar/voice/status
```

You can also use Terminal:

```bash
curl http://127.0.0.1:5000/api/health
curl http://127.0.0.1:5000/api/avatar/voice/status
```

If you use port 5050, replace `5000` in the URLs.

---

## 9. Test the news website and all major features

1. Open TBA and wait for **Top Stories**.
2. Select **Sports** or **Technology** to verify category RSS feeds.
3. Search for a topic (for example, `artificial intelligence`).
4. Open **Quick Read**. The article summary may be extractive, a publisher description, or unavailable if the publisher blocks extraction.
5. Confirm that a sentiment label and AI topic appear on cards when data is available.
6. Bookmark a story and open Saved Articles.
7. Click **Share**: supported devices show native sharing; desktop fallback downloads a PNG/card and attempts to copy the story link.
8. Click **Try Me** to open the avatar. Move the pointer near it to test eyes and blinking.
9. Select **Hindi -> Swara (female) -> Preview selected voice**, then switch to **Madhur (male)** and preview again.
10. Try **English** too: when selected gender maps to Edge voices, the female English voice is Neerja and the male voice is Prabhat.

The **voice preview** uses a fixed script and is the best first test: it does **not** require the news translator.

For end-to-end Hindi news narration, the original English article needs an available summary **and** successful Hindi translation. If external translation is rate-limited, the application may clearly fall back to English; the Swara/Madhur selection can still map to corresponding female/male English voices.

---

## 10. How voice selection works behind the scenes

```text
User opens story -> Try Me -> selects language and narrator
                 |-> English: narration text, no translation
                 |-> Hindi: attempt to translate available source summary
                 v
Flask /api/avatar/voice/<article_id>
                 v
Choose the actual language + narrator (Swara/Madhur)
                 v
edge-tts online synthesis -> MP3 -> browser player + SVG mouth movement
```

**Female Hindi:** Swara (`hi-IN-SwaraNeural`)
**Male Hindi:** Madhur (`hi-IN-MadhurNeural`)
**Female English fallback:** Neerja (`en-IN-NeerjaNeural`)
**Male English fallback:** Prabhat (`en-IN-PrabhatNeural`)

The backend audio cache is separated by **voice, language, article, and text fingerprint**. Selecting a new voice should stop old audio and discard late responses. If voice switching only works after a hard refresh, check for stale JavaScript: **Cmd + Shift + R**.

**Audio privacy/availability:** Browser playback is local, but online synthesis sends the narration script to the external Microsoft speech service. Read the service's current permitted usage before commercial deployment.

---

## 11. Optional: Offline open-source voices (advanced)

These are **not part of standard setup**:

**Piper Priyamvada (female) / Rohan (male).** This local TTS engine uses `onnxruntime`, which previously failed to resolve in your Intel Mac/Python 3.14 environment. If you still want it, first verify that your Python 3.11 and macOS version have a compatible ONNX Runtime wheel. Only then attempt:

```bash
python -m pip install -r requirements-piper-optional.txt
python scripts/download_piper_models.py --voice priyamvada
python scripts/download_piper_models.py --voice rohan
```

Voice model weights must be downloaded separately from Python packages, and individual voice datasets can have noncommercial licensing terms. Do not try to fix an ONNX Runtime incompatibility with `pip install --no-deps`.

**Divya / Indic Parler-TTS.** This is a much larger optional neural model that downloads weights and can be very slow on an Intel CPU. It is not recommended as the first setup. Consult `docs/OFFLINE_VOICES.md` and the model author's official instructions. Do not enable it in `.env` until installed successfully.

**Bottom line:** You can use **the complete standard website plus female/male online voices** without installing *any* of those optional packages.

---

## 12. Troubleshooting - match the symptom

| Problem | Likely cause | What to try |
|---|---|---|
| `ResolutionImpossible` / `No matching distribution found for onnxruntime` | Optional Piper not compatible with current Python/macOS | **Skip Piper.** Use Swara/Madhur from the normal requirements. For offline Piper, check Python 3.11/macOS wheel compatibility separately. |
| `python --version` still shows `3.14` | Old `.venv` activated | `deactivate` then `source .venv311/bin/activate`; re-check `python --version`. |
| `ModuleNotFoundError: flask` | Wrong interpreter or requirements not installed | Activate `.venv311`; run `python -m pip install -r requirements.txt`. |
| `edge-swara: false`, `edge-madhur: false` | `edge-tts` missing from the active environment | Activate `.venv311`; reinstall `requirements.txt`; verify `python -c "import edge_tts"`. |
| Female and male voices sound the same | Old browser JavaScript, old server code, or English fallback path | Confirm you're using this ZIP, hard-refresh (**Cmd + Shift + R**), use **Preview selected voice** and switch; inspect Flask errors. |
| `TooManyRequests` or Hindi translator error | Public translator rate limit | Test the fixed Hindi voice sample first. Wait for provider cooldown; English narration still works. |
| `503` from voice endpoint | Online voice service unavailable, timeout, or optional model missing | Check terminal logs, internet, status endpoint, selected voice and provider. |
| `422` from narration endpoint | Summary/translation unavailable or language incompatible with selected offline voice | Choose English, use headline-only mode when available, or test the fixed voice sample. |
| `404` from `/api/image/...` | A valid article image wasn't available | Category placeholder is expected; it doesn't stop narration. |
| Port 5000 already used | Another process or macOS service uses that port | Change `PORT=5050` in `.env` and restart Flask. |
| Changes in `.env` not applied | Flask was running with old settings | Stop with Ctrl+C, restart the Flask process. |
| `pip` appears to install but Flask can't import package | Installed into different Python env | Always use `python -m pip` while `.venv311` is active. |
| News headlines load but article summaries fail | Publisher robots policy/paywall/JS rendering/Google link encoding | Use the original article link; don't invent a summary. |

**When reporting an error**, include the *first* error line, the section that begins `The conflict is caused by:` if present, and:

```bash
python --version
python -m pip --version
uname -m
sw_vers -productVersion
```

---

## 13. Run tests before submitting the project

With the virtual environment active:

```bash
python -m unittest discover -s tests
```

For JavaScript smoke tests, first install Node.js 18+ if needed, then run:

```bash
node tests/frontend_smoke.js
node tests/avatar_voice_switch_smoke.js
node tests/share_card_smoke.js
```

These tests use mocks and do not establish that live Google News, Google Translator or online TTS will always be available. A final project demonstration should also include hands-on browsing and voice-preview tests.

---

## 14. Project file map

```text
TBA/
├── app.py                           Flask application and REST API
├── .env.example                     Safe, commented configuration template
├── .env                             Your private local configuration (create it)
├── .gitignore                       Keeps .env, Python environments, models out of Git
├── requirements.txt                 Standard installation including Swara/Madhur
├── requirements.txt    Legacy compatibility only; no longer needed
├── requirements-piper-optional.txt    OPTIONAL offline Piper only
├── requirements-parler-optional.txt    OPTIONAL heavy Divya only
├── docs/SETUP.md          This full installation guide
├── README.md                        App overview and architecture
├── scripts/
│   ├── setup_mac.sh                 One-command Mac setup
│   └── download_voice_service.py     OPTIONAL model downloader for Piper
├── services/                        Categorizer, sentiment, similarity, AI summary, voices
├── templates/                       HTML templates + SVG avatar
├── static/                          CSS, JavaScript, audio controls, share cards
├── tests/                           Python and JavaScript checks
└── models/                          Optional locally downloaded voice weights
```

---

## 15. Daily workflow: simplest possible

**First time:**

```bash
brew install python@3.11              # only if you do not already have it
cd /path/to/TBA
bash scripts/setup_mac.sh             # once, includes all standard voice packages
source .venv311/bin/activate
python app.py
```

**Every time after that:**

```bash
cd /path/to/TBA
source .venv311/bin/activate
python app.py
```

**When updating the project code:**

```bash
# After replacing the code files, in the same .venv311:
python -m pip install -r requirements.txt
python app.py
```

You need **one initial Flask restart after code changes**, but **not** when switching Swara and Madhur in the running interface.

---

## 16. Which features are actually AI/ML?

TBA's **default** backend uses TF-IDF + cosine similarity for topics, duplicate grouping and content-based recommendations; VADER for sentiment; and extractive text processing for Quick Read. Those do not require a paid AI API or a locally trained deep-learning model. Online Edge voices are pretrained neural TTS, but the models run at the speech provider, not on your Mac. Optional transformer sentiment and external generative summarization need their own configuration and were not activated by standard setup.

This distinction matters when presenting your MSc project. The standard installer gives you the **working news application and its standard AI-enabled voice features**, not a custom-trained deep-learning research model.

---

**Quick recap (Hinglish):** Ab Swara aur Madhur ke liye alag requirements install karne ki zaroorat nahi. Ek hi `requirements.txt` Flask, ML libraries aur normal male/female online voices install karega. `.venv311` Python packages ke liye hota hai aur `.env` settings ke liye. Piper aur Divya ko optional rakha hai kyunki unke heavy dependencies aapke Intel Mac par conflict de sakte hain.
