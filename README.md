# TBA

![TBA official logo](static/assets/tba-logo.webp)

**TBA** is a responsive news aggregation and reading application with built-in classical NLP analysis, article overviews, interactive voice narration, and shareable story cards. The user-facing project name is **TBA**.

## Quick start (macOS)

Python 3.11 is recommended for Intel Macs. From the extracted `TBA/` folder:

```bash
brew install python@3.11   # skip if you already have Python 3.11
bash scripts/setup_mac.sh
source .venv311/bin/activate
python app.py
```

Open **http://127.0.0.1:5000** (or the port set in `.env`). The setup script installs the core dependencies, **including both Swara and Madhur**. Do **not** install optional offline Piper requirements unless you need offline voices and have a compatible system.

## Brand assets

The official TBA logo is included in `static/assets/` and appears in the sidebar, mobile header, browser tab/app icon, social preview and generated story share cards. See [Branding guide](docs/BRANDING.md) for asset sizes and replacement instructions.

## Features

- Google News RSS discovery: top stories, India, world, sports, business, technology, entertainment, science and health
- Search, sort, topic filters, similar-story grouping, and saved articles
- TF-IDF topic similarity, VADER sentiment, duplicate detection, and related-story recommendations
- Quick Read extracts readable publisher text where permitted, otherwise clearly labels limited descriptions and unavailable content
- Voice presenter with animated SVG eyes, mouth, speech controls, and English/Hindi selection
- Online neural Hindi narration: **Swara (female)** and **Madhur (male)**, plus corresponding English fallback voices
- Branded TBA share-card PNGs, browser-native sharing when available, and dark mode

## Documentation

| Guide | Contents |
|---|---|
| [Setup guide](docs/SETUP.md) / [PDF](docs/TBA_Setup_Guide.pdf) | First-time installation, `.env`, voices, Mac troubleshooting |
| [ML and NLP](docs/AI_ML.md) | Implemented algorithms, evaluation notes and limitations |
| [Avatar](docs/AVATAR.md) | Presenter interactions, English/Hindi narration and animation |
| [Voices and sharing](docs/VOICES_AND_SHARING.md) | Voice selection and share cards |
| [Offline voices](docs/OFFLINE_VOICES.md) | Optional Piper/Parler installation caveats |
| [Testing](docs/TESTING.md) | Test commands and limitations |

Older fixes and implementation notes are archived in `docs/history/` and are not required for installation.

## Project layout

```text
TBA/
├── app.py                  Flask API and article processing
├── services/               NLP, sentiment, similarity, voices and optional AI summary
├── templates/              HTML and SVG character
├── static/                 Stylesheets and browser JavaScript
├── scripts/                Mac setup and optional offline voice download
├── tests/                  Offline/unit/browser-smoke tests
├── docs/                   Guides and legacy notes
├── demo/                   Standalone interactive SVG avatar
├── models/                 Optional downloaded offline voice weights
├── requirements.txt        Standard app + online female/male voices
└── .env.example            Optional configuration template
```

## API overview

| Endpoint | Purpose |
|---|---|
| `GET /api/news?category=top` | RSS feed and enriched headlines |
| `GET /api/article/<id>` | Quick Read overview |
| `GET /api/image/<id>` | Validated publisher photograph, if found |
| `POST /api/avatar/narration/<id>` | English/Hindi briefing script |
| `GET /api/avatar/voice/status` | Optional narrator availability |
| `POST /api/avatar/voice/sample` | Selected voice sample audio |
| `POST /api/avatar/voice/<id>` | Selected article's voice audio |
| `GET /api/health` | Server health |

**Technical honesty:** Default news analysis uses TF-IDF similarity and VADER, not a separately trained classifier. Summaries are extractive by default; external generative AI requires configuration. Hindi text translation uses external services and can rate-limit. `edge-tts` is a free client to a proprietary online speech service, not a fully open-source offline speech model. Publisher access and original images are not guaranteed. Always refer to original reporting.

-----------
# TBA: Hindi narrators + shareable news cards

## Recommended for an Intel Mac

Swara (female) and Madhur (male) are installed by the main `requirements.txt` through the open-source `edge-tts`
client. Microsoft provides the online neural voices; the models themselves are
NOT open source, and the text you synthesize is sent to Microsoft's speech
service. No paid API key or ONNX Runtime is necessary. Availability, usage
permissions and rate limits depend on Microsoft; do not treat this unofficial
interface as a guaranteed production SLA. Review service terms before
commercial use.

```bash
# In the active Python 3.11 virtual environment:
python -m pip install -r requirements.txt
python app.py
```

Open the website, choose any article, click Try me, choose Hindi, select
**Swara** or **Madhur** and click **Preview selected voice**. This fixed Hindi
example does not require translation. Full-article Hindi narration still
requires successful translation of that particular article.

## Offline open-source alternatives

The project retains Piper **Priyamvada** (female) and adds **Rohan** (male).
Piper is open source, but voice datasets can carry restrictive noncommercial
licensing. Review their model cards before redistributing audio commercially.
On an older Intel macOS with Python 3.14, ONNX Runtime may have no compatible
wheel. Prefer Python 3.11 if your macOS is supported and consult the PyPI
macOS minimum version of the wheel.

```bash
python -m pip install -r requirements-piper-optional.txt
python scripts/download_piper_models.py --voice priyamvada
python scripts/download_piper_models.py --voice rohan
```

Indic Parler Divya remains optional and GPU-heavy.

## Share a news card

Each story has a **Share** button. The browser builds a square PNG with an
article image (if loaded), story title, publisher, category, date, and source
link. On platforms supporting Web Share files it opens the native share sheet
with that PNG and original article URL. Otherwise it downloads the PNG and
tries to copy the link. It never uploads the image to this backend. Card
artwork is attributed to the source; users should verify reuse rights before
redistributing publisher photographs. The link may be a Google News RSS
redirect rather than a direct publisher URL.

## Security and robustness

- Voice API does not accept arbitrary text, only existing article IDs and a
  fixed sample sentence. Public deployments need authentication, rate limits
  and cost/traffic controls to prevent voice abuse.
- Online speech can fail due to network, terms or rate limits. The frontend
  displays a clear message; it does not silently fake a Hindi voice.
- The screenshot/card image is generated in the browser via Canvas with no
  external JS dependencies or access to private browser files.
- News Hindi translation is still a separate and potentially unreliable
  dependency. Voice preview works even when translation is down.

## Voice-switch regression fix (2026-10-17)

Read **docs/history/VOICE_SWITCH_FIX.md**. The dropdown can now select different English and Hindi male/female voices during playback without restarting Flask. English translation fallbacks use English neural voices instead of ignoring the dropdown.
