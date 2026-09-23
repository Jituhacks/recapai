"""
Unit and Integration Tests for Milestone 2: Meeting Intelligence, Schema Validation & Database
"""

import os
import gc
import pytest
import sqlite3
from app import app
from services.llm_service import (
    MeetingIntelligence,
    ActionItem,
    Participant,
    split_transcript,
    extract_fallback_intelligence
)
from services.intelligence_service import (
    canonicalize_participant_name,
    normalize_intelligence,
    process_transcript_intelligence
)
from services.database_service import (
    init_db,
    persist_meeting,
    get_meeting,
    list_meetings,
    delete_meeting,
    get_db_connection
)

TEST_DB = os.path.abspath("test_meeting_intel.db")

@pytest.fixture(autouse=True)
def setup_test_database():
    """Sets up a clean isolated test database for every test run."""
    gc.collect()
    try:
        if os.path.exists(TEST_DB):
            os.remove(TEST_DB)
    except Exception:
        pass

    init_db(TEST_DB)
    yield
    gc.collect()
    try:
        if os.path.exists(TEST_DB):
            os.remove(TEST_DB)
    except Exception:
        pass

@pytest.fixture
def client():
    app.config["TESTING"] = True
    with app.test_client() as client:
        yield client

# --------------------------------------------------------------------------------------
# 1. PYDANTIC SCHEMA VALIDATION
# --------------------------------------------------------------------------------------
def test_valid_meeting_intelligence_schema():
    """Verify valid structured dictionary parses into MeetingIntelligence Pydantic model."""
    data = {
        "summary": "Team agreed to launch mobile app next Friday and assigned tasks.",
        "key_points": ["Mobile app launch ready", "Backend APIs tested"],
        "decisions": ["Proceed with production deployment"],
        "action_items": [
            {
                "task": "Finalize payment gateway integration",
                "assigned_to": "Ravi Kumar",
                "deadline": "Friday",
                "priority": "high",
                "status": "in_progress"
            }
        ],
        "participants": [
            {
                "name": "Ravi Kumar",
                "responsibilities": ["Payment gateway integration"]
            }
        ],
        "deadlines": ["Friday"],
        "priorities": ["HIGH"]
    }
    model = MeetingIntelligence.model_validate(data)
    assert model.summary.startswith("Team agreed")
    assert len(model.action_items) == 1
    assert model.action_items[0].assigned_to == "Ravi Kumar"
    assert model.action_items[0].priority == "high"

def test_invalid_action_item_priority():
    """Verify invalid priority defaults or raises validation error."""
    with pytest.raises(Exception):
        ActionItem(task="Fix bug", priority="super_urgent")

# --------------------------------------------------------------------------------------
# 2. PARTICIPANT DEDUPLICATION & CANONICALIZATION
# --------------------------------------------------------------------------------------
def test_participant_canonicalization():
    """Verify single names map to fuller versions when referring to the same participant."""
    known = ["Ravi Kumar", "Anita Sharma"]
    assert canonicalize_participant_name("Ravi", known) == "Ravi Kumar"
    assert canonicalize_participant_name("ravi kumar", known) == "Ravi Kumar"
    assert canonicalize_participant_name("Anita", known) == "Anita Sharma"
    assert canonicalize_participant_name("John Doe", known) == "John Doe"

def test_intelligence_normalization_deduplication():
    """Verify deduplication of participants and action items normalization."""
    raw = MeetingIntelligence(
        summary="Sprint meeting discussing architecture.",
        key_points=["Scalability is key", "Scalability is key", "Database optimization"],
        decisions=["Adopt SQLite", "Adopt SQLite"],
        action_items=[
            ActionItem(task="Setup SQLite schema", assigned_to="Ravi", priority="high"),
            ActionItem(task="Write automated tests", assigned_to="Ravi Kumar", priority="medium")
        ],
        participants=[
            Participant(name="Ravi", responsibilities=["Setup SQLite schema"]),
            Participant(name="Ravi Kumar", responsibilities=["Write automated tests"])
        ],
        deadlines=["End of week", "End of week"],
        priorities=["HIGH", "HIGH", "MEDIUM"]
    )

    normalized = normalize_intelligence(raw)

    # Participants should be merged into single canonical "Ravi Kumar"
    assert len(normalized.participants) == 1
    assert normalized.participants[0].name == "Ravi Kumar"
    assert len(normalized.participants[0].responsibilities) == 2

    # Action items assignees should be canonicalized to "Ravi Kumar"
    for item in normalized.action_items:
        assert item.assigned_to == "Ravi Kumar"

    # Lists should be deduplicated
    assert len(normalized.key_points) == 2
    assert len(normalized.decisions) == 1
    assert len(normalized.deadlines) == 1
    assert len(normalized.priorities) == 2

