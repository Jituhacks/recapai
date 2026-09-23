"""
Infosys Springboard AI-Powered Career Intelligence Platform
Production meeting intelligence pipeline:
Upload -> FFmpeg -> Whisper -> Transcript -> LLM -> Validation -> SQLite
"""

import os
import sys
import glob
import time
import uuid
import shutil
import logging
import sqlite3
import subprocess
from datetime import datetime, timedelta, timezone
from typing import List, Literal, Optional

from flask import Flask, render_template, request, jsonify, send_file, url_for
from werkzeug.utils import secure_filename
from pydantic import BaseModel, Field, ValidationError, field_validator

# --------------------------------------------------------------------------------------
# 1. SETUP LOGGING & CONFIGURATION
# --------------------------------------------------------------------------------------
if sys.platform.startswith("win"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger(__name__)

app = Flask(__name__)
BASE_DIR = os.path.abspath(os.path.dirname(__file__))
UPLOAD_FOLDER = os.path.join(BASE_DIR, "uploads")
AUDIO_FOLDER = os.path.join(BASE_DIR, "audio")
MEDIA_FOLDER = os.path.join(BASE_DIR, "Media")
DB_PATH = os.path.join(BASE_DIR, "meeting_intelligence.db")

for folder in (UPLOAD_FOLDER, AUDIO_FOLDER, MEDIA_FOLDER):
    os.makedirs(folder, exist_ok=True)

app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER
app.config["AUDIO_FOLDER"] = AUDIO_FOLDER
app.config["MAX_CONTENT_LENGTH"] = 250 * 1024 * 1024

ALLOWED_EXTENSIONS = {"mp4", "mov", "avi", "mkv", "webm"}
WHISPER_MODEL_NAME = os.getenv("WHISPER_MODEL", "tiny")
LLM_MODEL = os.getenv("LLM_MODEL", "gpt-4o-mini")
LLM_MAX_RETRIES = int(os.getenv("LLM_MAX_RETRIES", "3"))
LLM_CHUNK_CHARS = int(os.getenv("LLM_CHUNK_CHARS", "12000"))
LLM_CHUNK_OVERLAP = int(os.getenv("LLM_CHUNK_OVERLAP", "500"))

whisper_model = None

# --------------------------------------------------------------------------------------
# 2. STRUCTURED OUTPUT SCHEMA
# --------------------------------------------------------------------------------------
Priority = Literal["low", "medium", "high", "critical", "unknown"]
Status = Literal["not_started", "in_progress", "blocked", "completed", "unknown"]


class Participant(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    responsibilities: List[str] = Field(default_factory=list)

    @field_validator("name")
    @classmethod
    def normalize_name(cls, value: str) -> str:
        value = " ".join(value.split()).strip()
        return value if value else "Unknown"


class ActionItem(BaseModel):
    task: str = Field(min_length=1, max_length=500)
    assigned_to: str = Field(default="Unknown", max_length=120)
    deadline: Optional[str] = Field(default=None, max_length=120)
    priority: Priority = "unknown"
    status: Status = "not_started"


class MeetingIntelligence(BaseModel):
    summary: str = Field(min_length=1)
    key_points: List[str] = Field(default_factory=list)
    decisions: List[str] = Field(default_factory=list)
    action_items: List[ActionItem] = Field(default_factory=list)
    participants: List[Participant] = Field(default_factory=list)
    deadlines: List[str] = Field(default_factory=list)
    priorities: List[str] = Field(default_factory=list)


# --------------------------------------------------------------------------------------
# 3. PROMPT TEMPLATES
# --------------------------------------------------------------------------------------
SYSTEM_PROMPT = """You are a production meeting-intelligence extraction service.
Use only facts present in the transcript. Never invent names, deadlines, decisions, or tasks.
If an assignee is unclear, use \"Unknown\". If a deadline is not stated, use null.
Normalize repeated participant names consistently and avoid duplicate participant records.
Return concise, factual meeting intelligence matching the provided schema exactly."""

CHUNK_PROMPT = """Analyze this transcript section. Extract only information explicitly supported
by this section. Preserve names as spoken, infer no missing deadline, and keep action items atomic.
Transcript section:\n{transcript}"""

MERGE_PROMPT = """Merge the structured analyses below into one final meeting record.
Deduplicate participants, key points, decisions, deadlines, priorities, and action items.
When duplicate action items differ, keep the most specific supported version.
Do not add facts that are absent from the analyses.
Analyses:\n{analyses}"""

# --------------------------------------------------------------------------------------
# 4. DATABASE
# --------------------------------------------------------------------------------------
def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db():
    with get_db() as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS meetings (
                id TEXT PRIMARY KEY,
                filename TEXT,
                transcript TEXT NOT NULL,
                summary TEXT NOT NULL,
                language TEXT,
                model_used TEXT,
                created_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS key_points (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                meeting_id TEXT NOT NULL,
                point TEXT NOT NULL,
                FOREIGN KEY(meeting_id) REFERENCES meetings(id) ON DELETE CASCADE
            );
            CREATE TABLE IF NOT EXISTS decisions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                meeting_id TEXT NOT NULL,
                decision TEXT NOT NULL,
                FOREIGN KEY(meeting_id) REFERENCES meetings(id) ON DELETE CASCADE
            );
            CREATE TABLE IF NOT EXISTS participants (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                meeting_id TEXT NOT NULL,
                name TEXT NOT NULL,
                responsibilities TEXT NOT NULL DEFAULT '[]',
                UNIQUE(meeting_id, name),
                FOREIGN KEY(meeting_id) REFERENCES meetings(id) ON DELETE CASCADE
            );
            CREATE TABLE IF NOT EXISTS action_items (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                meeting_id TEXT NOT NULL,
                task TEXT NOT NULL,
                assigned_to TEXT NOT NULL,
                deadline TEXT,
                priority TEXT NOT NULL,
                status TEXT NOT NULL,
                FOREIGN KEY(meeting_id) REFERENCES meetings(id) ON DELETE CASCADE
            );
            CREATE TABLE IF NOT EXISTS deadlines (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                meeting_id TEXT NOT NULL,
                deadline TEXT NOT NULL,
                FOREIGN KEY(meeting_id) REFERENCES meetings(id) ON DELETE CASCADE
            );
            """
        )


def persist_meeting(filename: str, transcript: str, language: str, intelligence: MeetingIntelligence) -> str:
    meeting_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc).isoformat()
    data = intelligence.model_dump()

    with get_db() as conn:
        conn.execute(
            "INSERT INTO meetings(id, filename, transcript, summary, language, model_used, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (meeting_id, filename, transcript, intelligence.summary, language, LLM_MODEL, now),
        )
        conn.executemany(
            "INSERT INTO key_points(meeting_id, point) VALUES (?, ?)",
            [(meeting_id, p) for p in data["key_points"]],
        )
        conn.executemany(
            "INSERT INTO decisions(meeting_id, decision) VALUES (?, ?)",
            [(meeting_id, d) for d in data["decisions"]],
        )
        for p in data["participants"]:
            conn.execute(
                "INSERT OR IGNORE INTO participants(meeting_id, name, responsibilities) VALUES (?, ?, ?)",
                (meeting_id, p["name"], __import__("json").dumps(p["responsibilities"])),
            )
        for item in data["action_items"]:
            conn.execute(
                """INSERT INTO action_items(meeting_id, task, assigned_to, deadline, priority, status)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (meeting_id, item["task"], item["assigned_to"], item["deadline"], item["priority"], item["status"]),
            )
        conn.executemany(
            "INSERT INTO deadlines(meeting_id, deadline) VALUES (?, ?)",
            [(meeting_id, d) for d in data["deadlines"]],
        )
    return meeting_id

# Initialize persistence for both `python app.py` and WSGI/Flask imports.
init_db()

# --------------------------------------------------------------------------------------
# 5. FFMPEG + WHISPER
# --------------------------------------------------------------------------------------
def ensure_ffmpeg_in_path():
    if shutil.which("ffmpeg") and shutil.which("ffprobe"):
        return True
    search_patterns = [
        os.path.expandvars(r"%LOCALAPPDATA%\Microsoft\WinGet\Packages\Gyan.FFmpeg*\*\bin"),
        os.path.expandvars(r"%LOCALAPPDATA%\Microsoft\WinGet\Packages\*\ffmpeg*\bin"),
        r"C:\ffmpeg\bin",
        r"C:\Program Files\ffmpeg\bin",
        r"C:\Program Files (x86)\ffmpeg\bin",
    ]
    for pattern in search_patterns:
        for match in glob.glob(pattern):
            if os.path.exists(os.path.join(match, "ffmpeg.exe")):
                os.environ["PATH"] = match + os.pathsep + os.environ.get("PATH", "")
                return True
    logger.warning("FFmpeg not found. Install FFmpeg and add it to PATH.")
    return False


def get_whisper_model():
    global whisper_model
    if whisper_model is None:
        import whisper
        logger.info("Loading Whisper model: %s", WHISPER_MODEL_NAME)
        whisper_model = whisper.load_model(WHISPER_MODEL_NAME)
    return whisper_model


def is_allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


def format_seconds_to_timestamp(seconds: float) -> str:
    td = timedelta(seconds=seconds)
    total_seconds = int(td.total_seconds())
    hours = total_seconds // 3600
    minutes = (total_seconds % 3600) // 60
    secs = total_seconds % 60
    return f"{hours:02d}:{minutes:02d}:{secs:02d}" if hours else f"{minutes:02d}:{secs:02d}"


def format_srt_timestamp(seconds: float) -> str:
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    millis = int((seconds - int(seconds)) * 1000)
    return f"{hours:02d}:{minutes:02d}:{secs:02d},{millis:03d}"


def generate_srt_subtitles(segments: list) -> str:
    lines = []
    for i, seg in enumerate(segments, start=1):
        lines.append(
            f"{i}\n{format_srt_timestamp(seg.get('start', 0.0))} --> {format_srt_timestamp(seg.get('end', 0.0))}\n{seg.get('text', '').strip()}\n"
        )
    return "\n".join(lines)


def extract_audio_with_ffmpeg(video_path: str, output_audio_path: str):
    ensure_ffmpeg_in_path()
    cmd = ["ffmpeg", "-i", video_path, "-vn", "-acodec", "pcm_s16le", "-ar", "16000", "-ac", "1", "-y", output_audio_path]
    start = time.time()
    result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=False)
    if result.returncode != 0:
        raise RuntimeError(f"FFmpeg failed: {result.stderr[-500:]}")
    if not os.path.exists(output_audio_path) or os.path.getsize(output_audio_path) == 0:
        raise RuntimeError("FFmpeg output audio is empty or missing.")
    return time.time() - start

