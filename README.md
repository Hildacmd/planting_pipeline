# Crop-specific dekadal planting-window estimation — GHA / ICPAC (11 countries)

Estimates **per-pixel planting dekad** for **maize, teff, wheat** inside **crop-specific masks**,
by fusing **Sentinel-2 red-edge phenology + FPAR + Sentinel-1 SAR**, constrained by your
**long-term-normal (LTN) phenology**, cross-checked against **WRSI rainfall onset**, and
aggregated to admin units — **season-stratified** per country using a crop-specific calendar.

Countries: Ethiopia, Kenya, Uganda, Tanzania, Rwanda, Burundi, South Sudan, Sudan, Somalia,
Eritrea (Djibouti excluded — negligible cropping).

**Reference runs (maize 2024):** Kenya Long rains + Short rains, and Ethiopia Meher (unimodal).
**Production scale is 250 m** — two concurrent 10 m country exports do not sustain on GEE, so 250 m is
the operational scale for the multi-country rollout; 10 m is the single-AOI reference ceiling.

## Where this fits your existing stack
You already run: **generic crop mask, LTN phenology, FPAR, WRSI**. This pipeline adds the two
missing pieces — **crop-specific masks** and **red-edge + SAR fusion** — and turns the outputs
into a **crop-specific cropping calendar** that then *feeds back* into WRSI as a better onset.

```
 generic crop mask ─┐                         ┌─ LTN phenology (prior + anomaly baseline)
 crop-specific mask ─┼─► [S2 red-edge + FPAR + S1 SAR fusion] ─► SOS ─► planting dekad ─┐
   (maize/teff/wheat)│         (season-stratified, per crop)        (─offset)           │
 FPAR (existing) ────┘                                                                  ▼
 CHIRPS ─► WRSI onset  ──────────────► cross-validate ◄────────────────────► WRSI (better onset in)
                                                     └─► zonal admin planting-window CSV + anomaly map
```

## Pipeline stages (code map)
| Stage | File | What it does |
|---|---|---|
| Config | `config/datasets.yaml`, `config/season_calendar.csv` | dataset IDs+APIs; crop-specific calendar |
| Optical | `src/s2_preprocess.py` | dekadal cloud-masked NDRE/VI composites (10 m) |
| SAR | `src/s1_preprocess.py` | dekadal VV/VH/ratio/RVI, terrain-flattened dB |
| FPAR + Fusion | `src/fusion_phenometrics.py` | fused greenness, SAR gap-fill, LTN-gated SOS |
| Planting | `src/planting_date.py` | SOS→planting offset, anomaly vs LTN, export |
| WRSI onset | `src/wrsi_feedback.py` | CHIRPS 25/20 mm onset cross-check |
| Soil WHC | `src/soil.py` | spatial water-holding capacity: SoilGrids texture → Saxton–Rawls FC & WP over root zone |
| WRSI balance | `src/wrsi_waterbalance.py` | **full FAO-56/33 WRSI in pure GEE** (Hargreaves ET0 + Kc + soil-water balance) |
| Zonal | `src/zonal_aggregate.py` | GAUL admin planting-window distributions |
| Orchestrate | `run.py` | loop viable (country×crop×season) products |

## Run
```bash
pip install -r requirements.txt
earthengine authenticate
export EE_PROJECT=your-gee-project
# one product:
python run.py --year 2024 --country Ethiopia --crop teff --mask-asset users/you/teff_mask_2024
# everything viable for a year:
python run.py --year 2024
```
Outputs (to Google Drive `planting_outputs/`): planting-dekad GeoTIFF per product + admin-1 CSV
of modal/P10/P50/P90 planting dekad. Djibouti auto-excluded (no viable rows).

