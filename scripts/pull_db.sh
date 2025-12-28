#!/bin/bash

# Locate the Project Root dynamically
# Get the directory where this script is actually saved (e.g., .../Clean-Project/scripts)
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )"
# The root is one level up from the scripts folder
PROJECT_ROOT="$SCRIPT_DIR/.."
ENV_FILE="$PROJECT_ROOT/.env"

if [ -f "$ENV_FILE" ]; then
    export $(grep -v '^#' "$ENV_FILE" | xargs)
else
    echo "Error: .env file not found at $ENV_FILE"
    exit 1
fi

# Define where to look for backups
if [ -d "$HOME/GoogleDrive/weather_data" ]; then
    BASE_DIR="$HOME/GoogleDrive/weather_data"
elif [ -d "/app/cloud_data" ]; then
    echo "Environment detected: Docker Container"
    BASE_DIR="/app/cloud_data"
else
    echo "Error: Base directory not found."
    exit 1
fi

BACKUP_DIR="$BASE_DIR/db_backups"

# Find the LATEST backup file
LATEST_BACKUP=$(ls -t "$BACKUP_DIR"/*.sql 2>/dev/null | head -n 1)

if [ -z "$LATEST_BACKUP" ]; then
    echo "No backup files found in $BACKUP_DIR"
    exit 1
fi

echo "Found latest backup: $LATEST_BACKUP"
echo "WARNING: This will WIPE the database '$POSTGRES_DB' and replace it with this backup."
read -p "Are you sure? (y/n) " -n 1 -r
echo
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo "Cancelled."
    exit 1
fi

# Kill active connections if app is running
echo "Terminating active connections..."
docker exec weather_db psql -U "$POSTGRES_USER" -d postgres -c "SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname = '$POSTGRES_DB' AND pid <> pg_backend_pid();" > /dev/null 2>&1

# Execute Restore
echo "Wiping old database..."
docker exec weather_db psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -c "DROP SCHEMA public CASCADE; CREATE SCHEMA public;"

echo "Restoring database..."
cat "$LATEST_BACKUP" | docker exec -i weather_db psql -U "$POSTGRES_USER" "$POSTGRES_DB"

if [ $? -eq 0 ]; then
    echo "Restore successful!"
else
    echo "Restore failed."
fi