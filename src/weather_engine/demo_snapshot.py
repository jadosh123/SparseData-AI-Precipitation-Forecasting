import json
from pathlib import Path
from weather_engine.utils import get_project_root
from sqlalchemy import create_engine, text

engine = create_engine(f"sqlite:///{get_project_root()}/data/weather.db")

ROOT = get_project_root()

query = """
SELECT cf.cell_id, cf.timestamp, cf.precipitation_t1, cf.precipitation_t3, cf.precipitation_t6, cf.precipitation_t12,
       cn.lat, cn.lon
FROM cell_forecasts cf
JOIN cell_neighbors cn ON cf.cell_id = cn.cell_id
WHERE cf.timestamp >= '2024-12-27 05:00:00' AND cf.timestamp <= '2024-12-27 23:00:00'
"""

with engine.connect() as conn:
    rows = [dict(r._mapping) for r in conn.execute(text(query)).fetchall()]

out_path = ROOT / "src" / "weather_engine" / "demo_snapshot" / "demo_snapshot.json"
with open(out_path, "w") as f:
    json.dump(rows, f, indent=2)

print(f"Wrote {len(rows)} rows to {out_path}")
