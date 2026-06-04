# AI-Enhanced Rain Forecasting Model for Data-Sparse Regions

## The Problem and Motivation

Accurate and localized rain prediction is crucial for various sectors, including agriculture, urban planning, and disaster preparedness. Many developing countries and hard-to-reach areas worldwide lack the resources to implement radar systems for granular and precise weather forecasts. A basic Doppler radar system can cost between $300,000 and $500,000, with more advanced models costing $1 million or more (excluding maintenance and operational costs). In contrast, a basic commercial weather system costs between $2,000 and $5,000+ for advanced models. Therefore, this project aims to develop and explore a much cheaper and more accessible solution by leveraging artificial intelligence, spatial interpolation, and data from commercial weather systems, addressing a critical need for many countries and data-sparse regions around the world.

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

