# In-Season Risk Monitoring — Design Spec (v1, frozen)

**Status:** design frozen (numbers agreed) · **not yet implemented.** A separate module from the
seasonal planting-window estimator; it re-runs each dekad through the maize cropping season.
**Region/crop:** GHA / ICPAC · **MAIZE only for now** (Kenya Long+Short rains, Ethiopia Meher); wheat
and teff are a later extension, and sorghum/pearl millet need the photoperiod branch (§2a) first.
**Stage timing** comes from the GDD Phenology Clock (`GDD_Phenology_Clock_Workflow.docx`, v2.1); this
doc specifies the *risk weighting* applied on top of it.

## 1. Concept

Continuous (dekadal) agricultural-risk monitoring in the **ASAP** style (JRC Anomaly hot Spots of
Agricultural Production): per-pixel climatological anomalies, **confirmed over time** (not one-off),
**weighted by the phenological stage** the pixel is in (an anomaly at silking hurts far more than at
ripening), masked to **maize area**, and aggregated to admin units by the **% of crop area affected**.

Stage is set by a **Growing-Degree-Day (GDD) thermal clock**, not the calendar.

## 2. GDD phenology clock — the stage-timing engine

The stage a field is in is produced by the **GDD Phenology Clock** (authoritative spec:
`GDD_Phenology_Clock_Workflow.docx`, v2.1). The risk module does **not** re-derive stages; it consumes
the clock's per-field flowering/maturity dates and applies the Ky weights (§3) on top.

**2a — Crop/cultivar split (Stage 2, decisive).** Route each field to a **thermal** or **photoperiod**
clock *before* accumulating. Maize (our current crop) and improved wheat are **thermal** — a fixed
thermal-time target to flowering is valid. **Landrace sorghum & pearl millet are photoperiod-sensitive**:
they flower on shortening daylength near end-of-rains, ~independent of sowing date, so GDD-from-SOS
predicts them weeks late. Scaling risk to Sudan/Eritrea millet **requires the photoperiod branch**
(threshold–hyperbolic, daylength from lat×DOY); where cultivar is unknown in the semi-arid north,
default to PP-sensitive.

**2b — GDD accumulation (Stage 4a, thermal branch — maize).**
```
GDD_day = max(0, (Tmax + Tmin)/2 − Tbase)   # maize Tbase 8–10 °C, cap Tmax at Tcap (~30 °C)
GDD_cum = Σ GDD_day from the SOS anchor (emergence); keep Tbase & stage target on the SAME anchor
```

**2c — Temperature input (Stage 3, redesigned).** Daily **air** Tmax/Tmin from **AgERA5 / ERA5-Land**
(blend **CHIRTS-daily** in data-sparse zones), **DEM lapse-corrected to 30 m** — elevation drives the
fine GDD signal. For Ethiopia use the **Wakjira et al. 2023** debiased daily 2 m product. **Never** use
land-surface temperature (LST) or 30 m Landsat thermal as the temperature itself (skin ≠ air; a single
8–16 d snapshot cannot build a daily Tmax/Tmin series).

**2d — Stage dates & calibration (Stages 5–6).** Roll SOS → flowering → maturity on thermal time.
Flowering (the Ky 1.5 window) is a **calibrated date**, not a fixed GDD fraction: the loop compares the
predicted flowering to the **observed EVI/NDVI peak** per field and tunes Tbase / the thermal-time
target (or Pcrit on the PP branch) per crop×zone — no ground truth required. A **Sentinel-1 SAR**
backscatter turnaround gives an independent structural second check. The **AEZ maturity class** (early
1300 / medium 1500 / late 1700 °C·d) seeds `GDD_maturity` as the prior before calibration.

## 3. Stage markers the clock predicts, and the Ky weighting

**Scope: MAIZE only for now** (thermal branch). Wheat/teff later; sorghum & pearl millet need the
photoperiod branch (§2a).

The GDD clock (§2, `src/gdd_clock.py`) emits four **stage-transition dekads** per pixel, at these GDD
fractions of the AEZ-seeded `GDD_maturity` (seed fractions; the flowering marker is recentred by the
EVI-peak calibration, §2d):

| Marker (clock band) | GDD fraction | Maize event |
|---|---|---|
| `peak_vegetative_dekad` | 0.45 | VT tasseling — end of vegetative growth / canopy peak |
| `flowering_dekad` | 0.55 | R1 silking — critical water/heat window |
| `grain_filling_dekad` | 0.65 | R2/R3 — yield formation begins |
| `maturity_dekad` | 1.00 | R6 physiological maturity — **end of season** |

The risk stage-weighting rides on the **intervals** between the markers (FAO-33 Ky), so an anomaly is
weighted by whichever interval the pixel is in at that dekad:

| Interval | Growth phase | Ky |
|---|---|---|
| SOS → peak-vegetative | Vegetative | **0.40** |
| **peak-vegetative → grain-filling** | **Flowering / reproductive (critical)** | **1.50** |
| grain-filling → maturity | Grain filling & ripening | **0.50** |
| whole season | — | 1.25 |

A water/heat hit at silking therefore counts ~3–4× the same anomaly during vegetative growth or grain
fill. `maturity_dekad` is the predicted **end of season**, closing the seasonal-risk accumulation.

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
