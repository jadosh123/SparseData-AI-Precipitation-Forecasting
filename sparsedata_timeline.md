# SparseData — Project Timeline
**Hard stop: July 2, 2026**
**Final deliverables: Working Streamlit demo + formal written report (20pp)**

---

## Phase 1 — RFSI Virtual Sensor Pipeline
### `Apr 1 → May 4` (~5 weeks)

**Feature engineering module**
- [x] Extract all feature engineering methods from notebook into standalone `feature_engineering.py`
- [x] Implement `main()` entry point that loads from `clean_station_data`, runs all transforms, and outputs a feature-ready dataframe
- [x] Confirm output schema matches exactly what XGBoost forecaster expects as input
- [ ] Unit test each transform method independently

**Spatial neighbor lookup**
- [ ] Build `get_k_neighbors(station_id, k=3)` using haversine distance on station lat/lon
- [ ] Load all 66 station coordinates and validate CRS is consistent
- [ ] Manually inspect neighbors for 5–6 geographically known stations and verify they make physical sense on a map
- [ ] Confirm Afula is excluded from the neighbor candidate pool at all times

**LLOCV fold logic**
- [ ] Implement LLOCV split: for each station, hold it out as validation, train on all others
- [ ] Write explicit assertion that held-out station ID appears nowhere in the training feature matrix for that fold
- [ ] Confirm held-out station is also excluded from neighbor lookup during its own fold
- [ ] Log per-fold train/val size to confirm no silent data leakage

**Interpolation model training (10 features)**
> Features: `rain`, `ws`, `stdwd`, `td`, `rh`, `tdmax`, `tdmin`, `u_vec`, `v_vec`, `rain_intensity_max`
- [ ] Train one spatial interpolation model per feature using LLOCV
- [ ] Report per-feature reconstruction errors (MAE, RMSE) across all folds
- [ ] Sanity check: pick one station, plot predicted vs actual for each feature over a representative week — outputs should look physically plausible
- [ ] Flag `stdwd` result separately — expected to be the weakest interpolating feature due to local turbulence variability

**RFSI → XGBoost wiring**
- [ ] For each Jezreel Valley grid cell, construct synthetic feature vector using trained interpolation models
- [ ] Feed synthetic feature vectors into existing XGBoost forecaster
- [ ] Run grid inference and store outputs → `cell_forecasts(lat, lon, precipitation_t1, t3, t6, t12)`
- [ ] **Phase 1 milestone: trained pipeline, evaluated, outputs stored in DB ✓**

---

## Phase 2 — Backend + Inference Pipeline
### `May 5 → May 18` (~2 weeks)

**Feature engineering pipeline**
- [ ] Package feature engineering, interpolation, and forecaster into a single callable inference pipeline
- [ ] Accepts: raw IMS hourly data drop
- [ ] Outputs: updated `cell_forecasts` rows

**FastAPI backend**
- [ ] Single `/predict` endpoint reading from `cell_forecasts` table
- [ ] Returns: JSON payload with lat/lon grid + precipitation forecasts per horizon
- [ ] Basic error handling: missing data, stale forecasts

**Cronjob**
- [ ] Cronjob triggers on IMS data drop completing a full hour
- [ ] Fetches current hour + lagged hours needed for features
- [ ] Runs clean → Silver → inference pipeline → stores outputs
- [ ] Test: simulate IMS data drop end-to-end, verify `cell_forecasts` populates correctly

**End-to-end test**
- [ ] IMS data in → `cell_forecasts` populated → `/predict` returns correct payload
- [ ] Fix `if_exists='replace'` in `clean_station_data` — downstream tables must not be wiped mid-pipeline
- [ ] **Phase 2 milestone: backend locked, no open bugs ✓**

---

## Phase 3 — Streamlit Frontend
### `May 19 → Jun 1` (~2 weeks)

**Heatmap**
- [ ] Interactive heatmap over Jezreel Valley grid cells
- [ ] Coarser cell resolution — prioritize visual clarity over granularity
- [ ] Color scale maps to precipitation probability or intensity

**Controls**
- [ ] Forecast horizon toggle: t+1 / t+3 / t+6 / t+12
- [ ] Hour selector for browsing historical forecasts
- [ ] Station overlay showing real IMS sensor locations

**Demo stability**
- [ ] Full walkthrough rehearsed: open app → select horizon → read forecast → explain methodology
- [ ] App does not crash on missing data or empty forecast hours
- [ ] Works on a clean machine with no local setup beyond `streamlit run`
- [ ] Record 4-minute demo video (required by report template alongside live demo)
- [ ] **Phase 3 milestone: demoable, stable, rehearsed ✓**

---

## Phase 4 — Report Writing
### `Jun 2 → Jun 22` (~3 weeks)

> Template requires: cover page (HE + EN), Hebrew abstract, English abstract, TOC, body (20pp max excl. appendices), appendices.
> Body structure: elevator pitch (optional), introduction, problem description, literature review, solution description, conclusions, AI usage, tests.

**Week 1 — Jun 2–8**
- [ ] Cover page (Hebrew + English), project metadata table, GitHub link
- [ ] Hebrew abstract + English abstract
- [ ] Introduction
- [ ] Problem description
- [ ] Literature review + comparison to similar works (RFSI paper, related precipitation nowcasting)

**Week 2 — Jun 9–15**
- [ ] Solution description: system architecture diagram
- [ ] Solution description: ETL pipeline (Bronze → Silver → Gold)
- [ ] Solution description: virtual sensor generation methodology
- [ ] Solution description: RFSI-inspired interpolation + XGBoost forecasting pipeline

**Week 3 — Jun 16–22**
- [ ] Results: interpolation errors per feature (MAE/RMSE table)
- [ ] Results: forecast accuracy per horizon (Recall, F1 at t+1/t+3/t+6/t+12)
- [ ] Results: Afula held-out test — virtual sensor vs actual, forecast vs actual
- [ ] Conclusions: what worked, what didn't, limitations (single error metric, interpolation vs forecast error not decomposed), future work
- [ ] Tests chapter
- [ ] AI usage section
- [ ] Verify every figure and table has a caption and is referenced in the body text
- [ ] Page count check — 20pp max excluding appendices
- [ ] **Phase 4 milestone: complete draft ready for polish ✓**

---

## Buffer — Final Polish
### `Jun 23 → Jul 2`

- [ ] Freeze all code — no new features after June 22
- [ ] Stress-test live demo: edge cases, empty hours, slow data
- [ ] Report: final proofread, formatting check (David 12pt HE / TNR 12pt EN, 1.5 line spacing, centered page numbers)
- [ ] Table of contents generated and accurate
- [ ] All appendices included (relevant code snippets, extra figures)
- [ ] Video link added to cover page table (max 4 minutes, publicly viewable)
- [ ] Supervisor final feedback addressed
- [ ] Submission package assembled
- [ ] **July 2 — everything submitted. Nothing left open. ✓**

---

## Dropped features — documented decisions

| Feature | Reason |
|---|---|
| `wdmax` | Circular interpolation unreliable near 0°/360°; max 0.36% importance across horizons; directional info captured by `u_vec`/`v_vec` |
| `wsmax` | Mean `ws` consistently higher importance across all horizons (peaks 1.41% vs 0.47%); sustained wind more predictive of precipitation than peak gust |

---

## Known limitations to acknowledge in report

- Interpolation error and forecast error are not decomposed — measured end-to-end only at forecast stage
- `stdwd` expected to be weakest interpolation target due to local turbulence variability
- Virtual sensor generalization validated on single held-out station (Afula) only