# --------------------------------------------------------------------------------------
# 6. LLM PROCESSING SERVICE
# --------------------------------------------------------------------------------------
def get_openai_client():
    if not os.getenv("OPENAI_API_KEY"):
        raise RuntimeError("OPENAI_API_KEY is not configured. Set it before using meeting intelligence.")
    from openai import OpenAI
    return OpenAI()


def split_transcript(text: str, chunk_chars: int = LLM_CHUNK_CHARS, overlap: int = LLM_CHUNK_OVERLAP) -> List[str]:
    text = " ".join((text or "").split())
    if not text:
        raise ValueError("Transcript is empty.")
    if len(text) <= chunk_chars:
        return [text]

    chunks = []
    start = 0
    while start < len(text):
        end = min(len(text), start + chunk_chars)
        if end < len(text):
            boundary = max(text.rfind(". ", start, end), text.rfind("? ", start, end), text.rfind("! ", start, end))
            if boundary > start + chunk_chars // 2:
                end = boundary + 1
        chunks.append(text[start:end].strip())
        if end >= len(text):
            break
        start = max(end - overlap, start + 1)
    return chunks


def _call_structured_llm(user_prompt: str) -> MeetingIntelligence:
    client = get_openai_client()
    last_error = None
    for attempt in range(1, LLM_MAX_RETRIES + 1):
        try:
            response = client.responses.parse(
                model=LLM_MODEL,
                input=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": user_prompt},
                ],
                text_format=MeetingIntelligence,
            )
            parsed = response.output_parsed
            if parsed is None:
                raise RuntimeError("LLM returned no parsed structured output.")
            return MeetingIntelligence.model_validate(parsed)
        except (ValidationError, Exception) as exc:
            last_error = exc
            logger.warning("LLM attempt %s/%s failed: %s", attempt, LLM_MAX_RETRIES, exc)
            if attempt < LLM_MAX_RETRIES:
                time.sleep(min(2 ** (attempt - 1), 4))
    raise RuntimeError(f"LLM processing failed after {LLM_MAX_RETRIES} attempts: {last_error}")


