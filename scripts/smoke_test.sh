#!/usr/bin/env sh
set -eu
FRONTEND_URL="${FRONTEND_URL:-http://localhost:${FRONTEND_PORT:-3450}}"
API_URL="${API_URL:-http://localhost:${API_PORT:-3451}/api/health}"
echo "Frontend: $FRONTEND_URL"
wget -qO- "$FRONTEND_URL" >/dev/null && echo "Frontend OK"
echo "API: $API_URL"
wget -qO- "$API_URL" && echo "\nAPI OK"
