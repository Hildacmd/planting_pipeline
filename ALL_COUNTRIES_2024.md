# ICPAC Planting Pipeline — All-Countries 2024 Run

**Crop-specific maize monitoring for the Greater Horn of Africa**
Google Earth Engine + Python · 250 m · 2024 season · project `ee-manzikye`

This document is the as-built record of the 2024 continental run: the products that were generated,
the datasets they use, the algorithms step-by-step, the A/B tests that shaped the design, and the
gaps that were found and how each was filled. It complements the per-module methodology documents
(`CPI_METHODOLOGY.md`, `RISK_MONITORING_METHODOLOGY.md`, `WATERLOGGING_METHODOLOGY.md`,
`YIELD_ESTIMATION_METHODOLOGY.md`, `KENYA_SEASON_REGIMES.md`) and the Colab notebook
`planting_pipeline_ALL_colab.ipynb`.

---

## 1. Scope

- **Region:** 11 ICPAC member states — Kenya, Ethiopia, Somalia, Uganda, Rwanda, Burundi, Tanzania,
  South Sudan, plus Eritrea/Djibouti/Sudan where a viable maize season exists.
- **Crop:** maize (the pipeline also supports teff and wheat where grown; only maize was run continentally for 2024).
- **Year:** 2024, every viable season per the ICPAC season calendar.
- **Grid:** 250 m, exported as Earth Engine image assets `cpi_<Country>_<Season>_2024`
  (bands `CPI, yield_tha_x100, S_water, S_heat, S_veg`) and a richer stack
  `cpiX_<Country>_<Season>_2024` (adds `planting_dekad` + 6 WRSI/WSI stage bands) that feeds the
  interactive apps.

---

## 2. The run — products generated

Sixteen maize products landed for 2024. Onset method and yield-ceiling (Yₘ) source are per season.

| # | Country | Season | Onset window (dekads) | Onset method | Viability | Yₘ (t/ha) | Yₘ source |
|---|---------|--------|-----------------------|--------------|-----------|-----------|-----------|
| 1 | Kenya | Long rains | Mar-d3–May-d3 | green-up cue-fusion | High | 3.2 highland / 2.1 rest | HarvestStat 70/30 (AEZ split) |
| 2 | Kenya | Short rains | Oct-d1–Nov-d3 | rainfall-anchored | Medium | 2.02 | HarvestStat 70/30 (level only) |
| 3 | Ethiopia | Meher | Apr-d2–Jun-d3 | green-up cue-fusion | High | 4.42 | HarvestStat 70/30 |
| 4 | Ethiopia | Belg | Mar-d1–Apr-d3 | rainfall-anchored | Medium | 4.5 (fallback) | too few HarvestStat units |
| 5 | Somalia | Gu | Apr-d2–Jun-d1 | green-up cue-fusion | Medium | 6.0 (fallback) | too few HarvestStat units |
| 6 | Somalia | Deyr | Oct-d2–Dec-d1 | rainfall-anchored | Medium | 4.5 (fallback) | too few HarvestStat units |
| 7 | Uganda | 1st rains | Mar-d1–May-d2 | green-up cue-fusion | High | 6.0 (fallback) | no HarvestStat match |
| 8 | Uganda | 2nd rains | Aug-d2–Oct-d2 | rainfall-anchored | High | 4.5 (fallback) | no HarvestStat match |
| 9 | Rwanda | Season A | Sep-d3–Nov-d2 | rainfall-anchored¹ | High | 6.0 (fallback) | no HarvestStat match |
| 10 | Rwanda | Season B | Feb-d2–Apr-d1 | rainfall-anchored | High | 4.5 (fallback) | no HarvestStat match |
| 11 | Burundi | Season A | Sep-d3–Nov-d2 | rainfall-anchored¹ | High | 6.0 (fallback) | no HarvestStat match |
| 12 | Burundi | Season B | Feb-d2–Apr-d1 | rainfall-anchored | High | 4.5 (fallback) | no HarvestStat match |
| 13 | Tanzania | Masika | Mar-d2–May-d2 | green-up cue-fusion | High | 6.0 (fallback) | no HarvestStat match |
| 14 | Tanzania | Msimu | Dec-d1–Feb-d1 (**cross-year**) | green-up cue-fusion | High | 6.0 (fallback) | no HarvestStat match |
| 15 | Tanzania | Vuli | Oct-d2–Dec-d1 | rainfall-anchored | Medium | 4.5 (fallback) | no HarvestStat match |
| 16 | South Sudan | Main | Apr-d2–Jul-d1 | green-up cue-fusion | Medium | 6.0 (fallback) | no HarvestStat match |

