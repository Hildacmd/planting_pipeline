# Risk-Monitoring Methodology — Maize, GHA / ICPAC

In-season, **stage-weighted**, **ASAP-style** agricultural-risk monitoring for maize (Kenya Long + Short
rains, Ethiopia Meher). Per-pixel climatological anomalies are computed dekad-by-dekad, weighted by the
growth stage, masked to the maize area, and aggregated to admin units by the **% of crop area affected**.

## 1. Pipeline at a glance

![Risk-monitoring pipeline](risk_monitoring_diagram.png)

Inputs (CHIRPS, ERA5-Land, MODIS/S2 NDVI, **SoilGrids texture → WHC**, planting + GDD clock,
WorldCereal maize) → four indicator families (**water, drought, vegetation, heat**) → **stage
weighting (FAO-33 Ky)** → **ASAP** admin aggregation (25/50/75 % of crop area) → the Risk Monitor.

## 2. Risk metrics selected for monitoring

| Metric | Family | What it detects | Direction |
|---|---|---|---|
| **WRSI** (whole-season & running) | water | crop water-need satisfaction | higher = safer |
| **Stage WRSI** (veg / flo / grf) | water | *when* satisfaction erodes | higher = safer |
| **WSI** (dekadal water stress) | water | the stress in each dekad/stage | higher = worse |
| **Crop-failure %** (season & @ flowering) | water | share of maize area with WRSI < 50 | higher = worse |
| **Water deficit (mm)** | water | cumulative unmet demand | higher = worse |
| **SPI-3** | drought | 3-month rainfall anomaly | − dry / + wet |
| **SPI-3 drought %** | drought | share of maize area SPI-3 ≤ −1 | higher = worse |
| **VCI (NDVI) / zFPAR** (confirm) | vegetation | canopy condition vs history | lower = worse |
| **Heat @ flowering** (in CPI) | heat | silking heat exposure | higher = worse |
| **CPI, yield** | composite | multi-stress relative yield | higher = safer |
| **SPI-3 wet %** | excess | surface/seasonal excess-wet, anomaly-based (wet-side) | higher = worse |
| **Soil-waterlogging index** (modelled, uncal.) | excess | root-zone aeration stress (soil-water model) | higher = worse |
| **Viability %, LVPD** (short rains) | onset | can the crop still succeed | — |

**Why these:** water is the dominant maize constraint in the GHA (WRSI/deficit/SPI-3); the stage split
isolates the *critical* flowering window; VCI and heat capture condition and thermal stress the water
balance misses; CPI integrates them into a yield-relevant score. Selection follows the JRC **ASAP**
indicator set [Rembold 2019] and FEWS/GeoWRSI [Verdin & Klaver 2002; Senay & Verdin 2003].

## 3. Algorithms & formulas

### 3.1 WRSI water balance (FAO-56/33) — `src/wrsi_waterbalance.py`
Dekadal balance from the pixel's planting dekad, wrapping into year+1 for the short rains:
```
ET₀   = Hargreaves(Tmax, Tmin, Ra(lat, DOY))                 # FAO-56 temperature method
WR    = Kc(days-since-planting) · ET₀                        # crop water requirement (mm)
Wb    = SW + P ;  AET = min(Wb, WR) ;  SW = min(Wb − AET, WHC)
WRSI  = 100 · ΣAET / ΣWR       deficit = Σ(WR − AET)
class: ≥95 no-stress · 80–95 good · 60–80 mediocre · 50–60 poor · <50 FAILURE
```
`WHC` (the soil bucket the balance fills and drains) is a **spatial, physically-derived** field — see
§3.7. The risk/CPI runs now pass this WHC into the balance (`SOIL.get_whc → run_wrsi_staged(whc_img=…)`);
the earlier flat 100 mm constant is retired.

### 3.2 Running WRSI, dekadal WSI, and the three-stage snapshots — `run_wrsi_staged`
The balance is accumulated dekad-by-dekad; a **running WRSI** and the **dekadal water stress** are
snapshotted at the end of the three FAO growth stages (vegetative = initial+dev · flowering = mid-season
· grain-fill = late):
```
running WRSI(t) = 100 · ΣAET(≤t) / ΣWR(≤t)
WSI_dekad       = 1 − AET_t / WR_t                            # 0–1 water stress in dekad t
wrsi_{veg,flo,grf} = running WRSI at that stage-end dekad
wsi_{veg,flo,grf}  = max WSI within the stage
crop-failure @ flowering = ( wrsi_flo < 50 )
```

