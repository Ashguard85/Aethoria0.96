from __future__ import annotations
from typing import Any


def clamp(v: int, lo: int, hi: int) -> int:
    return max(lo, min(hi, int(v)))


def ensure_memory(state: dict[str, Any]) -> dict[str, Any]:
    players = state.get("players", [])
    mem = state.setdefault("world_memory", {})
    mem.setdefault("version", "0.96")
    mem.setdefault("round_summaries", [])
    mem.setdefault("major_events", [])
    mem.setdefault("open_threats", [])
    mem.setdefault("applied_reactions", [])
    mem.setdefault("pending_reactions", [])
    fm = mem.setdefault("faction_memory", {})
    for p in players:
        fid = p.get("factionId") or p.get("faction_id") or p.get("id")
        name = p.get("factionName") or p.get("faction_name") or p.get("name") or fid
        if not fid:
            continue
        fm.setdefault(fid, {
            "faction_id": fid,
            "name": name,
            "war_score": 0,
            "corruption_score": 0,
            "stability_score": 0,
            "trade_score": 0,
            "nature_score": 0,
            "world_damage": 0,
            "world_help": 0,
        })
    compute_mood(state)
    return mem


def compute_mood(state: dict[str, Any]) -> str:
    mem = state.setdefault("world_memory", {})
    world = state.get("world", {})
    level = 0
    level += max(0, int(world.get("Weltenzorn", 0)) // 10)
    level += max(0, int(world.get("Aetherkorruption", 0)) // 12)
    level += max(0, int(world.get("Kriegsdruck", 0)) // 8)
    if int(world.get("Stabilität", 50)) <= 25:
        level += 2
    if int(world.get("Naturgleichgewicht", 50)) <= 25:
        level += 2
    level += min(3, len(mem.get("open_threats", [])))
    mem["threat_level"] = clamp(level, 0, 10)
    mood = "ruhig" if level == 0 else "unruhig" if level <= 2 else "angespannt" if level <= 4 else "feindselig" if level <= 7 else "katastrophal"
    mem["mood"] = mood
    return mood


def top_faction(mem: dict[str, Any], metric: str) -> dict[str, Any] | None:
    rows = [x for x in mem.get("faction_memory", {}).values() if int(x.get(metric, 0)) > 0]
    if not rows:
        return None
    return sorted(rows, key=lambda x: int(x.get(metric, 0)), reverse=True)[0]


def summarize_round(state: dict[str, Any]) -> dict[str, Any]:
    mem = ensure_memory(state)
    world = state.get("world", {})
    text = f"Runde {state.get('round', '?')}: Weltlage {mem.get('mood')}; Stabilität {world.get('Stabilität')}, Korruption {world.get('Aetherkorruption')}, Krieg {world.get('Kriegsdruck')}, Zorn {world.get('Weltenzorn')}."
    summary = {"round": state.get("round"), "mood": mem.get("mood"), "threat_level": mem.get("threat_level"), "text": text, "world": world}
    mem.setdefault("round_summaries", [])
    existing = next((i for i, x in enumerate(mem["round_summaries"]) if x.get("round") == state.get("round")), None)
    if existing is None:
        mem["round_summaries"].insert(0, summary)
    else:
        mem["round_summaries"][existing] = summary
    mem["round_summaries"] = mem["round_summaries"][:20]
    return summary


REACTIONS = [
    {
        "id": "handelsblockade",
        "name": "Handelsblockade",
        "text": "Die Wege werden unsicher. Wirtschaft -2. Betrifft besonders Fraktionen mit hohem Kriegseinfluss.",
        "world": {"Wirtschaft": -2},
        "when": "Kriegsdruck >= 10",
        "target_metric": "war_score",
    },
    {
        "id": "aethersturm",
        "name": "Aethersturm",
        "text": "Aether entlädt sich in belasteten Regionen. Aetherkorruption +1 und eine offene Bedrohung bleibt bestehen.",
        "world": {"Aetherkorruption": 1},
        "when": "Aetherkorruption >= 15 oder hohe Korruptionsschuld",
        "target_metric": "corruption_score",
    },
    {
        "id": "zorn_der_erde",
        "name": "Zorn der Erde",
        "text": "Die Welt schlägt gegen Ausbeutung zurück. Weltenzorn +1; Ziel ist die Fraktion mit dem höchsten Weltschaden.",
        "world": {"Weltenzorn": 1},
        "when": "Weltenzorn >= 20 oder hoher Weltschaden",
        "target_metric": "world_damage",
    },
    {
        "id": "heilender_impuls",
        "name": "Heilender Impuls",
        "text": "Die Welt belohnt sichtbare Stabilisierung. Stabilität +1 oder Naturgleichgewicht +1 nach Wahl der Spieler.",
        "choice": [{"Stabilität": 1}, {"Naturgleichgewicht": 1}],
        "when": "Eine Fraktion hat viel Welthilfe/Stabilisierung geleistet",
        "target_metric": "world_help",
    },
    {
        "id": "ruhe_vor_sturm",
        "name": "Ruhe vor dem Sturm",
        "text": "Keine direkte Wertänderung. Die Chronik markiert eine drohende Eskalation für die nächste Runde.",
        "world": {},
        "when": "mittlere Bedrohungslage ohne klaren Schuldigen",
        "target_metric": None,
    },
]


def score_reaction(rule: dict[str, Any], state: dict[str, Any]) -> int:
    mem = ensure_memory(state)
    world = state.get("world", {})
    rid = rule["id"]
    score = 0
    if rid == "handelsblockade":
        score += 5 if int(world.get("Kriegsdruck", 0)) >= 10 else 0
        score += 2 if top_faction(mem, "war_score") else 0
    elif rid == "aethersturm":
        score += 4 if int(world.get("Aetherkorruption", 0)) >= 15 else 0
        score += 2 if top_faction(mem, "corruption_score") else 0
    elif rid == "zorn_der_erde":
        score += 4 if int(world.get("Weltenzorn", 0)) >= 20 else 0
        score += 2 if top_faction(mem, "world_damage") else 0
    elif rid == "heilender_impuls":
        score += 4 if top_faction(mem, "world_help") else 0
        score += 1 if int(world.get("Stabilität", 50)) < 50 or int(world.get("Naturgleichgewicht", 50)) < 50 else 0
    elif rid == "ruhe_vor_sturm":
        score += 3 if 2 <= int(mem.get("threat_level", 0)) <= 5 else 1
    return score


def deterministic_reactions(state: dict[str, Any]) -> list[dict[str, Any]]:
    mem = ensure_memory(state)
    out = []
    for r in REACTIONS:
        rr = dict(r)
        rr["score"] = score_reaction(r, state)
        metric = rr.get("target_metric")
        rr["target"] = top_faction(mem, metric) if metric else None
        out.append(rr)
    out = sorted(out, key=lambda x: x["score"], reverse=True)
    # Always return three legal options; if all score 0, Ruhe vor dem Sturm will remain valid.
    mem["pending_reactions"] = out[:3]
    return out[:3]


def build_world_voice_prompt(state: dict[str, Any], extra_prompt: str | None = None) -> str:
    mem = ensure_memory(state)
    reactions = deterministic_reactions(state)
    snapshot = {
        "game": "AETHORIA",
        "version": "0.96",
        "round": state.get("round"),
        "world": state.get("world", {}),
        "mood": mem.get("mood"),
        "open_threats": mem.get("open_threats", []),
        "faction_memory": mem.get("faction_memory", {}),
        "recent_rounds": mem.get("round_summaries", [])[:4],
        "allowed_reactions": [
            {"option": i + 1, "id": r["id"], "name": r["name"], "text": r["text"], "target": (r.get("target") or {}).get("name"), "world": r.get("world"), "choice": r.get("choice")}
            for i, r in enumerate(reactions)
        ],
    }
    base = (
        "Du bist die Weltstimme von AETHORIA. Du darfst KEINE neuen Regeln, Kosten, Siegpunkte oder Strafen erfinden. "
        "Wähle genau eine der erlaubten Weltreaktionen oder empfehle keine Anwendung, wenn sie unfair wäre. "
        "Antworte kurz auf Deutsch mit: 1) gewählte Option-ID, 2) erzählerische Begründung, 3) Hinweis auf den regelgebundenen Effekt.\n\n"
        f"SPIELZUSTAND:\n{snapshot}"
    )
    if extra_prompt:
        base += "\n\nZUSÄTZLICHER APP-PROMPT:\n" + extra_prompt
    return base
