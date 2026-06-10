from __future__ import annotations

import json
import os
import re
import sqlite3
import unicodedata
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

DB_PATH = Path(os.getenv("AETHORIA_DB_PATH", "/data/aethoria.sqlite"))

METRICS = [
    "war_score",
    "corruption_score",
    "stability_score",
    "trade_score",
    "nature_score",
    "world_damage",
    "world_help",
    "expansion_score",
]


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def normalize_player_key(name: str | None) -> str:
    raw = (name or "Spieler").strip().casefold()
    raw = re.sub(r"\s+", " ", raw)
    return raw or "spieler"


def slugify(value: str) -> str:
    value = unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode("ascii")
    value = re.sub(r"[^a-zA-Z0-9]+", "-", value).strip("-").lower()
    return value or "kampagne"


def _conn() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(DB_PATH)
    con.row_factory = sqlite3.Row
    con.execute("""
        CREATE TABLE IF NOT EXISTS games (
            game_id TEXT PRIMARY KEY,
            state_json TEXT NOT NULL,
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
    """)
    con.execute("""
        CREATE TABLE IF NOT EXISTS campaigns (
            campaign_id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            memory_json TEXT NOT NULL,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
    """)
    con.execute("""
        CREATE TABLE IF NOT EXISTS campaign_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            campaign_id TEXT NOT NULL,
            game_id TEXT,
            game_number INTEGER,
            player_key TEXT,
            player_name TEXT,
            faction_id TEXT,
            event_type TEXT NOT NULL,
            text TEXT NOT NULL,
            impact_json TEXT,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
    """)
    return con


# ── Game storage ─────────────────────────────────────────────────────────────

def list_games() -> list[dict[str, Any]]:
    with _conn() as con:
        rows = con.execute("SELECT game_id, updated_at, state_json FROM games ORDER BY updated_at DESC").fetchall()
    out: list[dict[str, Any]] = []
    for row in rows:
        game_id = row["game_id"]
        updated_at = row["updated_at"]
        state_json = row["state_json"]
        try:
            state = json.loads(state_json)
            out.append({
                "game_id": game_id,
                "game_name": state.get("game_name"),
                "campaign_id": state.get("campaign_id"),
                "campaign_name": state.get("campaign_name"),
                "updated_at": updated_at,
                "round": state.get("round"),
                "players": len(state.get("players", [])),
            })
        except Exception:
            out.append({"game_id": game_id, "updated_at": updated_at})
    return out


def get_game(game_id: str) -> dict[str, Any] | None:
    with _conn() as con:
        row = con.execute("SELECT state_json FROM games WHERE game_id=?", (game_id,)).fetchone()
    if not row:
        return None
    return json.loads(row["state_json"])


def put_game(game_id: str, state: dict[str, Any]) -> dict[str, Any]:
    payload = json.dumps(state, ensure_ascii=False, separators=(",", ":"))
    with _conn() as con:
        con.execute(
            "INSERT INTO games(game_id, state_json, updated_at) VALUES (?, ?, CURRENT_TIMESTAMP) "
            "ON CONFLICT(game_id) DO UPDATE SET state_json=excluded.state_json, updated_at=CURRENT_TIMESTAMP",
            (game_id, payload),
        )
    return {"game_id": game_id, "saved": True}


# ── Campaign storage ─────────────────────────────────────────────────────────

def default_campaign_memory(campaign_id: str, name: str, player_names: list[str] | None = None, description: str = "") -> dict[str, Any]:
    mem: dict[str, Any] = {
        "version": "0.97",
        "campaign_id": campaign_id,
        "name": name,
        "description": description or "",
        "created_at": utc_now(),
        "updated_at": utc_now(),
        "game_count": 0,
        "absorbed_game_ids": [],
        "players": {},
        "faction_memory_global": {},
        "game_summaries": [],
        "chronicle": [],
        "open_threats": [],
        "world_scars": [],
        "mood": "ruhig",
        "threat_level": 0,
    }
    for name_ in player_names or []:
        ensure_campaign_player(mem, name_)
    return mem


def compute_campaign_reputation(pm: dict[str, Any]) -> str:
    harmful = int(pm.get("war_score", 0)) + int(pm.get("corruption_score", 0)) + int(pm.get("world_damage", 0))
    helpful = int(pm.get("stability_score", 0)) + int(pm.get("trade_score", 0)) + int(pm.get("nature_score", 0)) + int(pm.get("world_help", 0))
    if harmful >= helpful + 10:
        return "Gefürchtet"
    if helpful >= harmful + 10:
        return "Weltbewahrer"
    if int(pm.get("corruption_score", 0)) >= 8:
        return "Aetherfrevler"
    if int(pm.get("war_score", 0)) >= 8:
        return "Kriegstreiber"
    if int(pm.get("trade_score", 0)) >= 8:
        return "Handelsstifter"
    if int(pm.get("nature_score", 0)) >= 8:
        return "Naturhüter"
    return "Unbeschrieben"