def normalize_intelligence(data: MeetingIntelligence) -> MeetingIntelligence:
    # Participant deduplication and canonicalization.
    seen = {}
    for participant in data.participants:
        key = participant.name.strip().casefold()
        if key not in seen:
            seen[key] = Participant(name=participant.name.strip(), responsibilities=[])
        existing = seen[key].responsibilities
        for responsibility in participant.responsibilities:
            if responsibility and responsibility not in existing:
                existing.append(responsibility)

    canonical = {k: v.name for k, v in seen.items()}
    for item in data.action_items:
        key = item.assigned_to.strip().casefold()
        if key in canonical:
            item.assigned_to = canonical[key]
        elif not item.assigned_to.strip():
            item.assigned_to = "Unknown"

    data.participants = list(seen.values())
    data.key_points = list(dict.fromkeys(p.strip() for p in data.key_points if p.strip()))
    data.decisions = list(dict.fromkeys(d.strip() for d in data.decisions if d.strip()))
    data.deadlines = list(dict.fromkeys(d.strip() for d in data.deadlines if d.strip()))
    data.priorities = list(dict.fromkeys(p.strip() for p in data.priorities if p.strip()))
    return MeetingIntelligence.model_validate(data.model_dump())


def process_transcript_with_llm(transcript: str) -> MeetingIntelligence:
    chunks = split_transcript(transcript)
    if len(chunks) == 1:
        result = _call_structured_llm(CHUNK_PROMPT.format(transcript=chunks[0]))
        return normalize_intelligence(result)

    partials = []
    for index, chunk in enumerate(chunks, 1):
        logger.info("Processing transcript chunk %s/%s", index, len(chunks))
        partials.append(_call_structured_llm(CHUNK_PROMPT.format(transcript=chunk)).model_dump_json())

    merged = _call_structured_llm(MERGE_PROMPT.format(analyses="\n".join(partials)))
    return normalize_intelligence(merged)

