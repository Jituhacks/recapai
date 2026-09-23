import os
import json
import uuid
import sqlite3
import logging
from typing import Optional, Dict, Any, List
from datetime import datetime, timezone

from services.llm_service import MeetingIntelligence

logger = logging.getLogger(__name__)

DEFAULT_DB_PATH = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "meeting_intelligence.db")
)

def get_db_path(custom_path: Optional[str] = None) -> str:
    """Returns database path from parameter, env var, or default."""
    return custom_path or os.getenv("DATABASE_PATH") or DEFAULT_DB_PATH

def get_db_connection(db_path: Optional[str] = None) -> sqlite3.Connection:
    """
    Creates and returns a SQLite connection with Row factory and Foreign Keys enabled.
    """
    path = get_db_path(db_path)
    dir_name = os.path.dirname(path)
    if dir_name:
        os.makedirs(dir_name, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn

def init_db(db_path: Optional[str] = None) -> None:
    """
    Initializes database schema with relational tables and cascade constraints.
    """
    path = get_db_path(db_path)
    logger.info("Initializing SQLite database at: %s", path)
    with get_db_connection(path) as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS meetings (
                id TEXT PRIMARY KEY,
                filename TEXT NOT NULL,
                transcript TEXT NOT NULL,
                summary TEXT NOT NULL,
                language TEXT DEFAULT 'EN',
                model_used TEXT DEFAULT 'Whisper + LLM',
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

            CREATE TABLE IF NOT EXISTS priorities (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                meeting_id TEXT NOT NULL,
                priority TEXT NOT NULL,
                FOREIGN KEY(meeting_id) REFERENCES meetings(id) ON DELETE CASCADE
            );
            """
        )
    logger.info("SQLite database schema verified successfully.")

def persist_meeting(
    filename: str,
    transcript: str,
    language: str,
    model_used: str,
    intelligence: MeetingIntelligence,
    db_path: Optional[str] = None
) -> str:
    """
    Persists structured meeting intelligence into relational database inside an ACID transaction.
    
    Returns:
        meeting_id (UUID string)
    """
    path = get_db_path(db_path)
    meeting_id = str(uuid.uuid4())
    now_iso = datetime.now(timezone.utc).isoformat()
    data = intelligence.model_dump()

    with get_db_connection(path) as conn:
        conn.execute(
            """
            INSERT INTO meetings(id, filename, transcript, summary, language, model_used, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (meeting_id, filename, transcript, intelligence.summary, language, model_used, now_iso)
        )

        if data.get("key_points"):
            conn.executemany(
                "INSERT INTO key_points(meeting_id, point) VALUES (?, ?)",
                [(meeting_id, pt) for pt in data["key_points"]]
            )

        if data.get("decisions"):
            conn.executemany(
                "INSERT INTO decisions(meeting_id, decision) VALUES (?, ?)",
                [(meeting_id, dec) for dec in data["decisions"]]
            )

        for p in data.get("participants", []):
            conn.execute(
                """
                INSERT OR IGNORE INTO participants(meeting_id, name, responsibilities)
                VALUES (?, ?, ?)
                """,
                (meeting_id, p["name"], json.dumps(p.get("responsibilities", [])))
            )

        for item in data.get("action_items", []):
            conn.execute(
                """
                INSERT INTO action_items(meeting_id, task, assigned_to, deadline, priority, status)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    meeting_id,
                    item["task"],
                    item["assigned_to"],
                    item.get("deadline"),
                    item.get("priority", "unknown"),
                    item.get("status", "not_started")
                )
            )

        if data.get("deadlines"):
            conn.executemany(
                "INSERT INTO deadlines(meeting_id, deadline) VALUES (?, ?)",
                [(meeting_id, d) for d in data["deadlines"]]
            )

        if data.get("priorities"):
            conn.executemany(
                "INSERT INTO priorities(meeting_id, priority) VALUES (?, ?)",
                [(meeting_id, pr) for pr in data["priorities"]]
            )

    logger.info("Successfully persisted meeting intelligence with ID: %s", meeting_id)
    return meeting_id

def get_meeting(meeting_id: str, db_path: Optional[str] = None) -> Optional[Dict[str, Any]]:
    """
    Retrieves full meeting record and all associated relational intelligence.
    """
    path = get_db_path(db_path)
    with get_db_connection(path) as conn:
        meeting_row = conn.execute(
            "SELECT * FROM meetings WHERE id = ?", (meeting_id,)
        ).fetchone()

        if not meeting_row:
            return None

        result = dict(meeting_row)
        result["key_points"] = [
            r["point"] for r in conn.execute("SELECT point FROM key_points WHERE meeting_id = ?", (meeting_id,))
        ]
        result["decisions"] = [
            r["decision"] for r in conn.execute("SELECT decision FROM decisions WHERE meeting_id = ?", (meeting_id,))
        ]
        result["participants"] = [
            {
                "name": r["name"],
                "responsibilities": json.loads(r["responsibilities"]) if r["responsibilities"] else []
            }
            for r in conn.execute("SELECT name, responsibilities FROM participants WHERE meeting_id = ?", (meeting_id,))
        ]
        result["action_items"] = [
            {
                "id": r["id"],
                "task": r["task"],
                "assigned_to": r["assigned_to"],
                "deadline": r["deadline"],
                "priority": r["priority"],
                "status": r["status"]
            }
            for r in conn.execute("SELECT * FROM action_items WHERE meeting_id = ?", (meeting_id,))
        ]
        result["deadlines"] = [
            r["deadline"] for r in conn.execute("SELECT deadline FROM deadlines WHERE meeting_id = ?", (meeting_id,))
        ]
        result["priorities"] = [
            r["priority"] for r in conn.execute("SELECT priority FROM priorities WHERE meeting_id = ?", (meeting_id,))
        ]

        return result

def list_meetings(limit: int = 50, db_path: Optional[str] = None) -> List[Dict[str, Any]]:
    """
    Lists recent meetings with high-level summary metadata.
    """
    path = get_db_path(db_path)
    with get_db_connection(path) as conn:
        rows = conn.execute(
            """
            SELECT id, filename, summary, language, model_used, created_at
            FROM meetings ORDER BY created_at DESC LIMIT ?
            """,
            (limit,)
        ).fetchall()
        return [dict(r) for r in rows]

def delete_meeting(meeting_id: str, db_path: Optional[str] = None) -> bool:
    """
    Deletes meeting and automatically cascades deletion to all associated child records.
    """
    path = get_db_path(db_path)
    with get_db_connection(path) as conn:
        cursor = conn.execute("DELETE FROM meetings WHERE id = ?", (meeting_id,))
        return cursor.rowcount > 0