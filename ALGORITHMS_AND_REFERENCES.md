# Algorithms & References — Planting Window and GDD Stage-Weighted Risk Monitoring

Each algorithmic step is stated as the actual equation/logic used in the code, followed by the
reference(s) that support the method. Symbols: `P` precipitation, `PET`/`ET₀` reference ET, `Tmax/Tmin`
daily air temperature, `z` elevation, dekad = 10-day period (1–36/yr). **§C explains how the many spatial/temporal
resolutions are reconciled.** Citations are numbered and listed in **§D**. *Verify DOIs against your
library before formal publication.*

---

## A. Planting-window estimation algorithm

### A1. Optical red-edge signal — `src/s2_preprocess.py`
Per dekad, a cloud-masked median composite of the red-edge index:
```
NDRE1 = (B6 − B5) / (B6 + B5)          # Sentinel-2 red-edge (B5=705 nm, B6=740 nm)
keep pixels where Cloud Score+ cs_cdf ≥ 0.60
```
Red-edge NDRE is chlorophyll-sensitive and less soil-biased than NDVI on sparse early canopy, which
sharpens onset detection [1, 2]; cloud masking via Cloud Score+ [3].

### A2. SAR structural signal — `src/s1_preprocess.py`
```
RVI = 4·σ⁰VH / (σ⁰VV + σ⁰VH)           # terrain-flattened dB, speckle-filtered
```
The Radar Vegetation Index [4] tracks canopy structure and is cloud-penetrating, so it carries the
green-up signal when rainy-season cloud blinds the optical sensor [5, 6].

### A3. Cue fusion → gap-free greenness `G` — `src/fusion_phenometrics.py`
```
opt_G = mean( unitScale(NDRE), unitScale(FPAR) )
G     = opt_G  gap-filled by  unitScale(RVI)  where optical is missing
```

**What is actually happening.** No single sensor gives a clean, gap-free, fine-resolution greenness
curve through a tropical rainy season, so three are fused — each contributing where it is strongest:

- **Sentinel-2 red-edge NDRE** (10–20 m, ~5-day revisit) is the *sharpest onset signal* — chlorophyll-
  sensitive and fine-grained — but it is **cloud-gapped** exactly when onset happens.
- **MODIS FPAR** (500 m, 4-day composite) is *dense in time* and rarely missing, but *coarse in space*.
- **Sentinel-1 SAR RVI** (10 m, ~6–12 day) is *cloud-proof* (radar sees through cloud) but measures
  canopy **structure**, not chlorophyll — a weaker but always-available proxy.

The fusion is a **per-pixel, per-dekad decision** that reconciles their different resolutions in three moves:

1. **Put them on one grid and one scale.** Each layer is first composited to the common **dekadal**
   time step (§C) and resampled to the common **analysis grid**, then **`unitScale`-normalised to 0–1**
   so a 10 m red-edge value and a resampled 500 m FPAR value contribute *comparably* despite different
   native units and resolutions.
2. **Primary optical greenness** `opt_G = mean(NDRE', FPAR')` — this marries S2's **spatial detail**
   (NDRE carries the fine texture) with MODIS's **temporal density** (FPAR guarantees a value most
   dekads). It is the signal used wherever the sky was clear enough for S2.
3. **Cloud gap-fill.** Where the S2 composite is empty for that pixel-dekad (persistent cloud),
   `opt_G` is masked and the algorithm substitutes the **SAR** value `unitScale(RVI)`, which is
   unaffected by cloud. This keeps the series **gap-free** so SOS detection (§A4) never breaks on a
   missing dekad.

The output is one continuous 0–1 greenness image per dekad on the analysis grid — fine where S2 saw
the ground, still populated (via FPAR/SAR) where it did not. Multi-sensor optical+SAR phenology fusion
follows [5, 6]; FPAR from MODIS MCD15A3H [7].

