# New Methodologies & Changes — September 2026

**ICPAC Planting Pipeline · Greater Horn of Africa · maize · 2026-09**

This document records the methodologies **added or changed in September 2026**, the algorithms behind
each, and where each change lands in the codebase and the other methodology documents. It supplements
(does not replace) `CPI_METHODOLOGY.md`, `RISK_MONITORING_METHODOLOGY.md`,
`WATERLOGGING_METHODOLOGY.md`, `YIELD_ESTIMATION_METHODOLOGY.md`, `KENYA_SEASON_REGIMES.md`, and the
as-built run record `ALL_COUNTRIES_2024.md`.

---

## 1. Summary of changes (changelog)

| # | Change | Where | Why |
|---|--------|-------|-----|
| 1 | Extended the run from 3 validated products to **all 16 GHA maize seasons** | `run_all_maize_2024.py`, assets `cpi_*`/`cpiX_*` | Continental coverage for 2024 |
| 2 | **Rich band stack** `cpiX_*` (adds `planting_dekad` + 6 WRSI/WSI stage bands) | `run_all_maize_2024.py --rich`, `build_product_image()` | Feed the app panels for new countries |
| 3 | **WHC western-footprint gap-fill** | `src/soil.py get_whc` | Cached WHC ended at 32.3°E → Rwanda/Burundi empty, W-Uganda/Tanzania/S-Sudan clipped |
| 4 | **Season A → rainfall-anchored onset** | `run_all_maize_2024.py RAINFALL_ANCHORED` | Green-up fails in Rwanda/Burundi cloudy highlands (64 vs 3365 px) |
| 5 | **Cross-year onset (Msimu)** dekad-wrap | `src/utils.py`, s2/s1/fusion builders | Dec→Feb seasons span the year boundary |
| 6 | **Tier-1 app metrics** from the rich stack | `reduce_newcountries.py` | ASAP crop-failure, crop-area-fraction, phenology, mean WRSI for the apps |
| 7 | **Tier-2 app metrics** (SPI-3, deficit, LVPD, VCI) | `reduce_newcountries_tier2.py`, `backfill_deficit.py` | Complete the risk panels |
| 8 | **VCI from S_veg identity** (no extra GEE) | `reduce_newcountries_tier2.py` | Cheap, exact canopy-condition metric; replaces heavy FCCI fusion |
| 9 | **Per-polygon reduction** under compute throttle | `backfill_deficit.py`, `run_shortrains_regime.py` | Heavy graphs starve `reduceRegions`; single `reduceRegion` per admin works |
| 10 | **Kenya short-rains regime-specific windows** (PROVISIONAL) | `run_shortrains_regime.py`, `config/ond_regime_windows.csv` | Western/Rift bimodal counties plant Aug–Sep, not Oct–Nov |
| 11 | Season-comparison chart label overlap fixed | `risk_app.html` (`drawSeason`) | 16 seasons overlapped on the axis |

Downstream doc updates: `ALL_COUNTRIES_2024.md` (product table, gaps table), `KENYA_SEASON_REGIMES.md`
(regime windows), this file.

---

## 2. Algorithms, step by step

### A. Continental product build (`build_product_image`)

One reusable graph builds every country/season and returns the output image plus intermediates.

1. **AOI** from GAUL level-0; **season window** `(ss, se)` from `config/season_calendar.csv`.
2. **Onset:**
   - *Main seasons* → cue-fusion green-up (S2 NDRE + MODIS FPAR + S1 SAR gap-fill) → SOS → planting.
   - *Short/second seasons* → rainfall-anchored (CHIRPS 25/20 mm + P/PET), climatology-filled.
   - *Cross-year* (`ss > se`, e.g. Tanzania Msimu Dec→Feb) → build from year − 1 with dekads extended
     past 36 (`dekad_to_start_date` wraps).
3. **Staged FAO-56/33 water balance** (veg → flo → grf) → WRSI/WSI per stage.
4. **Stresses:** `S_water` (FAO-33 Ky-weighted), `S_heat` (flowering heat-degree-dekads),
   `S_veg` (down-weighted VCI/FPAR).
