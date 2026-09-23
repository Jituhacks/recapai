"""
Unit and Integration Tests for Milestone 1: Audio Processing & Whisper Transcription
"""

import os
import io
import pytest
from app import app
from services.validation_service import (
    is_allowed_file,
    validate_uploaded_file,
    validate_transcript,
    ALLOWED_EXTENSIONS
)
from services.audio_service import (
    extract_audio_with_ffmpeg,
    format_seconds_to_timestamp,
    generate_srt_subtitles,
    cleanup_files
)
from services.whisper_service import (
    transcribe_audio_file,
    get_default_model_name
)

@pytest.fixture
def client():
    app.config["TESTING"] = True
    with app.test_client() as client:
        yield client

# --------------------------------------------------------------------------------------
# 1. FILE UPLOAD & FORMAT VALIDATION TESTS
# --------------------------------------------------------------------------------------
def test_allowed_file_extensions():
    """Verify all supported video and audio extensions pass validation."""
    valid_files = ["meeting.mp4", "audio.wav", "call.mp3", "recording.m4a", "video.webm", "clip.mkv", "talk.avi", "presentation.mov"]
    for f in valid_files:
        assert is_allowed_file(f) is True, f"Failed for valid file: {f}"

def test_unsupported_file_extensions():
    """Verify invalid or dangerous extensions are strictly rejected."""
    invalid_files = ["malware.exe", "notes.txt", "script.sh", "archive.zip", "document.pdf", "image.png", "no_ext"]
    for f in invalid_files:
        assert is_allowed_file(f) is False, f"Should reject: {f}"

def test_empty_file_validation():
    """Verify that a 0-byte empty file is rejected safely."""
    empty_stream = io.BytesIO(b"")
    empty_stream.filename = "empty.mp4"
    is_valid, msg = validate_uploaded_file(empty_stream)
    assert is_valid is False
    assert "empty" in msg.lower()

def test_oversized_file_validation():
    """Verify files exceeding 250MB limit are rejected."""
    stream = io.BytesIO(b"dummy")
    stream.filename = "large.mp4"
    # Test with custom low max_size
    is_valid, msg = validate_uploaded_file(stream, max_size_bytes=4)
    assert is_valid is False
    assert "exceeds maximum allowed size" in msg.lower()

def test_no_file_validation():
    """Verify None file is handled gracefully without crashing."""
    is_valid, msg = validate_uploaded_file(None)
    assert is_valid is False
    assert "no file provided" in msg.lower()

# --------------------------------------------------------------------------------------
# 2. TRANSCRIPT VALIDATION TESTS
# --------------------------------------------------------------------------------------
def test_transcript_validation_valid():
    """Verify valid transcript text passes validation."""
    transcript = "Welcome everyone to our weekly engineering sprint planning meeting."
    is_valid, msg = validate_transcript(transcript)
    assert is_valid is True
    assert msg is None

def test_transcript_validation_empty():
    """Verify empty or whitespace-only transcript is rejected."""
    for empty in [None, "", "   ", "\n\t"]:
        is_valid, msg = validate_transcript(empty)
        assert is_valid is False
        assert msg is not None

def test_transcript_validation_too_short():
    """Verify transcript below minimum characters threshold is rejected."""
    is_valid, msg = validate_transcript("Hi", min_characters=10)
    assert is_valid is False
    assert "below the minimum threshold" in msg.lower()

# --------------------------------------------------------------------------------------
# 3. AUDIO SERVICE & FFMPEG HELPERS
# --------------------------------------------------------------------------------------
def test_format_seconds_to_timestamp():
    """Verify seconds are correctly converted to formatted timestamps."""
    assert format_seconds_to_timestamp(0) == "00:00"
    assert format_seconds_to_timestamp(65) == "01:05"
    assert format_seconds_to_timestamp(3665) == "01:01:05"

def test_generate_srt_subtitles():
    """Verify SRT subtitle generation produces standard numbered blocks."""
    segments = [
        {"id": 1, "start": 0.0, "end": 2.5, "text": "Hello world"},
        {"id": 2, "start": 2.5, "end": 5.0, "text": "This is a test"}
    ]
    srt = generate_srt_subtitles(segments)
    assert "1\n00:00:00,000 --> 00:00:02,500\nHello world" in srt
    assert "2\n00:00:02,500 --> 00:00:05,000\nThis is a test" in srt

def test_cleanup_files_nonexistent():
    """Verify cleanup_files does not raise exceptions when files don't exist."""
    cleanup_files("non_existent_file_12345.wav", None)

# --------------------------------------------------------------------------------------
# 4. TRANSCRIPTION ENDPOINT & SAMPLE VIDEO
# --------------------------------------------------------------------------------------
def test_transcribe_with_sample_video(client):
    """Integration test: Transcribe the actual Media sample video through Flask."""
    res = client.post("/transcribe", data={"use_sample": "true"})
    assert res.status_code == 200
    data = res.get_json()
    assert data["success"] is True
    assert "transcript" in data
    assert len(data["transcript"]) > 20
    assert "segments" in data
    assert len(data["segments"]) > 0
    assert "metrics" in data
    assert data["metrics"]["word_count"] > 0
    assert "srt" in data