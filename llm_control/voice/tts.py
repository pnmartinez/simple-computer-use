"""Text-to-speech utilities for the voice control server."""

import io
import os
import tempfile
from typing import Optional, Tuple

SUPPORTED_FORMATS = {
    "mp3": "audio/mpeg",
    "wav": "audio/wav",
}


def _select_pyttsx3_voice(engine, voice_hint: str) -> None:
    if not voice_hint:
        return
    voices = engine.getProperty("voices") or []
    voice_hint_lower = voice_hint.lower()
    for voice in voices:
        if voice_hint_lower in (voice.id or "").lower() or voice_hint_lower in (voice.name or "").lower():
            engine.setProperty("voice", voice.id)
            return
    engine.setProperty("voice", voice_hint)


def synthesize_speech(
    text: str,
    voice: Optional[str] = None,
    audio_format: str = "wav",
    provider: Optional[str] = None,
) -> Tuple[bytes, str]:
    """Synthesize speech for the given text.

    Args:
        text: The input text to synthesize.
        voice: Optional voice/language hint.
        audio_format: Output audio format (mp3 or wav).
        provider: Optional TTS provider override.

    Returns:
        Tuple of (audio_bytes, mime_type).
    """
    if not text:
        raise ValueError("Text is required for synthesis")

    resolved_format = audio_format.lower()
    if resolved_format not in SUPPORTED_FORMATS:
        raise ValueError("Unsupported audio format. Use 'mp3' or 'wav'.")

    resolved_provider = (provider or os.environ.get("TTS_PROVIDER", "pyttsx3")).lower()

    if resolved_provider == "pyttsx3":
        if resolved_format != "wav":
            raise ValueError("pyttsx3 only supports WAV output. Set format to 'wav'.")
        try:
            import pyttsx3
        except ImportError as exc:
            raise RuntimeError("pyttsx3 is not installed. Install it to use the local TTS provider.") from exc

        engine = pyttsx3.init()
        _select_pyttsx3_voice(engine, voice or "")
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as temp_file:
            temp_path = temp_file.name
        engine.save_to_file(text, temp_path)
        engine.runAndWait()
        with open(temp_path, "rb") as audio_file:
            audio_bytes = audio_file.read()
        os.remove(temp_path)
        return audio_bytes, SUPPORTED_FORMATS[resolved_format]

    if resolved_provider == "gtts":
        if resolved_format != "mp3":
            raise ValueError("gTTS only supports MP3 output. Set format to 'mp3'.")
        try:
            from gtts import gTTS
        except ImportError as exc:
            raise RuntimeError("gTTS is not installed. Install it to use the Google TTS provider.") from exc
        language = voice or os.environ.get("TTS_LANGUAGE", "es")
        tts = gTTS(text=text, lang=language)
        buffer = io.BytesIO()
        tts.write_to_fp(buffer)
        return buffer.getvalue(), SUPPORTED_FORMATS[resolved_format]

    raise ValueError(f"Unsupported TTS provider: {resolved_provider}")