### A3b. ubESTARFM — the spatiotemporal fusion that was tested (and shelved)
A stronger, heavier alternative to the SAR gap-fill was trialled: **unbiased ESTARFM** [8], which
*predicts* a fine-resolution value on a cloudy date instead of substituting SAR. It is the clearest
illustration of true spatial×temporal fusion, so the mechanism is worth stating:
```
On a clear base date t0 you have BOTH fine F(t0) (S2, 10/250 m) and coarse C(t0) (MODIS, 500 m).
 1. Local conversion coefficient  V = cov(F,C)/var(C)  in a moving window     (how a fine pixel
    responds to a coarse change — the spatial cross-scale relationship)
 2. Predict the fine value at target tp from the coarse change:
        F(tp) = F(t0) + V·( C(tp) − C(t0) )          (MODIS is cloud-free, so C(tp) is always known)
 3. UNBIASED step: force mean_coarsen(F_pred) = C(tp)  (removes ESTARFM's additive bias)
 4. TWO-PAIR temporal blend: predict from the nearest earlier and later clear base dates, weight by
    inverse coarse-change magnitude.
```
So it uses the **dense coarse** MODIS series to carry the **sparse fine** S2 series across cloud —
spatial fusion (local regression across scales) plus temporal fusion (blending base dates).
**Why it was shelved:** MODIS has no red-edge, so the only cross-scale partner is **NDVI**, whose
earlier, flatter green-up propagates into the fill and pulls SOS ~1 dekad early — a **documented
negative result** at matched resolution (−3 to −4 pts skill; `UBESTARFM_FINDING.md`). Resolution, not
fusion, is the dominant skill lever (§C).

### A4. Start-of-season (SOS) detection — `detect_sos`
Within the crop-calendar window, SOS is the earliest dekad where greenness crosses a **dynamic
amplitude threshold** with a sustained positive slope:
```
SOS = min{ dk : G(dk) ≥ baseline + 0.25·(amplitude)  AND  G(dk) − G(dk−1) > 0 }
```
The dynamic/relative amplitude-threshold method for SOS is the standard land-surface-phenology
approach [9, 10, 11].

### A5. Long-term-normal (LTN) prior — rainfall-led, greenness-confirmed — `src/ltn.py`
The search is anchored by a **rainfall onset normal** and confirmed by a **phenology normal**:
```
anchor = CHIRPS 25/20 mm onset climatology            # exists every season, every pixel
refine by MODIS MCD12Q2 Greenup normal where present  # ± ltn_pad dekads, pass-through where absent
```
Rainfall-based onset climatology [12, 13]; MODIS land-cover-dynamics phenology (Greenup) [14];
CHIRPS rainfall [15].

### A6. FEWS agroclimatic onset cross-check — `src/wrsi_feedback.py`
```
onset if:  P₀ ≥ 25 mm  AND  P₁+P₂ ≥ 20 mm            # FEWS/GeoWRSI 25/20 mm rule
           AND  P₀ / ET₀ ≥ 0.5                        # agroclimatic sufficiency gate
```
The 25/20 mm onset rule is the FEWS/GeoWRSI convention [12, 13]; the P/PET ≥ 0.5 growing-period
criterion is the FAO agroclimatic definition [16].

### A6b. "5 + 7" false-start gate — germination trigger + dry-spell continuity — `src/wrsi_feedback.py`
Per the inception report, false-start rejection for the **green-up-led seasons** (Long rains, Meher)
pairs a germination trigger with a dry-spell test, alongside P/PET (short rains already carry this via
the 25/20 mm three-dekad rule, so the gate is not applied there):
```
accept onset only if:
  (a) Σ rain over first 5 days ≥ 20 mm                 # germination trigger  ("high-confidence 5-day")
  (b) longest dry spell (<1 mm) ≤ 7 days in next 20 d  # continuity           ("extended 7-day outlook")
  (c) P/PET ≥ 0.5 at onset                             # adequacy (A6)
```
(a) ensures enough concentrated rain to wet the seed zone; (b) rejects onsets a killing dry spell
follows — the classic accumulation-plus-dry-spell onset criterion [40, 41]. Operationally the 5-day/
7-day windows are filled by the 6-obs+4-forecast blend; retrospective runs use observed CHIRPS.
Toggle `DRYSPELL_GATE` (default on). Complements P/PET (adequacy) with a **continuity** test.

