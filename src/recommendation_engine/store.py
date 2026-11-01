"""SQLite feedback log: the idempotency key and write share one transaction."""

from __future__ import annotations

import hashlib
import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path


class IdempotencyConflict(ValueError):
    pass


class FeedbackStore:
    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self._connection() as connection:
            connection.execute("PRAGMA journal_mode=WAL")
            connection.execute("""
                CREATE TABLE IF NOT EXISTS feedback (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    idempotency_key TEXT NOT NULL UNIQUE,
                    payload_hash TEXT NOT NULL,
                    user_id INTEGER NOT NULL CHECK (user_id > 0),
                    movie_id INTEGER NOT NULL CHECK (movie_id > 0),
                    rating REAL NOT NULL CHECK (rating >= 0.5 AND rating <= 5.0),
                    created_at TEXT NOT NULL
                )
            """)
            connection.execute("CREATE INDEX IF NOT EXISTS feedback_user ON feedback(user_id, id)")

    @contextmanager
    def _connection(self):
        connection = sqlite3.connect(self.path, timeout=10)
        connection.row_factory = sqlite3.Row
        try:
            with connection:
                yield connection
        finally:
            connection.close()

    def record(self, key: str, user_id: int, movie_id: int, rating: float) -> tuple[dict, bool]:
        payload = {"user_id": user_id, "movie_id": movie_id, "rating": float(rating)}
        payload_hash = hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()
        with self._connection() as connection:
            connection.execute("BEGIN IMMEDIATE")
            existing = connection.execute(
                "SELECT * FROM feedback WHERE idempotency_key = ?", (key,),
            ).fetchone()
            if existing:
                if existing["payload_hash"] != payload_hash:
                    raise IdempotencyConflict("This idempotency key was used for another payload")
                return self._public(existing), False
            created_at = datetime.now(timezone.utc).isoformat()
            cursor = connection.execute(
                """INSERT INTO feedback
                (idempotency_key, payload_hash, user_id, movie_id, rating, created_at)
                VALUES (?, ?, ?, ?, ?, ?)""",
                (key, payload_hash, user_id, movie_id, rating, created_at),
            )
            return {"id": cursor.lastrowid, **payload, "created_at": created_at}, True

    def latest_for_user(self, user_id: int) -> dict[int, float]:
        with self._connection() as connection:
            rows = connection.execute(
                "SELECT movie_id, rating FROM feedback WHERE user_id = ? ORDER BY id", (user_id,),
            ).fetchall()
        return {row["movie_id"]: row["rating"] for row in rows}

    @staticmethod
    def _public(row: sqlite3.Row) -> dict:
        return {name: row[name] for name in ["id", "user_id", "movie_id", "rating", "created_at"]}
