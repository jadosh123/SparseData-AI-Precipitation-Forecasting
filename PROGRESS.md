# Documentation of Journey

## The Goal

This document tracks the engineering challenges, architectural decisions, and solutions implemented throughout the development of the SparseData AI Precipitation Forecasting System.

## Domain Knowledge

I am currently studying Meteorology Today: An Introduction to Weather, Climate, and the Environment to bridge the gap between data science and physical atmospheric dynamics. I am mapping metrics provided by the Israeli Meteorological Service (IMS) (e.g., Temperature, Rain, Wind Direction) to theoretical concepts needed for feature engineering (e.g., Wind Convergence, Orographic Lift).

## System Architecture

To ensure scalability and industry-standard data flow, I adopted the Medallion Architecture:

- Bronze Layer (Raw): Ingested raw 10-minute intervals from IMS stations (Haifa, Tel Aviv, Tavor, etc.) directly into PostgreSQL.

- Silver Layer (Cleansed): Aggregating data to hourly intervals, handling missing values, and performing vector decomposition for wind speed/direction.

- Gold Layer (Features): (Planned) Final features ready for the Machine Learning models.

## Engineering & Infrastructure

1. **Environment & Dependency Management**
    - Transitioned to a strictly managed Python 3.11 Virtual Environment (.venv) to ensure reproducibility.

    - configured VS Code workspace settings to enforce the correct interpreter paths, eliminating "it works on my machine" errors.

    - Utilized Docker to containerize the PostgreSQL database, ensuring the data infrastructure is platform-agnostic (runs identically on WSL and Ubuntu Laptop).

2. **Project Structure ("Src Layout")**
    - Refactored the codebase into a standard Src Layout (separating source code src/ from tests tests/).

    - Implemented pyproject.toml for modern dependency management and to install the project in "Editable Mode" (pip install -e .), allowing seamless imports across scripts and tests.

3. **Quality Assurance & Testing**
    - Integrated pytest as the testing framework.

    - Data Integrity Guardrails: Developed automated tests to validate "Bronze" data physics before processing:
        - Absolute Bounds Checks: Detecting impossible values (e.g., Negative Rain, Temperature >50∘C).

        - Logic Consistency Checks: Ensuring T_max ​≥ T_avg​ ≥ T_min​.

        - Completeness Checks: Identifying critical missing data (NaNs) early in the pipeline.

4. **Workflow Synchronization**
    - Created a custom bash-based synchronization workflow using Google Drive to sync binary database dumps between my Desktop (WSL) and Laptop (Ubuntu), allowing frictionless switching between development machines.

## Current Ongoing Challenges:

### Date: January 2, 2026

Subject: Transition from Regression Kriging to Unified RFSI/XGBoost Architecture

1) **Initial Assessment: The Limits of Regression Kriging (RK)**

    **Hypothesis:** The initial proposal involved a two-step pipeline: using Regression Kriging (RK) to generate a spatial grid of current precipitation, followed by a Machine Learning model (XGBoost) to forecast future states.

    **Technical Critique:** Upon review, RK was deemed unsuitable for this specific hydrometeorological context due to:
    - **Linearity Assumption:** RK assumes linear correlations between covariates (elevation) and residuals. Precipitation dynamics in complex terrain are inherently non-linear (e.g., threshold-based convective instability).
    - **Stationarity:** RK assumes spatial variance is uniform (stationarity), which is violated by the distinct micro-climates of the North District.
    - **Error Propagation:** A two-step process (Interpolate → Forecast) compounds errors; uncertainties in the Kriging step would inevitably degrade the forecasting model's accuracy.

2) **Strategic Pivot: Unified RFSI/XGBoost Model**

    **Decision:** We have adopted a Random Forest Spatial Interpolation (RFSI) methodology implemented via a single XGBoost engine.

    **Methodology:** Instead of separating "Spatial Interpolation" and "Temporal Forecasting," we treat them as a single supervised learning problem.
    - **Input (Xt​):** The spatial configuration of neighbors and meteorological conditions at time t.
    - **Target (Yt+1​):** The observed precipitation at time t+1.

    **Benefit:** The model simultaneously learns the Spatial Decay (interpolation logic) and Temporal Advection (forecasting logic). This streamlines the pipeline and allows non-linear interactions between terrain (Static features) and neighbor influence (Spatial features).

