"""
SQLite persistence layer for saved evaluations.

Design decisions:
- Uses Python's built-in sqlite3 (no new dependencies).
- Database file defaults to evaluations.db in the project root — excluded
  from git via .gitignore, so personal evaluation history never gets
  committed to the public repo.
- Evaluations are only saved when the user explicitly clicks Save in the
  frontend (POST /history), not automatically on every /evaluate call.
- Full evaluation detail is stored per save (all 4 agent outputs + verdict),
  so history is genuinely useful to read back, not just a summary list.
- A delete endpoint (DELETE /history/{id}) allows cleanup of unwanted saves.
- All DB operations are synchronous (sqlite3 is not async-native). FastAPI
  runs them in a threadpool via run_in_executor to avoid blocking the event
  loop — see main.py for the wrapper pattern.
"""

import json
import sqlite3
from datetime import datetime
from pathlib import Path

DB_PATH = Path(__file__).parent / "evaluations.db"


def get_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row  # rows behave like dicts
    return conn


def init_db() -> None:
    """Create the evaluations table if it doesn't exist yet.

    Called once at app startup. Safe to call repeatedly — CREATE TABLE
    IF NOT EXISTS is idempotent.
    """
    with get_connection() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS evaluations (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                idea        TEXT    NOT NULL,
                saved_at    TEXT    NOT NULL,
                result_json TEXT    NOT NULL
            )
        """)
        conn.commit()


def save_evaluation(idea: str, result: dict) -> int:
    """Persist a full evaluation result. Returns the new row's id."""
    saved_at = datetime.utcnow().isoformat(timespec="seconds") + "Z"
    with get_connection() as conn:
        cursor = conn.execute(
            "INSERT INTO evaluations (idea, saved_at, result_json) VALUES (?, ?, ?)",
            (idea, saved_at, json.dumps(result)),
        )
        conn.commit()
        return cursor.lastrowid


def list_evaluations() -> list[dict]:
    """Return all saved evaluations, most recent first.

    Each row contains: id, idea (truncated to 120 chars for display),
    saved_at, viability_score, recommendation.
    """
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT id, idea, saved_at, result_json FROM evaluations ORDER BY id DESC"
        ).fetchall()

    result = []
    for row in rows:
        parsed = json.loads(row["result_json"])
        synthesis = parsed.get("synthesis", {})
        result.append({
            "id": row["id"],
            "idea_snippet": row["idea"][:120] + ("…" if len(row["idea"]) > 120 else ""),
            "saved_at": row["saved_at"],
            "viability_score": synthesis.get("viability_score"),
            "recommendation": synthesis.get("recommendation"),
        })
    return result


def get_evaluation(evaluation_id: int) -> dict | None:
    """Return a full saved evaluation by id, or None if not found."""
    with get_connection() as conn:
        row = conn.execute(
            "SELECT id, idea, saved_at, result_json FROM evaluations WHERE id = ?",
            (evaluation_id,),
        ).fetchone()

    if row is None:
        return None

    return {
        "id": row["id"],
        "idea": row["idea"],
        "saved_at": row["saved_at"],
        "result": json.loads(row["result_json"]),
    }


def delete_evaluation(evaluation_id: int) -> bool:
    """Delete a saved evaluation by id. Returns True if a row was deleted."""
    with get_connection() as conn:
        cursor = conn.execute(
            "DELETE FROM evaluations WHERE id = ?", (evaluation_id,)
        )
        conn.commit()
        return cursor.rowcount > 0