### A7. Planting date — `src/planting_date.py`
```
planting_dekad = SOS_dekad − emergence_offset         # maize 2 dekads; temperature-varying where LTN on
```
Satellite green-up marks emergence, which lags sowing by a crop/temperature-dependent offset; solving
planting from the phenological signal follows the satellite-to-planting-date literature [17, 18].

### A8. WRSI water balance (FAO-56/33) — `src/wrsi_waterbalance.py`
Full dekadal water accounting started at each pixel's planting dekad:
```
ET₀  = Hargreaves(Tmax, Tmin, Ra(lat, DOY))            # temperature ET₀
WR   = Kc(days-since-planting) · ET₀                   # crop water requirement
Wb   = SW + P ;  AET = min(Wb, WR) ;  SW = min(Wb − AET, WHC)
WRSI = 100 · ΣAET / ΣWR    (+ deficit mm, + FEWS class 1–5)
```
Reference ET₀ by Hargreaves [19]; Kc curve and crop-water-requirement framework FAO-56 [20];
grid-cell crop-water-balance / WRSI for FEWS [12, 13]; spatial water-holding capacity (WHC) from
**SoilGrids 2.0 texture** with field capacity and wilting point both derived by the **Saxton–Rawls
(2006) pedotransfer** [21, 21a] (legacy OpenLandMap builder retained via `whc_source: openlandmap`).

---

## B. GDD stage-weighted risk-monitoring algorithm

### B1. GDD phenology clock — thermal branch (maize) — `src/gdd_clock.py`
Per-pixel thermal time from the SOS anchor, on DEM-lapse-corrected daily air temperature:
```
T'max = Tmax − lapse·(z − z_coarse) ;  T'min likewise    # lapse = 6.5 °C/km, z = SRTM 30 m
GDD_dekad = 10 · max( 0, (min(T'max, Tcap) + T'min)/2 − Tbase )   # maize Tbase 8–10 °C, Tcap ~30 °C
GDD_cum(dk) = Σ_{d≥SOS} GDD_dekad
```
GDD single-equation formulation and cardinal temperatures [22]; anchoring a thermal-time crop clock to
a satellite-detected start date [17, 18, 23, 24]; environmental lapse-rate correction over terrain
[25] on the SRTM DEM [26]; daily air temperature from ERA5-Land / AgERA5 [27, 28].

### B2. Stage transitions & AEZ-seeded target
```
stage_dekad(s) = min{ dk : GDD_cum(dk) ≥ frac(s) · GDD_maturity }
frac:  peak_vegetative 0.45 · flowering 0.55 · grain_filling 0.65 · maturity 1.00
GDD_maturity (per pixel, AEZ class):  early 1300 · medium 1500 · late 1700 °C·d
```
Maize GDD-to-stage fractions from canonical maize development staging [22, 29]; length-of-growing-period
/ agro-ecological-zone basis for the maturity target [30, 31].

### B3. Stage sensitivity weights (FAO-33 Ky)
The risk weight applied to an anomaly is the yield-response factor of the interval the pixel is in:
```
Ky:  vegetative (SOS→peak-veg) 0.40 · flowering (peak-veg→grain-fill) 1.50 · grain-fill→maturity 0.50
```
Stage-specific yield-response factors Ky from FAO-33 [32] — an anomaly at silking (Ky 1.5) counts
~3–4× the same anomaly during vegetative growth or grain fill.

### B4. Meteorological drought — SPI-3 — `src/spi.py`
3-month CHIRPS accumulation, gamma-fit per pixel/period, mapped to a z-score by the **Wilson–Hilferty**
cube-root normal approximation of the gamma (pure GEE, no incomplete-gamma function):
```
a   = (μ/σ)²                                          # gamma shape, method of moments
SPI = ( (P₃/μ)^(1/3) − 1 + 1/(9a) ) · √(9a)          # ≤ −1 moderate, ≤ −1.5 severe drought
```
Standardized Precipitation Index [33, 34]; the cube-root (Wilson–Hilferty) normal approximation of the
gamma/χ² [35]; CHIRPS climatology [15].