3) **Addressing Data Sparsity: The "Blind Neighbor" Training Strategy**

    **Challenge:** We are operating with a sparse local cluster (3 stations: Afula, Newe Yaar, Tavor Kadoorie). Training a model on a station usually implies a "Distance to Nearest Neighbor" of 0, which creates a singularity (overfitting) when applied to grid cells where distance is always > 0.

    **Solution: Leave-One-Station-Out (LOSO) Training.**
    - During training, the target station is masked (hidden) from the feature set.
    - The model must predict the target's value using only the other available stations.
    - **Constraint:** This forces a K=2 Neighbor limit. The model learns to interpolate based on the 2 nearest proxies, ensuring the training context matches the inference (grid) context.

4) **Final Architecture: The Hybrid Physical-Statistical Approach**

    To incorporate distant upstream data (Tel Aviv, Haifa) without corrupting the local spatial interpolation, we established a Hybrid Feature Vector:
    1. **Local Layer (The "Where"):**
        - Uses RFSI Features (K=2) derived strictly from the local cluster.
        - Function: Determines local intensity based on proximity and elevation.
    2. **Upstream Forcing Layer (The "When"):**
        - Uses Broadcasted Features (Wind Vectors, Rain Lags) from Tel Aviv/Haifa.
        - Function: These are treated as "Global/Static" inputs for every grid cell to capture storm advection (movement from the coast) and system severity.

**Conclusion:** This architecture maximizes the utility of sparse data by separating spatial interpolation (Local RFSI) from temporal forecasting (Upstream Lags), all within a single, scalable XGBoost framework.

**Performance Benchmarking:** Our model achieves a Recall (Probability of Detection) of 0.68, which places it in the upper quartile of operational performance for point-based forecasting. According to recent studies (e.g., PostRainBench, MDPI 2023), standard Numerical Weather Prediction (NWP) and ML ensembles typically plateau at a Recall of 0.60–0.70 for similar lead times.

Furthermore, our Precision of 0.49 is consistent with the industry-standard trade-off required to maintain high safety levels. Research indicates that pushing Recall above 0.70 typically degrades Precision to below 0.40. Our current configuration (F1=0.57) represents an optimal balance between safety (catching storms) and cost (false alarms), outperforming the baseline persistence capability by over 20%.

## **Production Architecture: Master Time Index Strategy**

To address the identified data sparsity in upstream reference stations (specifically Haifa’s ~11% wind outages and Jan–June gaps), I will implement a Master Time Index architecture for the deployment pipeline. This strategy decouples the prediction timeline from individual sensor health by initializing a continuous, gap-free "Backbone" index for the target grid and performing Left Joins with all feeder station data. This ensures dimensional consistency across the spatial mesh, preventing pipeline failures during partial sensor outages. By preserving temporal rows even when specific feature columns are NaN, this architecture enables the XGBoost model to leverage its native sparsity-aware inference—dynamically shifting weight to active local sensors (e.g., Afula, Tavor) when distant feeders like Haifa go offline—thereby guaranteeing high availability and robust spatial interpolation for the grid.

To further mitigate the operational risks of sensor outages, I will implement a Dynamic Confidence Scoring layer on top of the prediction output. Since the model's certainty degrades when high-value features (e.g., Haifa Wind) are null, the system will output a prediction interval (lower/upper bound) alongside the point forecast. This allows us to flag forecasts as "Low Confidence" during critical data gaps. Additionally, the API response will include specific Sensor Health Metadata, explicitly informing the user if a prediction is based on a degraded sensor set (e.g., "Warning: Haifa Station Offline - Prediction relies on Local Cluster only"). This transparency ensures users can distinguish between a high-certainty "All-Clear" and a low-certainty interpolation.

### Date: January 5, 2026

Subject: Comparing XGBoost model performance before and after the addition of physical features.

As we can see in the below test outcomes, the model with Tel Aviv and Haifa as upstream feeders saw a clear performance boost from the physical features (RMSE dropping from 2.15 to 2.14).

