# TBA — Deploy on Render Free

## What is included

TBA serves both Flask APIs and the HTML/CSS/JavaScript frontend from one Python web service. The ZIP includes the official TBA logo and app icons. Standard Hindi Swara and Madhur narration uses `edge-tts` (online), while offline Piper/Parler voice models are not installed by default.

## Upload to GitHub

1. Extract `TBA_Render_Deployment_Ready.zip`.
2. Create a new GitHub repository. Upload the **contents of the `TBA` folder** so `app.py`, `requirements.txt`, and `render.yaml` are at the repository root. If GitHub shows `TBA/app.py` instead, set the Render Root Directory to `TBA`.
3. Never commit `.env`, keys, Python virtual environments, cached model weights, or private recordings. `.env.example` is safe if it contains no secrets.

## Create the service

1. Open https://dashboard.render.com and select **New > Blueprint**, then connect the GitHub repo containing `render.yaml`. Confirm it provisions a **Free** web service. Alternatively choose **New > Web Service** and use the commands below.
2. Runtime: Python. Build command: `pip install --upgrade pip && pip install -r requirements.txt`.
3. Start command: `gunicorn --bind 0.0.0.0:$PORT --workers 1 --threads 4 --timeout 120 --access-logfile - --error-logfile - app:app`.
4. Health check: `/api/health`. Python version: 3.11.11.
5. Environment: `FLASK_DEBUG=0`, `TBA_SENTIMENT_BACKEND=vader`, `TBA_ENABLE_PARLER=0`. If configuring optional external AI, enter its key only in Render's environment settings and not in the repository.
6. Deploy. First build can take several minutes. Visit the generated `onrender.com` URL.

## Test immediately after deployment

- `/api/health` returns a JSON status of `ok`.
- Home page loads and displays the TBA logo.
- `/api/news?category=top` returns an items list (may fail temporarily if Google restricts cloud IPs).
- Quick Read shows a summary only when readable article text or publisher metadata exists.
- Avatar > Hindi > preview Swara / Madhur (requires external speech service access); selected voices should switch without restarting.
- Share a card and test bookmarks. Image `404` means a story-specific image was unavailable, not that the app failed.

## Free tier caveats

Free instances can sleep when idle, resulting in cold starts. Instance memory and CPU are limited. The application caches feeds and article data in process memory; restarting or sleeping clears those caches, and the store of recent article IDs. If a story has expired, refresh the feed before trying Quick Read. The free filesystem is ephemeral. Avoid installing Torch, Parler, IndicF5, or Piper into the standard production environment. Online translation and narration can be unavailable, rate-limited, or subject to provider terms. Google News and publishers may block requests from cloud IP addresses. A passing health check does not guarantee third-party feeds or voices are currently available.

## Troubleshooting

- **Build fails**: inspect the Render Build Logs for the *first package that failed*. Use Python 3.11.11; do not install `requirements-piper-optional.txt` or `requirements-parler-optional.txt`.
- **No web page**: confirm the Render service root contains `app.py`; check Gunicorn logs.
- **503/502**: wait for cold start, inspect logs and memory usage; disable optional heavyweight models.
- **No news**: verify `/api/news?category=top` and inspect logs. Feed providers may deny cloud-hosted requests.
- **Hindi fails**: test English first, then the standalone Hindi voice sample. Translation and voice synthesis are separate external requests.
- **Sensitive credentials**: enter secrets in Render's environment UI, never commit `.env`.

## Local production-like test

```bash
python3.11 -m venv .venv311
source .venv311/bin/activate
pip install -r requirements.txt
PORT=10000 gunicorn --bind 127.0.0.1:10000 --workers 1 --threads 4 app:app
```

Open http://127.0.0.1:10000/api/health . Use Ctrl+C to stop.
