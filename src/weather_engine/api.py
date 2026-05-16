from pathlib import Path
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from weather_engine.database import SessionLocal
from weather_engine.folium_map import build_forecast_map
from sqlalchemy import text

_cached_rows = None

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
        

app = FastAPI()
templates = Jinja2Templates(directory=Path(__file__).parent / "templates")

@app.get("/", response_class=HTMLResponse)
def index(request: Request):
    return templates.TemplateResponse(request=request, name="index.html")

@app.get("/map", response_class=HTMLResponse)
def get_map(horizon: str = 'precipitation_t1'):
    rows = get_forecast_rows()
    fol_map = build_forecast_map(rows, horizon=horizon)
    html_map = fol_map._repr_html_()
    return HTMLResponse(content=html_map)
