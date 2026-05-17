from pathlib import Path
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from weather_engine.database import SessionLocal
from weather_engine.folium_map import build_forecast_map
from sqlalchemy import text
import json
from weather_engine.utils import get_project_root

# Local Cache
_cached_rows = None
_cached_demo_rows = None
_timestamps = None
_timestamp_idx = 0
ROOT = get_project_root()


def get_timestamps():
    global _timestamps
    if _timestamps is None:
        _timestamps = sorted(set(r["timestamp"] for r in get_demo_rows()))
    return _timestamps


def get_forecast_rows():
    query = """
    SELECT cf.*, cn.lat, cn.lon
    FROM cell_forecasts cf
    JOIN cell_neighbors cn ON cf.cell_id = cn.cell_id
    """

    global _cached_rows
    if _cached_rows is None:
        with SessionLocal() as db:
            _cached_rows = [dict(row._mapping) for row in db.execute(text(query)).fetchall()]
    return _cached_rows


def get_demo_rows():
    global _cached_demo_rows
        
    if _cached_demo_rows is None:
        demo_path = ROOT / "src" / "weather_engine" / "demo_snapshot" / "demo_snapshot.json"
        with open(demo_path, "r") as f:
            _cached_demo_rows = json.load(f)
    
    return _cached_demo_rows
    

app = FastAPI()
templates = Jinja2Templates(directory=Path(__file__).parent / "templates")


@app.get("/", response_class=HTMLResponse)
def index(request: Request):
    return templates.TemplateResponse(request=request, name="index.html")


@app.get("/map", response_class=HTMLResponse)
def get_map(horizon: str = 'precipitation_t1'):
    rows = get_forecast_rows()
    fol_map = build_forecast_map(rows, horizon=horizon)
    return HTMLResponse(content=_map_section_html(fol_map._repr_html_(), horizon, mode="live"))


def _map_section_html(map_html: str, horizon: str, mode: str = "live") -> str:
    btn_cls = "px-4 py-2 bg-sky-200 text-black rounded shadow hover:bg-gray-600"
    small_btn_cls = "px-3 py-2 bg-sky-200 text-black rounded shadow hover:bg-gray-600 text-sm"

    if mode == "demo":
        left_right = f"""
          <div class="flex gap-1">
            <button class="{btn_cls}" hx-get="/demo?direction=left&horizon={horizon}" hx-target="#map-section">←</button>
            <button class="{btn_cls}" hx-get="/demo?direction=right&horizon={horizon}" hx-target="#map-section">→</button>
          </div>"""
        toggle = f'<button class="{small_btn_cls}" hx-get="/map?horizon={horizon}" hx-target="#map-section">→ Live</button>'
    else:
        left_right = '<div class="w-16"></div>'
        toggle = f'<button class="{small_btn_cls}" hx-get="/demo" hx-target="#map-section">→ Demo</button>'

    horizons = [("precipitation_t1", "t+1h"), ("precipitation_t3", "t+3h"), ("precipitation_t6", "t+6h"), ("precipitation_t12", "t+12h")]
    endpoint = "/demo" if mode == "demo" else "/map"
    horizon_btns = " ".join(
        f'<button class="{btn_cls}" hx-get="{endpoint}?horizon={h}" hx-target="#map-section">{label}</button>'
        for h, label in horizons
    )

    return f"""
    <div id="map-section" class="mx-auto max-w-5xl">
      <div class="flex items-center justify-between mb-1 px-1">
        {left_right}
        <div class="flex gap-2">{horizon_btns}</div>
        {toggle}
      </div>
      {map_html}
    </div>"""


@app.get("/demo", response_class=HTMLResponse)
def get_demo_map(direction: str | None = None, horizon: str = 'precipitation_t1'):
    global _timestamp_idx
    timestamps = get_timestamps()

    if direction == "left":
        _timestamp_idx = max(0, _timestamp_idx - 1)
    elif direction == "right":
        _timestamp_idx = min(len(timestamps) - 1, _timestamp_idx + 1)

    current_ts = timestamps[_timestamp_idx]
    rows = [r for r in get_demo_rows() if r["timestamp"] == current_ts]
    fol_map = build_forecast_map(rows, horizon=horizon)
    return HTMLResponse(content=_map_section_html(fol_map._repr_html_(), horizon, mode="demo"))
    