### 3.3 SPI-3 drought (Wilson–Hilferty gamma) — `src/spi.py`
```
P3   = 3-month CHIRPS total (year-wrap aware)
a    = (μ/σ)²                                                 # gamma shape (method of moments)
SPI  = ((P3/μ)^(1/3) − 1 + 1/(9a)) · √(9a)                    # ≤ −1 mod · ≤ −1.5 sev drought
```
μ, σ = climatological mean/SD of P3 for the same period (CHIRPS 1981–2020).

### 3.4 Vegetation condition — VCI (NDVI) or zFPAR (ASAP-aligned)
Two selectable indices for the vegetation-stress term `S_veg` (`src/cpi.py`, env `VEG_INDEX`):
```
default  'ndvi' :  VCI  = (NDVI − NDVI_min)/(NDVI_max − NDVI_min)   S_veg = VEG_W·(1 − VCI)   [Kogan 1995]
                   MODIS MOD13Q1 NDVI, 250 m — matches the product grid
opt.     'fpar' :  zFPAR = (FPAR − μ)/σ                             S_veg = VEG_W·clamp(−zFPAR/2, 0, 1)
                   MODIS MCD15A3H FPAR, 500 m — the JRC-ASAP vegetation anomaly [Rembold 2019]
```
Both use the **seasonal-peak** value, current vs the historical distribution (2003–23). Default is
**NDVI/VCI** (finer 250 m, and VCI is the standard condition index); the **FPAR/zFPAR** option aligns
the vegetation anomaly with JRC-ASAP. Either way the term is **down-weighted** (`VEG_W = 0.4`) — a
confirmation on the physical water/heat stresses, not a driver (short-season NDVI/FPAR signal is weak).
Note FPAR *also* feeds the planting **cue fusion** (green-up/SOS detection), a separate use from this
in-season anomaly.

### 3.5 Stage weighting — FAO-33 Ky
An anomaly is weighted by the **yield-response factor** of the stage the pixel is in (from the GDD clock):
```
Ky:  vegetative 0.40 · flowering 1.50 (critical) · grain-fill 0.50
```
So a hit at silking counts ~3–4× the same anomaly during vegetative growth or grain fill
[Doorenbos & Kassam 1979].

### 3.6 ASAP admin aggregation — % of crop area affected
For each admin unit, using **CAF** (crop area fraction = maize px / total px) as the maize denominator:
```
affected% = maize-area with [hazard active & persistent ≥ 2 dekads] / maize-area
class:  ≥ 25% Watch · ≥ 50% Alert · ≥ 75% Critical           [Rembold 2019]
```
Reducers: **median** for dekad quantities; **mean** for the affected fraction.

### 3.7 Soil water-holding capacity (WHC) — SoilGrids texture + Saxton–Rawls — `src/soil.py`

WRSI/WSI/crop-failure are only as good as the **soil bucket** (WHC) the water balance fills and drains,
and that bucket varies sharply across the GHA (deep clay vs shallow sand). WHC is built **spatially and
physically**, with **both** field capacity and wilting point derived — no proxy:

![Soil-WHC workflow](soil_whc_diagram.png)

**Data provenance — derived, not downloaded.** ISRIC **SoilGrids 2.0** publishes *measured* soil
properties (sand, clay, SOC over 6 depth layers), hosted on GEE and read server-side — it does **not**
publish ready field-capacity/wilting-point/AWC layers. Those are **computed here** from texture with the
**Saxton & Rawls (2006)** pedotransfer functions (the field-standard approach):

```
inputs (per depth layer): Sa = sand fraction, Cl = clay fraction, OM = 1.724 · SOC%
wilting point   θ₁₅₀₀ = θ₁₅₀₀ₜ + (0.14·θ₁₅₀₀ₜ − 0.02)                              (WP)
  θ₁₅₀₀ₜ = −0.024Sa + 0.487Cl + 0.006OM + 0.005(Sa·OM) − 0.013(Cl·OM) + 0.068(Sa·Cl) + 0.031
field capacity  θ₃₃   = θ₃₃ₜ + (1.283·θ₃₃ₜ² − 0.374·θ₃₃ₜ − 0.015)                    (FC)
  θ₃₃ₜ   = −0.251Sa + 0.195Cl + 0.011OM + 0.006(Sa·OM) − 0.027(Cl·OM) + 0.452(Sa·Cl) + 0.299
AWC(z) = θ₃₃(z) − θ₁₅₀₀(z)                                    # plant-available fraction, per layer
WHC(mm) = Σ_layers AWC(z) · thickness(z)                      # clipped at FAO-56 rooting depth (maize 1.0 m)
```