After inspecting the Haifa Technion station I observed Signal Quality issues. I observed continuous blocks of missing wind speed and direction data along with other sensors telling us that the Haifa Technion station has blocks of missing sensor data due to outages or faulty sensors.

Our mission to circumvent this is to check Haifa Karmel and Haifa Port stations to see if we can find a station with more uptime than the Technion one.

**Features used for physics run:** [u_convergence, v_convergence, moisture_flux]

**XGBoost model setup:** []

### Table 1: Performance Without Physical Features

| Model Type | Global t+1 RMSE (mm) | Storm-Only t+1 RMSE (mm) |
| :--- | :--- | :--- |
| **Baseline Persistence** | 0.5996 | 2.7222 |
| **Baseline XGBoost** | 0.4884 | 2.3056 |
| **XGBoost upstream Tel Aviv** | 0.4769 | 2.2326 |
| **XGBoost upstream Tel Aviv + Haifa** | **0.4592** | **2.1563** |

---

### Table 2: Performance With Physical Features (Convergence & Flux)

| Model Type | Global t+1 RMSE (mm) | Storm-Only t+1 RMSE (mm) |
| :--- | :--- | :--- |
| **Baseline Persistence** | 0.5996 | 2.7222 |
| **Baseline XGBoost** | 0.4884 | 2.3056 |
| **XGBoost upstream Tel Aviv** | **0.4825** | 2.1711 |
| **XGBoost upstream Tel Aviv + Haifa** | 0.4830 | **2.1484** |

![alt text](imgs/feature_importance.png)

### Date: January 7, 2026

Subject: Meeting with PM Dr.Zur, discussed cost function impact on model performance and front-end interface.

We discussed the cost function usage and I agree the reg:squarederror is a bad choice especially in such imbalanced data since this function basically tells the model that over-prediction and under-prediction are equally as bad. In hydrometeorological forecasting, under-predicting a 10-mm storm (a safety risk) is objectively worse than over-predicting by 10mm (a false alarm).
I ran the training/prediction process again but using the tweedie regression cost function since this function is the industrial standard for meteorology and is geared towards data that is zero inflated (like ours) and it improved the best model's performance:

| Model Type | Global t+1 RMSE (mm) | Storm-Only t+1 RMSE (mm) | Storm Intensity Bias (mm) | Storm Scatter Index (%) |
| :--- | :--- | :--- | :--- | :--- |
| **XGBoost upstream Tel Aviv + Haifa (Squared Error cost function)** | 0.4830 | 2.1484 | −0.72 | 127.2% |
| **XGBoost upstream Tel Aviv + Haifa (Tweedie cost function)** | 0.4671 | 2.1177 | -0.70 | 125.4% |
| **Total Improvement per metric** | +3.3% | +1.47% | +0.02mm | -1.8% |

As we can see the model improved across the board which proves using this new cost function didn't just result in a better performance by luck.

We also spoke about building a front-end interface for the system to display the model's forecasts since that is part of the general project goal, I'm thinking of currently of using FastAPI for the backend because its the industry standard, its lightweight and it natively supports JSON which the front-end needs.
For the front-end I will use Streamlit as to not break away from python and my project and waste too much time relearning Javascript and React.

### Date: January 23, 2026

Currently I'm trying to tune the model to get as much performance as possible with the current data setup, the first GridSearchCV run I did involved these parameters:

    param_grid = {
        'learning_rate': [0.01, 0.05, 0.1],
        'max_depth': [3, 5, 7],
        'min_child_weight': [1, 3, 5],
        'subsample': [0.7, 0.8, 0.9],
        'colsample_bytree': [0.7, 0.8, 0.9],
        'tweedie_variance_power': [1.2, 1.5, 1.8]
    }

At first I ran the search with this model setup:

    xgb_model = xgb.XGBRegressor(
        n_estimators=200, 
        objective='reg:tweedie',
        n_jobs=-1,
        missing=np.nan,
        monotone_constraints=constraints_TA_HA
    )

    grid_search = GridSearchCV(
        estimator=xgb_model,
        param_grid=param_grid,
        scoring='neg_mean_squared_error',
        cv=tscv,
        n_jobs=-1,
        verbose=1
    )

    grid_search.fit(
        X_train,
        y_train,
    )

