import json
import pandas as pd
from weather_engine.database import engine
from weather_engine.utils import get_project_root

COLD_START_DIR = get_project_root() / "src" / "weather_engine" / "cold_start"
COLD_START_DIR.mkdir(parents=True, exist_ok=True)

cell_neighbors = pd.read_sql("SELECT * FROM cell_neighbors", engine).to_dict(orient="records")
station_metadata = pd.read_sql("SELECT * FROM station_metadata", engine).to_dict(orient="records")

with open(COLD_START_DIR / "cell_neighbors.json", "w") as f:
    json.dump(cell_neighbors, f, indent=2)

with open(COLD_START_DIR / "station_metadata.json", "w") as f:
    json.dump(station_metadata, f, indent=2)

print(f"Exported {len(cell_neighbors)} cell neighbors and {len(station_metadata)} station metadata records.")
