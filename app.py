"""
========================================================================================
Infosys Springboard AI-Powered Career Intelligence Platform
Milestones 1 & 2: Complete Audio Processing & Meeting Intelligence Pipeline
========================================================================================
Pipeline:
Meeting Recording -> Upload Validation -> Audio Processing (FFmpeg) ->
Whisper Transcription -> Transcript Validation -> LLM Intelligence ->
Schema Validation -> SQLite Relational Persistence -> API Response -> Web UI
"""

import os
import sys
import glob
import time
import uuid
import shutil
import logging
from typing import Optional
from werkzeug.utils import secure_filename
from dotenv import load_dotenv
from flask import Flask, render_template, request, jsonify, send_file, url_for

# Load environment variables from .env if present
load_dotenv()

# UTF-8 console output for Windows
if sys.platform.startswith("win"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger(__name__)

# Import services
from services.audio_service import (
    ensure_ffmpeg_in_path,
    extract_audio_with_ffmpeg,
    cleanup_files,
    format_seconds_to_timestamp
)
from services.validation_service import (
    ALLOWED_EXTENSIONS,
    MAX_UPLOAD_SIZE_BYTES,
    is_allowed_file,
    validate_uploaded_file,
    validate_transcript
)
from services.whisper_service import (
    get_default_model_name,
    transcribe_audio_file
)
from services.llm_service import (
    LLM_MODEL,
    MeetingIntelligence
)
from services.intelligence_service import (
    process_transcript_intelligence
)
from services.database_service import (
    init_db,
    persist_meeting,
    get_meeting,
    list_meetings,
    delete_meeting,
    get_db_path
)

# --------------------------------------------------------------------------------------
# 1. FLASK APPLICATION INITIALIZATION
# --------------------------------------------------------------------------------------
app = Flask(__name__)

BASE_DIR = os.path.abspath(os.path.dirname(__file__))
UPLOAD_FOLDER = os.path.join(BASE_DIR, "uploads")
AUDIO_FOLDER = os.path.join(BASE_DIR, "audio")
MEDIA_FOLDER = os.path.join(BASE_DIR, "Media")

for folder in (UPLOAD_FOLDER, AUDIO_FOLDER, MEDIA_FOLDER):
    os.makedirs(folder, exist_ok=True)

app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER
app.config["AUDIO_FOLDER"] = AUDIO_FOLDER
app.config["MEDIA_FOLDER"] = MEDIA_FOLDER
app.config["MAX_CONTENT_LENGTH"] = MAX_UPLOAD_SIZE_BYTES

# Auto-locate FFmpeg on startup
ensure_ffmpeg_in_path()

# Initialize SQLite database on startup
init_db()

# --------------------------------------------------------------------------------------
# 2. CORE HELPER FUNCTIONS
# --------------------------------------------------------------------------------------
def execute_transcription_flow(media_path: str) -> dict:
    """
    Executes FFmpeg audio extraction and Whisper speech-to-text on a local media file.
    Always cleans up intermediate audio files.
    """
    unique_id = uuid.uuid4().hex[:8]
    temp_audio_path = os.path.join(AUDIO_FOLDER, f"extracted_{unique_id}.wav")
    
    try:
        ffmpeg_time = extract_audio_with_ffmpeg(media_path, temp_audio_path)
        result = transcribe_audio_file(temp_audio_path)
        result["metrics"]["ffmpeg_extraction_sec"] = round(ffmpeg_time, 2)
        return result
    finally:
        cleanup_files(temp_audio_path)

# --------------------------------------------------------------------------------------
# 3. WEB UI & STATIC ROUTES
# --------------------------------------------------------------------------------------
@app.route("/")
def index():
    """Renders the main single-page interactive application."""
    return render_template("index.html")

@app.route("/health", methods=["GET"])
def health_check():
    """Health check and configuration diagnostic endpoint."""
    return jsonify({
        "status": "healthy",
        "ffmpeg_available": bool(shutil.which("ffmpeg")),
        "whisper_model": get_default_model_name(),
        "llm_model": os.getenv("LLM_MODEL", "gpt-4o-mini"),
        "llm_provider": os.getenv("LLM_PROVIDER", "openai"),
        "llm_configured": bool(os.getenv("OPENAI_API_KEY") or os.getenv("LLM_API_KEY")),
        "database": get_db_path(),
        "supported_formats": sorted(ALLOWED_EXTENSIONS),
        "max_upload_size_mb": app.config["MAX_CONTENT_LENGTH"] // (1024 * 1024)
    })

@app.route("/api/sample-video-info", methods=["GET"])
def sample_video_info():
    """Returns metadata for the default sample video."""
    sample_files = []
    for ext in ("mp4", "webm", "mkv", "avi", "mov", "wav", "mp3"):
        sample_files.extend(glob.glob(os.path.join(MEDIA_FOLDER, f"*.{ext}")))

    if not sample_files:
        return jsonify({"available": False, "message": "No sample media files found in Media directory."})

    path = sample_files[0]
    filename = os.path.basename(path)
    size_mb = round(os.path.getsize(path) / (1024 * 1024), 2)

    return jsonify({
        "available": True,
        "filename": filename,
        "size_mb": size_mb,
        "preview_url": url_for("get_sample_media", filename=filename)
    })

@app.route("/media/<path:filename>", methods=["GET"])
def get_sample_media(filename):
    """Serves media file from Media folder for browser preview."""
    path = os.path.join(MEDIA_FOLDER, secure_filename(filename))
    if not os.path.exists(path):
        return jsonify({"success": False, "error": "Media file not found."}), 404
    return send_file(path)

# --------------------------------------------------------------------------------------
# 4. MILESTONE 1: TRANSCRIPTION ENDPOINT
# --------------------------------------------------------------------------------------
@app.route("/transcribe", methods=["POST"])
def transcribe_endpoint():
    """
    Milestone 1 endpoint:
    Upload audio/video -> FFmpeg Audio extraction -> Whisper STT -> Return transcript.
    """
    temp_media_path = None
    started = time.time()

    try:
        is_sample = request.form.get("use_sample") == "true"
        
        if is_sample:
            sample_files = []
            for ext in ("mp4", "webm", "mkv", "avi", "mov", "wav", "mp3"):
                sample_files.extend(glob.glob(os.path.join(MEDIA_FOLDER, f"*.{ext}")))
            if not sample_files:
                return jsonify({"success": False, "error": "No sample media found in Media directory."}), 404

            source_path = sample_files[0]
            original_filename = os.path.basename(source_path)
            ext = original_filename.rsplit(".", 1)[-1]
            temp_media_path = os.path.join(UPLOAD_FOLDER, f"sample_{uuid.uuid4().hex[:8]}.{ext}")
            shutil.copyfile(source_path, temp_media_path)
            file_size_bytes = os.path.getsize(temp_media_path)
        else:
            file = request.files.get("video") or request.files.get("audio") or request.files.get("file")
            is_valid, error_msg = validate_uploaded_file(file, app.config["MAX_CONTENT_LENGTH"])
            if not is_valid:
                return jsonify({"success": False, "error": error_msg}), 400

            original_filename = secure_filename(file.filename) or "recording.mp4"
            ext = original_filename.rsplit(".", 1)[-1]
            temp_media_path = os.path.join(UPLOAD_FOLDER, f"{uuid.uuid4().hex[:8]}_{original_filename}")
            file.save(temp_media_path)
            file_size_bytes = os.path.getsize(temp_media_path)

        # Execute transcription pipeline
        output = execute_transcription_flow(temp_media_path)
        
        # Validate transcript output
        is_trans_valid, trans_err = validate_transcript(output.get("transcript"))
        if not is_trans_valid:
            return jsonify({"success": False, "error": f"Transcription produced invalid result: {trans_err}"}), 422

        total_elapsed = round(time.time() - started, 2)
        output["metrics"]["total_time_sec"] = total_elapsed

        return jsonify({
            "success": True,
            "filename": original_filename,
            "filesize_mb": round(file_size_bytes / (1024 * 1024), 2),
            "language": output["language"],
            "model_used": output["model_used"],
            "metrics": output["metrics"],
            "transcript": output["transcript"],
            "segments": output["segments"],
            "srt": output["srt"]
        })

    except Exception as exc:
        logger.exception("Error during /transcribe request:")
        return jsonify({"success": False, "error": str(exc)}), 500
    finally:
        cleanup_files(temp_media_path)

# --------------------------------------------------------------------------------------
# 5. MILESTONE 2: LLM PROCESSING ON RAW TRANSCRIPT
# --------------------------------------------------------------------------------------
@app.route("/api/process-transcript", methods=["POST"])
def process_transcript_api():
    """
    Milestone 2 Task 1-5 endpoint:
    Accepts raw transcript text -> Validates -> Runs LLM Intelligence -> Persists -> Returns.
    """
    try:
        payload = request.get_json(silent=True) or {}
        transcript = str(payload.get("transcript", "")).strip()

        is_valid, err = validate_transcript(transcript, min_characters=10)
        if not is_valid:
            return jsonify({"success": False, "error": f"Invalid transcript: {err}"}), 400

        filename = payload.get("filename", "transcript.txt")
        language = payload.get("language", "EN")
        model_used = f"{os.getenv('LLM_MODEL', 'gpt-4o-mini')}"

        intelligence = process_transcript_intelligence(transcript)
        meeting_id = persist_meeting(
            filename=filename,
            transcript=transcript,
            language=language,
            model_used=model_used,
            intelligence=intelligence
        )

        return jsonify({
            "success": True,
            "meeting_id": meeting_id,
            "filename": filename,
            "model_used": model_used,
            "meeting_intelligence": intelligence.model_dump()
        })

    except Exception as exc:
        logger.exception("Error during /api/process-transcript:")
        return jsonify({"success": False, "error": str(exc)}), 500

# --------------------------------------------------------------------------------------
# 6. COMPLETE END-TO-END PIPELINE: AUDIO/VIDEO -> WHISPER -> LLM -> DATABASE
# --------------------------------------------------------------------------------------
@app.route("/api/process-meeting", methods=["POST"])
def process_meeting_api():
    """
    Milestone 1 & Milestone 2 Unified Pipeline:
    Upload Media -> Validate -> Audio Processing -> Whisper STT -> Validate Transcript ->
    LLM Meeting Intelligence -> Schema Validation -> SQLite Persistence -> Structured Response.
    """
    temp_media_path = None
    started = time.time()

    try:
        is_sample = request.form.get("use_sample") == "true"

        if is_sample:
            sample_files = []
            for ext in ("mp4", "webm", "mkv", "avi", "mov", "wav", "mp3"):
                sample_files.extend(glob.glob(os.path.join(MEDIA_FOLDER, f"*.{ext}")))
            if not sample_files:
                return jsonify({"success": False, "error": "No sample media found in Media directory."}), 404

            source_path = sample_files[0]
            original_filename = os.path.basename(source_path)
            ext = original_filename.rsplit(".", 1)[-1]
            temp_media_path = os.path.join(UPLOAD_FOLDER, f"sample_{uuid.uuid4().hex[:8]}.{ext}")
            shutil.copyfile(source_path, temp_media_path)
            file_size_bytes = os.path.getsize(temp_media_path)
        else:
            file = request.files.get("video") or request.files.get("audio") or request.files.get("file")
            is_valid, error_msg = validate_uploaded_file(file, app.config["MAX_CONTENT_LENGTH"])
            if not is_valid:
                return jsonify({"success": False, "error": error_msg}), 400

            original_filename = secure_filename(file.filename) or "meeting.mp4"
            ext = original_filename.rsplit(".", 1)[-1]
            temp_media_path = os.path.join(UPLOAD_FOLDER, f"{uuid.uuid4().hex[:8]}_{original_filename}")
            file.save(temp_media_path)
            file_size_bytes = os.path.getsize(temp_media_path)

        # Step 1-3: FFmpeg Audio Extraction & Whisper Transcription
        transcription_result = execute_transcription_flow(temp_media_path)
        transcript_text = transcription_result.get("transcript", "").strip()

        # Step 4: Transcript Validation
        is_trans_valid, trans_err = validate_transcript(transcript_text, min_characters=10)
        if not is_trans_valid:
            return jsonify({"success": False, "error": f"Transcription validation failed: {trans_err}"}), 422

        # Step 5: LLM Processing & Meeting Intelligence Extraction
        llm_model_name = os.getenv("LLM_MODEL", "gpt-4o-mini")
        intelligence = process_transcript_intelligence(transcript_text)

        # Step 6: Database Persistence
        meeting_id = persist_meeting(
            filename=original_filename,
            transcript=transcript_text,
            language=transcription_result.get("language", "EN"),
            model_used=f"Whisper ({transcription_result.get('model_used')}) + LLM ({llm_model_name})",
            intelligence=intelligence
        )

        total_elapsed = round(time.time() - started, 2)
        transcription_result["metrics"]["total_time_sec"] = total_elapsed

        return jsonify({
            "success": True,
            "meeting_id": meeting_id,
            "filename": original_filename,
            "filesize_mb": round(file_size_bytes / (1024 * 1024), 2),
            "transcription": transcription_result,
            "transcript": transcript_text,
            "meeting_intelligence": intelligence.model_dump(),
            "models": {
                "whisper": transcription_result.get("model_used"),
                "llm": llm_model_name
            },
            "metrics": transcription_result["metrics"]
        })

    except Exception as exc:
        logger.exception("Error during /api/process-meeting end-to-end pipeline:")
        return jsonify({"success": False, "error": str(exc)}), 500
    finally:
        cleanup_files(temp_media_path)

# --------------------------------------------------------------------------------------
# 7. HISTORICAL MEETINGS DATABASE API
# --------------------------------------------------------------------------------------
@app.route("/api/meetings", methods=["GET"])
def list_meetings_api():
    """Returns list of recent meetings."""
    limit = min(int(request.args.get("limit", 50)), 100)
    meetings = list_meetings(limit=limit)
    return jsonify({"success": True, "count": len(meetings), "meetings": meetings})

@app.route("/api/meetings/<meeting_id>", methods=["GET"])
def get_meeting_api(meeting_id):
    """Retrieves full details and intelligence for a given meeting ID."""
    meeting_data = get_meeting(meeting_id)
    if not meeting_data:
        return jsonify({"success": False, "error": f"Meeting with ID '{meeting_id}' not found."}), 404
    return jsonify({"success": True, "meeting": meeting_data})

@app.route("/api/meetings/<meeting_id>", methods=["DELETE"])
def delete_meeting_api(meeting_id):
    """Deletes meeting record and cascades to child intelligence records."""
    deleted = delete_meeting(meeting_id)
    if not deleted:
        return jsonify({"success": False, "error": "Meeting not found or already deleted."}), 404
    return jsonify({"success": True, "message": f"Meeting '{meeting_id}' deleted successfully."})

# --------------------------------------------------------------------------------------
# 8. ERROR HANDLERS
# --------------------------------------------------------------------------------------
@app.errorhandler(413)
def request_entity_too_large(error):
    max_mb = app.config["MAX_CONTENT_LENGTH"] // (1024 * 1024)
    return jsonify({
        "success": False,
        "error": f"File exceeds maximum allowed size limit ({max_mb} MB). Please choose a smaller file."
    }), 413

@app.errorhandler(400)
def bad_request(error):
    return jsonify({"success": False, "error": "Bad request format or missing parameters."}), 400

@app.errorhandler(404)
def not_found(error):
    return jsonify({"success": False, "error": "Requested API endpoint not found."}), 404

@app.errorhandler(500)
def internal_error(error):
    return jsonify({"success": False, "error": "An internal server processing error occurred."}), 500

# --------------------------------------------------------------------------------------
# 9. SERVER ENTRYPOINT
# --------------------------------------------------------------------------------------
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    logger.info("============================================================")
    logger.info("Starting Infosys Career Intelligence Platform (Milestones 1 & 2)")
    logger.info("Web Dashboard: http://127.0.0.1:%s", port)
    logger.info("============================================================")
    app.run(host="0.0.0.0", port=port, debug=False)