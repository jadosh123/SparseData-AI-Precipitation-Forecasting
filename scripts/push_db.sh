#!/bin/bash

if [ ! -d "$HOME/GoogleDrive/weather_data" ]; then
    echo "Error: Google Drive is NOT mounted."
    echo "Run: rclone mount gdrive: ~/GoogleDrive --daemon"
    exit 1
fi

# Create the backup directory if it doesn't exist
BACKUP_DIR="$HOME/GoogleDrive/weather_data/db_backups/"
mkdir -p "$BACKUP_DIR"

# Define the backup filename format
FILENAME="backup_$(date +%Y-%m-%d_%H%M).sql"
BACKUP_PATH="$BACKUP_DIR$FILENAME"

# Run the pg_dump command and pipe the output to the backup file
docker exec weather_db pg_dump -U myuser weather_db > "$BACKUP_PATH"

# Check if the dump was successful (exit code 0)
if [ $? -eq 0 ]; then
  echo "Backup successful: $FILENAME"
else
  echo "Backup failed"
fi