# --------------------------------------------------------------------------------------
# 7. FLASK ROUTES
# --------------------------------------------------------------------------------------
@app.route("/")
def index():
    return render_template("index.html")


@app.route("/health", methods=["GET"])
def health_check():
    return jsonify({
        "status": "healthy",
        "ffmpeg_available": bool(shutil.which("ffmpeg")),
        "whisper_model": WHISPER_MODEL_NAME,
        "llm_model": LLM_MODEL,
        "llm_configured": bool(os.getenv("OPENAI_API_KEY")),
        "database": DB_PATH,
        "supported_formats": sorted(ALLOWED_EXTENSIONS),
        "max_upload_size_mb": app.config["MAX_CONTENT_LENGTH"] // (1024 * 1024),
    })


@app.route("/api/sample-video-info", methods=["GET"])
def sample_video_info():
    files = glob.glob(os.path.join(MEDIA_FOLDER, "*.mp4")) + glob.glob(os.path.join(MEDIA_FOLDER, "*.webm")) + glob.glob(os.path.join(MEDIA_FOLDER, "*.mkv"))
    if not files:
        return jsonify({"available": False})
    path = files[0]
    filename = os.path.basename(path)
    return jsonify({"available": True, "filename": filename, "size_mb": round(os.path.getsize(path)/(1024*1024), 2), "preview_url": url_for("get_sample_media", filename=filename)})


