"""SQLite response cache + request ledger. Never stores API keys."""

from __future__ import annotations

import hashlib
import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional


class ResponseCache(object):
    def __init__(self, path: Path):
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(self.path))
        self._conn.execute(
            "CREATE TABLE IF NOT EXISTS cache ("
            " cache_key TEXT PRIMARY KEY,"
            " payload TEXT NOT NULL,"
            " created_at TEXT NOT NULL)"
        )
        self._conn.execute(
            "CREATE TABLE IF NOT EXISTS ledger ("
            " id INTEGER PRIMARY KEY AUTOINCREMENT,"
            " ts TEXT NOT NULL,"
            " vendor TEXT NOT NULL,"
            " endpoint TEXT NOT NULL,"
            " activity_id TEXT,"
            " cache_hit INTEGER NOT NULL,"
            " status TEXT NOT NULL)"
        )
        self._conn.commit()

    def close(self):
        self._conn.close()

    def get(self, key: str) -> Optional[dict]:
        row = self._conn.execute(
            "SELECT payload FROM cache WHERE cache_key = ?", (key,)
        ).fetchone()
        if not row:
            return None
        return json.loads(row[0])

    def put(self, key: str, payload: dict):
        now = datetime.now(timezone.utc).isoformat()
        self._conn.execute(
            "INSERT OR REPLACE INTO cache(cache_key, payload, created_at) VALUES (?, ?, ?)",
            (key, json.dumps(payload), now),
        )
        self._conn.commit()

    def record(self, vendor, endpoint, status, activity_id=None, cache_hit=False):
        now = datetime.now(timezone.utc).isoformat()
        self._conn.execute(
            "INSERT INTO ledger(ts, vendor, endpoint, activity_id, cache_hit, status) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (now, vendor, endpoint, activity_id, 1 if cache_hit else 0, status),
        )
        self._conn.commit()

    def ledger_summary(self):
        rows = self._conn.execute(
            "SELECT vendor, endpoint, COUNT(*), SUM(cache_hit) FROM ledger "
            "GROUP BY vendor, endpoint"
        ).fetchall()
        return [
            {
                "vendor": vendor,
                "endpoint": endpoint,
                "requests": count,
                "cache_hits": int(hits or 0),
            }
            for vendor, endpoint, count, hits in rows
        ]


def cache_key(*parts) -> str:
    raw = json.dumps(parts, sort_keys=True, default=str)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()