### B5. Crop-water-stress & performance
```
crop-failure   = WRSI < 50                            # FEWS crop-performance failure class
CPI            = 100·[ 1 − Σ_stage Ky·(1 − ETa/ETm) ] # stage-weighted relative yield (FAO-33 closure)
```
WRSI crop-performance classes [12, 13]; the yield-limited closure `1 − Ya/Ym = Σ Ky(1 − ETa/ETm)` is
FAO-33 [32]. (Roadmap indicators: vegetation-condition VCI [36]; heat-stress at flowering.)

### B6. Admin aggregation — ASAP % of crop area — `spi_admin.py`, `risk_app.html`
```
CAF(unit)      = maize pixels / total pixels                       # crop area fraction (ASAP denominator)
affected%      = maize-area with [hazard active & persistent ≥2 dekads] / maize-area
ASAP class:  ≥25% Watch · ≥50% Alert · ≥75% Critical
```
The "% of crop area affected" hotspot classification is the JRC ASAP method [37].

### B7. Cultivar split & self-calibration (design; roadmap)
Maize/improved wheat use the **thermal** branch above; **landrace sorghum & pearl millet** are
photoperiod-sensitive and must use a threshold–hyperbolic **photoperiod branch** (daylength from
lat×DOY), else GDD-from-SOS predicts flowering weeks late [38, 39]. Stage targets self-calibrate
against the observed EVI/NDVI peak per crop×zone (CropSow-style inversion) [18], with a Sentinel-1 SAR
backscatter-turnaround structural check [6]. Full spec: `GDD_Phenology_Clock_Workflow.docx`.

---

## C. Spatial & temporal resolution — how the layers are reconciled

The pipeline mixes inputs spanning **10 m to ~11 km** and **daily to annual**. Two devices reconcile
them: a common **time step (the dekad)** and a common **analysis grid**, with normalisation before any
fusion and lapse-correction where fine detail must be injected into a coarse field.

| Layer | Native spatial | Native temporal | Handling |
|---|---|---|---|
| Sentinel-2 NDRE | 10–20 m | ~5-day revisit | native; dekadal median composite |
| Sentinel-1 SAR RVI | 10 m | ~6–12 day | native; dekadal composite |
| MODIS FPAR (MCD15A3H) | 500 m | 4-day | resampled to grid; dekad mean |
| MODIS MCD43A4 (ubESTARFM) | 500 m | daily NBAR | coarse partner in cross-scale regression |
| MODIS Greenup (MCD12Q2) | 500 m | annual | LTN prior, resampled |
| CHIRPS | ~5.5 km (0.05°) | daily | dekad **sum**; resampled to grid |
| ERA5-Land | ~9–11 km | hourly→daily | dekad **mean**; DEM-lapse downscaled |
| SRTM DEM | 30 m | static | native; drives lapse + AEZ |
| WorldCereal maize | 10 m | annual | native mask |

**Temporal reconciliation — the dekad is the universal clock.** Every source is composited or
aggregated to the same **36 dekads/year**: optical/SAR by *median compositing* of all acquisitions in
the 10-day window (which absorbs the differing revisit cycles — a dekad is long enough that even the
coarsest optical revisit usually yields ≥1 clear look, yet short enough to resolve crop phenology),
MODIS 4-day by dekad mean, CHIRPS daily by dekad **sum** (a flux), ERA5 daily by dekad **mean** (a
state). This *is* the temporal fusion: sensors of ~5-day to daily cadence are brought onto one calendar
so they can be combined and so SOS/GDD accumulate on a fixed step.

