import json
from weather_engine.database import SessionLocal
from weather_engine.utils import get_project_root
from sqlalchemy import text

ROOT = get_project_root()

_cached_demo_rows = None
_timestamps = None


def get_now_rows() -> list[dict]:
    query = """
    SELECT ci.cell_id, ci.timestamp, ci.rain, cn.lat, cn.lon
    FROM cell_interpolated ci
    JOIN cell_neighbors cn ON ci.cell_id = cn.cell_id
    WHERE ci.timestamp = (SELECT MAX(timestamp) FROM cell_interpolated)
    """
    with SessionLocal() as db:
        return [dict(row._mapping) for row in db.execute(text(query)).fetchall()]


def get_forecast_rows() -> list[dict]:
    query = """
    SELECT cf.*, cn.lat, cn.lon
    FROM cell_forecasts cf
    JOIN cell_neighbors cn ON cf.cell_id = cn.cell_id
    """
    with SessionLocal() as db:
        return [dict(row._mapping) for row in db.execute(text(query)).fetchall()]


def get_demo_rows() -> list[dict]:
    global _cached_demo_rows
    if _cached_demo_rows is None:
        demo_path = ROOT / "src" / "weather_engine" / "demo_snapshot" / "demo_snapshot.json"
        with open(demo_path, "r") as f:
            _cached_demo_rows = json.load(f)
    return _cached_demo_rows


def get_timestamps() -> list[str]:
    global _timestamps
    if _timestamps is None:
        _timestamps = sorted(set(r["timestamp"] for r in get_demo_rows()))
    return _timestamps
