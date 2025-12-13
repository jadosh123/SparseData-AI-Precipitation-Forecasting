# Daily Developer Workflow

**Project:** SparseData-AI-Precipitation-Forecasting

This guide explains how to start the environment after a restart, how to develop, and how to sync database changes between your Laptop (Development) and Desktop (Training).

---

## 🟢 1. START OF DAY (Boot Sequence)

_Perform these steps every time you restart your laptop._

### Step A: Connect the Cloud Drive

Your database backups live in Google Drive. You must mount the drive before starting Docker.
_(Skip this if you added it to Startup Applications)._

```bash
rclone mount gdrive: ~/GoogleDrive --daemon
```

Check: Run ls ~/GoogleDrive/weather_data. If you see your files, it works.
Step B: Start the Virtual Lab (Docker)

Start your Database and Python environment.

```bash
cd ~/repo/SparseData-AI-Precipitation-Forecasting
docker compose up -d
```

## 💻 2. DEVELOPMENT LOOP

Running Python Scripts

Do not run python src/script.py directly. You must run it inside the container.

```bash
# Syntax: docker compose run --rm app python [PATH_TO_SCRIPT]
docker compose run --rm app python src/ingest_data.py
```

checking the Database

To run SQL queries or check your data:

```bash
# Syntax: docker compose exec db psql -U myuser -d weather_db -c "[QUERY]"
docker compose exec db psql -U myuser -d weather_db -c "SELECT count(*) FROM raw_station_data;"
```

Adding New Python Libraries

If you need a new package (e.g., scikit-learn):

- Add the library name to requirements.txt.
- Rebuild the container:

```bash
docker compose up -d --build
```

## 💾 3. END OF DAY (Save & Sync)

How to ensure your work is saved and ready for the Desktop.

A. Syncing Code (Git)

Saves your scripts (.py), notebooks, and config changes.

```bash
git add .
git commit -m "Finished data cleaning logic"
git push origin main
```

B. Syncing Data (Database State)

Crucial: This saves the actual data rows (the weather observations) to the Cloud so your Desktop can see them.

```bash
# Run the backup script we created
bash scripts/push_db.sh
```

Result: A new .sql file (e.g., backup_2025-11-19_1800.sql) appears in your Google Drive.

## 🖥️ 4. SWITCHING TO DESKTOP

How to pick up where you left off on the powerful machine.

- Turn on Desktop.

- Pull Code:

```bash
cd ~/Projects/SparseData...
git pull origin main
```

Load Database: Run the restore script to wipe the desktop DB and load the fresh data from the laptop.

```bash
bash scripts/pull_db.sh
```

Start Training: Now your Desktop has the exact same code and exact same data as your Laptop.

## ⚠️ Troubleshooting

Error: docker: Error response from daemon: ... source path does not exist

- Cause: You forgot to run the rclone mount command (Step 1A) before starting Docker.

- Fix: Run the mount command, then run docker compose up -d again.

Error: psql: FATAL: database "weather_db" does not exist

- Cause: Docker isn't running.

- Fix: Run docker compose up -d.

## Mounting google drive on desktop to pull changes

```bash
sudo mount -t drvfs G: /mnt/g
ls -l "/mnt/g/My Drive"
cd ~
ln -s "/mnt/g/My Drive" ~/GoogleDrive
```

## Shutting down docker

```bash
docker compose down  # Deletes containers but not data
docker compose down -v # Deletes containers and data
```