**Spatial reconciliation — one analysis grid, normalise, then fuse.** A single grid is chosen — **250 m
in production** (multi-country; two concurrent 10 m country exports do not sustain on GEE), **10 m for a
single-AOI reference** run. Fine inputs (S2, S1, DEM, mask) sit at or below the grid and are used
natively; coarse inputs (MODIS, CHIRPS, ERA5) are **resampled up** to the grid. *Resampling places a
coarse value on fine pixels so it can be combined arithmetically — it does not manufacture new
information*; a CHIRPS-derived field is still ~5.5 km in true content even when written at 250 m. Before
any fusion, indices are **`unitScale`-normalised to 0–1** so layers of different native resolution and
units contribute on equal footing (§A3).

**Injecting genuine fine detail into a coarse field — only where physically justified.** The one place
a coarse variable gains real sub-grid structure is **temperature**: ERA5-Land (~9 km) is
**lapse-corrected against the 30 m SRTM DEM** (`T' = T − 6.5 °C/km · (z − z_coarse)`, §B1), because the
dominant fine-scale control on temperature *is* elevation — so a cool ridge and a warm valley in the
same reanalysis cell get correctly different GDD. Rainfall has no such universal fine predictor, so
**SPI-3 and the WRSI rainfall terms are honestly ~5.5 km** in information content: when SPI-3 is
overlaid on 250 m maize for admin aggregation it is nearest-resampled, and many maize pixels share one
SPI value — the admin **% of crop area** is still meaningful, but the per-pixel SPI is not truly 250 m,
and this is stated rather than implied.

**Where resolution matters most.** Onset skill is dominated by the *optical* grid (10 m → 250 m costs
~11 skill points — far more than any fusion choice), which is why the finest affordable grid is
preferred and why ubESTARFM's coarse-partner fill could not help (§A3b). The *water-balance and drought*
layers are climate-limited and therefore coarse by nature; their value is in the anomaly and the admin
roll-up, not in pixel-level sharpness.

---

## D. References

**Optical / SAR / fusion / phenology**
1. Eisfelder, C. et al. (2024). *Cropland & crop type with S1/S2 in GEE, Ethiopia.* Remote Sensing 16(5):866. https://doi.org/10.3390/rs16050866
2. Vrieling, A. et al. (2019). *S1 & S2 time series for meadow phenology.* Remote Sensing 11(5):542. https://doi.org/10.3390/rs11050542
3. Pasquarella, V. J. et al. (2023). *Cloud Score+ S2_HARMONIZED.* Google Earth Engine dataset (Sentinel-2 cloud/atmospheric masking).
4. Kim, Y. & van Zyl, J. J. (2009). *A time-series approach to estimate soil moisture using polarimetric radar data (Radar Vegetation Index).* IEEE TGRS 47(8), 2519–2527. https://doi.org/10.1109/TGRS.2009.2014944
5. (2025) *S1 SAR annual rice area & long-term SOS dynamics.* Scientific Reports. https://doi.org/10.1038/s41598-025-91655-z
6. Mercier, A. et al. (2020). *Evaluation of S1 & S2 time series for predicting wheat and rapeseed phenological stages.* ISPRS J. 163, 231–256. https://doi.org/10.1016/j.isprsjprs.2020.03.009
7. Myneni, R. et al. *MODIS MCD15A3H FPAR/LAI C6.1.* NASA LP DAAC. https://doi.org/10.5067/MODIS/MCD15A3H.061
8. Zhu, X. et al. (2010). *ESTARFM — enhanced spatial-temporal adaptive reflectance fusion.* RSE 114(11), 2610–2623. https://doi.org/10.1016/j.rse.2010.05.032

**Start-of-season / land-surface phenology**
9. White, M. A. et al. (1997). *A continental phenology model … (dynamic threshold).* Global Biogeochemical Cycles 11(2), 217–234. https://doi.org/10.1029/97GB00330
10. Jönsson, P. & Eklundh, L. (2002). *Seasonality extraction by function fitting to time-series satellite data.* IEEE TGRS 40(8), 1824–1832. https://doi.org/10.1109/TGRS.2002.802519
11. Jönsson, P. & Eklundh, L. (2004). *TIMESAT — a program for analyzing time-series of satellite sensor data.* Computers & Geosciences 30(8), 833–845. https://doi.org/10.1016/j.cageo.2004.05.006

