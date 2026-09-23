import os
import logging
from typing import Tuple, Optional, Set

logger = logging.getLogger(__name__)

# Supported audio and video extensions
ALLOWED_EXTENSIONS: Set[str] = {
    # Video formats
    "mp4", "mov", "avi", "mkv", "webm",
    # Audio formats
    "mp3", "wav", "m4a", "ogg", "flac", "aac"
}

# Maximum file size: 250 MB
MAX_UPLOAD_SIZE_BYTES: int = 250 * 1024 * 1024

def is_allowed_file(filename: Optional[str]) -> bool:
    """Checks if filename has an allowed extension."""
    if not filename or "." not in filename:
        return False
    ext = filename.rsplit(".", 1)[1].lower()
    return ext in ALLOWED_EXTENSIONS

def validate_uploaded_file(file, max_size_bytes: int = MAX_UPLOAD_SIZE_BYTES) -> Tuple[bool, Optional[str]]:
    """
    Validates uploaded FileStorage object or filepath.
    
    Returns:
        (is_valid, error_message)
    """
    if file is None:
        return False, "No file provided in request."

    filename = getattr(file, "filename", None) or str(file)
    if not filename or filename.strip() == "":
        return False, "No file selected for upload."

    if not is_allowed_file(filename):
        allowed_list = ", ".join(sorted(ALLOWED_EXTENSIONS)).upper()
        return False, f"Unsupported file format '{filename.rsplit('.', 1)[-1] if '.' in filename else ''}'. Allowed formats: {allowed_list}"

    # Check file stream/size if it's a werkzeug FileStorage or path
    try:
        if hasattr(file, "seek") and hasattr(file, "tell"):
            file.seek(0, os.SEEK_END)
            size = file.tell()
            file.seek(0)  # Reset pointer to beginning

            if size == 0:
                return False, "Uploaded file is empty (0 bytes)."
            if size > max_size_bytes:
                max_mb = max_size_bytes // (1024 * 1024)
                return False, f"Uploaded file ({size / (1024 * 1024):.1f} MB) exceeds maximum allowed size ({max_mb} MB)."
        elif isinstance(file, str) and os.path.exists(file):
            size = os.path.getsize(file)
            if size == 0:
                return False, "File is empty (0 bytes)."
            if size > max_size_bytes:
                max_mb = max_size_bytes // (1024 * 1024)
                return False, f"File exceeds maximum allowed size ({max_mb} MB)."
    except Exception as ex:
        logger.warning("Error reading file stream during validation: %s", ex)
        return False, f"Could not validate file stream: {str(ex)}"

    return True, None

def validate_transcript(transcript: Optional[str], min_characters: int = 5) -> Tuple[bool, Optional[str]]:
    """
    Validates that a transcript is valid non-empty text suitable for downstream processing.
    
    Returns:
        (is_valid, error_message)
    """
    if transcript is None:
        return False, "Transcript is missing (None)."

    cleaned = " ".join(str(transcript).split()).strip()
    if not cleaned:
        return False, "Transcript is empty or contains only whitespace."

    if len(cleaned) < min_characters:
        return False, f"Transcript contains only {len(cleaned)} characters, which is below the minimum threshold ({min_characters})."

    # Check if transcript is not just non-alphanumeric noise
    alnum_count = sum(1 for c in cleaned if c.isalnum())
    if alnum_count < 2:
        return False, "Transcript does not contain meaningful speech or text."

    return True, None