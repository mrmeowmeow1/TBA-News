# TBA narrator and sharing guide

## Narrator controls

Open an article → **AI presenter** → **Step 1: Select news language** → **Step 2: Choose narrator (Language + Female / Male)**. Step 2 is the only voice selector. Choosing a language there also updates Step 1; changing Step 1 keeps the chosen gender. The older **Advanced · Voice Engine (Optional)** dropdown was intentionally removed.

| Language | Online female | Online male | Caveat |
|---|---|---|---|
| English `en` | Neerja (`en-IN-NeerjaNeural`) | Prabhat (`en-IN-PrabhatNeural`) | Indian English |
| Hindi `hi` | Swara (`hi-IN-SwaraNeural`) | Madhur (`hi-IN-MadhurNeural`) | Native Hindi |
| Marathi `mr` | Aarohi (`mr-IN-AarohiNeural`) | Manohar (`mr-IN-ManoharNeural`) | Native Marathi |
| Bhojpuri `bho` | Swara (`hi-IN-SwaraNeural`) | Madhur (`hi-IN-MadhurNeural`) | **Hindi** voices read Bhojpuri text, accent approximate |
| Malayalam `ml` | Sobhana (`ml-IN-SobhanaNeural`) | Midhun (`ml-IN-MidhunNeural`) | Native Malayalam |

Every selection uses `edge-tts` to request a Microsoft online neural voice; no separate engine setting is required. The preview sends a fixed sample in **the selected language** and does not require translating a publisher article. Article narration first attempts to translate available news text. If translation fails or is rate-limited, TBA labels the text as an **English fallback** and uses the English voice matching the chosen female/male choice. The preview still tests the selected language even during an article-translation outage.

The system requires Internet access and sends narration text to an external speech service. Availability and rights depend on the provider. A successful `/api/avatar/voice/status` check proves a package is installed, not that the voice network is reachable.

## Offline models stay separate

The project keeps optional Hindi-only **Piper Priyamvada (female)**, **Piper Rohan (male)** and **experimental Indic Parler/Divya** backend integrations for use locally, without altering the public narrator menu. The model weights are not bundled. For installation, required files, API examples, resource limits and licensing see [OFFLINE_VOICES.md](OFFLINE_VOICES.md) and the README's optional offline-model section. Do not install large optional TTS models on Render Free.

## If speech does not play

1. Redeploy the full project, especially `templates/index.html`, `static/avatar.js`, and `static/avatar.css` (version `tba-avatar-v7-edge-protocol-2026`), then hard-refresh.
2. Open a news story, choose **Marathi Female Aarohi**, click **Preview selected voice**. Repeat for Malayalam, Hindi, Bhojpuri and both genders.
3. If the sample fails: confirm `edge-tts` was installed from `requirements.txt`, inspect Render's `/api/avatar/voice/status`, and check logs for voice-service connection errors.
4. If the preview speaks but an article plays in English: that is likely **translation fallback**, not the narrator dropdown. Read the on-screen notice and retry later. Translation is a distinct external dependency.
5. The browser may block playback until a direct user click. Press **Play** again if necessary. Browser/system or offline Piper narrator overrides are no longer exposed in the UI.

## Share cards and news source limits

Story sharing creates a branded PNG in the browser with a story title, source and link. Some publisher photographs cannot be downloaded, hotlinked or redistributed; TBA uses an image placeholder when necessary. Check reuse permissions before sharing publisher photographs. The original article remains the definitive source for facts.

## Hosting-specific troubleshooting (October 2026)

On Render, older `edge-tts` versions can fail with upstream speech handshake 403 even when `/api/avatar/voice/status` says the package is installed. This project now requires `edge-tts>=7.3.1`. Clear build cache and redeploy. If previews work while news remains English, that is a different problem: the translation provider failed. See [the dedicated Render multilingual troubleshooting guide](RENDER_MULTILINGUAL_FIX.md), including the optional Azure Translator F0 setup.
