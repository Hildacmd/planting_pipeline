# Yield-Estimation Methodology — Maize, GHA / ICPAC

Estimates maize **yield (t/ha)** and **total production (t)** per admin unit by scaling a **reference
potential yield** by the season's **relative performance** (the Crop Performance Index), then multiplying
by harvested area — the standard **yield-gap** framing. Computed for all three seasons (Kenya Long +
Short rains, Ethiopia Meher).

## 1. Framing — the yield-gap identity

Actual yield is potential yield times the fraction actually achieved:
```
Ya = (Ya / Ym) · Ym
     Ya = actual yield · Ym = attainable/potential yield · (Ya/Ym) = relative performance (0–1)
```
Our relative performance is the **CPI/100** (multi-stress, stage-weighted; see `CPI_METHODOLOGY`). This is
the FAO / GYGA yield-gap approach [van Ittersum et al. 2013; Lobell et al. 2009].

## 2. Workflow at a glance

![Yield-estimation workflow](yield_estimation_diagram.png)

CPI (relative yield) × Ym (potential yield) → **yield (t/ha)**; × harvested area → **total production**;
→ admin aggregation → yield & production maps. A **calibration loop** tunes Ym and the stress parameters
against observed yields.

## 3. The estimation chain — formulas

### 3.1 Actual yield per hectare — `src/cpi.py`
```
Ya (t/ha) = (CPI / 100) · Ym
          = (1 − S_water)(1 − S_heat)(1 − S_veg) · Ym
S_water = Σ_stage Ky·(1 − AET_stage/WR_stage)   (FAO-33, stage-weighted)
S_heat  = HEAT_K · Σ_flowering max(0, Tmax − 33)
S_veg   = VEG_W · (1 − VCI)
```

### 3.2 Total production — `swap_shortrains.py`, `cpi_admin.py`
```
P (t) = Σ_pixels  Ya · pixel_area_ha            pixel_area_ha = 6.25 (250 m grid)
      = mean(Ya) · n_maize_pixels · 6.25
```

### 3.3 Admin aggregation
```
yield (t/ha) per unit  = median Ya over the unit's maize pixels        # median = robust
production (t) per unit = Σ Ya · pixel_area_ha over the unit
```

## 4. Reference potential yield `Ym`

Ym is the **water-unlimited attainable yield** for the variety and zone — the ceiling the relative
performance scales. Sources, best to lightest:
- **GYGA** (Global Yield Gap Atlas) rainfed water-limited potential `Yw` for Kenya/Ethiopia maize
  [van Ittersum et al. 2013; gyga.org] — the preferred, location-specific ceiling.
- **Crop-model potential** (AquaCrop / DSSAT run to water-limited yield) per AEZ.
- **Agronomic reference** (used in v1): short-duration maize ≈ **4.5 t/ha**, medium/long ≈ **6 t/ha**.

Ym should ideally vary by **AEZ maturity class** (early < medium < late potential); v1 uses a per-season
constant, flagged for calibration (§6).

## 5. Harvested area

```
maize area (ha) = (maize-mask pixels) · pixel_area_ha
```
Mask: ESA **WorldCereal** maize [Van Tricht et al. 2023]. **Season caveat:** the mask is annual and does
not distinguish which season a pixel is planted, so **short-rains total production is an upper bound**
(much of that maize is long-rains only). **Yield (t/ha) is the reliable figure**; production is
indicative until a season-specific cropped-area layer is used.

## 6. Calibration & validation (essential before operational use)

The estimates are **physically-grounded but uncalibrated**. Calibration regresses estimated vs
**observed** yields and tunes the free parameters:
```
minimise  Σ (Ya_est − Ya_obs)²   over  { Ym(zone,variety), Ky, HEAT_K, VEG_W }
observed sources:  KALRO / county agriculture returns · FAO GIEWS · HarvestStat Africa
                   [Lee et al. 2025] · national statistics (KNBS, CSA Ethiopia)
```
Validate with cross-validation and report bias/RMSE per admin level. The **CPI pattern and relative
yields are robust**; calibration fixes the **absolute scale**.

## 7. Where this sits among yield methods

| Approach | Basis | Note |
|---|---|---|
| Mechanistic crop models (AquaCrop, DSSAT/CERES, WOFOST) | full soil–crop–weather simulation | most rigorous, data-hungry |
| Remote-sensing empirical (NDVI/fAPAR → yield) | statistical regression | needs dense yield labels [Lobell 2013] |
| Light-use efficiency (Monteith) | fAPAR × PAR × ε | biomass, then harvest index |
| **This work — hybrid** | FAO-33 water balance + AquaCrop multiplicative stress stacking + RS condition (VCI), scaled to Ym | transparent, calibratable, admin-scale |

## 8. Caveats
- **Ym reference, not measured** — absolute yields need calibration (§6).
- **Total production = upper bound** for the short rains (annual mask, §5).
- **Resolution:** ~5.5–11 km climate content on the 250 m grid — an **admin-scale** estimate, not field-level.
- **Parameters (Ky, HEAT_K, VEG_W) first-pass** — refine against trials.

## 9. Measured (2024, L1 medians; Ym = 4.5 short / 6 main; spatial SoilGrids/Saxton WHC)
| Season | Yield (t/ha) |
|---|---|
| Kenya Long rains | 4.2 |
| Kenya Short rains | 2.84 |
| Ethiopia Meher | 4.5 |

## 10. References
- van Ittersum, M. K. et al. (2013). *Yield gap analysis with local to global relevance (GYGA).* Field Crops Research 143, 4–17. https://doi.org/10.1016/j.fcr.2012.09.009
- Lobell, D. B., Cassman, K. G. & Field, C. B. (2009). *Crop yield gaps: their importance, magnitudes, and causes.* Annu. Rev. Environ. Resour. 34, 179–204.
- Lobell, D. B. (2013). *The use of satellite data for crop yield gap analysis.* Field Crops Research 143, 56–64.
- Doorenbos, J. & Kassam, A. H. (1979). *Yield response to water (Ky).* FAO Irrigation & Drainage Paper 33.
- Steduto, P. et al. (2009). *AquaCrop — concepts and principles.* Agron. J. 101, 426–437.
- Monteith, J. L. (1972). *Solar radiation and productivity in tropical ecosystems.* J. Applied Ecology 9, 747–766.
- Van Tricht, K. et al. (2023). *WorldCereal.* Earth Syst. Sci. Data 15, 5491–5515.
- Lee, D. et al. (2025). *HarvestStat Africa.* Scientific Data. https://doi.org/10.1038/s41597-025-05001-z
- Kogan, F. N. (1995). *VCI/TCI.* Adv. Space Res. 15(11), 91–100.
- Butler, E. E. & Huybers, P. (2013). *Adaptation of US maize to temperature variations.* Nat. Clim. Change 3, 68–72.

*Code: `src/cpi.py`, `run_cpi_shortrains.py`, `run_cpi.py`, `cpi_admin.py`, `swap_shortrains.py`.
Companion docs: `CPI_METHODOLOGY`, `RISK_MONITORING_METHODOLOGY`, `APP_STATISTICS_GUIDE`.
Verify DOIs/editions before formal use.*
