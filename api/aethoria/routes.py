from __future__ import annotations
from typing import Any
import os

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from .canon import game_data, cards_data, initial_state, validate_canon_consistency
from .storage import list_games, get_game, put_game
from .world_memory import ensure_memory, summarize_round, deterministic_reactions, build_world_voice_prompt
from .ollama import ask_ollama, health as ollama_health, OLLAMA_MODEL


class StatePayload(BaseModel):
    state: dict[str, Any]


class WorldVoicePayload(BaseModel):
    game_state: dict[str, Any]
    prompt: str | None = None
    model: str | None = None
    use_ollama: bool = True


app = FastAPI(title="AETHORIA Companion Backend", version="0.96.0")

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
        "version": "0.96",
        "backend": "FastAPI",
        "canon_consistent": not problems,
        "canon_problems": problems,
        "ollama_available": ollama_ok,
        "ollama_model": OLLAMA_MODEL,
        "ollama_error": ollama_error,
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
        "version": "0.96",
        "database_path": os.getenv("AETHORIA_DB_PATH", "/data/aethoria.sqlite"),
        "ollama_internal_url": os.getenv("OLLAMA_INTERNAL_URL", "http://ollama:11434"),
        "ollama_model": os.getenv("OLLAMA_MODEL", "llama3.1:8b"),
        "cors_allow_origins": os.getenv("CORS_ALLOW_ORIGINS", "*"),
    }
