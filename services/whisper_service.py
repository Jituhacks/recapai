import os
import time
import logging
from typing import Optional, Dict, Any, List

from services.audio_service import format_seconds_to_timestamp, generate_srt_subtitles

logger = logging.getLogger(__name__)

# Global cache for the loaded Whisper model instance
_whisper_model_instance = None
_loaded_model_name: Optional[str] = None

def get_default_model_name() -> str:
    """Returns the configured Whisper model name from environment or default."""
    return os.getenv("WHISPER_MODEL", "tiny").strip().lower()

def get_whisper_model(model_name: Optional[str] = None):
    """
    Lazy loads and caches OpenAI Whisper model into memory.
    """
    global _whisper_model_instance, _loaded_model_name
    target_name = (model_name or get_default_model_name()).strip().lower()

    if _whisper_model_instance is None or _loaded_model_name != target_name:
        import whisper
        logger.info("Loading OpenAI Whisper model: '%s'...", target_name)
        t0 = time.time()
        _whisper_model_instance = whisper.load_model(target_name)
        _loaded_model_name = target_name
        logger.info("Whisper model '%s' loaded in %.2fs.", target_name, time.time() - t0)

    return _whisper_model_instance

def transcribe_audio_file(
    audio_wav_path: str,
    model_name: Optional[str] = None,
    language: Optional[str] = None,
    fp16: bool = False
) -> Dict[str, Any]:
    """
    Transcribes a normalized WAV audio file using the OpenAI Whisper model.
    
    Returns:
        Dict containing:
        - transcript: str
        - language: str
        - segments: List[Dict]
        - srt: str
        - metrics: Dict
    """
    if not os.path.exists(audio_wav_path):
        raise FileNotFoundError(f"Audio file not found: {audio_wav_path}")

    model = get_whisper_model(model_name)
    actual_model_name = _loaded_model_name or "tiny"

    logger.info("Starting Whisper STT on %s (fp16=%s)...", audio_wav_path, fp16)
    start_time = time.time()

    transcribe_options: Dict[str, Any] = {
        "fp16": fp16,
        "verbose": False
    }
    if language:
        transcribe_options["language"] = language

    result = model.transcribe(audio_wav_path, **transcribe_options)
    whisper_time = time.time() - start_time

    full_text = str(result.get("text", "")).strip()
    detected_language = str(result.get("language", "en")).lower()
    raw_segments = result.get("segments", [])

    formatted_segments: List[Dict[str, Any]] = []
    total_audio_duration = 0.0

    for seg in raw_segments:
        s_start = float(seg.get("start", 0.0))
        s_end = float(seg.get("end", 0.0))
        s_text = str(seg.get("text", "")).strip()

        if s_end > total_audio_duration:
            total_audio_duration = s_end

        formatted_segments.append({
            "id": seg.get("id", len(formatted_segments) + 1),
            "start": round(s_start, 2),
            "end": round(s_end, 2),
            "start_formatted": format_seconds_to_timestamp(s_start),
            "end_formatted": format_seconds_to_timestamp(s_end),
            "text": s_text
        })

    srt_subtitles = generate_srt_subtitles(formatted_segments)
    word_count = len(full_text.split()) if full_text else 0

    logger.info(
        "Whisper STT finished in %.2fs: %d words, %d segments, %.1fs audio duration.",
        whisper_time, word_count, len(formatted_segments), total_audio_duration
    )

    return {
        "transcript": full_text,
        "language": detected_language.upper(),
        "model_used": actual_model_name,
        "segments": formatted_segments,
        "srt": srt_subtitles,
        "metrics": {
            "whisper_transcription_sec": round(whisper_time, 2),
            "audio_duration_sec": round(total_audio_duration, 2),
            "audio_duration_formatted": format_seconds_to_timestamp(total_audio_duration),
            "word_count": word_count,
            "segment_count": len(formatted_segments)
        }
    }