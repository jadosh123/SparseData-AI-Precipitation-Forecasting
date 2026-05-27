from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

from fastapi.templating import Jinja2Templates
from weather_engine.folium_map import build_forecast_map
from weather_engine.cache import get_forecast_rows
from weather_engine.utils import get_project_root

ROOT = get_project_root()
LIVE_MAPS_DIR = ROOT / "data" / "live_maps"
DEMO_MAPS_DIR = ROOT / "data" / "demo_maps"
HORIZONS = ["precipitation_t1", "precipitation_t3", "precipitation_t6", "precipitation_t12"]
HORIZON_LABELS = {
    "precipitation_t1": "t+1h",
    "precipitation_t3": "t+3h",
    "precipitation_t6": "t+6h",
    "precipitation_t12": "t+12h",
}

templates = Jinja2Templates(directory=Path(__file__).parent / "templates")


def to_israel_time(ts: str) -> str:
    dt = datetime.fromisoformat(ts).replace(tzinfo=timezone.utc)
    return dt.astimezone(ZoneInfo("Asia/Jerusalem")).strftime("%Y-%m-%d %H:%M")


def render_map_section(map_html: str, horizon: str, timestamp: str, mode: str = "live", idx: int = 0) -> str:
    return templates.get_template("map_section.html").render(
        map_html=map_html,
        horizon=horizon,
        timestamp=to_israel_time(timestamp),
        mode=mode,
        horizons=HORIZON_LABELS,
        idx=idx,
    )


def build_and_cache_live_maps() -> None:
    """Build all horizon maps from current forecasts and save to disk. Called by inference pipeline."""
    LIVE_MAPS_DIR.mkdir(parents=True, exist_ok=True)
    rows = get_forecast_rows()
    if not rows:
        return
    ts = rows[0]["timestamp"]
    for horizon in HORIZONS:
        fol_map = build_forecast_map(rows, horizon=horizon)
        html = render_map_section(fol_map._repr_html_(), horizon, ts, mode="live")
        (LIVE_MAPS_DIR / f"{horizon}.html").write_text(html)
