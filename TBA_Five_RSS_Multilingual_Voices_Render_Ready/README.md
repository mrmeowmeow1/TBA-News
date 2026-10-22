# TBA

## Recommended public hosting: Render Free

**[Start with DEPLOY_RENDER.md](DEPLOY_RENDER.md)** for a complete deployment walkthrough,
health checks, and an accurate explanation of image availability and free-plan limitations.
**Do not upload the ZIP itself as the service source:** extract its contents and push them to GitHub.

- Python is pinned to 3.11.9 using `.python-version` and `render.yaml`.
- The free-plan Gunicorn command uses one worker for correct in-memory RSS/article/image sharing.
- Local logos/icons load from `static/assets/`; live publisher photographs remain best-effort.
- Render free sleeps when idle; the next visit can take around a minute to wake up.


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

The official TBA logo is included in `static/assets/` and appears in the sidebar, mobile header, browser tab/app icon, social preview and generated story share cards. Logo files are in `static/assets/` for replacement if needed.

## Features

- Five direct publisher RSS sources (Indian Express, The Hindu, BBC, NDTV, Guardian) for top stories, India, world, sports, business, technology, entertainment, science and health
- Search, sort, topic filters, similar-story grouping, and saved articles
- TF-IDF topic similarity, VADER sentiment, duplicate detection, and related-story recommendations
- Quick Read extracts readable publisher text where permitted, otherwise clearly labels limited descriptions and unavailable content
- Voice presenter with animated SVG eyes, mouth, speech controls, and five visible languages: English, Hindi, Marathi, Bhojpuri, Malayalam
- Ten selectable language/gender narrator presets: online female/male English, Hindi, Marathi, Bhojpuri text (using clearly labeled Hindi voices), Malayalam; offline Hindi Piper/Parler remains optional
- Branded TBA share-card PNGs, browser-native sharing when available, and dark mode

## Documentation

- [Render deployment instructions](DEPLOY_RENDER.md) — deployment, feed diagnostics, images, publisher rights and free-plan limits.
- [Release notes](RELEASE_NOTES.md) — what changed in this multilingual/narrator update.
- [Narration languages and voices](docs/VOICES_AND_SHARING.md) — all ten combinations, fallback rules, offline models and troubleshooting.
- [Validation report](VALIDATION_REPORT.md) — static, frontend and backend validation limits.
- `tests/` includes offline Python fixtures, publisher RSS regression tests, and JavaScript smoke tests.

## Deploying to Render

This application is ready for one-click deployment on [Render](https://render.com):

1. **Connect your Git repository** to Render.
2. For a **Blueprint** use [`render.yaml`](render.yaml). For a **Web Service**, configure the commands below manually.
3. If setting up manually as a **Web Service**:
   - **Environment**: Python 3.11.9
   - **Build Command**: `pip install -r requirements.txt`
   - **Start Command**: `gunicorn --bind 0.0.0.0:$PORT --workers 1 --threads 4 --timeout 120 app:app`
   - **Health Check Path**: `/api/health`

## Project layout

```text
TBA/
├── app.py                  Flask API and article processing
├── services/               NLP, sentiment, similarity, voices and optional AI summary
├── templates/              HTML and SVG character
├── static/                 Stylesheets and browser JavaScript
├── scripts/                Mac setup and optional offline voice download
├── tests/                  Offline/unit/browser-smoke tests
├── docs/                   Guides and architectural documentation
├── models/                 Optional downloaded offline voice weights
├── requirements.txt        Production requirements (Flask, Gunicorn, ML, Edge-TTS)
├── Procfile                Render process definition
├── render.yaml             Render Blueprint definition
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

**Publisher image updates:** RSS `media:thumbnail`, `media:content`, enclosures and article metadata are checked. Editorial images as small as 160×90 pixels are accepted; blocked images fall back to a branded placeholder. The frontend also tries a publisher-hosted photo if the backend proxy fails.

**Technical honesty:** Default news analysis uses TF-IDF similarity and VADER, not a separately trained classifier. Summaries are extractive by default; external generative AI requires configuration. Hindi text translation uses external services and can rate-limit. `edge-tts` is a free client to a proprietary online speech service, not a fully open-source offline speech model. Publisher access and original images are not guaranteed. Always refer to original reporting.
