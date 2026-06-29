from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from weather_engine.cache import get_demo_rows, get_forecast_rows, get_forecast_timestamp, get_now_rows, get_now_timestamp, get_timestamps
from weather_engine.map_builder import (
    DEMO_MAPS_DIR,
    LIVE_MAPS_DIR,
    render_map_section,
)
from weather_engine.folium_map import build_forecast_map
from weather_engine.utils import get_project_root

ROOT = get_project_root()

app = FastAPI()
app.mount("/static", StaticFiles(directory=ROOT / "static"))
templates = Jinja2Templates(directory=Path(__file__).parent / "templates")


@app.get("/", response_class=HTMLResponse)
def index(request: Request):
    return templates.TemplateResponse(request=request, name="index.html")


@app.get("/about", response_class=HTMLResponse)
def about(request: Request):
    return templates.TemplateResponse(request=request, name="about.html")


@app.get("/map", response_class=HTMLResponse)
def get_map(horizon: str = "precipitation_t1"):
    path = LIVE_MAPS_DIR / f"{horizon}.html"
    if path.exists():
        ts = get_now_timestamp() if horizon == "now" else get_forecast_timestamp()
        if ts:
            return HTMLResponse(content=render_map_section(path.read_text(), horizon, ts, mode="live"))
    if horizon == "now":
        rows = get_now_rows()
        fol_map = build_forecast_map(rows, horizon="rain")
        ts = rows[0]["timestamp"]
    else:
        rows = get_forecast_rows()
        fol_map = build_forecast_map(rows, horizon=horizon)
        ts = rows[0]["timestamp"]
    return HTMLResponse(content=render_map_section(fol_map._repr_html_(), horizon, ts, mode="live"))


@app.get("/demo", response_class=HTMLResponse)
def get_demo_map(direction: str | None = None, horizon: str = "precipitation_t1", idx: int = 0):
    timestamps = get_timestamps()

    if direction == "left":
        idx = max(0, idx - 1)
    elif direction == "right":
        idx = min(len(timestamps) - 1, idx + 1)

    current_ts = timestamps[idx]

    cached_path = DEMO_MAPS_DIR / f"{idx}_{horizon}.html"
    if cached_path.exists():
        map_html = cached_path.read_text()
    else:
        rows = [r for r in get_demo_rows() if r["timestamp"] == current_ts]
        map_html = build_forecast_map(rows, horizon=horizon)._repr_html_()
        DEMO_MAPS_DIR.mkdir(parents=True, exist_ok=True)
        cached_path.write_text(map_html)

    return HTMLResponse(content=render_map_section(map_html, horizon, current_ts, idx=idx, mode="demo"))
