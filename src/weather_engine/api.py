from pathlib import Path
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from weather_engine.database import SessionLocal
from sqlalchemy import text

app = FastAPI()
templates = Jinja2Templates(directory=Path(__file__).parent / "templates")

@app.get("/", response_class=HTMLResponse)
def index(request: Request):
    return templates.TemplateResponse(request=request, name="index.html")

@app.get("/predict", response_class=HTMLResponse)
def predict(request: Request):
    query = """
    SELECT cf.*, cn.lat, cn.lon
    FROM cell_forecasts cf
    JOIN cell_neighbors cn ON cf.cell_id = cn.cell_id
    """
    with SessionLocal() as db:
        rows = [dict(row._mapping) for row in db.execute(text(query)).fetchall()]
    return templates.TemplateResponse(request=request, name="predict.html", context={"rows": rows})
