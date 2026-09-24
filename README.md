# ⚡ MeetIntel-AI
### Milestones 1 & 2: Complete Audio Processing & Meeting Intelligence Pipeline

An end-to-end automated platform that transforms raw audio/video meeting recordings into structured, actionable business intelligence with sub-second retrieval, timestamp-synchronized playback, and relational database persistence.

---

## 🏛️ Pipeline Architecture

```
                      +-----------------------------+
                      | Meeting Audio / Video Input |
                      +-----------------------------+
                                     |
                                     v
                      +-----------------------------+
                      |    File Upload Validation   |
                      | (Format, Size & Sanity Check|
                      +-----------------------------+
                                     |
                                     v
                      +-----------------------------+
                      |   FFmpeg Audio Processing   |
                      |   (16kHz Mono 16-bit PCM)   |
                      +-----------------------------+
                                     |
                                     v
                      +-----------------------------+
                      |   Whisper Speech-to-Text    |
                      | (Neural STT + Timestamping) |
                      +-----------------------------+
                                     |
                                     v
                      +-----------------------------+
                      |    Transcript Validation    |
                      +-----------------------------+
                                     |
                                     v
                      +-----------------------------+
                      |    LLM Processing Service   |
                      | (Chunking + Schema Parsing) |
                      +-----------------------------+
                                     |
                                     v
                      +-----------------------------+
                      | Structured Meeting Insights |
                      |  • Executive Summary        |
                      |  • Key Discussion Points    |
                      |  • Key Decisions            |
                      |  • Action Items (Assigned)  |
                      |  • Participant Mapping      |
                      |  • Deadlines & Priorities   |
                      +-----------------------------+
                                     |
                                     v
                      +-----------------------------+
                      | SQLite Relational Database  |
                      | (ACID Cascade Persistence)  |
                      +-----------------------------+
                                     |
                                     v
                      +-----------------------------+
                      | Interactive Web Dashboard   |
                      +-----------------------------+
```

---

## 🚀 Key Features

### Milestone 1: Audio Processing & Transcription
- **Multi-Format Media Support**: Seamlessly processes video (`MP4`, `MOV`, `AVI`, `MKV`, `WebM`) and audio (`MP3`, `WAV`, `M4A`, `OGG`, `FLAC`, `AAC`).
- **FFmpeg 16kHz Normalization**: Auto-locates system FFmpeg and extracts standard 16kHz mono audio streams.
- **OpenAI Whisper STT**: Ultra-fast, high-accuracy neural transcription with word-level & segment-level timestamps.
- **Transcript Validation**: Multi-stage validation ensuring non-empty, semantically rich transcript output.
- **SRT Subtitle Generation**: Automatic generation of numbered SubRip (`.srt`) files.
- **Accuracy Verification (WER >= 90%)**: Dynamic programming Levenshtein WER computation achieving >95% accuracy on test recordings.

### Milestone 2: Meeting Intelligence & Persistence
- **Executive Summarization**: Distills complex meetings into concise, high-level executive summaries.
- **Action Item Extraction**: Extracts tasks, assignees, deadlines, priority levels (`high`, `medium`, `low`), and statuses (`not_started`, `in_progress`, `completed`).
- **Participant & Responsibility Mapping**: Canonicalizes name variations (e.g., merging "Ravi" and "Ravi Kumar") without creating duplicate records.
- **Long Transcript Handling**: Context-aware chunking with natural sentence boundary detection and map-reduce aggregation.
- **Exponential Retry & Graceful Resilience**: Handles transient API failures with backoff retry and deterministic NLP fallback for offline execution.
- **SQLite Relational Persistence**: ACID-compliant storage across normalized tables (`meetings`, `key_points`, `decisions`, `participants`, `action_items`, `deadlines`, `priorities`) with cascading deletions.
- **Interactive Single-Page UI**: Dark/light glassmorphism UI with live 7-step visual stepper, video seek-jump from timestamps, real-time search with match highlights, and multi-format export (Markdown, JSON, TXT, SRT).

---

## 🛠️ Tech Stack & Requirements

- **Backend**: Python 3.10+ & Flask 3.1
- **Speech-to-Text**: OpenAI Whisper (`tiny`/`base`)
- **Audio Processing**: FFmpeg
- **Data Validation & Schemas**: Pydantic 2.x
- **LLM Engine**: OpenAI / Structured LLM API & Heuristic Fallback
- **Database**: SQLite3 with Foreign Keys & Cascade Constraints
- **Frontend**: Vanilla HTML5, CSS3 (Glassmorphism), JavaScript (ES6+)
- **Testing**: Pytest

---

## 📦 Installation & Setup

### 1. Clone Repository & Setup Virtual Environment
```bash
# Navigate to project directory
cd "Infosys AI Powered Career Intelligence Platform"

# Create and activate Python virtual environment
python -m venv venv
# On Windows PowerShell:
.\venv\Scripts\Activate.ps1
# On Linux/macOS:
source venv/bin/activate
```

### 2. Install Dependencies
```bash
pip install -r requirements.txt
```

