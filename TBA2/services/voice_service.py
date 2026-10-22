"""Multilingual narration: optional Hindi Piper/Parler and online Edge voices.

Edge TTS is an open-source client to a Microsoft online voice service; the
underlying voice models are proprietary. Text is sent to that provider.
Hindi translation remains a separate step.
"""
from __future__ import annotations

from io import BytesIO
import asyncio
from pathlib import Path
import importlib.util
import os
import threading
import wave

BASE = Path(__file__).resolve().parents[1]
PIPER_MODEL = Path(os.environ.get(
    "TBA_PIPER_MODEL", str(BASE / "models" / "hi_IN-priyamvada-medium.onnx")
)).expanduser().resolve()
ROHAN_MODEL = Path(os.environ.get(
    "TBA_PIPER_ROHAN_MODEL", str(BASE / "models" / "hi_IN-rohan-medium.onnx")
)).expanduser().resolve()
_PIPER = {}
_PARLER = None
_LOCK = threading.Lock()
_PARLER_LOCK = threading.Lock()


class VoiceUnavailable(RuntimeError):
    pass


def available():
    def installed(model):
        return bool(model.is_file() and
                    model.with_suffix(model.suffix + ".json").is_file()
                    and importlib.util.find_spec("piper") is not None)
    online = importlib.util.find_spec("edge_tts") is not None
    return {
        "piper": installed(PIPER_MODEL),
        "piper-rohan": installed(ROHAN_MODEL),
        "edge-swara": online,
        "edge-madhur": online,
        "parler": (os.getenv("TBA_ENABLE_PARLER", "0") == "1"
                   and importlib.util.find_spec("parler_tts") is not None
                   and importlib.util.find_spec("transformers") is not None),
    }


def _piper(provider="piper"):
    model = ROHAN_MODEL if provider == "piper-rohan" else PIPER_MODEL
    if not available().get(provider):
        raise VoiceUnavailable(
            "Piper Hindi model not installed. See docs/OFFLINE_VOICES.md "
            "for Python/ONNX requirements and downloads."
        )
    with _LOCK:
        if provider not in _PIPER:
            import importlib
            piper = importlib.import_module("piper")
            _PIPER[provider] = piper.PiperVoice.load(str(model))
    return _PIPER[provider]


def _piper_wav(text, provider="piper"):
    voice = _piper(provider)
    buf = BytesIO()
    with _LOCK:
        with wave.open(buf, "wb") as wav:
            if hasattr(voice, "synthesize_wav"):
                voice.synthesize_wav(text, wav)
            else:
                voice.synthesize(text, wav)
    return buf.getvalue()


async def _edge_mp3_async(text, provider, language="hi"):
    import importlib
    edge_tts = importlib.import_module("edge_tts")
    # Bhojpuri has no dedicated Edge TTS narrator in this configuration: Hindi
    # voices read genuine Bhojpuri Devanagari text with approximate pronunciation.
    # English fallback must not silently use one shared browser voice. The
    # selected gender is preserved with a matching en-IN neural narrator.
    names = {
        "hi": {"edge-swara": "hi-IN-SwaraNeural", "edge-madhur": "hi-IN-MadhurNeural"},
        "mr": {"edge-swara": "mr-IN-AarohiNeural", "edge-madhur": "mr-IN-ManoharNeural"},
        "bho": {"edge-swara": "hi-IN-SwaraNeural", "edge-madhur": "hi-IN-MadhurNeural"},
        "ml": {"edge-swara": "ml-IN-SobhanaNeural", "edge-madhur": "ml-IN-MidhunNeural"},
        "en": {"edge-swara": "en-IN-NeerjaNeural", "edge-madhur": "en-IN-PrabhatNeural"},
    }
    name = names[language][provider]
    audio = bytearray()
    async for chunk in edge_tts.Communicate(text, voice=name, rate="-5%").stream():
        if chunk.get("type") == "audio":
            audio.extend(chunk.get("data", b""))
            if len(audio) > 12 * 1024 * 1024:
                raise VoiceUnavailable("Online voice audio was too large")
    if not audio:
        raise VoiceUnavailable("Online voice provider returned no audio; retry later")
    return bytes(audio)


def _edge_mp3(text, provider, language="hi"):
    if not available().get(provider):
        raise VoiceUnavailable("Install the optional edge-tts package to use this narrator")
    try:
        return asyncio.run(_edge_mp3_async(text, provider, language))
    except Exception as exc:
        # edge-tts <= 7.2.8 started receiving WebSocket HTTP 403 in Oct 2026.
        # Avoid passing an upstream request URL/token back to a public client.
        upstream_status = getattr(exc, "status", None)
        name = type(exc).__name__
        if upstream_status in (401, 403) or (name == "WSServerHandshakeError" and "403" in str(exc)):
            raise VoiceUnavailable(
                "Microsoft speech rejected the connection (403). Confirm edge-tts 7.3.1+ "
                "is installed on Render, clear its build cache, then redeploy. "
                "If it persists, inspect outbound speech access in Render logs."
            ) from exc
        if isinstance(exc, (asyncio.TimeoutError, TimeoutError)):
            raise VoiceUnavailable("Online speech service timed out; try again.") from exc
        raise VoiceUnavailable(
            f"Online speech service failed ({name}). Check Render logs and the speech provider."
        ) from exc


