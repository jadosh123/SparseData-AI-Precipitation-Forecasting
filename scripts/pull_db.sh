#!/bin/bash

# Locate the Project Root dynamically
# Get the directory where this script is actually saved (e.g., .../Clean-Project/scripts)
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )"
# The root is one level up from the scripts folder
PROJECT_ROOT="$SCRIPT_DIR/.."
DEST_DB="$PROJECT_ROOT/data/weather.db"
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
LATEST_BACKUP=$(ls -t "$BACKUP_DIR"/*.db 2>/dev/null | head -n 1)

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

# Execute Restore (File Copy)
echo "Overwriting local database at $DEST_DB..."

if [ -f "$DEST_DB" ]; then
    # Optional: Safety backup of the current state before overwriting
    cp "$DEST_DB" "${DEST_DB}.pre_restore"
    
    # Clean up old WAL/SHM files to prevent corruption warnings upon restart
    rm -f "$DEST_DB-wal" "$DEST_DB-shm"
fi

# The actual restore
cp "$LATEST_BACKUP" "$DEST_DB"

# Check result of the copy command
if [ $? -eq 0 ]; then
    echo "Restore successful! (Previous state saved as .pre_restore)"
    
    # Touch the file to ensure Docker picks up the change timestamp
    touch "$DEST_DB"
else
    echo "Restore failed."
    exit 1
fi