### 3. Configure Environment Variables
Copy `.env.example` to `.env` and configure your API keys (optional):
```bash
cp .env.example .env
```
Key settings in `.env`:
```env
PORT=5000
WHISPER_MODEL=tiny
LLM_PROVIDER=openai
LLM_MODEL=gpt-4o-mini
OPENAI_API_KEY=your_openai_api_key_here
DATABASE_PATH=meeting_intelligence.db
```

### 4. FFmpeg Verification
The application automatically locates FFmpeg on Windows (WinGet packages, AppData, standard PATH). To verify manually:
```bash
ffmpeg -version
```

---

## 🚀 Running the Application

### Start the Flask Server:
```bash
python app.py
```
Open your browser at **`http://127.0.0.1:5000`**.

---

## 📡 API Endpoints

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/` | Serves interactive single-page web dashboard |
| `GET` | `/health` | Subsystem diagnostics and configuration check |
| `GET` | `/api/sample-video-info` | Returns demo media metadata |
| `POST` | `/transcribe` | **Milestone 1**: Audio/video extraction & Whisper STT |
| `POST` | `/api/process-transcript` | **Milestone 2**: Raw transcript -> LLM Intelligence -> Database |
| `POST` | `/api/process-meeting` | **Full Pipeline**: Upload -> Audio -> Whisper -> LLM -> Database |
| `GET` | `/api/meetings` | Lists historical persisted meetings |
| `GET` | `/api/meetings/<meeting_id>` | Retrieves complete intelligence for a specific meeting |
| `DELETE` | `/api/meetings/<meeting_id>` | Deletes meeting and cascades delete to child tables |

---

## 🧪 Automated Testing & Accuracy Verification

### Run Complete Pytest Test Suite:
```bash
pytest tests/ -v
```

### Run Standalone Accuracy Benchmark (Milestone 1 — Task 5):
```bash
python tests/test_accuracy.py
```

### 📊 Benchmark Results:
```
================================================================================
TASK 5: FINAL ACCURACY BENCHMARK REPORT
================================================================================
| Recording | Format | Reference Words | Hypothesis Words | Substitutions | Deletions | Insertions | WER | Accuracy | Target (>=90%) |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Simplilearn AI Explained | MP4 Video | 680 | 687 | 23 | 0 | 7 | 0.0441 | 95.59% | **PASS** |
| AI Explained Mono Audio | WAV Audio | 680 | 687 | 23 | 0 | 7 | 0.0441 | 95.59% | **PASS** |
| Tech Talk Intro Snippet | MP3 Audio | 127 | 125 | 2 | 3 | 1 | 0.0472 | 95.28% | **PASS** |
================================================================================
```

---

## 📋 Milestone Verification Checklist

### MILESTONE 1 — Audio Processing & Transcription
- [x] **Task 1 — Whisper Transcription**: Upload -> FFmpeg Audio Extraction -> Whisper Neural STT -> Transcript -> Subtitles (`.srt`). (**PASS**)
- [x] **Task 2 — File Upload Validation**: Multi-format validation (MP4, MOV, AVI, MKV, WebM, MP3, WAV, M4A), empty file rejection, oversized file rejection (250MB limit), temp file cleanup. (**PASS**)
- [x] **Task 3 — Transcript Validation**: Ensures non-empty, semantically valid transcripts before downstream processing. (**PASS**)
- [x] **Task 4 — Interface**: Clean drag-and-drop file upload, video/audio preview player, synced transcript jump, search with match highlights, theme toggle. (**PASS**)
- [x] **Task 5 — Accuracy Testing**: Verified against ground-truth reference transcripts across formats (WER 4.4% - 4.7%, Accuracy **>95%**, exceeding 90% target). (**PASS**)

### MILESTONE 2 — Meeting Intelligence
- [x] **Task 1 — LLM Processing Service**: Configurable provider/model architecture, Pydantic schema validation, sentence-boundary chunking, and exponential retry handling. (**PASS**)
- [x] **Task 2 — Meeting Summarization Module**: Generates factual executive summaries and key discussion points from real transcripts. (**PASS**)
- [x] **Task 3 — Action Item Extraction Engine**: Extracts tasks, assignees, deadlines, priority levels, and execution statuses. (**PASS**)
- [x] **Task 4 — Participant & Responsibility Mapping**: Canonicalizes participant name variations (e.g. "Ravi" / "Ravi Kumar") and maps specific deliverables without duplicates. (**PASS**)
- [x] **Task 5 — Meeting Data Model & Database Persistence**: Relational SQLite schema with cascade deletion (`meetings`, `key_points`, `decisions`, `participants`, `action_items`, `deadlines`, `priorities`). (**PASS**)
- [x] **Task 6 — Processing API & Service Integration**: Clean modular service orchestration (`services/`) exposed through `/api/process-meeting`. (**PASS**)

---

## 🔒 Security Best Practices

- Secrets, credentials, and API keys are strictly loaded from environment variables (`.env`).
- `.env`, `venv/`, `__pycache__/`, `*.db`, and uploaded media files are excluded via `.gitignore`.
- Filenames sanitized using `secure_filename`.
- Temporary audio extraction files are cleaned up in `finally` blocks.

---
*Infosys Springboard AI-Powered Career Intelligence Platform — 2026*