**Rainfall onset / WRSI / water balance**
12. Verdin, J. & Klaver, R. (2002). *Grid-cell-based crop water accounting for FEWS.* Hydrological Processes 16, 1617–1630. https://doi.org/10.1002/hyp.1025
13. Senay, G. B. & Verdin, J. (2003). *GIS crop water balance model, Ethiopia (25/20 mm onset; WRSI).* Can. J. Remote Sensing 29(6), 687–692. https://doi.org/10.5589/m03-039
14. Friedl, M. et al. (2019). *MODIS MCD12Q2 Land Cover Dynamics (Greenup) C6.* NASA LP DAAC. https://doi.org/10.5067/MODIS/MCD12Q2.006
15. Funk, C. et al. (2015). *CHIRPS.* Scientific Data 2:150066. https://doi.org/10.1038/sdata.2015.66
16. Frère, M. & Popov, G. F. (1979). *Agrometeorological crop monitoring and forecasting (P/PET ≥ 0.5 growing period).* FAO Plant Production & Protection Paper 17. FAO, Rome.

**Planting-date from phenology**
17. Sadeh, Y. et al. (2019). *Sowing-date detection at field scale using CubeSats.* Computers & Electronics in Agriculture 157, 568–580. https://doi.org/10.1016/j.compag.2019.01.042
18. Liu, Y., Diao, C. & Yang, Z. (2023). *CropSow: remotely sensed crop-modeling framework for planting-date estimation.* ISPRS J. 202, 334–355. https://doi.org/10.1016/j.isprsjprs.2023.06.012

**Evapotranspiration**
19. Hargreaves, G. H. & Samani, Z. A. (1985). *Reference ET from temperature.* Applied Eng. in Agriculture 1(2), 96–99. https://doi.org/10.13031/2013.26773
20. Allen, R. G. et al. (1998). *Crop evapotranspiration (Kc, ET₀).* FAO Irrigation & Drainage Paper 56. FAO, Rome. https://www.fao.org/3/x0490e/x0490e00.htm
21. Saxton, K. E. & Rawls, W. J. (2006). *Soil water characteristic estimates by texture and organic matter for hydrologic solutions.* Soil Sci. Soc. Am. J. 70(5), 1569–1578. https://doi.org/10.2136/sssaj2005.0117 — FC (θ₃₃) & WP (θ₁₅₀₀) pedotransfer used for WHC.
21a. Poggio, L. et al. (2021). *SoilGrids 2.0: producing soil information for the globe with quantified spatial uncertainty.* SOIL 7, 217–240. https://doi.org/10.5194/soil-7-217-2021 — sand/clay/SOC texture inputs. (Legacy: OpenLandMap 33 kPa water content, https://doi.org/10.5281/zenodo.2784001.)

**GDD clock / temperature / staging**
22. McMaster, G. S. & Wilhelm, W. W. (1997). *Growing degree-days: one equation, two interpretations.* Agric. & Forest Meteorology 87(4), 291–300. https://doi.org/10.1016/S0168-1923(97)00027-0
23. Aires, U. R. V. et al. (2026). *Operational field-scale sowing/emergence from daily synthetic HLS.* Journal of Remote Sensing 6:0878. https://doi.org/10.34133/remotesensing.0878
24. Zhou, Q. et al. (2024). *From phenological metrics to field-level planting dates.* ISPRS J. 216, 259–273. https://doi.org/10.1016/j.isprsjprs.2024.07.031
25. Minder, J. R. et al. (2010). *Surface temperature lapse rates over complex terrain.* J. Geophysical Research 115, D14122. https://doi.org/10.1029/2009JD013493
26. Farr, T. G. et al. (2007). *The Shuttle Radar Topography Mission.* Reviews of Geophysics 45, RG2004. https://doi.org/10.1029/2005RG000183
27. Muñoz-Sabater, J. et al. (2021). *ERA5-Land.* Earth System Science Data 13, 4349–4383. https://doi.org/10.5194/essd-13-4349-2021
28. Copernicus Climate Change Service (2020). *AgERA5 — agrometeorological indicators.* Copernicus CDS. https://doi.org/10.24381/cds.6c68c9bb
29. Abendroth, L. J. et al. (2011). *Corn growth and development (GDD stage targets).* Iowa State Univ. Extension PMR 1009.
30. FAO (1996 / updated). *Agro-ecological zoning & length of growing period.* FAO Soils Bulletin 73 / GAEZ framework.
31. Jaetzold, R. & Schmidt, H. *Farm Management Handbook of Kenya (agro-ecological zones).* Ministry of Agriculture, Kenya.

