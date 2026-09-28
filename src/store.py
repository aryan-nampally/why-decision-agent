"""Canonical record store (SQLite).

The store never decides what is relevant — Hindsight does. It only hydrates a
document_id returned by recall into the full record that was actually written.
"""
from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from .config import DB_PATH
from .schema import DecisionRecord, Postmortem, Signal

Record = DecisionRecord | Postmortem | Signal
_MODELS = {"adr": DecisionRecord, "postmortem": Postmortem, "signal": Signal}


class Store:
    def __init__(self, path: Path = DB_PATH):
        path.parent.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(path, check_same_thread=False)
        self.db.execute(
            "CREATE TABLE IF NOT EXISTS records ("
            " id TEXT PRIMARY KEY, kind TEXT NOT NULL, date TEXT NOT NULL, body TEXT NOT NULL)"
        )
        self.db.commit()

    def put(self, rec: Record) -> None:
        self.db.execute(
            "INSERT OR REPLACE INTO records (id, kind, date, body) VALUES (?, ?, ?, ?)",
            (rec.id, rec.kind, rec.date.isoformat(), rec.model_dump_json()),
        )
        self.db.commit()

    def get(self, rid: str) -> Record | None:
        row = self.db.execute("SELECT kind, body FROM records WHERE id = ?", (rid,)).fetchone()
        return _MODELS[row[0]].model_validate_json(row[1]) if row else None

    def all(self, kind: str | None = None) -> list[Record]:
        q, args = "SELECT kind, body FROM records", ()
        if kind:
            q, args = q + " WHERE kind = ?", (kind,)
        rows = self.db.execute(q + " ORDER BY date", args).fetchall()
        return [_MODELS[k].model_validate_json(b) for k, b in rows]

    def clear(self) -> None:
        self.db.execute("DELETE FROM records")
        self.db.commit()


def dump_json(records: list[Record]) -> str:
    return json.dumps([json.loads(r.model_dump_json()) for r in records], indent=2)
