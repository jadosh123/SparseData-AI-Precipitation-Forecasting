from datetime import datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

from fastapi.templating import Jinja2Templates
from weather_engine.folium_map import build_forecast_map
from weather_engine.cache import get_forecast_rows, get_now_rows
from weather_engine.utils import get_project_root

ROOT = get_project_root()
LIVE_MAPS_DIR = ROOT / "data" / "live_maps"
DEMO_MAPS_DIR = ROOT / "data" / "demo_maps"
HORIZONS = ["precipitation_t1", "precipitation_t3", "precipitation_t6", "precipitation_t12"]
HORIZON_LABELS = {
    "precipitation_t1":  ("t+1h",  1),
    "precipitation_t3":  ("t+3h",  3),
    "precipitation_t6":  ("t+6h",  6),
    "precipitation_t12": ("t+12h", 12),
}

templates = Jinja2Templates(directory=Path(__file__).parent / "templates")


IL = ZoneInfo("Asia/Jerusalem")


def to_israel_time(ts: str) -> dict:
    dt = datetime.fromisoformat(ts).replace(tzinfo=timezone.utc).astimezone(IL)
    return {"full": dt.strftime("%Y-%m-%d %H:%M"), "short": dt.strftime("%H:%M")}


def _horizon_times(base_ts: str) -> dict[str, dict]:
    """For each horizon return its label and formatted target time (with day abbr if crossing midnight)."""
    base = datetime.fromisoformat(base_ts).replace(tzinfo=timezone.utc).astimezone(IL)
    result = {"now": {"label": "Now", "time": base.strftime("%H:%M"), "day": base.strftime("%a")}}
    for key, (label, hours) in HORIZON_LABELS.items():
        target = base + timedelta(hours=hours)
        result[key] = {"label": label, "time": target.strftime("%H:%M"), "day": target.strftime("%a")}
    return result


def render_map_section(map_html: str, horizon: str, timestamp: str, mode: str = "live", idx: int = 0) -> str:
    return templates.get_template("map_section.html").render(
        map_html=map_html,
        horizon=horizon,
        timestamp=to_israel_time(timestamp),
        mode=mode,
        horizons=_horizon_times(timestamp),
        idx=idx,
    )


def build_and_cache_live_maps() -> None:
    """Build all horizon maps from current forecasts and save to disk. Called by inference pipeline."""
    LIVE_MAPS_DIR.mkdir(parents=True, exist_ok=True)
    rows = get_forecast_rows()
    if not rows:
        return
    for horizon in HORIZONS:
        fol_map = build_forecast_map(rows, horizon=horizon)
        (LIVE_MAPS_DIR / f"{horizon}.html").write_text(fol_map._repr_html_())

    now_rows = get_now_rows()
    if now_rows:
        fol_map = build_forecast_map(now_rows, horizon="rain")
        (LIVE_MAPS_DIR / "now.html").write_text(fol_map._repr_html_())
