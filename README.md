# AETHORIA Companion v0.96

Git- und Portainer-taugliches Repository für die AETHORIA Companion App.

Enthalten:

- dunkles Companion-Frontend
- FastAPI-Backend
- SQLite-Persistenz
- kanonische v0.96-Spieldaten
- 18 Geheimziele und 60 Karten
- Weltgedächtnis
- regelgebundene Weltreaktionen
- Ollama-Anbindung als optionale Weltstimme

## Ports

Standardwerte im Repo:

- Frontend/App: `3450`
- API: `3451`
- Ollama extern: `11434`

Die Werte stehen in `.env.example` und können in Portainer als Stack-Environment überschrieben werden.

## Lokaler Test

```bash
cp .env.example .env
docker compose up --build
```

Dann öffnen:

```text
http://localhost:3450
```

API-Test:

```text
http://localhost:3451/api/health
```

## Portainer aus Git

1. Repository in Git hochladen.
2. Portainer öffnen.
3. **Stacks → Add stack → Repository** wählen.
4. Repository-URL eintragen.
5. Compose path setzen:

```text
docker-compose.yml
```

6. Environment-Variablen aus `.env.portainer.example` in Portainer übernehmen und anpassen.

## Externes Ollama

Dieses Repo geht standardmäßig davon aus, dass Ollama außerhalb des Stacks läuft, zum Beispiel direkt auf dem Host.

Standard:

```env
OLLAMA_INTERNAL_URL=http://host.docker.internal:11434
```

Wenn Ollama auf einem anderen System läuft, setze in Portainer:

```env
OLLAMA_INTERNAL_URL=http://<OLLAMA-HOST>:11434
```

## Dockerisiertes Ollama

Optional liegt unter `deploy/docker-compose.with-ollama.yml` eine Variante mit eigenem Ollama-Container.

## Nicht ins Git committen

Nicht committen:

- `.env`
- SQLite-Dateien
- Runtime-Daten
- Ollama-Modellordner
- Backups
- lokale Logs

Das ist in `.gitignore` bereits vorbereitet.


## Hinweis: Server-Speichern statt JSON

Diese Korrektur macht die sichtbaren Spielstand-Buttons serverbasiert:

- **Server speichern** schreibt den aktuellen Zustand nach SQLite unter `AETHORIA_DB_PATH` (`/data/aethoria.sqlite`).
- **Server laden** listet vorhandene Spielstände über `/api/games` und lädt einen gewählten Spielstand.
- **JSON importieren/exportieren** bleibt nur als manuelles Backup erhalten.

Die Backend-Endpunkte sind:

- `GET /api/games`
- `GET /api/games/{game_id}`
- `PUT /api/games/{game_id}`
- `GET /api/config`
