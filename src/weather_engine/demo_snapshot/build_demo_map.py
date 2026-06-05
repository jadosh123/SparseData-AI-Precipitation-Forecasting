"""
Pre-builds all demo map HTML files (one per timestamp × horizon) from demo_snapshot.json.
Run this once after regenerating demo_snapshot.json.
Output: data/demo_maps/{timestamp_idx}_{horizon}.html
"""

import json
from weather_engine.utils import get_project_root
from weather_engine.folium_map import build_forecast_map

ROOT = get_project_root()
DEMO_MAPS_DIR = ROOT / "data" / "demo_maps"
HORIZONS = ["precipitation_t1", "precipitation_t3", "precipitation_t6", "precipitation_t12"]


def build_and_cache_demo_maps() -> None:
    demo_path = ROOT / "src" / "weather_engine" / "demo_snapshot" / "demo_snapshot.json"
    with open(demo_path) as f:
        rows = json.load(f)

    timestamps = sorted(set(r["timestamp"] for r in rows))
    DEMO_MAPS_DIR.mkdir(parents=True, exist_ok=True)

    print(f"Building {len(timestamps)} timestamps × {len(HORIZONS)} horizons = {len(timestamps) * len(HORIZONS)} maps...")
    for idx, ts in enumerate(timestamps):
        ts_rows = [r for r in rows if r["timestamp"] == ts]
        for horizon in HORIZONS:
            fol_map = build_forecast_map(ts_rows, horizon=horizon)
            path = DEMO_MAPS_DIR / f"{idx}_{horizon}.html"
            path.write_text(fol_map._repr_html_())
        print(f"  [{idx + 1}/{len(timestamps)}] {ts}")

    print(f"Done. Maps written to {DEMO_MAPS_DIR}")


if __name__ == "__main__":
    build_and_cache_demo_maps()
