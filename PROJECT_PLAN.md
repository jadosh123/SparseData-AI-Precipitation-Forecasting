# Project Plan

1. **Phase 1: Infrastructure & Feature Engineering (Dec – Jan)**
    - Goal: Finalize the ETL pipeline (Bronze Silver) and implement "Gold Layer" logic (Lags, Wind Convergence).

    - Deliverable: A robust, fully populated Feature Store ready for model training.

2. **Phase 2: Alpha Prototype (Feb - Due Date)**

    - Goal: Validate the modeling hypothesis via a Comparative Analysis Notebook.

    - Deliverable: A demo showing that the proposed "Spatial Feature" model (XGBoost) statistically outperforms a baseline local-only model (RMSE), validating the logic before optimization.

3. **Phase 3: Systems Optimization (Mar – Apr)**
    - Goal: Scale the system to the full sensor network and optimize latency.

    - Validation Task: Expand the pipeline to ingest all surrounding stations (Newe Ya'ar, Afula, Tavor). Perform Target-Oriented Validation by treating the Nazareth station (2023–2025) as a "blind" hold-out set to rigorously quantify the forecast error against ground truth.

    - Performance Task: Develop a custom C++ Regression-Kriging Kernel (via PyBind11) or utilize JIT Compilation (Numba) to precompile critical loops, ensuring the system meets real-time requirements.

4. **Phase 4: Productization & Deployment (May – Jun)**
    - Goal: Build the Streamlit Dashboard (Heatmaps/Alerts) and finalize Docker orchestration.

    - Deliverable: Final Report, Presentation, and deployed "One-Click" System.
