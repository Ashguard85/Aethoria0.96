#!/usr/bin/env sh
set -eu
MODEL="${OLLAMA_MODEL:-llama3.1:8b}"
# In Portainer: exec in den Ollama-Container oder lokal: docker compose exec ollama ...
ollama pull "$MODEL"