@app.route("/media/<path:filename>")
def get_sample_media(filename):
    path = os.path.join(MEDIA_FOLDER, filename)
    return send_file(path) if os.path.exists(path) else (jsonify({"error": "File not found"}), 404)


def _transcribe_path(video_path: str):
    audio_path = os.path.join(AUDIO_FOLDER, f"{uuid.uuid4().hex[:8]}.wav")
    try:
        ffmpeg_time = extract_audio_with_ffmpeg(video_path, audio_path)
        start = time.time()
        result = get_whisper_model().transcribe(audio_path, fp16=False, verbose=False, language=None)
        whisper_time = time.time() - start
        full_text = result.get("text", "").strip()
        language = result.get("language", "en")
        raw_segments = result.get("segments", [])
        segments = []
        duration = 0.0
        for seg in raw_segments:
            s, e = float(seg.get("start", 0)), float(seg.get("end", 0))
            duration = max(duration, e)
            segments.append({"id": seg.get("id", len(segments)+1), "start": round(s,2), "end": round(e,2), "start_formatted": format_seconds_to_timestamp(s), "end_formatted": format_seconds_to_timestamp(e), "text": seg.get("text", "").strip()})
        return {
            "transcript": full_text,
            "language": language,
            "segments": segments,
            "srt": generate_srt_subtitles(segments),
            "metrics": {"ffmpeg_extraction_sec": round(ffmpeg_time,2), "whisper_transcription_sec": round(whisper_time,2), "audio_duration_sec": round(duration,2), "audio_duration_formatted": format_seconds_to_timestamp(duration), "word_count": len(full_text.split()), "segment_count": len(segments)},
        }
    finally:
        if os.path.exists(audio_path):
            os.remove(audio_path)


@app.route("/transcribe", methods=["POST"])
def transcribe_video():
    temp_video_path = None
    started = time.time()
    try:
        is_sample = request.form.get("use_sample") == "true"
        if is_sample:
            files = glob.glob(os.path.join(MEDIA_FOLDER, "*.mp4")) + glob.glob(os.path.join(MEDIA_FOLDER, "*.webm"))
            if not files:
                return jsonify({"success": False, "error": "No sample video found."}), 404
            source = files[0]
            original_filename = os.path.basename(source)
            ext = original_filename.rsplit(".",1)[1]
            temp_video_path = os.path.join(UPLOAD_FOLDER, f"sample_{uuid.uuid4().hex[:8]}.{ext}")
            shutil.copyfile(source, temp_video_path)
        else:
            file = request.files.get("video")
            if not file or not file.filename:
                return jsonify({"success": False, "error": "No video file provided."}), 400
            if not is_allowed_file(file.filename):
                return jsonify({"success": False, "error": f"Unsupported format. Allowed: {', '.join(sorted(ALLOWED_EXTENSIONS))}"}), 400
            original_filename = secure_filename(file.filename) or "video.mp4"
            temp_video_path = os.path.join(UPLOAD_FOLDER, f"{uuid.uuid4().hex[:8]}_{original_filename}")
            file.save(temp_video_path)

        output = _transcribe_path(temp_video_path)
        output["metrics"]["total_time_sec"] = round(time.time() - started, 2)
        return jsonify({"success": True, "filename": original_filename, "model_used": WHISPER_MODEL_NAME, **output})
    except Exception as exc:
        logger.exception("Transcription failed")
        return jsonify({"success": False, "error": str(exc)}), 500
    finally:
        if temp_video_path and os.path.exists(temp_video_path):
            os.remove(temp_video_path)