**Static → materialize once.** Texture is time-invariant, so `get_whc()` returns a server-side image EE
caches; for production it is exported **once** (`export_whc_to_asset`, stays in EE; or
`export_whc_to_drive`, a single GeoTIFF) and referenced via `soil_cfg['whc_asset']` — nothing recomputes
or re-downloads per run. Legacy OpenLandMap FC (with a 0.45·FC wilting-point proxy) remains selectable
via `whc_source: openlandmap`.

**Effect (2024 sample, 100 cm root zone).** Saxton WHC is tighter and more physical than the proxy:

| Site | Saxton WHC (mm) | old OpenLandMap (mm) |
|---|---|---|
| Turkana (arid, sandy) | 109 | 47 |
| Machakos (semi-arid) | 122 | 197 |
| Trans-Nzoia (humid highland) | 129 | 194 |
| Ethiopia Arsi (Meher belt) | 131 | 212 |

(vs. the retired flat **100 mm** everywhere.) The spatial WHC matters most in the semi-arid zones where
stored soil water — not just rainfall — decides whether the crop bridges dry spells.

**One soil definition, everywhere.** All six water-balance entry points — the planting-window WRSI
(viability gate, LVPD) *and* the risk/CPI stage monitor — now draw WHC from the same `get_whc()`
switchboard, so soil water is defined identically across planting and risk. Materialize once with
`python run_export_whc.py` (exports the GHA WHC to an EE asset), then set `soil.whc_asset` to that id.

### 3.8 Excess rain / waterlogging — the wet-side layer — `src/excess.py`

WRSI is a **deficit** index: soil water is capped at WHC and anything above just runs off, so
**waterlogging is invisible to it**. Yet excess water is a real failure mechanism (root hypoxia, seed
rot, denitrification / N leaching, disease, lodging) — acute in wet years (e.g. the April–May 2024
Kenya floods). This adds a dedicated wet-side layer, classed like the drought side.

**Shipped metric — SPI-3 wet tail (anomaly-based):**
```
excess/waterlogging : SPI-3 >= +1.5 (very wet, McKee 1993)  ->  % of maize area "very wet"
→ % of maize area affected → Watch ≥ 25 % / Alert ≥ 50 % / Critical ≥ 75 % (same ASAP rule)
```
Computed for **all three seasons** (waterlogging is onset-independent — the OND short rains can flood
hard, e.g. the 2023 El Niño season) — unlike the 5+7 false-start gate, which is green-up-only. Validated
against the April–May 2024 central-Rift-Valley floods (e.g. Ol Kalou 36 %, Bahati 35 % of maize area
very wet). SPI-3 is **anomaly-based**, so it correctly separates *anomalously* wet from *normally* wet.

**Second metric — modelled soil waterlogging (AquaCrop aeration stress, UNCALIBRATED):**
```
daily root-zone balance: W = f(daily CHIRPS − ET), capped at saturation, gravitational water above
  field capacity draining at the soil's rate τ (SoilGrids/Saxton Ksat)          [Raes et al. 2009]
aeration stress = clamp((W − thr)/(SAT − thr), 0, 1),  thr = anaerobiosis point (½ FC→SAT)
waterlog index  = 100 · peak CONSECUTIVE stage-weighted aeration (resets when the soil drains)
```
This is what "excess above field capacity" should mean physically — it uses the **maize water balance
and the soil's own field capacity, saturation and drainage** (all from the SoilGrids/Saxton soil, §3.7).
Because it is **soil-relative**, well-drained/sandy soils drain the excess and don't flag (arid Garissa →
0), fixing the failure of an earlier fixed-mm-threshold prototype (which misranked well-drained convective
storms above true waterlogging — that prototype is retired). **Crucially it is a DIFFERENT hazard from
SPI-3-wet:** SPI-3 sees *surface / seasonal anomalous wet*; the aeration index sees *root-zone soil
saturation* — e.g. the 2024 Ol Kalou event was largely surface flooding (high SPI-wet) on well-draining
highland soils (low modelled aeration). Its parameters (τ, anaerobiosis threshold, ET, scale, and the
establishment-worst stage weights below) are **first-pass and UNCALIBRATED** — no waterlogging
ground-truth exists to certify the ranking — so it ships **clearly labelled as indicative**, to be
cross-checked against SPI-3-wet and calibrated against crop-cut / field reports.

