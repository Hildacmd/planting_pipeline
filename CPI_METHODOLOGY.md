# Crop Performance Index (CPI) Methodology — Maize, GHA / ICPAC

The **Crop Performance Index** estimates maize **relative yield (Ya/Ym, 0–100)** by stacking independent
stresses — **water, heat, vegetation** — multiplicatively (AquaCrop / crop-model logic), each weighted
by growth stage. From CPI we derive **yield (t/ha)** and **total production (t)**. Computed for all three
seasons (Kenya Long + Short rains, Ethiopia Meher).

## 1. Pipeline at a glance

![CPI pipeline](cpi_diagram.png)

Staged water balance, ERA5-Land Tmax and MODIS NDVI → three stress fractions (**S_water, S_heat, S_veg**)
→ multiplicative stacking → **CPI** → **yield (t/ha)** and **total production** → admin aggregation.

## 2. The multiplicative model

Each hazard is an independent 0–1 yield reduction; surviving fractions multiply (a crop that loses 40 %
to water and 20 % to heat retains 0.6 × 0.8 = 48 %):
```
Ya/Ym = (1 − S_water) · (1 − S_heat) · (1 − S_veg)
CPI   = 100 · Ya/Ym                         (0 = total loss, 100 = potential)
```
Multiplicative stacking of independent stresses is the AquaCrop / crop-model convention
[Steduto et al. 2009; Raes et al. 2009].

## 3. The three stress components — `src/cpi.py`

### 3.1 Water stress `S_water` — FAO-33, stage-weighted
From the per-stage actual/required ET of the staged water balance (`run_wrsi_staged`):
```
S_water = clamp( Σ_stage  Ky_stage · (1 − AET_stage / WR_stage) , 0, 1 )
Ky:  vegetative 0.40 · flowering 1.50 · grain-fill 0.50
```
This is the FAO-33 water-limited yield reduction — the same Ky that stress-weights the risk monitor
[Doorenbos & Kassam 1979].

### 3.2 Heat stress `S_heat` — flowering heat
Maize is acutely heat-sensitive at silking (pollen sterility), so heat is accumulated **only during the
flowering stage** from ERA5-Land dekad-mean Tmax:
```
S_heat = clamp( HEAT_K · Σ_flowering max(0, Tmax_dekad − HEAT_TCAP) , 0, 1 )
HEAT_TCAP = 33 °C      HEAT_K = 0.06 per heat-degree-dekad
```
[Butler & Huybers 2013 — maize yield sensitivity to high temperature].

### 3.3 Vegetation stress `S_veg` — VCI (NDVI) or zFPAR (down-weighted confirmation)
Selectable index (`src/cpi.py`, env `VEG_INDEX`); default NDVI/VCI, optional ASAP-aligned FPAR anomaly:
```
'ndvi' (default): VCI   = (NDVI_peak − NDVI_min)/(NDVI_max − NDVI_min)   S_veg = VEG_W·(1 − VCI)
                  MODIS MOD13Q1, 250 m, current vs 2003–23                                [Kogan 1995]
'fpar' (opt.)   : zFPAR = (FPAR_peak − μ)/σ                              S_veg = VEG_W·clamp(−zFPAR/2,0,1)
                  MODIS MCD15A3H, 500 m — JRC-ASAP vegetation anomaly                  [Rembold 2019]
VEG_W = 0.40
```
Vegetation condition is a *response*, not a driver, and the short-rains signal is weak — so it is
**down-weighted** and acts as a confirmation on the physical (water/heat) stresses. Default is NDVI/VCI
(finer grid, standard condition index); the FPAR/zFPAR option aligns the anomaly with JRC-ASAP.

## 4. Yield and production
```
yield (t/ha) = CPI/100 · Ym
total (t)    = yield · maize_area_ha        (250 m pixel = 6.25 ha; area from the maize mask)
Ym (reference potential):  short-duration maize ≈ 4.5 t/ha · medium/long ≈ 6 t/ha
```

## 5. Parameters (v1)

| Parameter | Value | Meaning |
|---|---|---|
| Ky (veg / flo / grf) | 0.40 / 1.50 / 0.50 | FAO-33 stage yield-response factors |
| HEAT_TCAP | 33 °C | dekad-mean Tmax above which flowering is hurt |
| HEAT_K | 0.06 | yield loss per heat-degree-dekad at flowering |
| VEG_W | 0.40 | vegetation-condition weight |
| Ym | 4.5 / 6.0 t/ha | reference potential (short / main season) |

## 6. Calibration & caveats — read this

- **Ym is a reference, not a measurement.** The CPI *pattern* and the *relative* yields across
  zones/seasons are robust; **absolute yields require calibration** of Ym against observed yields
  (KALRO, FAO/GIEWS, HarvestStat Africa) before operational use.
- **Total production assumes the whole maize mask plants each season.** The WorldCereal mask does not
  distinguish season, so **short-rains totals are an upper bound** (much of that maize is long-rains
  only). Treat **yield (t/ha)** as the reliable figure; total production as indicative.
- **Parameters (HEAT_K, VEG_W, HEAT_TCAP) are first-pass**; refine against local trials.
- **Resolution:** CPI inherits ~5.5–11 km climate content on the 250 m grid — an admin-scale estimate.

## 7. Measured (2024, L1 medians)

| Season | CPI | Yield (t/ha) |
|---|---|---|
| Kenya Long rains | 70 | 4.2 |
| Kenya Short rains | 63 | 2.84 |
| Ethiopia Meher | 75 | 4.5 |

Main seasons out-score the marginal short rains, as expected. Values are on the **spatial
SoilGrids/Saxton–Rawls WHC** basis (§ Risk-Monitoring 3.7); replacing the earlier flat 100 mm shifted
only the Long rains (CPI 73→70) — the spatial WHC differs from the national aggregate most in specific
semi-arid units, not the median.

## 8. References
- Steduto, P. et al. (2009). *AquaCrop — concepts and principles.* Agron. J. 101, 426–437.
- Raes, D. et al. (2009). *AquaCrop — algorithms and software.* Agron. J. 101, 438–447.
- Doorenbos, J. & Kassam, A. H. (1979). *Yield response to water (Ky).* FAO Irrigation & Drainage Paper 33.
- Butler, E. E. & Huybers, P. (2013). *Adaptation of US maize to temperature variations.* Nat. Clim. Change 3, 68–72.
- Kogan, F. N. (1995). *VCI/TCI for drought detection.* Adv. Space Res. 15(11), 91–100.
- Rembold, F. et al. (2019). *ASAP: a new anomaly hot spots of agricultural production system.* Agric. Systems 168, 247–257.
- Allen, R. G. et al. (1998). *Crop evapotranspiration.* FAO-56.
- Van Ittersum, M. K. et al. (2013). *Yield gap analysis (GYGA) — a review.* Field Crops Research 143, 4–17.

*Code: `src/cpi.py`, `run_cpi_shortrains.py`, `run_cpi.py`, `cpi_admin.py`. Risk context:
`RISK_MONITORING_METHODOLOGY`. App numbers: `APP_STATISTICS_GUIDE`.*