*Dekads: 1 = 1–10 Jan … 36 = 21–31 Dec. Yₘ is the attainable-yield ceiling; the estimate is
`yield = (CPI/100) × Yₘ`. Only Kenya and Ethiopia have enough matched HarvestStat sub-national units
to fit a calibrated Yₘ; the rest use season defaults (6.0 main / 4.5 short-duration) until reference
statistics are matched.*
*¹ Rwanda/Burundi Season A was moved from green-up to rainfall-anchored onset after the first run —
their persistently cloudy equatorial highlands defeat green-up (§6).*

**Orchestration.** `run_all_maize_2024.py` submits the batch, staged by viability
(`--stage high|medium|all`). Skip-guards check both existing assets and in-flight tasks so a re-run
only submits what is missing. `calibrate_ym_all.py` fits Yₘ against HarvestStat and prints
paste-ready values. `poll_tasks.py --watch` follows the batch to completion.

---

## 3. Datasets used

All inputs are free / open. The pipeline is GEE-native; the ground-truth statistics are the only
non-EO inputs.

### 3.1 Core dynamic inputs (per-season)

| Dataset | Variable | Resolution | Cadence | Source / GEE ID | Role |
|---|---|---|---|---|---|
| Sentinel-2 MSI L2A | Red-edge NDRE/NDVI | 10–20 m | 5-day | `COPERNICUS/S2_SR_HARMONIZED` | Primary green-up onset cue |
| Cloud Score+ | Clear-pixel score | 10 m | per pass | `GOOGLE/CLOUD_SCORE_PLUS/V1/S2_HARMONIZED` | S2 cloud masking |
| Sentinel-1 SAR GRD | C-band backscatter (RVI) | 10 m | 6–12 day | `COPERNICUS/S1_GRD` | Cloud-proof gap-fill in cue fusion |
| MODIS FPAR/LAI | FPAR | 500 m | 4-day | `MODIS/061/MCD15A3H` | Canopy-build confirmation in cue fusion |
| CHIRPS v2.0 | Rainfall (P) | ~5.5 km | daily/dekadal | `UCSB-CHG/CHIRPS/DAILY` | Rainfall onset, SPI-3, WRSI water balance |
| ERA5-Land | Tmax/Tmin, radiation | ~9 km | daily | `ECMWF/ERA5_LAND/DAILY_AGGR` | ET₀ (Hargreaves), flowering heat, GDD |
| MODIS NDVI (MOD13Q1) | NDVI | 250 m | 16-day | `MODIS/061/MOD13Q1` | VCI → CPI vegetation stress |

### 3.2 Core static inputs

| Dataset | Variable | Resolution | Source / GEE ID | Role |
|---|---|---|---|---|
| ESA WorldCereal | Maize / active-cropland mask | 10 m | `ESA/WorldCereal/2021/MODELS/v100` | Crop mask → cropped-area fraction, harvested area |
| SoilGrids (+ Saxton-Rawls) | AWC, FC, SAT | 30–250 m | derived | WHC for WRSI; hydrology for waterlogging |
| SRTM 30 m DEM | Elevation | 30 m | `USGS/SRTMGL1_003` | AEZ elevation belt (highland ≥ 1800 m), GDD lapse |
| GAUL admin 0/1/2 | Boundaries | vector | FAO/ASAP | Country AOI, admin aggregation |
| GADM / OCHA CODs | Boundaries L1/2/3 | vector | GADM | County/ward aggregation (Kenya wards etc.) |
| MODIS MCD12Q2 | Green-up phenometrics | 500 m | `MODIS/061/MCD12Q2` | Phenology LTN prior (single-year seasons) |

### 3.3 Ground-truth / calibration (non-EO)

| Dataset | Level | Cadence | Source | Role |
|---|---|---|---|---|
| HarvestStat Africa v1.2 | Admin unit (FEWS NET `fnid`) | annual/seasonal | Zenodo (FEWS-NET-harmonized) | Yₘ calibration reference (yield 70/30) |
| GEOGLAM Crop Monitor calendars | Sub-national | static | GEOGLAM/UMD | Reference planting window → skill hit-rate |
| FEWS NET Data Warehouse (FDW) | Admin / livelihood zone | seasonal | FEWS NET | Alternative sub-national stats |
| Crop-cutting (Kenya, 5 counties) | Ward / point | campaign 2021/22 | partners | Independent yield validation (Kenya only) |