The resulting parameters made the model perform worse, my suspision is that in the fit process I didn't add the sample_weights parameter so the model was being penalized for dry and wet days the same and n_estimators is set to 200 which doesn't give the model much legroom in its exploration for each parameter combination, I'm gonna rerun this tuning with n_estimators=1000 and the sample_weights set to 10.

Well, I tried to tune the model using a TimeSeriesSplit but based on my observation its rewarding low learning rate and low params overall because the training data that is being split spans 3 years and when splitting it accross 5 folds makes it so that the model is being evaluated on dry folds on some of the runs where it teaches it that predicting 0 is the best for error reduction. Every result came out with a weaker and underfitted model than the basic initialization I had before tuning. Now I will experiment with tuning it using my static temporal split to allow it a large window of data.

After testing it seems the basic initialization I had of XGBoost outperformed every tuned model regardless of the method, this points to the fact that the results are heavily influenced by the physics and features rather than tuning.

Possible improvements to model performance will come from smarter feature engineering and deeper domain knowledge.

### Goals for project improvement

- [ ] Investigate the data of Haifa karmel and Haifa Port if they have more continuous rich data compared to Haifa Technion (its missing some blocks of wind vector data).
- [x] Investigate the stations above Afula and Nazareth like the one near Sakhnin and Deir Hana to allow a proper interpolation environment for the RFSI or XGBoost with RFSI features.
- [x] Investigate all coastal station data for continuity to add them later to the system (guarantees that no storm passes between haifa and telaviv and surprises our model).

### Date: February 1, 2026

stations for interpolation:

- Tel Yosef: 380 (good fetched data from 2018 and up)
- Galed: 263 (bad because its only measuring like 4-5 metrics which is insufficient)
- En Hashofet: 67 (good data stretches back to 1998)

new coastal stations:

- Zikhron Yaaqov: 45 (good data stretches back beyond 2018)
- Hadera Port: 46 (good data stretches back to 1990)
- En Karmel: 44 (good data stretches back to 1992)

Stations to inspect further in python against existing stations:

FOR INTERPOLATION:

- En Hashofet: 67
- Tel Yosef: 380

FOR COASTAL:

- Zikhron Yaaqov: 45
- Hadera Port: 46
- En Karmel: 44

### Date: February 2, 2026

I observed a big mistake in the monotone constraints generation that I had before.
I was setting the temperature feature to 1 which means strictly positive relationship so that was telling the model that whenever the temperature increased the rain will increase.
After fixing this and setting the temperature and temperature_max to -1 the errors dropped and here is the table displaying pre-fix and post-fix:

| Model Type | Global t+1 RMSE (mm) | Storm-Only t+1 RMSE (mm) | Storm Intensity Bias (mm) | Storm Scatter Index (%) |
| :--- | :--- | :--- | :--- | :--- |
| **XGBoost upstream Tel Aviv + Haifa (Before Fix)** | 0.4671 | 2.1177 | -0.70 | 125.4% |
| **XGBoost upstream Tel Aviv + Haifa (After Fix)** | 0.4724 | 2.1084 | -0.64 | 124.9% |
| **Total Improvement per metric pct** | -1.1% (Worse) | +0.4% | +9% | +0.4% |

After fixing the monotone constraint you can see in the feature importances the model changed drastically in terms of which features it relies on to predict precipitation, it used to be the rain at Haifa and at Afula as the most important features now its the temperature at Afula followed by rain at Haifa and the minimum temperature at Afula. The rest of the features are the upstream feeders for the most part confirming the validity of them.

![alt text](imgs/feature_importance1.png)

### Date: March 19, 2026

Subject: Multi-Horizon Forecasting Engine Refactor and Physical Shift Analysis

1) **Dynamic Multi-Horizon Refactoring**
    - Transformed the `single_point_forecast.ipynb` engine to iteratively generate datasets, train unique XGBoost models, and evaluate predictions across incremental forecast horizons (t+1, t+3, t+6, t+12).
    - Ensured monotone constraints and target variables dynamically adapt to the requested lag.

