# Why multilingual narration works locally but may fail on Render

TBA has **two separate online operations**:

1. **Translate the news text**: preferred configured Azure Translator F0 REST API (if you provide a key); otherwise best-effort public Google Translate/MyMemory providers. No Azure key is needed for voice samples.
2. **Synthesize audio**: Python `edge-tts` sends speech requests to Microsoft's online Edge speech service. This is independent of translation.

The browser menu only selects a language and gender. Changing the menu cannot repair an upstream error.

## October 2026 `edge-tts` breaking change

`edge-tts` 7.2.8 and earlier experienced HTTP 403 WebSocket handshake errors after Microsoft's October 2026 protocol change. **Version 7.3.1** was released on October 13 with an upstream fix. Older versions can still be installed if an old deploy/build cache is reused or an older requirements file is deployed. This release requires `edge-tts>=7.3.1,<8` and Render's blueprint builds with `pip install --no-cache-dir -r requirements.txt`.

**Action:** Push the whole updated project to GitHub. In Render go to **Manual Deploy > Clear build cache & deploy** (wording may vary). Check logs for the installed version. If you created a manual web service, update its build command to `pip install --no-cache-dir -r requirements.txt`.

After deploy, open:

`https://YOUR-APP.onrender.com/api/avatar/voice/status`

Look for an `edge_tts_version` of at least `7.3.1`. The `providers` object merely confirms the Python package is installed; it **does not** prove the outbound voice request can succeed.

## Exact voice test (does NOT translate articles)

From macOS or Linux terminal:

```bash
curl -fsS -X POST 'https://YOUR-APP.onrender.com/api/avatar/voice/sample' \
  -H 'Content-Type: application/json' \
  -d '{"language":"mr","provider":"edge-swara"}' \
  -o marathi.mp3
```

From Windows PowerShell:

```powershell
$uri = 'https://YOUR-APP.onrender.com/api/avatar/voice/sample'
$body = '{"language":"mr","provider":"edge-swara"}'
Invoke-WebRequest -Uri $uri -Method Post -ContentType 'application/json' -Body $body -OutFile marathi.mp3
```

If this fails, check the **Render Logs**: `Voice preview unavailable`, `WSServerHandshakeError`, `403`, `timeout`, or `NoAudioReceived`. Try the **Preview selected voice** button within a news story. A successful sample response is `audio/mpeg` and contains MP3 data, not JSON. Repeat with `hi`, `bho`, `ml`, `en` and `edge-madhur` for male.

## If samples play but the article stays in English

This is a **translation** outage, not a voice-selection bug. Render shared IPs can be blocked/rate-limited by public translators. TBA intentionally falls back to an English briefing instead of pretending it has correctly translated a story. Look for the explicit `translation unavailable` notice.

### Optional reliable hosted translation: Azure Translator F0

1. Create a **Translator** resource at https://portal.azure.com. If eligible, select the **F0 free tier** (Microsoft currently lists 2 million standard translation characters/month; usage and availability rules can change).
2. In **Keys and Endpoint**, locate the Translator key and resource region.
3. In **Render > Your Web Service > Environment**, set:
   - `TBA_AZURE_TRANSLATOR_KEY` = your secret key (not in `.env`, GitHub or frontend files)
   - `TBA_AZURE_TRANSLATOR_REGION` = your resource region such as `eastus` (use the region shown in Azure)
4. Save and redeploy/restart. The app will try Azure first, then public translation providers as a fallback.
5. Open `/api/avatar/voice/status` and confirm `azure_translation_configured: true` (this says a key is set, **not** that the key or account has been verified).
6. Open a current story, select Marathi and wait for translated Devanagari text. Then press Play. Try Malayalam next (Malayalam script), and Hindi/Bhojpuri (Devanagari). Bhojpuri audio is still read by a Hindi voice, with approximate accent.

Microsoft Translator documentation currently lists translation support for Hindi (`hi`), Marathi (`mr`), Bhojpuri (`bho`), and Malayalam (`ml`). F0 requires an Azure subscription/resource; it is optional and not an automatic hosted service bundled with TBA.

## Symptom reference

| Symptom | Most likely layer | What to check |
|---|---|---|
| Preview fails for every language | Speech connection | `edge_tts_version`, Render logs, upstream 403, outbound reachability |
| Preview works, article language remains English | Translation | Google/MyMemory rate limit; optionally configure Azure Translator |
| Audio generates but doesn't start automatically on phone | Browser autoplay policy | Tap **Play** again after generation; check site media permissions |
| Selected Bhojpuri voice sounds Hindi | Voice availability | Intentional Hindi-accented fallback; not a native Bhojpuri voice |
| An article disappears or returns 404 | In-memory story state | Refresh news feed; free instance may have restarted |

**Limitations:** Code or hosting changes cannot guarantee uninterrupted access to Microsoft's consumer Edge voices; the upstream service may change. If 7.3.1+ still fails with a 403 on Render, do not change narrator languages blindly—inspect the actual Render traceback and consider an authorized hosted speech service. Offline Piper Hindi weights are optional, local-only, and **not** a replacement for online Marathi/Malayalam/Bhojpuri on Render Free.
