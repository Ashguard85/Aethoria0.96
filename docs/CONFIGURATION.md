# Konfiguration

| Variable | Zweck | Standard |
|---|---|---|
| `FRONTEND_PORT` | öffentlicher App-Port | `3450` |
| `API_PORT` | öffentlicher API-Port | `3451` |
| `FRONTEND_BIND_IP` | Host-Bind-IP Frontend | `0.0.0.0` |
| `API_BIND_IP` | Host-Bind-IP API | `0.0.0.0` |
| `AETHORIA_DATA_DIR` | Hostpfad für SQLite | `./runtime/aethoria-data` |
| `AETHORIA_DB_FILE` | SQLite-Dateiname | `aethoria.sqlite` |
| `OLLAMA_INTERNAL_URL` | URL, die der API-Container für Ollama nutzt | `http://host.docker.internal:11434` |
| `OLLAMA_MODEL` | Ollama-Modell | `llama3.1:8b` |
| `CORS_ALLOW_ORIGINS` | erlaubte Browser-Origins | `*` |

Für produktivere Nutzung kannst du `CORS_ALLOW_ORIGINS` später auf deine App-URL einschränken.
