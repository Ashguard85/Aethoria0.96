from __future__ import annotations
import json
import os
import sqlite3
from pathlib import Path
from typing import Any

DB_PATH = Path(os.getenv("AETHORIA_DB_PATH", "/data/aethoria.sqlite"))


def _conn() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(DB_PATH)
    con.execute("""
        CREATE TABLE IF NOT EXISTS games (
            game_id TEXT PRIMARY KEY,
            state_json TEXT NOT NULL,
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
    """)
    return con


def list_games() -> list[dict[str, Any]]:
    with _conn() as con:
        rows = con.execute("SELECT game_id, updated_at, state_json FROM games ORDER BY updated_at DESC").fetchall()
    out = []
    for game_id, updated_at, state_json in rows:
        try:
            state = json.loads(state_json)
            out.append({"game_id": game_id, "updated_at": updated_at, "round": state.get("round"), "players": len(state.get("players", []))})
        except Exception:
            out.append({"game_id": game_id, "updated_at": updated_at})
    return out


def get_game(game_id: str) -> dict[str, Any] | None:
    with _conn() as con:
        row = con.execute("SELECT state_json FROM games WHERE game_id=?", (game_id,)).fetchone()
    if not row:
        return None
    return json.loads(row[0])


def put_game(game_id: str, state: dict[str, Any]) -> dict[str, Any]:
    payload = json.dumps(state, ensure_ascii=False, separators=(",", ":"))
    with _conn() as con:
        con.execute(
            "INSERT INTO games(game_id, state_json, updated_at) VALUES (?, ?, CURRENT_TIMESTAMP) "
            "ON CONFLICT(game_id) DO UPDATE SET state_json=excluded.state_json, updated_at=CURRENT_TIMESTAMP",
            (game_id, payload),
        )
    return {"game_id": game_id, "saved": True}
