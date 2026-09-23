"""
End-to-End Integration Tests for Complete Meeting Intelligence Pipeline
"""

import os
import json
import pytest
from app import app
from services.database_service import init_db, get_meeting

@pytest.fixture
def client():
    app.config["TESTING"] = True
    with app.test_client() as client:
        yield client

def test_health_check_endpoint(client):
    """Verify /health returns 200 with all subsystems healthy."""
    res = client.get("/health")
    assert res.status_code == 200
    data = res.get_json()
    assert data["status"] == "healthy"
    assert data["ffmpeg_available"] is True
    assert "whisper_model" in data
    assert "supported_formats" in data
    assert len(data["supported_formats"]) >= 8

def test_sample_video_info_endpoint(client):
    """Verify /api/sample-video-info detects demo recording."""
    res = client.get("/api/sample-video-info")
    assert res.status_code == 200
    data = res.get_json()
    assert data["available"] is True
    assert "filename" in data
    assert data["size_mb"] > 0
    assert "preview_url" in data

def test_end_to_end_meeting_pipeline_with_sample(client):
    """
    Complete End-to-End Pipeline Test:
    Upload/Sample -> FFmpeg -> Whisper -> Transcript Validation ->
    LLM Meeting Intelligence -> SQLite Persistence -> API Response.
    """
    res = client.post("/api/process-meeting", data={"use_sample": "true"})
    assert res.status_code == 200
    data = res.get_json()

    # Top-level checks
    assert data["success"] is True
    assert "meeting_id" in data
    meeting_id = data["meeting_id"]

    # Transcription checks
    assert "transcription" in data
    assert len(data["transcription"]["transcript"]) > 20
    assert len(data["transcription"]["segments"]) > 0

    # Meeting Intelligence checks
    assert "meeting_intelligence" in data
    intel = data["meeting_intelligence"]
    assert "summary" in intel
    assert len(intel["summary"]) > 10
    assert "key_points" in intel
    assert "decisions" in intel
    assert "action_items" in intel
    assert "participants" in intel
    assert "deadlines" in intel
    assert "priorities" in intel

    # Database persistence verification
    stored = get_meeting(meeting_id)
    assert stored is not None
    assert stored["id"] == meeting_id
    assert stored["summary"] == intel["summary"]

def test_get_and_list_meetings_endpoints(client):
    """Verify /api/meetings and /api/meetings/<id> endpoints return persisted data."""
    # List meetings
    list_res = client.get("/api/meetings")
    assert list_res.status_code == 200
    list_data = list_res.get_json()
    assert list_data["success"] is True
    assert "meetings" in list_data

    if list_data["meetings"]:
        sample_id = list_data["meetings"][0]["id"]
        # Get individual meeting
        item_res = client.get(f"/api/meetings/{sample_id}")
        assert item_res.status_code == 200
        item_data = item_res.get_json()
        assert item_data["success"] is True
        assert item_data["meeting"]["id"] == sample_id