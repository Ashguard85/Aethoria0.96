from __future__ import annotations
import json
import os
from pathlib import Path

CANON_DIR = Path(os.getenv("AETHORIA_CANON_DIR", "/app/data"))


def _load(name: str) -> dict:
    candidates = [
        CANON_DIR / name,
        Path("/app/data") / name,
        Path(__file__).resolve().parents[2] / "data" / name,
        Path(__file__).resolve().parents[1] / "data" / name,
    ]
    # /data is only a fallback for legacy installs. Normally /data is the SQLite volume.
    candidates.append(Path("/data") / name)
    for path in candidates:
        if path.exists():
            with path.open("r", encoding="utf-8") as f:
                return json.load(f)
    searched = ", ".join(str(p) for p in candidates)
    raise FileNotFoundError(f"Kanon-Datei nicht gefunden: {name}. Gesucht in: {searched}")


def game_data() -> dict:
    return _load("aethoria_game_data_v0.96.json")


def cards_data() -> dict:
    return _load("cards_v0.96.json")


def initial_state() -> dict:
    return _load("initial_game_state_v0.96.json")


def validate_canon_consistency() -> list[str]:
    problems: list[str] = []
    g = game_data()
    c = cards_data()
    if len(g.get("factions", [])) != 6:
        problems.append("Erwartet 6 Fraktionen")
    if len(c.get("secret_objectives", [])) != 18:
        problems.append("Erwartet 18 Geheimziele")
    decks = c.get("decks", {})
    for deck_name in ["Fraktionsdeck", "Forschungsdeck", "Weltreaktionsdeck", "Taktikdeck"]:
        if len(decks.get(deck_name, [])) != 15:
            problems.append(f"{deck_name}: erwartet 15 Karten")
    return problems