def ensure_campaign_player(mem: dict[str, Any], name: str | None) -> dict[str, Any]:
    display = (name or "Spieler").strip() or "Spieler"
    key = normalize_player_key(display)
    players = mem.setdefault("players", {})
    if key not in players:
        players[key] = {
            "player_key": key,
            "name": display,
            "games_played": 0,
            "factions_played": {},
            "last_faction": None,
            "reputation": "Unbeschrieben",
            "remembered_events": [],
            **{m: 0 for m in METRICS},
        }
    else:
        # Keep latest capitalization/name spelling.
        players[key]["name"] = display
    return players[key]


def get_campaign(campaign_id: str) -> dict[str, Any] | None:
    with _conn() as con:
        row = con.execute("SELECT memory_json FROM campaigns WHERE campaign_id=?", (campaign_id,)).fetchone()
    if not row:
        return None
    return json.loads(row["memory_json"])


def put_campaign(mem: dict[str, Any]) -> dict[str, Any]:
    mem["updated_at"] = utc_now()
    payload = json.dumps(mem, ensure_ascii=False, separators=(",", ":"))
    with _conn() as con:
        con.execute(
            "INSERT INTO campaigns(campaign_id, name, memory_json, created_at, updated_at) VALUES (?, ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP) "
            "ON CONFLICT(campaign_id) DO UPDATE SET name=excluded.name, memory_json=excluded.memory_json, updated_at=CURRENT_TIMESTAMP",
            (mem["campaign_id"], mem.get("name", mem["campaign_id"]), payload),
        )
    return mem


def create_campaign(name: str, player_names: list[str] | None = None, description: str = "") -> dict[str, Any]:
    base = slugify(name)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
    campaign_id = f"{base}-{stamp}"
    mem = default_campaign_memory(campaign_id, name.strip() or "AETHORIA-Kampagne", player_names, description)
    return put_campaign(mem)


def list_campaigns() -> list[dict[str, Any]]:
    with _conn() as con:
        rows = con.execute("SELECT campaign_id, name, memory_json, created_at, updated_at FROM campaigns ORDER BY updated_at DESC").fetchall()
    out: list[dict[str, Any]] = []
    for row in rows:
        try:
            mem = json.loads(row["memory_json"])
            out.append({
                "campaign_id": row["campaign_id"],
                "name": row["name"],
                "created_at": row["created_at"],
                "updated_at": row["updated_at"],
                "game_count": mem.get("game_count", 0),
                "players": len(mem.get("players", {})),
                "mood": mem.get("mood", "ruhig"),
                "threat_level": mem.get("threat_level", 0),
            })
        except Exception:
            out.append({"campaign_id": row["campaign_id"], "name": row["name"], "updated_at": row["updated_at"]})
    return out


def list_campaign_games(campaign_id: str) -> list[dict[str, Any]]:
    mem = get_campaign(campaign_id)
    if not mem:
        return []
    ids = set(mem.get("absorbed_game_ids", []))
    games = []
    for g in list_games():
        if g.get("campaign_id") == campaign_id or g.get("game_id") in ids:
            games.append(g)
    return games


def _top_score_player(state: dict[str, Any]) -> dict[str, Any] | None:
    players = state.get("players") or []
    if not players:
        return None
    return sorted(players, key=lambda p: int(p.get("score", 0)), reverse=True)[0]


