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
