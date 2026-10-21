from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from .models import EventDraft


class Storage:
    def __init__(self, path: Path):
        self.path = path
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self) -> None:
        with self._connect() as conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS drafts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    payload TEXT NOT NULL,
                    pending_field TEXT,
                    status TEXT NOT NULL DEFAULT 'active',
                    updated_at TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_drafts_user_status
                    ON drafts(user_id, status);

                CREATE TABLE IF NOT EXISTS created_events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    google_event_id TEXT NOT NULL,
                    payload TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );
                """
            )

    def save_new_draft(self, user_id: int, draft: EventDraft, pending_field: str | None) -> int:
        now = datetime.now(timezone.utc).isoformat()
        with self._connect() as conn:
            conn.execute(
                "UPDATE drafts SET status='replaced', updated_at=? WHERE user_id=? AND status='active'",
                (now, user_id),
            )
            cur = conn.execute(
                "INSERT INTO drafts(user_id, payload, pending_field, status, updated_at) VALUES(?,?,?,?,?)",
                (user_id, json.dumps(draft.to_dict(), ensure_ascii=False), pending_field, "active", now),
            )
            return int(cur.lastrowid)

    def update_draft(self, draft_id: int, draft: EventDraft, pending_field: str | None) -> None:
        with self._connect() as conn:
            conn.execute(
                "UPDATE drafts SET payload=?, pending_field=?, updated_at=? WHERE id=? AND status='active'",
                (
                    json.dumps(draft.to_dict(), ensure_ascii=False),
                    pending_field,
                    datetime.now(timezone.utc).isoformat(),
                    draft_id,
                ),
            )

    def get_active_draft(self, user_id: int):
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM drafts WHERE user_id=? AND status='active' ORDER BY id DESC LIMIT 1",
                (user_id,),
            ).fetchone()
        return self._row_to_draft(row)

    def get_draft(self, draft_id: int):
        with self._connect() as conn:
            row = conn.execute("SELECT * FROM drafts WHERE id=?", (draft_id,)).fetchone()
        return self._row_to_draft(row)

    def _row_to_draft(self, row):
        if not row:
            return None
        return {
            "id": row["id"],
            "user_id": row["user_id"],
            "draft": EventDraft.from_dict(json.loads(row["payload"])),
            "pending_field": row["pending_field"],
            "status": row["status"],
        }

    def set_status(self, draft_id: int, status: str) -> None:
        with self._connect() as conn:
            conn.execute(
                "UPDATE drafts SET status=?, updated_at=? WHERE id=?",
                (status, datetime.now(timezone.utc).isoformat(), draft_id),
            )

    def cancel_active(self, user_id: int) -> bool:
        with self._connect() as conn:
            cur = conn.execute(
                "UPDATE drafts SET status='cancelled', updated_at=? WHERE user_id=? AND status='active'",
                (datetime.now(timezone.utc).isoformat(), user_id),
            )
            return cur.rowcount > 0

    def log_created_event(self, user_id: int, google_event_id: str, draft: EventDraft) -> None:
        with self._connect() as conn:
            conn.execute(
                "INSERT INTO created_events(user_id, google_event_id, payload, created_at) VALUES(?,?,?,?)",
                (
                    user_id,
                    google_event_id,
                    json.dumps(draft.to_dict(), ensure_ascii=False),
                    datetime.now(timezone.utc).isoformat(),
                ),
            )