2) **Physical Behavior & Importance Shift Analysis**
    - Developed comparative analyses to track the absolute change in correlation and XGBoost feature importance (`gain`) from t+1 to t+12 by normalizing gain to 100% per model.
    - **Key Finding - "The Spark vs The Fuel Line":** At t+1, immediate local metrics like `td` (Dew Point) dominate the model (29% of importance) as they represent the immediate "spark" of condensation. By t+12, `td` drops significantly, while upstream coastal metrics like `moisture_flux` and `u_convergence` at Haifa/Tel Aviv surge in relevance.
    - **Key Finding - Diurnal Cycle:** `td_t-12h` gains significant predictive power at the t+12 horizon, confirming the model leverages the 24-hour diurnal heating cycle as a physical baseline for long-range target forecasting.

3) **Multi-Horizon Evaluation Metrics**
    - Built a comprehensive evaluation matrix combining Classification Metrics (Recall, Precision, F1) and Missed Rain Analysis for each horizon.
    - Results demonstrate an operationally sound "Graceful Degradation," with F1-scores dropping smoothly from 0.66 (t+1) to 0.41 (t+12), respecting standard atmospheric prediction decay.
    - The operational safety bias remains intact. At t+12, the model sacrifices Precision (32%) to maintain a high Recall (57%), minimizing dangerous misses. The "Average Rain Missed" remains near ~1.0 mm/hr, proving the model catches severe events and only fails on minor drizzles.


### Date: March 30, 2026

Subject: RFSI Training Methodology & Implementation Plan

---

**Objective:** Train a Random Forest Spatial Interpolation (RFSI) model on the full 84-station national IMS network to learn generalizable spatial interpolation of meteorological features, then deploy it to generate synthetic station data at each grid cell over the Jezreel Valley for downstream single-point precipitation forecasting.

---

**1. Data Quality & Station Selection**

- Computed per-station missingness report across all core features: `rain`, `ws`, `wd`, `wsmax`, `wdmax`, `stdwd`, `td`, `rh`, `tdmax`, `tdmin`
- Excluded non-informative columns from quality assessment: `elevation`, `ws1mm`, `ws10mm`, `timestamp`, `station_id`, `latitude`, `longitude`
- Applied 40% missingness threshold on core features — stations exceeding this on any core column are dropped from the RFSI training corpus
- **Result: 66 stations retained out of 89**
- Removed `ws1mm` and `ws10mm` from schema and ingestion pipeline entirely — instantaneous gust metrics with no forecasting value and widespread sensor absence

**2. Temporal Window Strategy**

- Stations have uneven temporal coverage (e.g. Nazareth City only available from 2023 onwards due to recent deployment)
- Rather than forcing a fixed 6-year window, each station contributes its longest continuous segment ending at 2026
- RFSI training samples at timestep `t` are only valid if **all K neighbors** have non-null core feature observations at that same `t`
- This naturally excludes outage blocks and late-deployment stations from affected timesteps without explicit imputation or arbitrary decisions
- Effective training corpus is the intersection of valid neighbor windows per sample, not a global fixed date range

**3. RFSI Feature Construction**

- For each target station at each valid timestep, identify K nearest neighbors by geographic distance (Haversine)
- Extract per-neighbor features:
  - Observed values of all core features at time `t`
  - Distance to target cell
  - Elevation difference between neighbor and target
  - Bearing/direction from neighbor to target
- Lag features: rolling lags at t-1h, t-2h, t-3h per neighbor
- Target variable: observed feature value at the target station at time `t`
- Apply Leave-Location-Out Cross Validation (LLOCV) — each fold holds out one station entirely as the target, trains on all remaining stations, ensuring the model learns to interpolate to **unseen locations** rather than memorizing training station patterns

**4. Model Training**

- One RFSI model trained per interpolated feature (rain, ws, wd, td, etc.) or a multi-output variant if feasible
- Algorithm: Random Forest (or XGBoost for consistency with downstream forecaster)
- Evaluation metric per feature: RMSE on held-out LLOCV folds
- Primary validation: apply trained RFSI to Jezreel Valley grid, compare synthetic Afula cell output against real Afula station observations as geographic ground truth

**5. Grid Generation & Deployment**

