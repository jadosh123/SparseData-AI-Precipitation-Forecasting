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
