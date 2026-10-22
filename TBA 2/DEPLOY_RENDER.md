# TBA News — Render Free Web Service deployment

**This ZIP contains the original Flask app and its full frontend, AI/ML, share cards, image proxy and multilingual narrator.**
It has a production Gunicorn command, a Render Blueprint (`render.yaml`) and a 3.11.9 Python pin.
The free tier is suited to demonstrations and coursework, not guaranteed 24/7 uptime.

## 1. Push the project to GitHub

1. Extract this ZIP.
2. Create a new repository at https://github.com/new.
3. Upload the extracted **contents** (`app.py`, `render.yaml`, `requirements.txt`, `static/`,
   `templates/`, `services/`, etc.) **to the repository root**.
4. Do **not** upload a `.env` file, API keys, downloaded voice models, or local virtual environments.

## 2. Create a free Render web service

1. Visit https://dashboard.render.com and sign in.
2. Select **New > Web Service**, link your GitHub repository, and choose the branch.
3. Choose **Language: Python 3**, **Instance type: Free**.
4. Set the build command: `pip install -r requirements.txt`
5. Set the start command:
   `gunicorn --bind 0.0.0.0:$PORT --workers 1 --threads 4 --timeout 120 app:app`
6. Under **Environment**, add `PYTHON_VERSION=3.11.9`, `TBA_RESOLVE_GOOGLE_LINKS=1`,
   `FLASK_DEBUG=0`, and `TBA_ENABLE_PARLER=0`.
7. (Optional) Set the health check path to `/api/health`.
8. Click **Deploy Web Service**. A public `https://<service>.onrender.com` URL appears after deployment.

Alternative: select **New > Blueprint**, pick your repository, and Render reads `render.yaml`.
Review the cost shown at confirmation: it should say **Free**.

## 3. Check deployment

- Open `/` — homepage and bundled logo should load.
- Open `/api/health` — JSON should contain `"status": "ok"`.
- Open `/api/news?category=top` — should return `items` if Google News RSS is reachable.
- Open the homepage and observe images. For images that cannot be downloaded from a publisher,
  the design deliberately shows the branded category illustration rather than a broken image.
- Click **Quick read** for an article; open a narrator and test each desired voice.
- Run `python scripts/check_deployment.py https://<service>.onrender.com` from your computer
  for the public, read-only health/static/RSS smoke checks.

## 4. Will article images always work?

**Bundled static images:** yes, if the app is up and the deploy succeeded. They are inside `static/assets/`.
**Live news photographs:** best-effort. The backend first checks RSS media links, then tries publisher
og:image/Twitter/JSON-LD images, validates image bytes and dimensions and serves a safe resized copy.
This improves on direct hotlinking, but cannot defeat publisher access restrictions, deleted photographs,
missing metadata, robots policies, HTTP 403/429 or network errors. On failure the card displays a
category placeholder, not a blank card. This is a source-availability limitation, not a Render bug.

News metadata and image bytes are cached in the **running process's memory**. Keep exactly one
Gunicorn worker unless you replace in-memory caches with shared storage. When the free service goes
idle and restarts, these caches reset; the next `/api/news` request rebuilds them. Older shared story
deep-links may fail if their story has left the current feed. No database is included in this ZIP.

## 5. Free-plan caveats

- Render free services sleep after **15 minutes** of no requests; startup may take **about one minute**.
- Free instance hours are **750 per workspace per month**; included bandwidth/build minutes also apply.
- Files written by the app and in-memory caches are not durable after spin-down or restart.
- Don't add large `torch`, `transformers`, Parler or offline Piper models on the free 512 MB plan.
  The standard voices use `edge-tts` remotely, and translations need third-party services, both of
  which may rate-limit or change their availability.
- RSS and publisher websites may throttle cloud IP ranges. A live 100% image success guarantee is not
  possible without a licensed/authorized image content provider.
- If cost avoidance matters, don't add a payment method without reviewing usage/billing settings.

## 6. Troubleshooting

- **Build error / incompatible Python:** confirm `PYTHON_VERSION=3.11.9`, redeploy.
- **Internal server error:** inspect Render Logs; verify `app:app` and dependency installation.
- **No headlines:** inspect Logs; Google News or DNS may be temporarily blocked. Check `/api/news`.
- **Some images absent:** publisher likely blocked images; the category fallback is expected.
- **Voice not working:** `edge-tts` needs outbound Microsoft voice-service connectivity; online
  availability is not guaranteed. Language-select and browser speech fallback depend on client UI.
- **Slow first load:** expected after free service sleeps. Try again when `/api/health` is reachable.

Official references:
https://render.com/docs/deploy-flask
https://render.com/docs/free
https://render.com/docs/python-version