def _update_campaign_mood(mem: dict[str, Any], final_world: dict[str, Any] | None = None) -> None:
    world = final_world or {}
    level = 0
    level += int(world.get("Weltenzorn", 0)) // 10 if world else 0
    level += int(world.get("Aetherkorruption", 0)) // 12 if world else 0
    level += int(world.get("Kriegsdruck", 0)) // 8 if world else 0
    if world and int(world.get("Stabilität", 50)) <= 25:
        level += 2
    if world and int(world.get("Naturgleichgewicht", 50)) <= 25:
        level += 2
    level += min(4, len(mem.get("open_threats", [])) // 2)
    level += min(3, len(mem.get("world_scars", [])) // 3)
    mem["threat_level"] = max(0, min(10, level))
    mem["mood"] = "ruhig" if level == 0 else "unruhig" if level <= 2 else "angespannt" if level <= 4 else "feindselig" if level <= 7 else "katastrophal"


def absorb_game_into_campaign(campaign_id: str, game_id: str, state: dict[str, Any], game_name: str | None = None) -> dict[str, Any]:
    mem = get_campaign(campaign_id)
    if not mem:
        raise KeyError("Kampagne nicht gefunden")

    absorbed = set(mem.setdefault("absorbed_game_ids", []))
    if game_id in absorbed:
        return {"campaign": mem, "absorbed": False, "already_absorbed": True}

    game_number = int(mem.get("game_count", 0)) + 1
    world_memory = state.get("world_memory") or {}
    faction_memory = world_memory.get("faction_memory") or {}
    final_world = state.get("world") or {}
    winner = _top_score_player(state)
    at = utc_now()

    player_summaries = []
    for p in state.get("players", []) or []:
        player_name = p.get("name") or f"Spieler {len(player_summaries) + 1}"
        player = ensure_campaign_player(mem, player_name)
        faction_id = p.get("factionId") or p.get("faction_id") or "unbekannt"
        faction_name = p.get("factionName") or p.get("faction_name") or faction_id
        fm = faction_memory.get(faction_id, {}) if isinstance(faction_memory, dict) else {}

        player["games_played"] = int(player.get("games_played", 0)) + 1
        player["last_faction"] = faction_name
        player.setdefault("factions_played", {})[faction_id] = int(player.setdefault("factions_played", {}).get(faction_id, 0)) + 1
        for metric in METRICS:
            player[metric] = int(player.get(metric, 0)) + int(fm.get(metric, 0) or 0)
        player["reputation"] = compute_campaign_reputation(player)

        event = {
            "game_number": game_number,
            "game_id": game_id,
            "game_name": game_name or state.get("game_name") or game_id,
            "round": state.get("round"),
            "faction_id": faction_id,
            "faction_name": faction_name,
            "score": p.get("score", 0),
            "at": at,
            "text": f"Spiel {game_number}: {player_name} spielte {faction_name}; Krieg {fm.get('war_score', 0)}, Korruption {fm.get('corruption_score', 0)}, Welthilfe {fm.get('world_help', 0)}, Weltschaden {fm.get('world_damage', 0)}.",
        }
        player.setdefault("remembered_events", []).insert(0, event)
        player["remembered_events"] = player["remembered_events"][:30]
        player_summaries.append({
            "player_key": player["player_key"],
            "name": player_name,
            "faction_id": faction_id,
            "faction_name": faction_name,
            "score": p.get("score", 0),
            "reputation": player["reputation"],
        })

        fg = mem.setdefault("faction_memory_global", {}).setdefault(faction_id, {"faction_id": faction_id, "name": faction_name, "games_seen": 0, **{m: 0 for m in METRICS}})
        fg["games_seen"] = int(fg.get("games_seen", 0)) + 1
        fg["name"] = faction_name
        for metric in METRICS:
            fg[metric] = int(fg.get(metric, 0)) + int(fm.get(metric, 0) or 0)

        with _conn() as con:
            con.execute(
                "INSERT INTO campaign_events(campaign_id, game_id, game_number, player_key, player_name, faction_id, event_type, text, impact_json) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (campaign_id, game_id, game_number, player["player_key"], player_name, faction_id, "player_summary", event["text"], json.dumps(event, ensure_ascii=False)),
            )

    # Carry over unresolved threats and notable memories into the campaign world.
    for threat in (world_memory.get("open_threats") or [])[:12]:
        t = dict(threat)
        t["source_game_id"] = game_id
        t["source_game_number"] = game_number
        mem.setdefault("open_threats", []).insert(0, t)
    mem["open_threats"] = mem.get("open_threats", [])[:40]

    for e in (world_memory.get("major_events") or [])[:12]:
        ce = dict(e)
        ce["source_game_id"] = game_id
        ce["source_game_number"] = game_number
        mem.setdefault("chronicle", []).insert(0, ce)
    mem["chronicle"] = mem.get("chronicle", [])[:120]

    scar_text = None
    if int(final_world.get("Aetherkorruption", 0)) >= 20:
        scar_text = "Aethernarben bleiben in dieser Welt sichtbar."
    elif int(final_world.get("Weltenzorn", 0)) >= 20:
        scar_text = "Die Welt trägt Zornnarben aus dieser Partie."
    elif int(final_world.get("Kriegsdruck", 0)) >= 10:
        scar_text = "Grenzlande erinnern sich an die Kriege dieser Partie."
    if scar_text:
        mem.setdefault("world_scars", []).insert(0, {"game_number": game_number, "game_id": game_id, "text": scar_text, "at": at})
        mem["world_scars"] = mem["world_scars"][:30]

    summary = {
        "game_number": game_number,
        "game_id": game_id,
        "game_name": game_name or state.get("game_name") or game_id,
        "round": state.get("round"),
        "at": at,
        "winner": {"name": winner.get("name"), "score": winner.get("score", 0)} if winner else None,
        "players": player_summaries,
        "final_world": final_world,
    }
    mem.setdefault("game_summaries", []).insert(0, summary)
    mem["game_summaries"] = mem["game_summaries"][:50]
    mem["game_count"] = game_number
    mem["absorbed_game_ids"].append(game_id)
    _update_campaign_mood(mem, final_world)
    put_campaign(mem)
    return {"campaign": mem, "absorbed": True, "already_absorbed": False, "summary": summary}
