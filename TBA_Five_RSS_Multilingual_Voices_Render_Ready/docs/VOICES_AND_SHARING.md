# TBA narrator languages — Render Edition

## Using the narrator

1. Open a news story and choose **Listen** (AI news presenter).
2. Under **Step 1**, choose English, Hindi, Marathi, Bhojpuri, or Malayalam.
3. Under **Step 2**, select a language + Female/Male voice combination. The large preset menu includes **10 options** (five languages × two voices). It updates Step 1 automatically.
4. Click **Preview selected voice** to test the selected voice with a built-in sample. Then click **Play narration** to hear the chosen article.
5. For locally installed voices only, use **Advanced · Voice engine** to choose Piper or Parler. These offline modes are *Hindi only*.

| News language | Online female voice | Online male voice | Important limitations |
|---|---|---|---|
| English (`en`) | Neerja (`en-IN-NeerjaNeural`) | Prabhat (`en-IN-PrabhatNeural`) | Native Indian-English voices |
| Hindi (`hi`) | Swara (`hi-IN-SwaraNeural`) | Madhur (`hi-IN-MadhurNeural`) | Real Hindi neural voices |
| Marathi (`mr`) | Aarohi (`mr-IN-AarohiNeural`) | Manohar (`mr-IN-ManoharNeural`) | Real Marathi neural voices |
| Bhojpuri (`bho`) | **Swara — Hindi voice** | **Madhur — Hindi voice** | Bhojpuri TEXT, but synthesized by a Hindi voice. Not a dedicated Bhojpuri accent; some words may be pronounced inaccurately. |
| Malayalam (`ml`) | Sobhana (`ml-IN-SobhanaNeural`) | Midhun (`ml-IN-MidhunNeural`) | Real Malayalam neural voices |

**Two different stages:** TBA first translates the available article information into the selected language using an external service, and then sends that text to an online narrator. If translation is blocked, unavailable, or rate-limited, the application clearly returns an *English fallback*, played with the English narrator matching the selected gender. It does not claim to have produced a Malayalam/Marathi/etc. translation when it has not.

The Edge TTS service sends speech text to Microsoft's online service, needs outbound Internet connectivity, and may be unavailable on some cloud deployments. `edge-tts` is in `requirements.txt`. No API key is configured. Service availability and usage rights depend on the upstream provider.

## Offline voices

The GitHub/Render ZIP includes Piper/Parler support code, **not the multi-hundred-megabyte model weight files**. On a compatible local machine you can separately install Hindi `.onnx` and `.onnx.json` voice files under `models/`, plus the optional requirements files. Render Free (512 MB RAM) is not suitable for large Parler weights. The online narrators are the default.

## Diagnosing missing language choices

- Make sure the new `templates/index.html` and `static/avatar.js` have been pushed together, including the `?v=tba-avatar-v5-multilang` asset version.
- In Render choose **Manual Deploy → Deploy latest commit** (or enable auto deploy), then hard refresh the site (Ctrl/Cmd + Shift + R).
- The big **Step 2** selector now remains rendered even before the avatar JavaScript updates voice labels.
- Use `/api/avatar/voice/status` to confirm the backend can import `edge-tts`. A `true` status confirms the package is installed, not that Microsoft can be reached from Render.
- Use **Preview selected voice** to test each of the 10 choices *without depending on a news article translation*. If voice preview fails, check Render logs and external connectivity.

## Source, images and sharing

The five publisher feeds and image/Quick Read fallbacks from the previous release are unchanged. Publisher licensing, images, article extraction and translation remain subject to upstream availability and permissions. Social sharing uses the existing share-card implementation.