def audio_mime(provider: str) -> str:
    return "audio/mpeg" if provider.startswith("edge-") else "audio/wav"


def valid_audio(blob: bytes, provider: str, limit=16 * 1024 * 1024) -> bool:
    if len(blob) > limit or len(blob) < 4:
        return False
    return (blob.startswith((b"ID3", b"\xff\xfb", b"\xff\xf3", b"\xff\xf2"))
            if provider.startswith("edge-") else blob.startswith(b"RIFF"))


def _load_parler():
    global _PARLER
    if not available()["parler"]:
        raise VoiceUnavailable(
            "Indic Parler-TTS is not enabled. See docs/OFFLINE_VOICES.md; "
            "install optional model dependencies and set TBA_ENABLE_PARLER=1."
        )
    with _PARLER_LOCK:
        if _PARLER is None:
            import importlib
            torch = importlib.import_module("torch")
            transformers = importlib.import_module("transformers")
            parler_tts = importlib.import_module("parler_tts")
            AutoTokenizer = transformers.AutoTokenizer
            ParlerTTSForConditionalGeneration = parler_tts.ParlerTTSForConditionalGeneration
            device = "cuda:0" if torch.cuda.is_available() else ("mps" if getattr(torch.backends, "mps", None) and torch.backends.mps.is_available() else "cpu")
            model_id = "ai4bharat/indic-parler-tts"
            model = ParlerTTSForConditionalGeneration.from_pretrained(model_id).to(device)
            model.eval()
            _PARLER = (model, AutoTokenizer.from_pretrained(model_id),
                       AutoTokenizer.from_pretrained(model.config.text_encoder._name_or_path),
                       torch, device)
    return _PARLER


def _parler_wav(text):
    # Neural generation is computationally heavy, especially on CPU. Model
    # downloads can be multiple gigabytes, and are never triggered by Piper.
    import importlib
    sf = importlib.import_module("soundfile")
    model, tokenizer, description_tokenizer, torch, device = _load_parler()
    description = (
        "Divya speaks Hindi like a professional female radio news presenter, "
        "with a clear, warm and engaging voice, measured pace, moderately "
        "expressive intonation and excellent studio recording quality "
        "without background noise."
    )
    with _PARLER_LOCK, torch.inference_mode():
        desc = description_tokenizer(description, return_tensors="pt").to(device)
        prompt = tokenizer(text, return_tensors="pt").to(device)
        audio = model.generate(input_ids=desc.input_ids,
                               attention_mask=desc.attention_mask,
                               prompt_input_ids=prompt.input_ids,
                               prompt_attention_mask=prompt.attention_mask)
    out = BytesIO()
    sf.write(out, audio.cpu().numpy().squeeze(), model.config.sampling_rate, format="WAV")
    return out.getvalue()


def synthesize_hindi(text: str, provider: str = "piper") -> bytes:
    if not text or not text.strip():
        raise ValueError("Cannot synthesize empty Hindi text")
    if provider in ("piper", "piper-rohan"):
        return _piper_wav(text, provider)
    if provider in ("edge-swara", "edge-madhur"):
        return _edge_mp3(text, provider)
    if provider == "parler":
        return _parler_wav(text)
    raise ValueError("Unknown voice provider")


def synthesize_speech(text: str, provider: str, language: str = "hi") -> bytes:
    """Synthesize the requested *actual* language without misleading fallbacks.

    Edge selections have Hindi, Marathi, Malayalam and Indian-English male/female voices.
    Bhojpuri uses the Hindi voices as a clearly labelled pronunciation fallback.
    Local Piper/Parler installations support Hindi only.
    """
    if language == "hi":
        return synthesize_hindi(text, provider)
    if language in ("mr", "bho", "ml", "en"):
        if not text or not text.strip():
            raise ValueError("Cannot synthesize empty text")
        if provider in ("edge-swara", "edge-madhur"):
            return _edge_mp3(text, provider, language=language)
        lang_names = {
            "mr": "Marathi",
            "bho": "Bhojpuri",
            "ml": "Malayalam",
            "en": "English",
        }
        name = lang_names.get(language, language)
        raise VoiceUnavailable(f"This narrator supports Hindi only. Choose Swara or Madhur for {name} narration.")
    raise ValueError(f"Unsupported language: {language}")