**Stage weighting is the mirror image of the deficit side.** For deficit, flowering is worst
(FAO-33 Ky 1.5). For **excess**, **establishment / early-vegetative is worst** — young maize is
acutely waterlogging-intolerant (days of saturation kill the stand):
```
deficit Ky   : veg 0.40 · flo 1.50 · grf 0.50     (flowering worst)   [Doorenbos & Kassam 1979]
excess weight: veg 1.00 · flo 0.60 · grf 0.35     (establishment worst) — first-pass, calibratable
```
The **ordering** is literature-grounded [Zaidi et al. 2004; Ren et al. 2014; Kaur et al. 2020]; there is
**no FAO-33-equivalent standardised "waterlogging Ky"**, so the numeric weights are a first-pass derived
from the relative yield-loss order in those studies and are **flagged for calibration** (like the CPI
heat/veg params). SPI-3 is shared with the drought side (the wet tail vs the dry tail).

## 4. Persistence & confirmation
Anomalies must be **persistent** (≥ 2 consecutive dekads); SPI-3 is inherently anti-blip (3-month
integration). Anomalies are graded against the pixel's own **historical distribution** (z-score /
percentile), so a single wet/dry dekad cannot trip a warning.

## 5. Resolution — honest note
Planting and phenology are genuinely **250 m** (Sentinel-2/1 + elevation-resolved). **WRSI, SPI-3, WSI,
deficit** carry **~5.5–11 km** (CHIRPS / ERA5) information content displayed on the 250 m grid — robust
for admin roll-ups, not pixel-sharp. Stated, not implied.

## 6. References
- Verdin, J. & Klaver, R. (2002). *Grid-cell crop water accounting for FEWS.* Hydrol. Processes 16, 1617–1630.
- Senay, G. B. & Verdin, J. (2003). *GIS crop water balance (WRSI).* Can. J. Remote Sensing 29(6), 687–692.
- Allen, R. G. et al. (1998). *Crop evapotranspiration.* FAO Irrigation & Drainage Paper 56.
- Hargreaves, G. H. & Samani, Z. A. (1985). *Reference ET from temperature.* Appl. Eng. Agric. 1(2), 96–99.
- McKee, T. B. et al. (1993). *The SPI.* 8th Conf. Applied Climatology, AMS, 179–184.
- Wilson, E. B. & Hilferty, M. M. (1931). *The distribution of chi-square.* PNAS 17(12), 684–688.
- Funk, C. et al. (2015). *CHIRPS.* Scientific Data 2:150066.
- Muñoz-Sabater, J. et al. (2021). *ERA5-Land.* ESSD 13, 4349–4383.
- Kogan, F. N. (1995). *VCI/TCI for drought detection.* Adv. Space Res. 15(11), 91–100.
- Doorenbos, J. & Kassam, A. H. (1979). *Yield response to water (Ky).* FAO Irrigation & Drainage Paper 33.
- Rembold, F. et al. (2019). *ASAP anomaly hot spots.* Agric. Systems 168, 247–257.
- Saxton, K. E. & Rawls, W. J. (2006). *Soil water characteristic estimates by texture and organic matter for hydrologic solutions.* Soil Sci. Soc. Am. J. 70(5), 1569–1578. https://doi.org/10.2136/sssaj2005.0117
- Poggio, L. et al. (2021). *SoilGrids 2.0: producing soil information for the globe with quantified spatial uncertainty.* SOIL 7, 217–240. https://doi.org/10.5194/soil-7-217-2021
- Zaidi, P. H. et al. (2004). *Tolerance to excess moisture in maize: susceptible crop stages and identification of tolerant genotypes.* Field Crops Research 90(2–3), 189–202. https://doi.org/10.1016/j.fcr.2004.03.002 — early-vegetative most waterlogging-susceptible.
- Ren, B. et al. (2014). *Effects of waterlogging on the yield and growth of summer maize under field conditions.* Canadian J. Plant Science 94(1), 23–31. https://doi.org/10.4141/cjps2013-175
- Kaur, G. et al. (2020). *Impacts and management strategies for crop production in waterlogged or flooded soils: a review.* Agronomy Journal 112(3), 1475–1501. https://doi.org/10.1002/agj2.20093
- Raes, D. et al. (2009). *AquaCrop — the FAO crop model to simulate yield response to water: II. Main algorithms and software description (incl. aeration/waterlogging stress).* Agronomy Journal 101(3), 438–447. https://doi.org/10.2134/agronj2008.0140s

*Full algorithm-to-citation mapping: `ALGORITHMS_AND_REFERENCES`. Frozen design & roadmap:
`RISK_MONITORING_DESIGN`. App number definitions: `APP_STATISTICS_GUIDE`.*