> **What counts as field data.** HarvestStat and GEOGLAM are *harmonized official / institutional*
> products, not primary field measurement. The **only primary field measurement** in the programme is
> the Kenya crop-cutting campaign (5 counties, 2021/2022 short rains). This distinction matters for
> how much weight each carries in validation.

---

## 4. Algorithms, step by step

The pipeline is four modules over a common onset anchor. All water-balance and phenology maths run
inside Google Earth Engine; nothing is downloaded to run the model.

### Module 1 — Planting window (onset)

**Goal:** per-pixel planting dekad.

1. **Season window** from the calendar (`sos_detection_window`), e.g. Kenya Long rains = Mar-d3–May-d3.
2. **Main seasons — cue-fusion green-up:**
   a. Build dekadal Sentinel-2 red-edge composites (NDRE1/NDRE2, cloud-masked with Cloud Score+ ≥ 0.60).
   b. Add MODIS FPAR (dekadal) as a canopy-build confirmation.
   c. Gap-fill cloud-blank dekads with Sentinel-1 SAR (RVI), so the greenness series is unbroken.
   d. Fuse into one greenness track; detect the first **sustained** green-up crossing inside the
      window = **start-of-season (SOS)**, nudged by an MCD12Q2 climatological prior (`ltn_pad = 2`).
   e. Convert SOS → planting with a crop offset (maize −2 dekads, wheat/teff −1).
3. **Short / second seasons — rainfall-anchored onset:** green-up is too weak, so onset is the first
   dekad with **≥ 25 mm** and a **≥ 20 mm** follow-on, supported by P/PET, from CHIRPS; a 44-year
   CHIRPS climatology fills pixels the single year leaves blank.
4. **Cross-year seasons** (e.g. Tanzania Msimu, Dec→Feb): the season window wraps past dekad 36. The
   graph is built from the **prior year** with dekads extended (34, 35, 36, 37…40) so December imagery
   is addressed correctly; the water balance runs from year − 1.

### Module 2 — Risk monitoring (staged WRSI + stresses)

**Goal:** stage-aware water, heat, and vegetation stress.

1. **Staged FAO-56/33 water balance** forward from the planting dekad through **vegetative →
   flowering → grain-fill**, using CHIRPS P, Hargreaves ET₀ from ERA5-Land, and SoilGrids WHC. Each
   stage yields a running **WRSI** (100 = no water limitation) and a **WSI** (max dekadal deficit).
2. **Water stress** `S_water` = FAO-33 stage-weighted deficit, with **Ky = {veg 0.4, flo 1.5, grf 0.5}**
   — flowering weighted heaviest.
3. **Heat stress** `S_heat` = heat-degree-dekads above a maize threshold during flowering
   (`HEAT_K = 0.06`), capturing pollen sterility. *Threshold caveat:* dekad-mean flowering Tmax peaks
   at 22.9 / 25.9 / 29.3 °C across Kenya's three season regimes, so the shipped 33 °C cap rarely fires
   — heat is a confirmation, not the driver, in most GHA maize.
4. **Vegetation stress** `S_veg` = down-weighted (VEG_W 0.4) 1 − VCI (Kogan) or a standardized FPAR
   anomaly (ASAP convention) — a condition confirmation on the water/heat signal.

### Module 3 — Crop Performance Index & yield

**Goal:** one 0–100 index and a yield estimate.

1. **Multiplicative CPI** (AquaCrop-style independent hazards):

   `CPI = 100 · (1 − S_water)(1 − S_heat)(1 − S_veg)`

2. **Yield** `= (CPI / 100) · Yₘ`, where **Yₘ is the attainable ceiling**, calibrated per
   (country, season) against HarvestStat with a **least-squares-through-origin fit, 70/30 train/test**.
3. **AEZ-aware Yₘ** where it helps: Kenya Long rains uses a per-pixel ceiling — **highland (≥ 1800 m)
   3.2 t/ha, rest 2.1 t/ha** — because the highland edge is *potential*, not water timing. Ethiopia
   Meher keeps a single Yₘ (no region-level lowland gradient). Uncalibrated countries use season
   defaults (6.0 main / 4.5 short) until reference statistics are matched.

### Module 4 — Flooding / waterlogging (wet-side hazard)

**Goal:** the excess-water risk WRSI is blind to (it saturates at 100).

1. **SPI-3 wet anomaly** (validated) — 3-month standardized-precipitation surplus (Wilson-Hilferty
   gamma) flags surface / seasonal excess rainfall.
