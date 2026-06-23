# AI-Enhanced Rain Forecasting Model for Data-Sparse Regions

## The Problem and Motivation

Accurate and localized rain prediction is crucial for various sectors, including agriculture, urban planning, and disaster preparedness. Yet vast areas of the globe lack weather radar coverage entirely — ground-based Doppler networks are concentrated in wealthy or heavily populated countries, leaving oceans, polar regions, deserts, and much of the developing world as meteorological blind spots where forecasters rely solely on satellite estimates and numerical weather models.

Many of these regions lack the resources to deploy radar infrastructure. A basic Doppler radar system can cost between $300,000 and $500,000, with more advanced models exceeding $1 million (excluding maintenance and operational costs). In contrast, a commercial weather station costs between $2,000 and $5,000.

This project explores a cheaper, ML-based alternative grounded in the RFSI (Random Forest Spatial Interpolation) methodology, which has been shown to outperform traditional kriging for meteorological interpolation. By combining readings from a sparse network of ground stations with terrain-aware spatial interpolation and a downstream forecasting model, the system constructs a virtual forecasting radar — delivering localized precipitation nowcasts without any radar infrastructure.

## How It Works

**1. Data Collection** — Every hour, raw readings are fetched from weather stations operated by the Israel Meteorological Service (IMS) via their public API. Stations cover the Jezreel Valley and surrounding coastal reference points (Haifa, Tel Aviv).

**2. Processing** — Raw observations are cleaned and aggregated into hourly intervals, filtering out anomalies and standardizing units.

**3. Spatial Interpolation** — A XGBoost Spatial Interpolation model trained on the Random Forest Spatial Interpolation methodology estimates current weather conditions — rainfall, wind speed and direction, relative humidity, dew point — at 1,271 virtual grid cells across the valley (~0.935 km spacing). Terrain features derived from SRTM elevation data (slope, roughness, topographic position) are included for rain, wind, and humidity models.

**4. Forecasting** — A single point XGBoost forecasting model takes the interpolated grid as input and predicts rainfall at each cell across four time horizons: t+1h, t+3h, t+6h, and t+12h.

**5. Visualization** — A FastAPI web server serves an interactive Folium map showing the interpolated precipitation map and latest forecast, updated automatically each hour via a cronjob.

## Model Performance

Evaluated on a held-out virtual sensor at Afula (station 16, cell 33, 2.21 km apart).

### Spatial Interpolation (vs IDW baseline)

| Feature | RFSI MAE | IDW MAE | RFSI RMSE | IDW RMSE |
| :--- | :--- | :--- | :--- | :--- |
| rain — mm/h (global) | **0.0432** | 0.0479 | **0.3255** | 0.3596 |
| rain — mm/h (events ≥ 0.1mm) | — | — | **1.4819** | 1.5624 |
| ws — m/s | **0.7924** | 1.1119 | **1.0042** | 1.2957 |
| td — °C | 1.2967 | **1.0182** | 1.6628 | **1.4104** |
| rh — % | **4.2538** | 4.2575 | **5.6431** | 5.8825 |
| tdmax — °C | 1.1890 | **0.9822** | 1.6070 | **1.3671** |
| tdmin — °C | 1.3368 | **1.0904** | 1.8160 | **1.5004** |
| u_vec — m/s | **0.8624** | 0.9760 | **1.1308** | 1.2184 |
| v_vec — m/s | **0.7278** | 0.7655 | **0.9352** | 1.0043 |

### Rainfall Forecast (storm hours only, vs persistence baseline)

| Horizon | RMSE | Skill vs Persistence | Persistence RMSE |
|---|---|---|---|
| t+1h | 1.6370 | +10.9% | 1.8368
| t+3h | 1.7483 | +13.4% | 2.0181
| t+6h | 1.7080 | +17.6% | 2.0719
| t+12h | 1.7404 | +18.5% | 2.1344

Skill improves with longer horizons as persistence degrades faster than the model.

---

## Project Structure