# --------------------------------------------------------------------------------------
# 3. CHUNKING LOGIC FOR LONG TRANSCRIPTS
# --------------------------------------------------------------------------------------
def test_split_transcript_short():
    """Verify short transcripts are returned as a single chunk."""
    text = "Short meeting transcript under 100 characters."
    chunks = split_transcript(text, chunk_chars=500)
    assert len(chunks) == 1
    assert chunks[0] == text

def test_split_transcript_long():
    """Verify long text is cleanly split into multiple chunks at sentence boundaries."""
    sentences = [f"Sentence {i} discussing important project Milestone {i}." for i in range(1, 50)]
    long_text = " ".join(sentences)
    chunks = split_transcript(long_text, chunk_chars=300, overlap=50)
    assert len(chunks) > 1
    for c in chunks:
        assert len(c) <= 350
        assert len(c) > 0

# --------------------------------------------------------------------------------------
# 4. DATABASE PERSISTENCE & RETRIEVAL
# --------------------------------------------------------------------------------------
def test_database_persistence_and_retrieval():
    """Verify full meeting intelligence is persisted to SQLite and retrieved accurately."""
    intel = MeetingIntelligence(
        summary="The team met to review Sprint 4 progress.",
        key_points=["Backend is 95% complete", "Frontend UI design approved"],
        decisions=["Freeze code on Thursday"],
        action_items=[
            ActionItem(task="Deploy staging environment", assigned_to="Priya", deadline="Thursday", priority="high", status="in_progress")
        ],
        participants=[
            Participant(name="Priya", responsibilities=["Deploy staging environment"])
        ],
        deadlines=["Thursday"],
        priorities=["HIGH"]
    )

    meeting_id = persist_meeting(
        filename="sprint4_review.mp4",
        transcript="Full meeting transcript text here.",
        language="EN",
        model_used="Whisper + LLM",
        intelligence=intel,
        db_path=TEST_DB
    )

    assert meeting_id is not None
    assert len(meeting_id) > 10

    # Retrieve from DB
    retrieved = get_meeting(meeting_id, db_path=TEST_DB)
    assert retrieved is not None
    assert retrieved["id"] == meeting_id
    assert retrieved["filename"] == "sprint4_review.mp4"
    assert retrieved["summary"] == intel.summary
    assert len(retrieved["key_points"]) == 2
    assert retrieved["key_points"][0] == "Backend is 95% complete"
    assert len(retrieved["decisions"]) == 1
    assert len(retrieved["action_items"]) == 1
    assert retrieved["action_items"][0]["assigned_to"] == "Priya"
    assert retrieved["action_items"][0]["priority"] == "high"
    assert len(retrieved["participants"]) == 1
    assert retrieved["participants"][0]["name"] == "Priya"

def test_database_cascading_delete():
    """Verify deleting a meeting cascades and cleans up all relational child tables."""
    intel = extract_fallback_intelligence("Ravi and Anita discussed the product launch.")
    meeting_id = persist_meeting("test.mp4", "transcript", "EN", "model", intel, db_path=TEST_DB)

    # Verify rows exist
    with get_db_connection(TEST_DB) as conn:
        assert conn.execute("SELECT COUNT(*) FROM meetings WHERE id=?", (meeting_id,)).fetchone()[0] == 1
        assert conn.execute("SELECT COUNT(*) FROM key_points WHERE meeting_id=?", (meeting_id,)).fetchone()[0] > 0

    # Delete meeting
    deleted = delete_meeting(meeting_id, db_path=TEST_DB)
    assert deleted is True

    # Verify cascade deletion
    with get_db_connection(TEST_DB) as conn:
        assert conn.execute("SELECT COUNT(*) FROM meetings WHERE id=?", (meeting_id,)).fetchone()[0] == 0
        assert conn.execute("SELECT COUNT(*) FROM key_points WHERE meeting_id=?", (meeting_id,)).fetchone()[0] == 0
        assert conn.execute("SELECT COUNT(*) FROM action_items WHERE meeting_id=?", (meeting_id,)).fetchone()[0] == 0
        assert conn.execute("SELECT COUNT(*) FROM participants WHERE meeting_id=?", (meeting_id,)).fetchone()[0] == 0

# --------------------------------------------------------------------------------------
# 5. API ENDPOINT /api/process-transcript
# --------------------------------------------------------------------------------------
def test_api_process_transcript(client):
    """Integration test: Verify /api/process-transcript processes raw text, persists, and returns valid JSON."""
    raw_transcript = (
        "Good morning team. Today Ravi Kumar agreed to complete the API integration by Friday. "
        "Anita Sharma will finish the test automation suite by Monday. We have decided to launch "
        "the mobile application next month. Priority for this week is critical bug fixing."
    )

    res = client.post(
        "/api/process-transcript",
        json={"transcript": raw_transcript, "filename": "morning_standup.txt"}
    )
    assert res.status_code == 200
    data = res.get_json()
    assert data["success"] is True
    assert "meeting_id" in data
    assert "meeting_intelligence" in data
    intel = data["meeting_intelligence"]
    assert "summary" in intel
    assert len(intel["action_items"]) >= 1
    assert len(intel["participants"]) >= 1