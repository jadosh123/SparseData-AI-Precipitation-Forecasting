from fastapi import FastAPI
from weather_engine.database import SessionLocal
from sqlalchemy import text


class CellForecast():
    cell_id: int
    lat: float
    lon: float
    precipitation_t1: float
    precipitation_t3: float
    precipitation_t6: float
    precipitation_t12: float


app = FastAPI()

@app.get("/predict")
def predict():
    query = """
    SELECT cf.*, cn.lat, cn.lon
    FROM cell_forecasts cf
    JOIN cell_neighbors cn ON cf.cell_id = cn.cell_id
    """
    
    with SessionLocal() as db:
        rows = db.execute(text(query)).fetchall()
        return [dict(row._mapping) for row in rows]
    
    