@app.route("/api/process-transcript", methods=["POST"])
def process_transcript_api():
    """Task 1-5: transcript -> LLM -> schema validation -> persistence."""
    try:
        payload = request.get_json(silent=True) or {}
        transcript = str(payload.get("transcript", "")).strip()
        if len(transcript) < 10:
            return jsonify({"success": False, "error": "Transcript must contain at least 10 characters."}), 400
        intelligence = process_transcript_with_llm(transcript)
        meeting_id = persist_meeting(payload.get("filename", "transcript.txt"), transcript, payload.get("language", "unknown"), intelligence)
        return jsonify({"success": True, "meeting_id": meeting_id, "model_used": LLM_MODEL, "intelligence": intelligence.model_dump()})
    except Exception as exc:
        logger.exception("Meeting intelligence processing failed")
        return jsonify({"success": False, "error": str(exc)}), 500


@app.route("/api/process-meeting", methods=["POST"])
def process_meeting_api():
    """Task 6: Upload -> Whisper -> LLM -> extraction -> participant mapping -> database."""
    temp_video_path = None
    started = time.time()
    try:
        file = request.files.get("video")
        if not file or not file.filename:
            return jsonify({"success": False, "error": "No video file provided."}), 400
        if not is_allowed_file(file.filename):
            return jsonify({"success": False, "error": "Unsupported video format."}), 400

        filename = secure_filename(file.filename) or "meeting.mp4"
        temp_video_path = os.path.join(UPLOAD_FOLDER, f"{uuid.uuid4().hex[:8]}_{filename}")
        file.save(temp_video_path)

        transcription = _transcribe_path(temp_video_path)
        if not transcription["transcript"]:
            return jsonify({"success": False, "error": "Whisper returned an empty transcript."}), 422

        intelligence = process_transcript_with_llm(transcription["transcript"])
        meeting_id = persist_meeting(filename, transcription["transcript"], transcription["language"], intelligence)

        return jsonify({
            "success": True,
            "meeting_id": meeting_id,
            "filename": filename,
            "transcription": transcription,
            "intelligence": intelligence.model_dump(),
            "models": {"whisper": WHISPER_MODEL_NAME, "llm": LLM_MODEL},
            "total_time_sec": round(time.time() - started, 2),
        })
    except Exception as exc:
        logger.exception("End-to-end meeting processing failed")
        return jsonify({"success": False, "error": str(exc)}), 500
    finally:
        if temp_video_path and os.path.exists(temp_video_path):
            os.remove(temp_video_path)


@app.route("/api/meetings/<meeting_id>", methods=["GET"])
def get_meeting_api(meeting_id):
    with get_db() as conn:
        meeting = conn.execute("SELECT * FROM meetings WHERE id = ?", (meeting_id,)).fetchone()
        if not meeting:
            return jsonify({"success": False, "error": "Meeting not found."}), 404
        result = dict(meeting)
        result["key_points"] = [r["point"] for r in conn.execute("SELECT point FROM key_points WHERE meeting_id=?", (meeting_id,))]
        result["decisions"] = [r["decision"] for r in conn.execute("SELECT decision FROM decisions WHERE meeting_id=?", (meeting_id,))]
        result["participants"] = [dict(r) for r in conn.execute("SELECT name, responsibilities FROM participants WHERE meeting_id=?", (meeting_id,))]
        result["action_items"] = [dict(r) for r in conn.execute("SELECT task, assigned_to, deadline, priority, status FROM action_items WHERE meeting_id=?", (meeting_id,))]
        result["deadlines"] = [r["deadline"] for r in conn.execute("SELECT deadline FROM deadlines WHERE meeting_id=?", (meeting_id,))]
        return jsonify({"success": True, "meeting": result})


@app.errorhandler(413)
def too_large(_):
    return jsonify({"success": False, "error": "File exceeds 250 MB limit."}), 413


@app.errorhandler(404)
def not_found(_):
    return jsonify({"success": False, "error": "Endpoint not found."}), 404


if __name__ == "__main__":
    ensure_ffmpeg_in_path()
    init_db()
    port = int(os.environ.get("PORT", 5000))
    logger.info("Starting Meeting Intelligence service on http://127.0.0.1:%s", port)
    app.run(host="0.0.0.0", port=port, debug=False)