5. **CPI** `= 100·(1−S_water)(1−S_heat)(1−S_veg)`; **yield** `= (CPI/100)·Ym` (AEZ-aware calibrated Ym).
6. **Rich export** (`--rich`) appends `planting_dekad`, `wrsi_veg/flo/grf`, `wsi_veg/flo/grf` → `cpiX_*`.

### B. WHC western-footprint gap-fill (`src/soil.py get_whc`)

**Problem:** the materialized asset `whc_saxton_soilgrids_gha_250m` was exported only east of ~32.3°E;
west of it WHC was masked, collapsing the whole water balance (S_water, WSI, CPI empty).

**Fix:**
```
cached = ee.Image(whc_asset)
fill   = build_whc_saxton_mm(...)                     # live SoilGrids + Saxton-Rawls, global
whc    = cached.unmask(fill, sameFootprint=False)     # cached where present, SoilGrids elsewhere
```
`sameFootprint=False` is essential — the default (True) will not fill *outside* the cached asset's
footprint. No data download is needed: SoilGrids (`projects/soilgrids-isric/*`) is global on GEE.

### C. Onset routing fixes

- **Season A** (Rwanda/Burundi main season) added to `RAINFALL_ANCHORED`: their persistently cloudy
  equatorial highlands defeat green-up (64 planting px vs 3,365 from rainfall onset over the maize mask).
- **Cross-year wrap:** `dekad_to_start_date(year, dekad)` now advances the year while `dekad > 36`;
  the S2/S1/FPAR base collections filter to `dekad_to_start_date(year, max(dekads)+2)`.

### D. App admin-metric derivation — Tier-1 (`reduce_newcountries.py`)

Reduces the rich `cpiX_*` bands to admin-1/2 (local GADM 4.1 geometry + GEE `reduceRegions`), median
for 0–100 bands. Derived, all from bands already on GEE:

- **crop_area_frac** = mean of the maize mask (unmasked to 0) over the admin unit.
- **mean_WRSI** = mean of `(wrsi_veg + wrsi_flo + wrsi_grf)/3` over maize pixels.
- **fail_pct (ASAP crop-failure)** = % of maize pixels with **seasonal-min WRSI < 50**.
- **failflo_pct** = % of maize pixels with `wrsi_flo < 50` (flowering failure).
- **phenology stage dekads** from modal planting + FAO-56 durations:
  `pkv = md + L_ini + L_dev`, `flo = pkv + ⌈L_mid/2⌉`, `grf = pkv + L_mid`, `mat = grf + L_late`
  (durations: standard maize LGP 12 for green-up seasons, EARLY LGP 9 for rainfall seasons; wrap 1–36).

### E. App admin-metric derivation — Tier-2 (`reduce_newcountries_tier2.py`)

Each metric is its own `reduceRegions` request (a single combined request is too heavy and hangs).

- **SPI-3 (drought)** — `src/spi.py spi3(aoi, year, end_month)` (Wilson-Hilferty gamma, CHIRPS,
  1981–2020 baseline). Report `spi3_mean` and `spi3_dry_pct` = % pixels with SPI-3 ≤ −1.
- **Water deficit (mm)** — `run_wrsi_fao33(..., planting_dekad_img, ...)['deficit_mm']`, reusing the
  `planting_dekad` band already in the `cpiX_` asset (no fusion re-run).
- **LVPD (last-viable-planting)** — climatological `LGP_end + RESIDUAL − EARLY_CYCLE`, where
  `LGP_end` = latest dekad with `P/PET ≥ 0.5` over the 44-yr CHIRPS climatology; `crop_viable_pct` =
  % maize pixels with `planting ≤ LVPD`.
- **VCI (canopy condition)** — see §F.

### F. VCI from the S_veg identity (no extra GEE)

The CPI's vegetation stress is `S_veg = VEG_W·(1 − VCI)` with `VEG_W = 0.4`, stored as a 0–100 band
(`S_veg_col = 40·(1 − VCI)`). VCI is therefore **exactly recoverable** from the already-reduced S_veg,
and because the transform is linear the admin median commutes:

```
VCI = 100·(1 − S_veg_col / 40)        # 0–100, high = good canopy
```

This replaces the heavy S2/S1/FPAR **FCCI fusion** (which is expensive to evaluate live per admin unit)
with a zero-cost, exact vegetation-condition metric, written into the app's "Canopy condition" column.

### G. Per-polygon reduction under compute throttle

