import os
import sys
import glob
import time
import shutil
import logging
import subprocess
from datetime import timedelta

logger = logging.getLogger(__name__)

def ensure_ffmpeg_in_path() -> bool:
    """
    Checks if ffmpeg and ffprobe are accessible on PATH.
    If not, automatically searches common Windows paths (such as WinGet packages,
    Program Files, etc.) and prepends the directory to os.environ['PATH'].
    """
    if shutil.which("ffmpeg") and shutil.which("ffprobe"):
        return True

    search_patterns = [
        os.path.expandvars(r"%LOCALAPPDATA%\Microsoft\WinGet\Packages\Gyan.FFmpeg*\*\bin"),
        os.path.expandvars(r"%LOCALAPPDATA%\Microsoft\WinGet\Packages\*\ffmpeg*\bin"),
        r"C:\ffmpeg\bin",
        r"C:\Program Files\ffmpeg\bin",
        r"C:\Program Files (x86)\ffmpeg\bin",
        os.path.expandvars(r"%USERPROFILE%\AppData\Local\Microsoft\WinGet\Packages\Gyan.FFmpeg*\*\bin")
    ]

    for pattern in search_patterns:
        for match in glob.glob(pattern):
            ffmpeg_exe = os.path.join(match, "ffmpeg.exe")
            if os.path.exists(ffmpeg_exe):
                os.environ["PATH"] = match + os.pathsep + os.environ.get("PATH", "")
                logger.info("Auto-discovered FFmpeg and added to PATH: %s", match)
                return True

    logger.warning("FFmpeg not found in standard system locations.")
    return False

# Run search on import
ensure_ffmpeg_in_path()

def format_seconds_to_timestamp(seconds: float) -> str:
    """Formats float seconds into HH:MM:SS or MM:SS string."""
    td = timedelta(seconds=max(0.0, seconds))
    total_seconds = int(td.total_seconds())
    hours = total_seconds // 3600
    minutes = (total_seconds % 3600) // 60
    secs = total_seconds % 60
    return f"{hours:02d}:{minutes:02d}:{secs:02d}" if hours else f"{minutes:02d}:{secs:02d}"

def format_srt_timestamp(seconds: float) -> str:
    """Formats float seconds into SRT timestamp format: HH:MM:SS,mmm."""
    seconds = max(0.0, seconds)
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    millis = int(round((seconds - int(seconds)) * 1000))
    if millis >= 1000:
        millis = 999
    return f"{hours:02d}:{minutes:02d}:{secs:02d},{millis:03d}"

def generate_srt_subtitles(segments: list) -> str:
    """Builds standard SubRip (.srt) formatted text from timestamped segment list."""
    lines = []
    for i, seg in enumerate(segments, start=1):
        s_start = float(seg.get("start", 0.0))
        s_end = float(seg.get("end", 0.0))
        text = str(seg.get("text", "")).strip()
        lines.append(
            f"{i}\n{format_srt_timestamp(s_start)} --> {format_srt_timestamp(s_end)}\n{text}\n"
        )
    return "\n".join(lines)

def extract_audio_with_ffmpeg(input_media_path: str, output_audio_path: str) -> float:
    """
    Extracts or converts audio from any supported media format (video or audio)
    into a normalized 16kHz mono 16-bit PCM WAV file optimized for Whisper.
    
    Returns:
        float: Duration in seconds taken for the FFmpeg conversion.
    Raises:
        FileNotFoundError: If input media path does not exist.
        RuntimeError: If FFmpeg fails or output file is empty.
    """
    if not os.path.exists(input_media_path):
        raise FileNotFoundError(f"Input media file does not exist: {input_media_path}")

    ensure_ffmpeg_in_path()

    output_dir = os.path.dirname(output_audio_path)
    if output_dir:
        os.makedirs(output_dir, exist_ok=True)

    # Convert to 16kHz, mono, PCM 16-bit WAV
    cmd = [
        "ffmpeg",
        "-i", input_media_path,
        "-vn",                   # Disable video stream
        "-acodec", "pcm_s16le",  # 16-bit PCM
        "-ar", "16000",          # 16kHz sampling rate
        "-ac", "1",              # 1 channel (mono)
        "-y",                    # Overwrite output
        output_audio_path
    ]

    logger.info("Executing FFmpeg command: %s", " ".join(cmd))
    start_time = time.time()
    
    result = subprocess.run(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        check=False
    )
    
    elapsed_time = time.time() - start_time

    if result.returncode != 0:
        error_msg = result.stderr[-500:] if result.stderr else "Unknown FFmpeg error"
        logger.error("FFmpeg extraction failed (code %d): %s", result.returncode, error_msg)
        raise RuntimeError(f"FFmpeg audio processing failed: {error_msg}")

    if not os.path.exists(output_audio_path) or os.path.getsize(output_audio_path) == 0:
        raise RuntimeError("FFmpeg completed but extracted audio file is missing or empty (0 bytes).")

    logger.info("FFmpeg extraction finished in %.2fs -> %s", elapsed_time, output_audio_path)
    return elapsed_time

def cleanup_files(*file_paths: str) -> None:
    """Safely deletes temporary files with error suppression."""
    for path in file_paths:
        if path and os.path.exists(path):
            try:
                os.remove(path)
                logger.info("Successfully cleaned up temporary file: %s", path)
            except Exception as ex:
                logger.warning("Could not clean up temporary file '%s': %s", path, ex)