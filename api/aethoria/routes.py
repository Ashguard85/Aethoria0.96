from __future__ import annotations
from typing import Any
import os

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from .canon import game_data, cards_data, initial_state, validate_canon_consistency
from .storage import (
    list_games,
    get_game,
    put_game,
    list_campaigns,
    create_campaign,
    get_campaign,
    put_campaign,
    list_campaign_games,
    absorb_game_into_campaign,
    ensure_campaign_player,
)
from .world_memory import ensure_memory, summarize_round, deterministic_reactions, build_world_voice_prompt
from .ollama import ask_ollama, health as ollama_health, OLLAMA_MODEL


class StatePayload(BaseModel):
    state: dict[str, Any]


class WorldVoicePayload(BaseModel):
    game_state: dict[str, Any]
    prompt: str | None = None
    model: str | None = None
    use_ollama: bool = True


class CampaignCreatePayload(BaseModel):
    name: str = Field(..., min_length=1)
    description: str | None = None
    player_names: list[str] = Field(default_factory=list)


class CampaignUpdatePayload(BaseModel):
    name: str | None = None
    description: str | None = None
    player_names: list[str] = Field(default_factory=list)


class CampaignAbsorbPayload(BaseModel):
    state: dict[str, Any]
    game_name: str | None = None


app = FastAPI(title="AETHORIA Companion Backend", version="0.97.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=os.getenv("CORS_ALLOW_ORIGINS", "*").split(","),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/health")
async def health() -> dict:
    problems = validate_canon_consistency()
    ollama_ok = False
    ollama_error = None
    try:
        await ollama_health()
        ollama_ok = True
    except Exception as e:
        ollama_error = str(e)
    return {
        "status": "ok" if not problems else "warning",
        "app": "AETHORIA Companion",
        "version": "0.97",
        "backend": "FastAPI",
        "canon_consistent": not problems,
        "canon_problems": problems,
        "ollama_available": ollama_ok,
        "ollama_model": OLLAMA_MODEL,
        "ollama_error": ollama_error,
        "features": ["sqlite_games", "campaign_world_memory", "player_name_memory"],
    }


@app.get("/api/canon")
async def get_canon() -> dict:
    return game_data()


@app.get("/api/cards")
async def get_cards() -> dict:
    return cards_data()


@app.get("/api/initial-state")
async def get_initial_state() -> dict:
    st = initial_state()
    ensure_memory(st)
    return st


# ── Game save/load ───────────────────────────────────────────────────────────

@app.get("/api/games")
async def games() -> dict:
    return {"games": list_games()}


@app.get("/api/games/{game_id}")
async def game(game_id: str) -> dict:
    st = get_game(game_id)
    if not st:
        raise HTTPException(status_code=404, detail="Spielstand nicht gefunden")
    ensure_memory(st)
    return {"game_id": game_id, "state": st}


@app.put("/api/games/{game_id}")
async def save_game(game_id: str, payload: StatePayload) -> dict:
    st = payload.state
    ensure_memory(st)
    put_game(game_id, st)
    return {"game_id": game_id, "saved": True, "world_memory": st.get("world_memory", {})}


# ── Campaigns / persistent world chronicle ───────────────────────────────────

@app.get("/api/campaigns")
async def campaigns() -> dict:
    return {"campaigns": list_campaigns()}


@app.post("/api/campaigns")
async def new_campaign(payload: CampaignCreatePayload) -> dict:
    mem = create_campaign(payload.name, payload.player_names, payload.description or "")
    return {"campaign": mem, "created": True}


@app.get("/api/campaigns/{campaign_id}")
async def campaign(campaign_id: str) -> dict:
    mem = get_campaign(campaign_id)
    if not mem:
        raise HTTPException(status_code=404, detail="Kampagne nicht gefunden")
    return {"campaign": mem}


@app.put("/api/campaigns/{campaign_id}")
async def update_campaign(campaign_id: str, payload: CampaignUpdatePayload) -> dict:
    mem = get_campaign(campaign_id)
    if not mem:
        raise HTTPException(status_code=404, detail="Kampagne nicht gefunden")
    if payload.name is not None and payload.name.strip():
        mem["name"] = payload.name.strip()
    if payload.description is not None:
        mem["description"] = payload.description
    for player_name in payload.player_names or []:
        ensure_campaign_player(mem, player_name)
    put_campaign(mem)
    return {"campaign": mem, "saved": True}


@app.get("/api/campaigns/{campaign_id}/games")
async def campaign_games(campaign_id: str) -> dict:
    mem = get_campaign(campaign_id)
    if not mem:
        raise HTTPException(status_code=404, detail="Kampagne nicht gefunden")
    return {"campaign_id": campaign_id, "games": list_campaign_games(campaign_id)}


@app.post("/api/campaigns/{campaign_id}/absorb-game/{game_id}")
async def campaign_absorb_game(campaign_id: str, game_id: str, payload: CampaignAbsorbPayload) -> dict:
    try:
        result = absorb_game_into_campaign(campaign_id, game_id, payload.state, payload.game_name)
    except KeyError:
        raise HTTPException(status_code=404, detail="Kampagne nicht gefunden")
    return result


# ── World memory / Ollama ─────────────────────────────────────────────────────

@app.post("/api/world/analyze")
async def analyze_world(payload: StatePayload) -> dict:
    st = payload.state
    mem = ensure_memory(st)
    summary = summarize_round(st)
    reactions = deterministic_reactions(st)
    return {"world_memory": mem, "summary": summary, "deterministic_reactions": reactions}


@app.post("/api/world/reactions")
async def world_reactions(payload: StatePayload) -> dict:
    st = payload.state
    mem = ensure_memory(st)
    reactions = deterministic_reactions(st)
    return {"world_memory": mem, "deterministic_reactions": reactions}


@app.post("/api/ollama/world-voice")
async def ollama_world_voice(payload: WorldVoicePayload) -> dict:
    st = payload.game_state
    mem = ensure_memory(st)
    reactions = deterministic_reactions(st)
    prompt = build_world_voice_prompt(st, payload.prompt)
    if not payload.use_ollama:
        return {
            "ollama_available": False,
            "model": payload.model or OLLAMA_MODEL,
            "world_voice": None,
            "prompt": prompt,
            "deterministic_reactions": reactions,
            "warning": "Ollama wurde deaktiviert; nur regelgebundene Reaktionen zurückgegeben.",
        }
    try:
        result = await ask_ollama(prompt, payload.model)
        return {
            "ollama_available": True,
            "model": result["model"],
            "world_voice": result["response"],
            "prompt": prompt,
            "deterministic_reactions": reactions,
            "world_memory": mem,
        }
    except Exception as e:
        return {
            "ollama_available": False,
            "model": payload.model or OLLAMA_MODEL,
            "world_voice": None,
            "prompt": prompt,
            "deterministic_reactions": reactions,
            "world_memory": mem,
            "warning": f"Ollama nicht erreichbar oder Modell fehlt: {e}",
        }


@app.get("/api/config")
async def config() -> dict:
    return {
        "app": "AETHORIA Companion",
        "version": "0.97",
        "canon_version": "0.96",
        "database_path": os.getenv("AETHORIA_DB_PATH", "/data/aethoria.sqlite"),
        "ollama_internal_url": os.getenv("OLLAMA_INTERNAL_URL", "http://ollama:11434"),
        "ollama_model": os.getenv("OLLAMA_MODEL", "llama3.1:8b"),
        "cors_allow_origins": os.getenv("CORS_ALLOW_ORIGINS", "*"),
        "features": {
            "games_sqlite": True,
            "campaigns": True,
            "player_name_memory": True,
        },
    }
