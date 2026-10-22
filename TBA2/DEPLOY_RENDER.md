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
4. Set the build command: `pip install --no-cache-dir -r requirements.txt`
5. Set the start command:
   `gunicorn --bind 0.0.0.0:$PORT --workers 1 --threads 4 --timeout 120 app:app`
6. Under **Environment**, add `PYTHON_VERSION=3.11.9`, `TBA_NEWS_SOURCE=direct`, `TBA_RESOLVE_GOOGLE_LINKS=0`,
   `FLASK_DEBUG=0`, and `TBA_ENABLE_PARLER=0`.
7. (Optional) Set the health check path to `/api/health`.
8. Click **Deploy Web Service**. A public `https://<service>.onrender.com` URL appears after deployment.

Alternative: select **New > Blueprint**, pick your repository, and Render reads `render.yaml`.
Review the cost shown at confirmation: it should say **Free**.

## 3. Check deployment

- Open `/` — homepage and bundled logo should load.
- Open `/api/health` — JSON should contain `"status": "ok"`.
- Open `/api/news?category=top` — should return `items`, `sources`, and `feeds_responding` (uncached) when direct publisher RSS feeds are reachable.
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
- **No headlines:** inspect Logs for each of the five direct feeds; publishers or DNS may be temporarily blocked. Check `/api/news?category=top&refresh=1` (contains `feeds_responding` and `sources`).
- **Some images absent:** publisher likely blocked images; the category fallback is expected.
- **Voice not working:** the October 2026 Microsoft speech protocol change made old `edge-tts` releases fail with 403. Redeploy with `edge-tts>=7.3.1` **after clearing Render build cache** and check `/api/avatar/voice/status` for `edge_tts_version`. If the preview still fails, inspect Render's voice-service traceback; outbound service access is not guaranteed.
- **Previews work but non-English article text does not:** public translation may be limited from hosting IPs. Optional Azure Translator F0 can provide a keyed translation service; see `docs/RENDER_MULTILINGUAL_FIX.md`.
- **Slow first load:** expected after free service sleeps. Try again when `/api/health` is reachable.

Official references:
https://render.com/docs/deploy-flask
https://render.com/docs/free
https://render.com/docs/python-version

## 7. Five-source RSS release (October 2026)

Default `TBA_NEWS_SOURCE=direct`; `TBA_RESOLVE_GOOGLE_LINKS=0` is recommended. Google News is **not** used for the main app in this deployment. The five configured publishers are The Indian Express, The Hindu, BBC News, NDTV.com and The Guardian, with topical feeds for the existing categories. If one feed cannot be reached, the others may still supply cards; the response provides `feeds_responding` and `sources` for diagnosis (on an uncached request).

Use this manual check after deployment:

```bash
curl 'https://YOUR-RENDER-URL.onrender.com/api/news?category=top&refresh=1'
```

Confirm `"feed_mode":"direct"` and a nonempty `items` array. Open one returned card, verify its `url` is a direct publisher URL (not `news.google.com`), click Quick Read, and inspect its image. Short RSS descriptions are **not** presented as fabricated full-article summaries; some publishers block server-side article fetching. If such a page is blocked, Quick Read shows the publisher excerpt/description if sufficiently informative, otherwise a clear original-story button. Not every photo can be displayed.

**Copyright/permission:** The Indian Express and NDTV RSS policies explicitly restrict RSS consumption to personal, non-commercial use. All news and photos remain the publishers' property. A public/revenue-generating news service needs proper permission or licensing as applicable. TBA provides clear source credit and links to originals; don't assume an RSS URL grants syndication rights.


## Multilingual narrator update (this ZIP)

Redeploy the **entire extracted repository**, especially `templates/index.html`, `static/avatar.js`, and `static/avatar.css`. The narrator assets use a new `v=tba-avatar-v7-edge-protocol-2026` cache-busting query. Hard refresh the browser after deployment.

Open an article → AI presenter → **Step 2 · Choose narrator (Language + Female / Male)**. The menu has 10 combinations and is the only narrator engine control (the confusing Advanced voice-engine selector was removed). The **Preview selected voice** button works even without a translated article. Translation itself still depends on an external provider and may fall back to English, clearly labeled.

Bhojpuri uses Hindi neural voices to read Bhojpuri text; this is an approximation, not a native Bhojpuri voice. See `docs/VOICES_AND_SHARING.md` for the complete mapping and testing guide.

## Simplified narrator update (v6)

The **Advanced · Voice Engine (Optional)** dropdown is no longer shown. Select the language + female/male voice in **Step 2**. This always uses the matching online narrator, avoiding accidental selection of Hindi-only Piper/Parler for Marathi, Bhojpuri or Malayalam. The preview uses the selected language, even when an article has fallen back to English because translation failed.

Optional offline Hindi Piper/Parler setup instructions are retained in `README.md` and `docs/OFFLINE_VOICES.md`, **not installed on Render**. Test each online preview after updating GitHub and redeploying; a syntax/smoke test cannot confirm Microsoft voice service connectivity from your Render instance.

## October 2026 hosted narrator fix (v7)

This version changes `requirements.txt` to require `edge-tts>=7.3.1,<8`, adds voice diagnostics to `/api/avatar/voice/status`, and supports optional Azure Translator for Hindi, Marathi, Bhojpuri and Malayalam article text. Update the entire repository, **clear Render's build cache**, and redeploy. After that, test the Marathi voice sample separately from article translation. Details: `docs/RENDER_MULTILINGUAL_FIX.md`.
