# In-Season Risk Monitoring — Design Spec (v1, frozen)

**Status:** design frozen (numbers agreed) · **not yet implemented.** A separate module from the
seasonal planting-window estimator; it re-runs each dekad through the maize cropping season.
**Region/crop:** GHA / ICPAC · maize (Kenya Long+Short rains, Ethiopia Meher; extensible).

## 1. Concept

Continuous (dekadal) agricultural-risk monitoring in the **ASAP** style (JRC Anomaly hot Spots of
Agricultural Production): per-pixel climatological anomalies, **confirmed over time** (not one-off),
**weighted by the phenological stage** the pixel is in (an anomaly at silking hurts far more than at
ripening), masked to **maize area**, and aggregated to admin units by the **% of crop area affected**.

Stage is set by a **Growing-Degree-Day (GDD) thermal clock**, not the calendar.

## 2. GDD phenology clock

```
GDD_day = clamp(Tmean − 10, 0, 20)          # maize: base 10 °C, upper cap 30 °C; Tmean = ERA5-Land
GDD_cum = Σ GDD_day from the detected planting dekad
stage   = GDD_cum / GDD_maturity
```
`GDD_maturity` (°C·d) from the **AEZ maturity class already produced by the pipeline**:

| Maturity class | GDD to maturity |
|---|---|
| Early (dry lowland, short-cycle) | 1300 |
| Medium | 1500 |
| Late (humid highland, long-cycle) | 1700 |

## 3. Stage boundaries (fraction of GDD-to-maturity) — LOCKED

| Stage fraction | Maize phase | Ky (FAO-33) |
|---|---|---|
| 0.00–0.45 | Establishment + Vegetative (VE→V12) | **0.40** |
| **0.45–0.60** | **Flowering (VT tasseling → R1 silking)** | **1.50** |
| 0.60–0.80 | Yield formation / grain fill (R2→R4) | **0.50** |
| 0.80–1.00 | Ripening (R5→R6 physiological maturity) | **0.20** |
| — | Whole season | 1.25 |

Flowering window locked **tight (0.45–0.60)** — tasseling→silking only, the true critical
water/heat period.

## 4. Hazards — FROZEN v1

All hazards are per-pixel anomalies vs a **per-pixel historical climatology**, require **persistence
(≥ 2 consecutive dekads)**, and are **stage-weighted by Ky** before admin aggregation.

| # | Hazard | Indicator (vs climatology) | Data (baseline) | Persistence |
|---|---|---|---|---|
| H1 | **Water / drought** | (a) **SPI-3** ≤ −1 moderate / ≤ −1.5 severe; (b) crop-water deficit `1−ETa/ETm` ×Ky | CHIRPS gamma-fit 1981– ; FAO-33/WRSI balance | SPI-3 ≥ 2 consecutive dekads |
| H2 | **Heat stress** | days Tmax > 35 °C in the flowering window, anomaly vs normal ×Ky(flower)=1.5 | ERA5-Land ~30–45 yr | within flowering, ≥ 2 dekads |
| H3 | **Vegetation (confirmation)** | NDRE/NDVI **VCI** z-score vs per-pixel multi-year mean | MODIS/S2 | confirms a driver; not standalone |
| H4 | **Onset / establishment failure** | detected onset − LTN onset normal (delay > 2 dekads, or no onset) | CHIRPS + RS onset normals | early-season, pre-GDD-clock |

## 5. Headline outputs — FROZEN

1. **Crop Performance Index (CPI)** — stage-weighted relative yield (FAO-33 water-limited closure):
   `CPI = 100 · [ 1 − Σ_stage Ky·(1 − ETa/ETm)_stage ]`, clamped 0–100. Yield-relevant, stage-weighted
   sibling of WRSI (which is un-weighted water satisfaction).
2. **Crop-failure %** — % of maize area (CAF) where CPI (or WRSI) is in the failure class (< 50).
   The ASAP headline number per admin unit.
3. **Per-hazard risk maps** (H1–H4) and a **combined hotspot** map (any hazard active).

## 6. ASAP admin closure — % of maize area affected

For each admin unit and hazard/output, using **CAF** (crop area fraction) as the maize denominator:

| % of maize area affected | ASAP class |
|---|---|
| ≥ 25 % | Watch |
| ≥ 50 % | Alert |
| ≥ 75 % | Critical |

## 7. Temporal products

- **10-day (dekadal)** — instantaneous stage-weighted risk each dekad (live frame).
- **Monthly** — 3-dekad aggregate (bulletin cadence).
- **Seasonal** — cumulative over planting→maturity; the seasonal CPI and crop-failure % are the
  end-of-season summary.

## 8. Reuse of existing pipeline assets

Planting dekad ✓ · ERA5-Land T (ET₀/GDD) ✓ · AEZ maturity → GDD_maturity ✓ · FAO-33 Ky (sibling of
the WRSI Kc curve) ✓ · WRSI ETa/ETm & failure class ✓ · CHIRPS ~45 yr → SPI-3 · LTN onset normal (H4)
· CAF (maize denominator).

## 9. References

- Doorenbos, J. & Kassam, A.H. (1979). *Yield response to water.* FAO Irrigation & Drainage Paper 33. (Ky)
- Allen, R.G. et al. (1998). *Crop evapotranspiration.* FAO-56. (Kc, ET₀)
- McKee, T.B. et al. (1993). *The relationship of drought frequency and duration to time scales.* (SPI)
- Funk, C. et al. (2015). *CHIRPS.* Scientific Data 2:150066.
- Muñoz-Sabater, J. et al. (2021). *ERA5-Land.* ESSD 13, 4349–4383.
- Rembold, F. et al. (2019). *ASAP: a new global early warning system…* Agricultural Systems 168, 247–257. (25%-area hotspot method)

---
*Frozen [design date TBD]. Implementation is a follow-on module; not built yet.*