## Data sources + access APIs
| Layer | Source / ID | API |
|---|---|---|
| Optical red-edge | `COPERNICUS/S2_SR_HARMONIZED` | GEE; CDSE openEO / Sentinel Hub / STAC |
| Cloud mask | `GOOGLE/CLOUD_SCORE_PLUS/...` (+ S2_CLOUD_PROBABILITY) | GEE |
| SAR | `COPERNICUS/S1_GRD` | GEE; CDSE; ASF HyP3 (RTC) |
| FPAR | `MODIS/061/MCD15A3H`; CGLS FPAR 300 m | GEE; NASA AppEEARS; CGLS/VITO |
| LTN phenology | USGS/FEWS eMODIS phenology; `MODIS/061/MCD12Q2` | USGS EROS; FEWS NET Data Portal; GEE |
| Rainfall (WRSI) | `UCSB-CHG/CHIRPS/DAILY` | GEE; Climate Hazards Center |
| PET/ET0 & soil (WRSI) | ERA5-Land Tmin/Tmax (Hargreaves ET0); SoilGrids WHC | GEE; ISRIC |
| WRSI engine | Full FAO-56/33 water balance in Google Earth Engine (`wrsi_waterbalance.py`); GeoWRSI 3.x = legacy reference only | GEE; USGS FEWS software (legacy) |
| Generic/maize mask | `ESA/WorldCereal/2021/MODELS/v100` | GEE; WorldCereal openEO |
| Crop calendars | FEWS NET; FAO GIEWS; GEOGLAM Crop Monitor | portals / country briefs |
| Reference labels | EthCT2020; HarvestStat Africa | Mendeley; Dryad/GitHub |

Full endpoints in `config/datasets.yaml`.

## WRSI now runs entirely in GEE (no GeoWRSI hand-off)
`src/wrsi_waterbalance.py` implements the full FAO-56/33 dekadal water balance:
- **ET0** by Hargreaves from **ERA5-Land** 2 m Tmin/Tmax (global — GRIDMET does *not* cover
  Africa), with extraterrestrial radiation Ra computed per dekad from latitude + day-of-year.
- **Kc curve** per crop from `config/crop_coefficients.yaml` (FAO-56 stage lengths; teff is an
  approximate small-grain analogue — flagged).
- **Per-pixel soil-water balance** that starts at each pixel's *detected planting dekad*:
  `Wb = SW + P; AET = min(Wb, WR); SW = min(Wb−AET, WHC)`, wrapping into year+1 when the cycle
  crosses the year end. `WRSI = 100·ΣAET/ΣWR`; also outputs deficit (mm) and FEWS crop-performance
  class.
- **Spatial WHC** (`src/soil.py`): plant-available water = (field capacity − wilting point)
  integrated over the crop root zone. **Production (`whc_source: saxton_soilgrids`)** derives
  **both** FC (θ₃₃) and WP (θ₁₅₀₀) from **SoilGrids 2.0** sand/clay/SOC via the **Saxton–Rawls
  (2006)** pedotransfer — no proxy. Legacy **OpenLandMap 33 kPa** FC (with a 0.45·FC wilting-point
  proxy) stays available via `whc_source: openlandmap`. Root depths per crop in
  `crop_coefficients.yaml` (maize/wheat 1.0 m, teff 0.6 m); toggle with `soil.use_spatial_whc`.
  Static — materialize once with `run_export_whc.py` and set `soil.whc_asset`.
- Validated numerically: WRSI = 100 well-watered, 0 total drought, drops correctly for
  peak-stage and chronic-deficit rainfall; Saxton WHC ≈ 109–131 mm across GHA (maize, 1 m root) and scales sandy→clay
  (88→231 mm).

## Key design decisions
- **SOS ≠ planting**: planting = SOS − crop emergence offset (maize 2, wheat 1, teff 1 dekads).
- **SAR is mandatory, not optional**: rainy-season onset = peak cloud; S1 carries the signal.
- **Red-edge (NDRE) over NDVI** for onset: chlorophyll-sensitive, less soil noise on sparse
  early canopy — better for teff/wheat.
- **Cue fusion is the production greenness; ubESTARFM was tested and shelved.** ubESTARFM
  spatiotemporal fusion (S2×MODIS) is a *documented negative result* for onset — at matched 250 m it
  costs −3 to −4 pts vs cue fusion (MODIS has no red-edge, so its NDVI fill pulls SOS ~1 dekad early).
  See `UBESTARFM_FINDING.md`. **Resolution is the dominant skill lever** (10 m→250 m ≈ −11 pts), so spend
  compute on resolution, not fusion. The code is retained (`src/estarfm.py`) but off the production path.
- **LTN prior gates the search** to reject weeds/second-flush false starts.
- **Irrigated wheat (Sudan Gezira) is decoupled from rainfall** — use scheme calendar + SAR,
  not CHIRPS onset.
- **Teff realism**: only Ethiopia (and marginal Eritrea) — the teff product is Ethiopia-centric.

## In-season risk monitoring & GDD phenology clock (maize)
Beyond the seasonal planting window, an ASAP-style **in-season monitoring** layer, **stage-weighted**
on a **GDD phenology clock**:
- **GDD clock** (`src/gdd_clock.py`, `run_gdd.py`, thermal branch): in-GEE SOS anchor + ERA5-Land daily
  air-T (DEM lapse-corrected) + **AEZ-seeded GDD_maturity** → per-pixel **peak-vegetative / flowering /
  grain-filling / maturity** dekads. Fully pixel-specific. Spec: `GDD_Phenology_Clock_Workflow.docx`.
