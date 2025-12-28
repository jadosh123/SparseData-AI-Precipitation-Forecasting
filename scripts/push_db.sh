#!/bin/bash

# 1. Locate the Project Root & Load .env
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )"
ENV_FILE="$SCRIPT_DIR/../.env"

if [ -f "$ENV_FILE" ]; then
    export $(grep -v '^#' "$ENV_FILE" | xargs)
else
    echo "Error: .env file not found at $ENV_FILE"
    exit 1
fi

# 2. Define Backup Directory (Smart Detection)
# If running on Host (Linux/WSL), use Home. If inside Docker, use /app/cloud_data
if [ -d "/app/cloud_data" ]; then
    BASE_DIR="/app/cloud_data"
else
    BASE_DIR="$HOME/GoogleDrive/weather_data"
fi

if [ ! -d "$BASE_DIR" ]; then
    echo "Error: Google Drive path not found at $BASE_DIR"
    echo "Ensure Drive is mounted or volume is mapped."
    exit 1
fi

BACKUP_DIR="$BASE_DIR/db_backups/"
mkdir -p "$BACKUP_DIR"

# 3. Define filename
FILENAME="backup_$(date +%Y-%m-%d_%H%M).sql"
BACKUP_PATH="$BACKUP_DIR$FILENAME"

# 4. Run pg_dump using variables from .env
echo "Backing up database '$POSTGRES_DB' as user '$POSTGRES_USER'..."

# Note: We do NOT need to pipe password here if .env is loaded and pg_dump finds it,
# but usually for docker exec we rely on the container's environment or trust.
docker exec weather_db pg_dump -U "$POSTGRES_USER" -O -x "$POSTGRES_DB" > "$BACKUP_PATH"

# 5. Check result
if [ $? -eq 0 ]; then
  echo "Backup successful: $FILENAME"
else
  echo "Backup failed"
  rm -f "$BACKUP_PATH" # Delete empty file if failed
fi