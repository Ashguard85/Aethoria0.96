# Portainer Deployment

## Empfohlene Variante

Für vorhandenes Ollama auf dem Host oder im LAN:

```text
docker-compose.yml
```

## Wichtige Environment-Variablen

```env
FRONTEND_BIND_IP=0.0.0.0
FRONTEND_PORT=3450
API_BIND_IP=0.0.0.0
API_PORT=3451
AETHORIA_DATA_DIR=/srv/docker/aethoria/data
AETHORIA_DB_FILE=aethoria.sqlite
OLLAMA_INTERNAL_URL=http://host.docker.internal:11434
OLLAMA_MODEL=llama3.1:8b
CORS_ALLOW_ORIGINS=*
```

Für Zugriff von anderen Geräten im Netzwerk öffnest du im Browser:

```text
http://<SERVER-IP>:3450
```

API-Test:

```text
http://<SERVER-IP>:3451/api/health
```

## Host-Ollama erreichbar machen

Wenn Ollama direkt auf dem Docker-Host läuft und der Container es nicht erreicht, prüfe auf dem Host:

```bash
curl http://localhost:11434/api/tags
```

Bei Linux-Hosts setzt das Compose `host.docker.internal` über `host-gateway`.

Falls Ollama nur auf Loopback lauscht und Docker trotzdem nicht verbinden kann, kann ein systemd Override nötig sein:

```ini
[Service]
Environment="OLLAMA_HOST=0.0.0.0:11434"
```

Danach:

```bash
sudo systemctl daemon-reload
sudo systemctl restart ollama
```

## Persistenz

SQLite wird im Container unter `/data/aethoria.sqlite` geschrieben. Auf dem Host liegt die Datei dort, wo `AETHORIA_DATA_DIR` hinzeigt.