- **Risk layers** (`src/spi.py`, `spi_admin.py`, `risk_app.html`): **SPI-3** drought (CHIRPS gamma,
  Wilson–Hilferty) + **WRSI crop-failure %**, masked to maize (CAF), ASAP **25/50/75 %** of crop area →
  Watch/Alert/Critical; FAO-33 **Ky** stage-weighting (silking ≈ 3–4× vegetative). Design + roadmap:
  `RISK_MONITORING_DESIGN.md`. Explore: **2024 Maize Risk Monitor** (`risk_app.html`).

## Caveats
Reference implementation for a GEE environment; requires your auth + crop-specific mask assets.
Planting windows in `season_calendar.csv` are **indicative** — calibrate against FEWS NET / FAO
GIEWS / GEOGLAM before operational use. Smallholder mixed pixels blur SOS; resolution is the lever
(reach for native-10 m S2 or Planet 3 m) — ubESTARFM was tested for this and does *not* help onset.

See `REFERENCES.md` for the supporting literature.

---

## Methodology testing (2026-09) — what has and has not been validated

Five controlled experiments re-examined core pipeline choices. Full algorithms, formulas, an
illustrative workflow diagram and peer-reviewed references:
**[`Methodology_Testing/METHODOLOGY_TESTING.md`](Methodology_Testing/METHODOLOGY_TESTING.md)**
(runnable Colabs: `Methodology_Testing/0{1..5}_*.ipynb`).

| component | status |
|---|---|
| SoilGrids/Saxton WHC | **kept on physical grounds, NOT skill-validated.** No rank gain anywhere; the uniform bucket detects the Kitui 2022 failure better (14/15 vs 5/15 wards severe) |
| Fixed 120 d cycle (long rains) | **wrong by 48 d** against farmer-reported cycle length (n=27 counties). The EXISTING GDD clock (ERA5-Land, Tbase 9, 1300/1500/1700) recovers most of it: MAE 23 d, r +0.80. Replace the fixed cycle, keep the clock |
| Fixed 90 d cycle (short rains) | **validated** — GDD within 5 d, and all three stages within 5 d of the fixed Kc timing |
| Per-zone Ym (`YM_HIGHLAND`) | **kept**, justified by out-of-sample ranking (Spearman 0.725→0.830), not MAE; independently corroborated by the Kenya Insurance Atlas (4.12/2.72 vs 3.7/2.3) |
| DMP biomass yield | out-ranks CPI on **all 3 representative frames** (KE long +0.76 vs +0.59, KE short +0.72 vs +0.09, ET Meher +0.60 vs -0.40) and is close to unbiased there (implied HI 0.34-0.48, in the agronomic band). The old "cannot see ASAL crop failure, implied HI 0.02" came from **targeted ASAL drought crop-cuts** where a near-zero harvest forces the implied HI down whatever the model does - it is not a measured limitation. Shipped as a RANKING covariate on the 8 anti-correlated products; not a reported yield, because its level rests on only 3 frames |
| DMP as `S_veg` | **rejected** — no rank gain in any season (Ethiopia admin-2, n=39: ρ ≈ 0 for both arms) |
| GDD maturity target | AEZ proxy disagrees with observed varieties in **30% of counties** (under-calls cold highlands, over-calls bimodal west). BUT the operational table's targets (1030/1300/2020) scored significantly WORSE than the current 1300/1500/1700 (Δ −11.9 d, CI [−19.9,−3.1]) — adopt its stage structure only after re-test |
| CHIRTS vs ERA5-Land for the clock | **no significant difference** at county scale (Δ −0.4 d, CI [−14.5,+14.9]). CHIRTS LTN 1996–2025 is built and useful for grid consistency with CHIRPS, but is not an accuracy fix |
| `agroecology.lgp_dekads` | **defect** — returns a 320–334 d max-run in bimodal western Kenya, merging two rainy seasons into one "growing period" |

**Scoring standard adopted:** leave-one-out CV + paired bootstrap CI, scored under BOTH a per-arm
and a fixed Ym, with Spearman reported alongside MAE. A single 70/30 split at n ≈ 45 carries a
±0.10 t/ha standard deviation — larger than any effect measured here, and it produced two
false positives before this standard was adopted.