2. **Soil aeration-stress index** (modelled, uncalibrated) — days the root zone sits above field
   capacity toward saturation during the cycle, from a SoilGrids + Saxton-Rawls hydrology.

---

## 5. A/B tests conducted

Design choices were settled by held-out tests, not preference. The table records what was tried,
the result, and the decision. "MAE" is held-out mean absolute error in t/ha against HarvestStat
unless noted.

| Test | Hypothesis | Result | Decision |
|---|---|---|---|
| **ubESTARFM fusion for onset** | Spatiotemporal S2×MODIS fusion sharpens SOS | No benefit to onset | **Rejected** — keep cue fusion |
| **AEZ highland Yₘ split** (Kenya Long) | Cool highland has a higher ceiling than lowland | MAE 0.57 → **0.40** | **Adopted** (3.2 / 2.1 t/ha) |
| **Yₘ recalibration to HarvestStat** | v1 Yₘ too high (national ~2× over) | Kenya Long bias +2.03 → **+0.04**, MAE 2.3 → **0.61** | **Adopted** (70/30 calibrated Yₘ) |
| **Zone-aware LGP** (180 d highland season) | Longer highland growing period improves yield | MAE 0.57 → **0.66** (worse) | **Rejected** — the highland lever is Yₘ, not season length |
| **CHIRPS-LTN rainfall-driven Yₘ** | Rainfall climatology predicts the ceiling | MAE 0.589 (no gain) | **Rejected** |
| **Ethiopia Meher highland split** | Same highland lever as Kenya | No lowland gradient at region level | **Rejected** — single Yₘ 4.42 |
| **S_veg swap to ET-based index** | ET anomaly beats VCI for vegetation stress | Dead at admin-2 (n = 39 kills the n = 5 signal) | **Rejected** — keep VCI/FPAR |
| **DMP vs CPI ranking** | Dry-matter productivity ranks seasons better | DMP out-ranks CPI in 4/5 counties | **Logged** — CPI kept operationally; DMP noted as a candidate |
| **WHC variants (4)** | SoilGrids WHC choice changes skill | Only KE short-rains county wins (bias, not skill); SoilGrids *hides* the Kitui 2022 drought | **Kept default**, flagged SoilGrids limitation |
| **CHIRTS LTN & xlsx GDD targets** | CHIRTS temperature / spreadsheet GDD improve the clock | No gain over ERA5; xlsx GDD *worse* | **Rejected** — keep `gdd_clock` on ERA5 |
| **Kenya OND window trim** | Short-rains window dk 28–34 too wide | 0 % of 825 farmer records & 14 k planner cells plant after dk 33; trim cut late-regime MAE 2.24 → 1.37 | **Adopted** — window Oct-d1–Nov-d3 |

See `Methodology_Testing/` and the memory notes for the full protocols and figures.

---

## 6. Gaps identified and how they were filled

| Gap / failure | Symptom | Fix |
|---|---|---|
| **Cross-year season** (Tanzania Msimu, Dec→Feb) | Batch failed: *"Empty date ranges not supported"* — `ee.List.sequence(34, 4)` empty | `dekad_to_start_date` now wraps dekads > 36 into the next year; base collections filter to `max(dekad)+2`; orchestrator builds from year − 1 with an extended dekad range. Verified: 3,135 valid SOS pixels, planting dekads 32–38 |
| **GAUL-2015 = old Kenya districts** | County geometries empty at admin-1/2 | Crosswalk old districts → modern counties (e.g. Kitui = "Kitui" + "Mwingi") |
| **Ethiopia HarvestStat name mismatch** | 70/30 fit dropped most regions | Alias crosswalk (SNNPR → Southern Nations, Benishangul Gumuz → Benshangul-Gumaz, etc.); Sidama has no GADM-4.1 polygon (documented) |
| **Yield over-prediction** | v1 ~18–32× over crop-cutting in ASAL (mask artefact), ~2× at national vs HarvestStat | Root cause = Yₘ too high; recalibrated Yₘ to HarvestStat (70/30), added AEZ split |
| **LTN cannot give onset** | Threshold SOS never triggers on a climatological mean (79–92 % of pixels blank) | Compute onset from individual years; use LTN only as a prior/pad |
| **Colab memory / timeout** | *"User memory limit exceeded"*, *"Computation timed out"* on `reduceRegions` | `tileScale`, coarsen county reduce to 1 km, auto batch-export fallback |
| **geemap API-key hang** | `GOOGLE_MAPS_API_KEY` `TimeoutException` on `new_map()` | Monkeypatch `userdata` to raise `SecretNotFoundError`; keyless SATELLITE basemap |
| **"No module named 'src'"** | Import fails after kernel restart | Re-run Drive-mount + `sys.path.insert`; setup guard cell |
| **EE sample > 5000 elements** | *"query aborted"* on stress sampling | Recursive quadtree sampling |
| **Drive duplicate exports** | Re-exports create `" (N).tif"`; scripts read stale canonical | Canonicalize newest-first |
| **South Sudan key error** | `KeyError 'South Sudan'` in GAUL lookup | Key `GAUL_NAME` as `South_Sudan`; `.replace(" ", "_")` fallback |
| **GEE task cap** | Only ~2–3 concurrent on free tier | Queue accepts ~3,000; stage by viability and let it drain |
| **Cached-WHC western footprint** | Rwanda & Burundi products were **entirely empty**; western Uganda / Tanzania / South Sudan silently clipped. The materialized SoilGrids WHC asset ends at **32.3 °E**; west of it WHC is masked, so the whole water balance (S_water, WSI) and CPI collapse | `get_whc` now fills any gap in the cached asset with a live SoilGrids + Saxton-Rawls WHC build (`unmask(fill, sameFootprint=False)`) — fast cached path where it exists, SoilGrids everywhere else. Affected products deleted and re-run |
| **Green-up onset fails in cloudy highlands** | Rwanda/Burundi **Season A** (the main season) yielded only ~64 planting pixels vs 3,365 maize pixels — S-2/S-1/FPAR cue fusion cannot find a sustained green-up under persistent equatorial-highland cloud | Route **Season A** to **rainfall-anchored** onset (CHIRPS 25/20 mm + climatology), the same method used for short/second seasons; full coverage restored |

