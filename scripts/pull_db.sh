#!/bin/bash

# 1. Define where to look
BACKUP_DIR="$HOME/GoogleDrive/weather_data/db_backups"

# 2. Find the LATEST backup file (sort by time, pick top one)
LATEST_BACKUP=$(ls -t "$BACKUP_DIR"/*.sql 2>/dev/null | head -n 1)

# Check if a file was found
if [ -z "$LATEST_BACKUP" ]; then
    echo "No backup files found in $BACKUP_DIR"
    exit 1
fi

echo "Found latest backup: $LATEST_BACKUP"
echo "WARNING: This will WIPE the current 'weather_db' and replace it with this backup."
read -p "Are you sure? (y/n) " -n 1 -r
echo    # (optional) move to a new line
if [[ ! $REPLY =~ ^[Yy]$ ]]
then
    echo "Cancelled."
    exit 1
fi

echo "Wiping old database..."
docker exec weather_db psql -U myuser -d weather_db -c "DROP SCHEMA public CASCADE; CREATE SCHEMA public;"

# 3. Restore the database
# We use 'docker exec -i' (Interactive) to accept the piped file
echo "Restoring database..."
cat "$LATEST_BACKUP" | docker exec -i weather_db psql -U myuser weather_db

# 4. Check result
if [ $? -eq 0 ]; then
    echo "Restore successful!"
else
    echo "Restore failed."
fi