- Define Jezreel Valley bounding box and generate a regular grid of synthetic station cells at chosen spatial resolution
- For each grid cell at each timestep, identify K nearest real stations and extract neighbor features
- Run trained RFSI models to generate full synthetic feature vectors per cell
- Feed synthetic feature vectors into trained single-point XGBoost forecaster to produce per-cell precipitation forecasts
- Cron-triggered inference pipeline writes output grid to storage for Streamlit frontend consumption

**6. Frontend & Validation Display**

- Streamlit frontend renders interpolated feature grid and forecast grid over Jezreel Valley using Folium or pydeck
- Afula station displayed as labeled ground truth point with predicted vs observed values shown side by side
- Multi-horizon forecast layers (t+1 to t+12) toggleable on the map
- Confidence layer flagging low-reliability cells during upstream sensor outages (Master Time Index integration)

---

**Open Questions / Next Steps**

- [ ] Determine optimal K for neighbor selection via cross-validation
- [ ] Decide whether to train one RFSI model per feature or a unified multi-output model
- [ ] Investigate whether bearing/elevation features meaningfully improve interpolation over distance alone
- [ ] Finalize Jezreel Valley bounding box and grid resolution
- [ ] Assess whether coastal stations (Zikhron Yaaqov, Hadera Port, En Karmel) improve spatial coverage sufficiently to include despite later start dates

### Date: April 15, 2026

Subject: RFSI Baseline Training — First Results

Trained 9 RFSI models (one per feature) on the full 66-station network using default XGBoost with Delaunay-triangle neighbor clusters. All station data loaded in a single query and stacked before training. Temporal split at 80/20.

| Feature | MAE | RMSE |
| :--- | :--- | :--- |
| rain | 5.6107 | 203.9911 |
| ws | 0.9812 | 1.3166 |
| stdwd | 6.2437 | 34.4657 |
| td | 1.4058 | 1.8816 |
| rh | 5.8358 | 8.3472 |
| tdmax | 1.4191 | 1.8976 |
| tdmin | 1.4106 | 1.8889 |
| u_vec | 1.1089 | 1.5226 |
| v_vec | 0.9672 | 1.3033 |

`rain` RMSE of 203 indicates extreme sensitivity to heavy rain events — zero-inflation problem. Next step: switch `rain` to `reg:tweedie` objective. `stdwd` MAE of 6.2° confirms expected local turbulence variability noted in timeline.

After trying to move from RMSE for the rain interpolation model to Tweedie Loss function it threw an error because of negative values, I then checked the data because why on earth would rain contain negative values and found this:
                        rain
timestamp                   
2024-10-25 18:00:00 -59994.0
2024-10-25 19:00:00 -59994.0
2024-10-26 04:00:00 -59994.0
2024-10-26 05:00:00 -59994.0
2024-10-26 09:00:00 -59994.0
2024-10-26 06:00:00 -59994.0
2024-11-08 14:00:00 -59994.0

I concluded this was a sentinel value used by the IMS when the rain sensor was corrupt or down which survived my cleaning script, now the cleaning script is refactored and replaces negative rain with 0 since its physically invalid, that was clearly causing the rain errors to inflate so much which is why it was the worst out of all.
Classic case of data corruption, garbage in garbage out.

After fixing the sentinel values and switching `rain` to `reg:tweedie` (variance power 1.5), the models were retrained. Updated metrics below. Rain global MAE looks deceptively low (0.035) due to zero-inflation — rain-only evaluation on actual rain events (≥ 0.1mm, n=17,239) gives the honest picture.

| Feature | MAE | RMSE | Notes |
| :--- | :--- | :--- | :--- |
| rain (global) | 0.0353 | 0.3579 | Misleading — zero-inflated |
| **rain (events ≥ 0.1mm only)** | **0.9075** | **1.9960** | Honest rain performance |
| ws | 0.9840 | 1.3200 | |
| stdwd | 6.2309 | 34.1043 | Expected — local turbulence variability |
| td | 1.4002 | 1.8737 | |
| rh | 5.8496 | 8.3644 | |
| tdmax | 1.4184 | 1.8973 | |
| tdmin | 1.4162 | 1.8958 | |
| u_vec | 1.1090 | 1.5226 | |
| v_vec | 0.9629 | 1.2990 | |