**Stage weighting / yield response**
32. Doorenbos, J. & Kassam, A. H. (1979). *Yield response to water (Ky).* FAO Irrigation & Drainage Paper 33. FAO, Rome.

**Drought index (SPI)**
33. McKee, T. B., Doesken, N. J. & Kleist, J. (1993). *The relationship of drought frequency and duration to time scales (SPI).* 8th Conf. Applied Climatology, AMS, 179–184.
34. Guttman, N. B. (1999). *Accepting the Standardized Precipitation Index: a calculation algorithm.* J. American Water Resources Assoc. 35(2), 311–322. https://doi.org/10.1111/j.1752-1688.1999.tb03592.x
35. Wilson, E. B. & Hilferty, M. M. (1931). *The distribution of chi-square (cube-root normal approximation).* PNAS 17(12), 684–688. https://doi.org/10.1073/pnas.17.12.684

**Vegetation condition / hotspots / photoperiod**
36. Kogan, F. N. (1995). *Application of vegetation index and brightness temperature for drought detection (VCI).* Advances in Space Research 15(11), 91–100. https://doi.org/10.1016/0273-1177(95)00079-T
37. Rembold, F. et al. (2019). *ASAP: a new global early-warning system to detect anomaly hot spots of agricultural production.* Agricultural Systems 168, 247–257. https://doi.org/10.1016/j.agsy.2018.07.002
38. Folliard, A. et al. (2004). *Modeling sorghum response to photoperiod: a threshold–hyperbolic approach.* Field Crops Research 89(1), 59–70. https://doi.org/10.1016/j.fcr.2004.01.006
39. Sanon, M. et al. (2014). *Photoperiod sensitivity of local millet and sorghum varieties in West Africa.* NJAS 68, 29–39. https://doi.org/10.1016/j.njas.2013.11.004

**Onset false-start criterion (A6b)**
40. Sivakumar, M. V. K. (1988). *Predicting rainy season potential from the onset of rains in the Sudanian and Sahelian zones of West Africa.* Agric. & Forest Meteorology 42(4), 295–305. https://doi.org/10.1016/0168-1923(88)90039-1 — accumulation + no-dry-spell onset definition.
41. Stern, R. D., Dennett, M. D. & Dale, I. C. (1982). *Analysing daily rainfall measurements to give agronomically useful results. I. Direct methods.* Experimental Agriculture 18(3), 223–236. https://doi.org/10.1017/S001447970001379X — onset & dry-spell risk from daily rainfall.

**Excess rain / waterlogging (B, wet-side)**
42. Zaidi, P. H. et al. (2004). *Tolerance to excess moisture in maize: susceptible crop stages and identification of tolerant genotypes.* Field Crops Research 90(2–3), 189–202. https://doi.org/10.1016/j.fcr.2004.03.002
43. Ren, B. et al. (2014). *Effects of waterlogging on the yield and growth of summer maize under field conditions.* Canadian J. Plant Science 94(1), 23–31. https://doi.org/10.4141/cjps2013-175
44. Kaur, G. et al. (2020). *Impacts and management strategies for crop production in waterlogged or flooded soils: a review.* Agronomy Journal 112(3), 1475–1501. https://doi.org/10.1002/agj2.20093

---
*References 1–8, 12–13, 15, 17–20, 22–24, 26–28, 31–32, 37–39 are drawn from the project's verified
citation set; 9–11, 14, 16, 21, 25, 29–30, 33–36 are the canonical method sources added here for the
specific algorithm steps — confirm their DOIs/editions against your library before publication.*