```
database/               # SQLite schema
models/
├── spatial_interpolation/   # RFSI models, one per meteorological feature
└── single_point/            # XGBoost forecast models, one per horizon (t+1/3/6/12h)
src/weather_engine/     # All application logic
├── inference_pipeline.py    # Hourly cronjob — fetches, processes, interpolates, forecasts
├── cold_start/              # Static JSON files for bootstrapping the DB on first run
├── api.py                   # FastAPI backend
└── templates/               # Jinja2 HTML templates
static/                 # Images and GIFs served by the frontend
tests/                  # Deployment smoke tests
pyproject.toml          # Dependencies split into core (deployment) and dev
```

---

## Setup

### Prerequisites

**1. IMS API Key** — Register at the [Israel Meteorological Service](https://ims.gov.il) to obtain an API key for accessing station data. Set it in your `.env` file.

**2. Running in a different region?** — The system expects the following meteorological fields from your data source. Map your provider's naming convention to these:

| Field | Meaning | Unit |
|---|---|---|
| `rain` | Precipitation | mm/h |
| `ws` | Wind speed | m/s |
| `wd` | Wind direction | degrees |
| `stdwd` | Standard deviation of wind direction | degrees |
| `td` | Dew point temperature | °C |
| `rh` | Relative humidity | % |
| `tdmax` | Maximum dew point temperature | °C |
| `tdmin` | Minimum dew point temperature | °C |

Wind vector components (`u_vec`, `v_vec`) are derived from `ws` and `wd` during processing — no separate mapping needed.

**3. Retraining for a new region** — Model training and performance analysis code lives in the `training-and-analysis` branch. RFSI models are trained via `train_rfsi.py`; XGBoost forecast models are trained and evaluated via `single_point_forecast.ipynb`. Both save the final models to `models/` upon completion.

### Data requirements for training:

- Place CSV files in `data/`. Expected format (10-minute observations, aggregated to hourly by the pipeline):
  ```
  timestamp,station_id,latitude,longitude,elevation,rain,wsmax,wdmax,ws,wd,stdwd,td,rh,tdmax,tdmin,ws1mm,ws10mm
  2020-01-01T00:00:00+02:00,78,32.8466,35.1123,,0.0,1.8,77.0,1.2,86.0,8.1,9.5,96.0,9.6,9.4,1.5,1.2
  ```
- Create `data/station_metadata.json` — an array of station dicts:
  ```json
  [{ "station_id": 10, "latitude": 33.1288, "longitude": 35.8045, "elevation": 942, "dist_to_coast": 55.86 }]
  ```
- Initialize `data/weather.db` using the schema in `database/init.sql`.
- Set `UTCDIFF` in `ingest_data.py` to the UTC offset your data source uses for timestamps. IMS always sends UTC+2 regardless of the offset shown in the timestamp string, so the default is `2`.
- Place SRTM `.hgt` elevation tiles for your region in `data/elevation_data/`. Tiles can be downloaded from [NASA EarthData](https://earthdata.nasa.gov) or [OpenTopography](https://opentopography.org).
- Place a distance-to-coast NetCDF file at `data/dist_to_GSHHG_v2.3.7_1m.nc`. This file is used to compute each station's and cell's distance to the nearest coastline. The GSHHG dataset is available at [NOAA](https://www.ngdc.noaa.gov/mgg/shorelines/).

### Setting up environment

Run the following to create a virtual environment, activate it, and install all dependencies:
```bash
python -m venv .venv
source .venv/bin/activate
pip install -e .[dev]
```

If you're on the live deployment stage then run the following to get the core dependencies:
```bash
python -m venv .venv
source .venv/bin/activate
pip install -e .
```

### Training Pipeline (`training-and-analysis` branch)

Before training set the heldout station to be tested on in spatial.py via the HOLDOUT_STATION global variable.

Also in cell_generation.py define the bounding box of the area you want to work with by these global variables (currently its around Jezreel Valley):
```bash 
LAT_MAX = 32.75
LON_MAX = 35.45
LAT_MIN = 32.45
LON_MIN = 35.05
```

Once the prerequisites above are in place, activate the virtual environment and run the following steps in order:

```bash
source .venv/bin/activate

# 1. Ingest raw CSV data into weather.db
python src/weather_engine/ingest_data.py

# 2. Clean and aggregate ingested data into clean_station_data in weather.db
python src/weather_engine/clean_data.py

# 3. Compute station neighbors (needed for RFSI)
python src/weather_engine/spatial.py

# 4. Train RFSI spatial interpolation models (saves to models/spatial_interpolation/)
python src/weather_engine/train_rfsi.py

# 5. Train XGBoost forecast models and evaluate performance
#    Open and run single_point_forecast.ipynb — saves to models/single_point/

# 6. Generate virtual grid cells for the target region
python src/weather_engine/cell_generation.py

# 7. Run the full interpolation + forecast pipeline over historical data
python src/weather_engine/cell_full_pipeline.py
```

After training, copy the `models/` directory to the deployment branch.

If you want to evaluate the model's performance you can run the data_analysis_full_pipeline.ipynb notebook which will find the closest cell to the target held out station that you defined, it will fetch all the forecasts and interpolations and display error metrics for you against the ground truths of that held out station (Keep in mind any distance can inflate the error numbers a little bit).

To prepare for live deployment run ```python src/weather_engine/export_cold_start.py```
That will take all the cell neighbors data and export it to a json for a cold start in live deployment.

---

### Live Deployment (`deployment-code` branch)

**1. Copy trained models** — Copy the `models/` directory from the training branch into the deployment branch.

**2. Set up environment**

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e .
cp .env.example .env  # fill in your IMS API key and discord webhook for alerts
```

**3. Initialize the database**

```bash
sqlite3 data/weather_live.db
.read database/init.sql
.exit
mkdir -p logs data
```

**4. Build demo maps**

```bash
source .venv/bin/activate
python src/weather_engine/demo_snapshot/build_demo_map.py
```

**5. First inference run** — bootstraps static tables from the cold start JSONs and fetches initial data:

```bash
python src/weather_engine/inference_pipeline.py
```

**6. Set up the cronjob** — runs at 10 minutes past every hour:

```
15 * * * * /path/to/repo/.venv/bin/python /path/to/repo/src/weather_engine/inference_pipeline.py >> /path/to/repo/logs/inference.log 2>&1
```

**7. Start the server**

```bash
uvicorn src.weather_engine.api:app --host 0.0.0.0 --port 8000
```

---

## Scaling

The current deployment uses SQLite and a single server instance, which is appropriate for a regional system with low write frequency (one cronjob writer, read-only web traffic). SQLite handles concurrent reads well at this scale.

To scale to a larger coverage area or higher traffic:

- **Migrate to Postgres** — SQLite column types map cleanly to Postgres (`REAL` → `FLOAT`, `INTEGER` → `INTEGER`). The SQLAlchemy layer means the change is mostly a connection string swap with minor schema type adjustments.
- **Dedicated DB/worker instance** — Run Postgres and the inference cronjob on a single dedicated instance. This is the sole writer.
- **N API instances** — Deploy N read-only FastAPI instances behind a load balancer (e.g. AWS ALB), all pointing their connection strings at the DB instance. Each instance is stateless and interchangeable.

---

## Known Limitations

- Generalization of virtual sensors is validated on a single held-out location (Afula). Performance at other locations may differ.
- Wind speed (`ws`) shows a systematic positive bias at Afula due to local orographic channeling — a site-specific effect not representative of the full grid.
- Temperature features show a ~+1°C positive bias at the evaluated cell, likely due to local valley microclimate effects.
- RFSI underperforms IDW on temperature features (td, tdmax, tdmin) by a small margin. A hybrid approach was not pursued to keep the pipeline uniform.
- IMS API observations lag ~10–20 minutes behind real time — effective forecast horizons are very close to but not exactly t+1/3/6/12h.
- Main bottleneck of the system is the time it takes to fetch the data from the IMS for all stations used in the grid (19 stations currently), with a properly integrated system with full access to the databases they use it would reduce the whole time by around 3-4 minutes. Also current interpolation and forecasting is embarrassingly parallel so in the case of deploying this system over a large area/country the code can easily be changed to use multithreading so each thread handles its own cell.