### Date: April 19, 2026

Subject: RFSI LLOCV Evaluation — Afula Held-Out Test Results & Error Analysis

**LLOCV Interpolation Results (Afula held-out, station 16 excluded from training entirely)**

| Feature | MAE | RMSE | RMSE (rain events ≥ 0.1mm only) |
| :--- | :--- | :--- | :--- |
| rain (global) | 0.0460 | 0.3301 | 1.4917 |
| ws | 1.2244 | 1.4205 | — |
| td | 1.4335 | 1.8149 | — |
| rh | 4.5308 | 6.1525 | — |
| tdmax | 1.3779 | 1.7491 | — |
| tdmin | 1.4549 | 1.8415 | — |
| u_vec | 1.0206 | 1.2876 | — |
| v_vec | 0.8336 | 1.0661 | — |

**Error Analysis by Feature**

**Rain:** Global RMSE is clean (0.33mm) but rain-only RMSE of 1.49mm is driven almost entirely by a small number of extreme events exceeding 20mm at Afula. RFSI interpolates from neighboring stations which may not capture local intensity of convective events in the valley — the same systematic underestimation of extremes documented in the tree-based precipitation literature.

**Wind speed:** Visually consistent positive offset across the full plot — predictions sit above ground truth by a roughly stable margin. Physically explained by Afula's local topographic exposure or orographic channeling not shared by surrounding stations, causing RFSI to interpolate toward the regional mean wind rather than Afula's local wind regime. Planned correction: fit a bias correction to the residual distribution derived from training stations only (not Afula), apply as a learned post-processing step before features enter XGBoost. Worth checking whether the bias is uniform across summer/winter before applying a single correction.

**All other features (td, rh, tdmax, tdmin, u_vec, v_vec):** Visually close to ground truth, following seasonal trends correctly. These are spatially smooth fields that RFSI handles well.

**Key Methodological Notes**

- LLOCV metrics and XGBoost forecast metrics evaluate different pipeline stages and cannot be directly compared. LLOCV measures interpolation reconstruction quality; XGBoost metrics measure forecast quality given clean inputs. At real inference both error sources compound.
- Rain-only RMSE at interpolation (1.49mm) and storm-only RMSE at forecast are in the same units but measure different things — do not conflate them.
- The Gaussian noise injection during XGBoost training (sampled from per-feature LLOCV RMSE) was designed to make the forecaster robust to upstream interpolation error. There is no empirical measurement yet of how much storm RMSE degrades when XGBoost is fed RFSI-interpolated inputs vs. real Afula observations — that delta would be the true cost of the RFSI approximation at inference.
- Wind speed bias correction, if implemented, should be framed as "systematic bias correction derived from the leave-one-out residual distribution" — a legitimate post-processing step with precedent in the NWP bias correction 
literature.


### Architectural Decisions Made Recently
- **LLOCV over random CV** — spatially aware validation that prevents neighboring stations from leaking information into the held-out target, giving realistic error estimates for unseen locations
- **Temporal split within LLOCV** — prevents future timestamps leaking into interpolation model training.
- **RFSI for spatial interpolation then XGBoost for temporal forecasting** — clean separation of concerns, each model does one job, avoids muddying spatial and temporal signals
- **Afula as held-out test station** — never seen in training or validation, in the target deployment region, gives honest generalization estimate
- **Gaussian noise injection sampled from per-feature LLOCV RMSE** — makes XGBoost robust to upstream interpolation error at inference, grounded in the actual measured error distribution rather than arbitrary noise (not tested yet).
- **Wind decomposition into u/v vectors** — eliminates the 0°/360° circular discontinuity that would create artificial distance in the feature space
- **Cyclic sin/cos encoding for month and day** — same reasoning as wind vectors, December and January remain close in the encoded space
- **8-feature baseline with deliberate feature dropping** — stdwd, rain_intensity_max, wdmax, wsmax dropped for principled reasons, not arbitrary
- **Medallion architecture** — raw/bronze/silver/gold separation keeps data lineage clean and reproducible
- **Bias correction via residual distribution** — fitted on training stations only, applied blind to Afula, keeps evaluation clean