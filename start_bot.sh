#!/usr/bin/env bash
# Set up the local environment and start the RentSpot bot.
set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV_DIR="$PROJECT_DIR/venv"
LOG_DIR="$PROJECT_DIR/logs"
ENV_FILE="$PROJECT_DIR/.env"

cd "$PROJECT_DIR"

if [[ ! -f "$ENV_FILE" ]]; then
    echo "Error: .env file not found. Add RENTBOT_TOKEN, API_ID, and API_HASH before starting the bot." >&2
    exit 1
fi

for variable in RENTBOT_TOKEN API_ID API_HASH; do
    if ! grep -Eq "^[[:space:]]*(export[[:space:]]+)?${variable}[[:space:]]*=[[:space:]]*[^[:space:]#]" "$ENV_FILE"; then
        echo "Error: $variable is missing or empty in .env." >&2
        exit 1
    fi
done

if [[ ! -d "$VENV_DIR" ]]; then
    python3 -m venv "$VENV_DIR"
fi

# asyncio is part of Python's standard library and must not be installed from PyPI.
"$VENV_DIR/bin/python" -m pip install --upgrade pip
sed -E '/^[[:space:]]*asyncio([[:space:]]|$)/d' requirements.txt | \
    "$VENV_DIR/bin/python" -m pip install -r /dev/stdin

mkdir -p "$LOG_DIR"
echo "Starting bot; output is appended to logs/bot.log"
exec "$VENV_DIR/bin/python" bot_core.py >> "$LOG_DIR/bot.log" 2>&1
