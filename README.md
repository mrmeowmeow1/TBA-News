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