The FAO-56 water-balance deficit graph is heavy. Under GEE free-tier **restricted mode**,
`reduceRegions` over a whole FeatureCollection **starves and returns null**, while a single
`reduceRegion` over **one admin polygon** is light enough to succeed (slower, but complete).
`backfill_deficit.py` loops one polygon at a time and writes each CSV durably. Use this pattern for any
heavy live metric under the throttle (also used by `run_shortrains_regime.py`).

---

## 3. Kenya short-rains regime-specific windows (PROVISIONAL) — `run_shortrains_regime.py`

### Problem
The national short-rains onset window is **Oct-d1–Nov-d3 (dk 28–33)**. Western/Rift **bimodal**
counties plant their second season **Aug–Sep** (some late-Aug), so a single window pins them all to the
window edge (dk 28–29), erasing the real Aug–Sep signal.

### Evidence (from `config/ond_regime_windows.csv`, `Cropyield-Data/ond_regimes.csv`)
- OND farmer survey (825 dated records, 30 counties): **median Sep-d2 (dk ~25); 82.9% before dk 28**.
- Growing Season Planner (14,301 cells, independent): bimodal, 56% before dk 28.
- Earliest onsets: **Garissa dk 23 (Aug-d3)**, Nyandarua dk 24, Busia/Isiolo/Kakamega/Vihiga dk 25.
  **No county reaches July (dk 19–21)** in any validated record — the earliest is late August.

### Algorithm
1. **Regime assignment** (`Cropyield-Data/ond_regimes.csv`): 18 western/Rift counties = *early*
   (Aug–Sep); eastern/coastal = *late* (Oct–Nov). County names aliased to GADM `NAME_1`.
2. **Regime mask:** paint the early-county polygons onto a GEE image (`early_img = 1` there).
3. **Two onsets** (rainfall-anchored, year-2024 unmasked by 44-yr CHIRPS climatology):
   - `onset_early` over **early window** (Aug-d3–Oct-d2, dk 24–29),
   - `onset_late` over **late window** (Oct-d1–Nov-d3, dk 28–33).
4. **Mosaic:** `planting = onset_late.where(early_img, onset_early)`.
5. **Re-reduce** the planting distribution (modal / mean / p10 / p50 / p90) per admin unit
   (per-polygon under throttle, §G) and update **only the planting columns** of the `ke_short` skill CSVs.

### Caveats (why this is PROVISIONAL, and labeled so in the app)
- Held-out validation is significant **only at the boundary** (CI lower bound +0.00, n = 16) — see
  `KENYA_SEASON_REGIMES.md` sec 7. Re-test against a second season of OND survey data before adopting
  by default.
- **~39%** of mapped western short-rains area may be the **standing long-rains crop**, not a new
  planting; the rainfall onset can fire on the long-rains tail, pinning early counties near the window
  start (e.g. Bungoma → dk 24).

### Open items (under review)
- **Bomet:** classified *late* (dk 35, Nov-d2) on **Insurance Atlas** records (n = 22, only n = 2 survey).
  dk 35 is later than every eastern county and contradicts its Mau/Rift **bimodal** neighbours
  (Nandi dk 26, Narok dk 26.5, all *early*). **Recommended reassignment to *early*** pending confirmation.
- **Window start:** the *early* window at dk 24 clips Garissa's dk 23; widening the start to
  **dk 22 (Aug-d1)** captures the genuine late-August tail without asserting an (unsupported) July window.

---

## 4. Affected files

- Pipeline: `run_all_maize_2024.py`, `src/soil.py`, `src/utils.py`, `src/s2_preprocess.py`,
  `src/s1_preprocess.py`, `src/fusion_phenometrics.py`, `src/cpi.py`.
- App data: `reduce_newcountries.py`, `reduce_newcountries_tier2.py`, `backfill_deficit.py`,
  `run_shortrains_regime.py`, `app_data.py`, `embed_app_data.py`, `pw_app.html`, `risk_app.html`.
- Notebook & docs: `planting_pipeline_ALL_colab.ipynb`, `ALL_COUNTRIES_2024.md/.docx`, this file.
- Config/reference: `config/season_calendar.csv`, `config/ond_regime_windows.csv`,
  `Cropyield-Data/ond_regimes.csv`, `newc_*_skill_WKT.csv`.