---

## 7. Validation summary

- **Planting dekad (strong).** Kenya MAM 2024: **92.9 % within ±2 dekads** of 4.8 M farmer records;
  **100 % within the GIEWS calendar window**. Ethiopia Meher: **100 % in window**.
- **Yield (calibrated, honest).** After Yₘ recalibration, Kenya Long rains national bias is **+0.04 t/ha**
  (was +2.03) and held-out **MAE 0.61** (was 2.3). Kenya Short rains is **level-only** (r ≈ 0 — the
  model sets the right average but does not rank ASAL counties, consistent with the crop-cutting finding).
  Ethiopia Meher **MAE 0.41** (small n, 2024 model vs 2021 obs).
- **Coverage caveat.** 13 of 16 products use a **fallback Yₘ** — their CPI (the season-quality signal)
  is fully valid, but the absolute t/ha is provisional until each country's sub-national statistics
  are matched to admin polygons.

---

## 8. Reproducing the run

```bash
# environment: EE_PROJECT must be your Earth Engine cloud project
export EE_PROJECT=ee-manzikye

# 1) submit every viable 2024 maize product (250 m CPI/yield assets)
python run_all_maize_2024.py --stage all --submit

# 1b) richer stack (planting_dekad + 6 WRSI/WSI stage bands) for the app panels
python run_all_maize_2024.py --stage all --rich --submit

# 2) calibrate the yield ceiling Ym against HarvestStat (70/30), print paste-ready values
python calibrate_ym_all.py

# 3) watch the batch to completion
python poll_tasks.py --watch 300         # cpi_*  assets
python poll_rich.py  --watch 300         # cpiX_* assets

# 4) build the app data + notebook
python app_data.py                       # -> app_data.json embedded into pw_app.html / risk_app.html
python build_colab_all.py                # -> planting_pipeline_ALL_colab.ipynb
```

Interactive exploration for any single country/season is in **`planting_pipeline_ALL_colab.ipynb`**
(set `COUNTRY` / `SEASON`, run Modules 1–4). Onset method and cross-year handling are chosen from the
calendar automatically, so the notebook demo is the same computation as the operational run.

---

## 9. Key references

- Doorenbos & Kassam (1979) — FAO-33 stage yield-response factors (Ky).
- Allen et al. (1998) — FAO-56 crop water requirements / ET₀.
- Steduto, Raes et al. (2009) — AquaCrop multiplicative stress stacking.
- Kogan (1995) — Vegetation Condition Index.
- Butler & Huybers (2013) — maize flowering heat sensitivity.
- Rembold et al. (2019) — ASAP standardized anomalies (zFPAR).
- HarvestStat Africa v1.2 — harmonized sub-national African crop statistics (Zenodo).
- GEOGLAM Crop Monitor — reference crop calendars.

See `REFERENCES.md` for the full list.
