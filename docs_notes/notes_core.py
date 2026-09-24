# -*- coding: utf-8 -*-
"""Stage notes for the four core Colab modules (01 to 04).

Each entry is (anchor, markdown). The anchor is a substring of the code cell the note
belongs to; the note is inserted as a markdown cell immediately above it.
"""

# ---------------------------------------------------------------- shared setup
SETUP = [
("!pip -q install", r"""
### Stage 0 · Runtime

**What runs.** Installs the Earth Engine Python client and `geemap` into the Colab runtime. Nothing is
computed here.

**Expected output.** One line, `installed.`, after 30 to 60 s on a cold runtime. Pip warnings about
dependency resolution are normal and can be ignored.

**If it fails.** Re-run the cell. A repeated failure usually means the runtime lost its network
connection; use *Runtime → Restart session* and start again.
"""),

("ee.Initialize(project=PROJECT)", r"""
### Stage 0b · Earth Engine sign-in

**What runs.** Connects to Earth Engine under the cloud project `PROJECT`. On a fresh runtime a
browser prompt appears; approve it with the Google account that has Earth Engine access.

**Expected output.** `EE ready: ok` within a few seconds. Anything else means the sign-in did not
complete.

**Which project to use.** Compute is identical across projects, but the **export queue is per
project**. `ee-manzikye` has stalled with tasks sitting in READY for hours. If you are going to
export, set `PROJECT = "indigo-proxy-484220-q8"` before running.
"""),

("drive.mount", r"""
### Stage 0c · Pipeline code on Drive

**What runs.** Mounts Google Drive and puts `/content/drive/MyDrive/planting_pipeline` on the Python
path, so `from src import ...` resolves to the pipeline modules rather than to anything installed by
pip.

**Expected output.** `Mounted at /content/drive` followed by
`pipeline on path: /content/drive/MyDrive/planting_pipeline`.

**If you get an `AssertionError`.** The folder is not where the cell expects it. Either upload the
whole `planting_pipeline` folder to the top level of My Drive, or edit `PIPE_DIR` to the real path.
The folder must contain `run.py`, `src/` and `config/`.
"""),

("aoi_run = ee.Geometry.Rectangle", r"""
### Stage 0d · Run configuration

**What you choose here.**

| Variable | Meaning |
|---|---|
| `COUNTRY`, `SEASON` | select a row of `config/season_calendar.csv`; this fixes the season window and the crop calendar |
| `YEAR` | the season's planting year. A season that crosses new year (short rains, Deyr) is still keyed by its planting year |
| `S1_ORBIT` | Sentinel-1 orbit. `ASCENDING` over Kenya, because Sentinel-1B failed in 2022 and descending coverage is sparse |
| `aoi` | the whole country, from the GAUL level-0 boundary |
| `aoi_run` | the area actually computed. It ships as a **test box**, 34.4 to 37.8 E and 1.2 S to 1.2 N, about 380 by 265 km over western and central Kenya |

**Time is counted in dekads, not dates.** A dekad is a third of a month, numbered 1 to 36 through the
year: dekad 1 is 1 to 10 January, dekad 9 is 21 to 31 March, dekad 36 is 21 to 31 December. Days 21 to
the month end are one dekad, so a dekad is 8, 9, 10 or 11 days long. `utils.dekad_label(9)` prints
`9·Mar`. Where a season crosses the new year the code uses a **global dekad** `gd` running 1 to 72,
which is the dekad of `YEAR` for 1 to 36 and of `YEAR + 1` for 37 to 72.

**Season windows this notebook can use.**

| Country · season | SOS detection window | Dekads |
|---|---|---|
| Kenya · Long rains | Mar-d3 to May-d3 | 9 to 15 |
| Kenya · Short rains | Oct-d1 to Nov-d3 | 28 to 33 |
| Ethiopia · Meher | Apr-d2 to Jun-d3 | 11 to 18 |

**Expected output.** One line, for example `Kenya · Long rains · 2024 · S1 ASCENDING`.

**Before you switch to the whole country.** Replace `aoi_run` with `aoi` only when the test box has
run cleanly. The country is roughly ten times the area, and Sentinel-2 and Sentinel-1 compositing
scales with it. Expect minutes to become tens of minutes, and expect `getInfo()` calls to time out;
at country scale use `ee.batch.Export` instead of reading results back into the notebook.
"""),
]

PLANTING = ("planting dekad computed for", r"""
### Stage 1 · Planting dekad

**What this stage does.** It estimates, for every maize pixel, the dekad the crop was planted. Every
later module is anchored on this number, so an error here propagates into the water balance, the CPI
and the yield. Two different methods run, chosen by season.

**Main seasons: cue-fusion green-up.** Optical greenness is combined with radar so that cloud does not
leave holes. For each dekad a fused greenness proxy is built,

$$G_t=\tfrac{1}{2}\Big[\mathrm{unit}(\mathrm{NDRE}_t;0,0.7)+\mathrm{unit}(\mathrm{FPAR}_t;0,0.9)\Big],
\qquad G_t \leftarrow \mathrm{unit}(\mathrm{RVI}_t;0.1,0.8)\ \text{where optical is missing,}$$

where $\mathrm{unit}(x;a,b)$ rescales $x$ from $[a,b]$ to $[0,1]$. NDRE is the Sentinel-2 red-edge
index, FPAR is MODIS MCD15A3H, and RVI is the Sentinel-1 radar vegetation index, which rises with
canopy and is unaffected by cloud.

Start of season is the first dekad in the window at which greenness crosses a quarter of the season's
own amplitude and is still rising:

$$G_{\text{thr}}=G_{\min}+0.25\,(G_{\max}-G_{\min}),\qquad
\mathrm{SOS}=\min\{\,t:\ G_t\ge G_{\text{thr}}\ \wedge\ G_{t+1}-G_t\ge 0\ \wedge\ |t-\mathrm{SOS}_{\mathrm{LTN}}|\le 2\,\}$$

The last condition keeps the answer within two dekads of the climatological onset, which rejects weed
flushes and a second green-up. It is applied only where a climatology exists, so a sparse second-season
normal cannot reject every pixel.

Planting precedes visible green-up, so the detected SOS is shifted back by the crop's emergence lag:

$$\text{planting dekad} = \mathrm{SOS} - 2 \quad \text{(maize; wheat and teff use 1).}$$

**Short rains: rainfall onset.** Green-up detection is unreliable in the short rains, so the FEWS NET
rule is used instead. Onset is the first dekad with

$$P_t \ge 25\ \mathrm{mm}\quad\text{and}\quad P_{t+1}+P_{t+2}\ge 20\ \mathrm{mm}
\quad\text{and}\quad P_t/ET_{0,t}\ge 0.5 .$$

The first two conditions are the classic 25/20 mm rule; the third is an agroclimatic gate that asks
whether the rain was large relative to evaporative demand.

**Expected output.** A single line, `planting dekad computed for <country> <season>`. Nothing is
evaluated yet: Earth Engine is lazy, so errors in this cell often only surface at the next one, where
a number is actually requested.

**Expected values.** The result must fall inside the SOS window of the table above, minus the
emergence offset. For Kenya long rains 2024 the modal planting dekad is **8** (11 to 20 March), with
the 10th to 90th percentile of the 253 constituencies spanning dekads **7 to 9**. A modal dekad
outside 6 to 11 for that season means the fusion locked onto the wrong green-up.
""")

NOTES = {}

# ---------------------------------------------------------------- 01 planting
NOTES["01_planting_window.ipynb"] = SETUP + [
PLANTING,

("dryspell_false_start", r"""
### Stage 2 · False-start gate, and the first real number

**What this stage does.** A first rain can germinate a crop and then stop, killing it. The inception
report's **5 + 7 rule** rejects those pixels. Both halves must hold at the estimated planting date:

* **germination trigger**: at least **20 mm** of rain in the first **5 days**;
* **continuity**: no dry spell longer than **7 days** inside the following **20 days**, where a dry day
  is one with less than 1 mm.

Pixels that fail are masked out, which is why the count printed here is lower than the number of maize
pixels in the box. The short rains do not need the gate, because the 25/20 mm onset rule already
contains a continuity test.

**Expected output.** `valid maize pixels: N`. This is the first cell that actually forces Earth Engine
to compute, so it takes the longest, typically one to three minutes for the test box.

**How to read N.** One 250 m pixel is **6.25 ha**, so `N × 6.25` is the maize area the estimate covers.
Compare it with the maize area of the box: for the shipped western-Kenya box, a result within a factor
of two of a few hundred thousand hectares is sensible.

* `N = 0` almost always means the crop mask and `aoi_run` do not overlap, or the season window is wrong
  for the country you selected.
* An N that collapses when you add the gate, rather than falling by a fraction, means the planting
  estimate is too early: the gate is then testing rain before the season began.
"""),

("ee_layer(M, planting.clip", r"""
### Stage 3 · Map

**What this stage does.** Draws the planting dekad on an interactive map. The colour ramp runs from the
first dekad of the SOS window to three dekads past its end, so dark blue is early planting and yellow
is late. The layer panel at the top right toggles layers and sets opacity.

**What to look for.** Planting should vary smoothly with elevation and rainfall, and should be later as
you move into drier country. Salt-and-pepper noise over a small area is usually cloud; a hard straight
edge is a tile or orbit boundary and means the Sentinel-1 orbit setting is wrong for that area.
"""),

("Planting-window STATISTICS", r"""
### Stage 4 · Planting-window statistics

**What this stage does.** Turns the map into numbers, in three parts.

**1. Distribution over maize area.** A frequency histogram of the planting dekad is converted to area,

$$A_d = n_d \times 6.25\ \mathrm{ha},$$

and summarised by the modal dekad, the area-weighted mean, and area-weighted quantiles $q$ defined as
the dekad at which the cumulative planted area first reaches $q$ of the total.

**2. Calendar agreement (skill).** The estimate is compared with the FEWS and FAO indicative planting
window for the country and season. The hit rate is the share of maize area whose estimated dekad falls
inside that window; the bias is the mean signed difference in dekads, positive meaning later than the
calendar.

**3. Per-admin table and ranked bar.** The same statistics per administrative unit, ranked, so the late
and early districts are visible.

**Expected values, Kenya long rains 2024.** Against the shipped 253-constituency table: modal dekad
**8**, area-weighted mean **8.05**, p10 **7.3**, p90 **8.8**, mean calendar hit rate **0.73**, mean
bias **−1.95 dekads** relative to the calendar window. The negative bias is expected and is a property
of the calendar, not an error: the indicative window starts at Mar-d2 while most farmers in the west
plant in Mar-d1 to Mar-d3.

**Red flags.** A hit rate below 0.3, a modal dekad at either edge of the window, or a distribution with
two widely separated peaks over a small area. The last one usually means two season regimes have been
mixed; see `KENYA_SEASON_REGIMES.md`.
"""),

("Farmer validation", r"""
### Stage 5 · Farmer validation, 2024 long rains

**What this stage does.** Compares the estimate with what farmers reported, which is the only
independent test in this notebook. It runs for Kenya long rains only. Three metrics, per county,
weighted by the number of farmers surveyed:

$$\text{bias}=\overline{\hat{d}-d},\qquad
\mathrm{MAE}=\overline{|\hat{d}-d|},\qquad
\text{hit rate}=\Pr\big(|\hat{d}-d|\le 2\ \text{dekads}\big),$$

with $\hat d$ the estimated and $d$ the farmer-reported planting dekad. A tolerance of two dekads is
used because farmers report a planting month or a modal date, not a day.

**Expected values.** The shipped county file has **42 counties**: bias **−0.31 dekads**, MAE **1.02
dekads**, and **93 %** of counties within two dekads. In other words the estimate is on average three
days early and typically wrong by about ten days, which is inside the precision at which farmers
report.

**Interpretation.** An MAE near 1 dekad is the working accuracy of this product. Do not read a
one-dekad difference between two counties as real. Do read a three-dekad difference as real.

**If the live check is skipped.** Where `aoi_run` does not cover enough counties, the cell falls back
to the shipped CSV and says so. That is the documented number above, not a check on the run you just
did.
"""),

("County \u2192 Ward drill-down", r"""
### Stage 6 · Ward drill-down

**What this stage does.** Repeats the validation at ward level, writes a nested county to ward JSON for
the dashboard, and draws observed against estimated planting per county.

**Expected values.** The shipped ward file holds **855 wards across 42 counties**: farmer-weighted bias
**−0.38 dekads**, MAE **1.09 dekads**, and **96 %** of wards within two dekads. Ward-level error is
almost identical to county level, which tells you the residual error is not a boundary or aggregation
artefact but the genuine spread of planting within a season.

**Using the JSON.** The structure is `{County: {Ward: {obs, est, err, farmers, n_px}}}`. Wards with a
small `n_px` carry few maize pixels, so their estimate is noisy; filter on it before ranking wards.
"""),
]

# ---------------------------------------------------------------- 02 risk
NOTES["02_risk_monitoring.ipynb"] = SETUP + [
PLANTING,

("run_wrsi_staged", r"""
### Stage 2 · Staged water balance: WRSI, WSI and crop failure

**What this stage does.** It runs a full FAO-56 and FAO-33 dekadal soil-water balance for every pixel,
starting at that pixel's own planting dekad, and reports how much of the crop's water requirement was
actually met. There is no hand-off to GeoWRSI; the balance is computed in Earth Engine.

**Reference evaporation, Hargreaves.** ERA5-Land daily 2 m temperature gives, per dekad,

$$ET_0 = 0.0023\,R_a\,(T_{\text{mean}}+17.8)\,\sqrt{T_{\max}-T_{\min}}\quad[\mathrm{mm\,d^{-1}}],$$

with extraterrestrial radiation $R_a$ computed per pixel from latitude and the mid-dekad day of year.
Hargreaves is used because it needs only temperature. ERA5-Land is used because GRIDMET does not cover
Africa.

**Crop water requirement.** The FAO-56 crop coefficient curve is stepped by dekads since planting: it
holds at $K_{c,\text{ini}}$ through the initial stage, ramps linearly to $K_{c,\text{mid}}$ through
development, holds, then ramps to $K_{c,\text{end}}$. For maize the pipeline uses
$K_c = 0.30 \rightarrow 1.20 \rightarrow 0.35$ over stages of 3, 4, 3 and 2 dekads, a 12-dekad cycle.
Then

$$WR_t = K_{c,t}\, ET_{0,t}.$$

**The balance.** Soil water starts empty at planting, which is the WRSI convention, and each dekad

$$W_t = SW_{t-1}+P_t,\qquad AET_t=\min(W_t,\,WR_t),\qquad
SW_t=\min\big(W_t-AET_t,\ WHC\big),$$

with rainfall $P$ from CHIRPS and the water-holding capacity $WHC$ from SoilGrids through the
Saxton and Rawls pedotransfer functions, integrated over a 1 m maize root zone. Water above $WHC$ is
discarded, which is exactly why this index cannot see waterlogging; that is what module 4 is for.

**The index.** Cumulated over the cycle,

$$\mathrm{WRSI}=100\,\frac{\sum_t AET_t}{\sum_t WR_t}.$$

The staged version snapshots the running WRSI at the end of each of the three stages, giving
`wrsi_veg`, `wrsi_flo` and `wrsi_grf`. The last is the whole-cycle value. `wsi_*` are the worst single
dekad of stress inside each stage.

**Classes (FEWS and GeoWRSI).**

| WRSI | Class |
|---|---|
| 95 to 100 | no or very mild deficit |
| 80 to 95 | mild |
| 60 to 80 | mediocre |
| 50 to 60 | poor |
| below 50 | **crop failure** |

`failflo` in this cell is the crop-failure flag at flowering, `wrsi_flo < 50`. Flowering is used because
FAO-33 makes it the stage where a deficit costs the most yield.

**Expected values.** In a normal Kenyan long rains, WRSI at flowering over maize sits between **70 and
100**, and the failure flag covers a small share of the area. An AOI-wide mean below 40, or a failure
flag over most of the map, almost always means the planting anchor is too early, so the balance is
being run through the dry weeks before the season.

**SPI-3.** The meteorological companion, a three-month standardised precipitation index from CHIRPS
against the 1981 to 2020 climatology. Earth Engine has no incomplete gamma function, so the
Wilson and Hilferty cube-root normal approximation is used:

$$a=\left(\frac{\mu}{\sigma}\right)^{2},\qquad
\mathrm{SPI}=\left[\left(\frac{P_3}{\mu}\right)^{1/3}-1+\frac{1}{9a}\right]\sqrt{9a}.$$

Classes follow McKee: **−1 moderate drought, −1.5 severe, −2 extreme**, and the wet mirror. By
construction SPI is roughly standard normal, so about 16 % of pixels below −1 in any given year is
normal. A map where most pixels are below −1 is a drought; a map where **all** of them are, including
the highlands, points at a CHIRPS gap rather than at weather.
"""),

("fused_condition", r"""
### Stage 3 · Fused canopy condition index

**What this stage does.** Provides a vegetation cross-check on the water balance. FCCI is the peak fused
greenness reached over the season,

$$\mathrm{FCCI}=100\times\max_{t\in\text{season}}G_t,$$

with the same fused $G$ as the planting stage, so it is cloud-proof through its radar fill and works at
10 to 20 m.

**Why it exists.** WRSI is a model: it says what the weather and the soil should have done to the crop.
FCCI is an observation: it says what the canopy actually looked like. When they disagree, something in
between is wrong, most often the planting date or irrigation the model does not know about.

**Expected values.** 0 to 100, higher being a more vigorous canopy. Vigorous rainfed maize peaks high,
failed or unplanted land stays low. Because $G$ uses fixed rescaling rather than a multi-year baseline,
values are comparable between pixels without an archive, but they are **not** an anomaly: a
consistently dry district looks low every year.

**Caveat to carry into any interpretation.** Where the peak dekad was cloudy, the value came from the
radar proxy, which is the less exact of the two cues.
"""),

("ee_layer(M, staged['wrsi_flo']", r"""
### Stage 4 · Map

**Layers, and how to read them together.**

| Layer | Range | Reading |
|---|---|---|
| WRSI at flowering | 40 to 100 | red is a deficit, green is satisfied demand |
| Crop failure at flowering | 0 or 1 | red where WRSI is below 50 |
| SPI-3 | −2 to 2 | red dry, blue wet, against 1981 to 2020 |
| Canopy condition, FCCI | 0 to 100 | red is a poor canopy, green is vigorous |

**The useful comparison is between layers, not within one.** Low WRSI with low FCCI is a real water
deficit that the crop felt. Low WRSI with high FCCI is usually irrigation, a spring, or a wrong planting
date. High WRSI with low FCCI points at a hazard the water balance cannot see, which is pests, disease,
flooding, or a field that was never planted.
"""),
]

# ---------------------------------------------------------------- 03 CPI / yield
NOTES["03_cpi_yield.ipynb"] = SETUP + [
PLANTING,

("cpi_img,yld=CPI.cpi", r"""
### Stage 2 · Crop performance index and yield

**What this stage does.** It converts three separate stresses into one relative-yield index, then into a
yield in tonnes per hectare.

**The stacking.** Following AquaCrop and the crop-model convention, each hazard is an independent
fractional yield reduction and they multiply:

$$\frac{Y_a}{Y_m}=(1-S_{\text{water}})(1-S_{\text{heat}})(1-S_{\text{veg}}),
\qquad \mathrm{CPI}=100\,\frac{Y_a}{Y_m}.$$

Multiplying, rather than adding, means two moderate stresses compound but neither alone can take the
index to zero.

**Water stress, FAO-33.** Built from the per-stage actual and required evapotranspiration of the water
balance, weighted by the FAO-33 yield-response factors $K_y$:

$$S_{\text{water}}=\sum_{s\in\{\text{veg},\text{flo},\text{grf}\}}
K_{y,s}\left(1-\frac{AET_s}{WR_s}\right),
\qquad K_y = 0.4,\ 1.5,\ 0.5,$$

clamped to $[0,1]$. Flowering carries three times the weight of grain filling, which is the whole point
of running the balance stage by stage rather than over the season.

**Heat stress.** Accumulated heat-degree-dekads above a cap, over the flowering window only, because the
damage mechanism is pollen sterility:

$$S_{\text{heat}}=\min\Big(1,\ 0.06 \sum_{t\in\text{flowering}} \max(T_{\max,t}-33,\ 0)\Big),$$

with $T_{\max}$ the dekad-mean daily maximum from ERA5-Land.

**Expect this term to be zero in Kenya, and treat that as correct.** The cap is a dekad-mean, and
measured dekad-mean flowering $T_{\max}$ peaks at 22.9, 25.9 and 29.3 °C across Kenya's three season
regimes, so 33 °C cannot be reached in two of them. The term is live for lowland and Sahelian seasons.
If you are testing the threshold, pass `tcap=` and `k=` to `s_heat` rather than editing the module.

**Vegetation stress.** A deliberately down-weighted confirmation from the satellite, not a driver:

$$S_{\text{veg}}=0.4\,(1-\mathrm{VCI}),\qquad
\mathrm{VCI}=\frac{\mathrm{NDVI}_{\text{peak}}-\mathrm{NDVI}_{\min}}{\mathrm{NDVI}_{\max}-\mathrm{NDVI}_{\min}},$$

over the 2003 to 2023 climatology. The weight of 0.4 caps its contribution at a 40 % yield reduction,
because a vegetation index confirms a stress but does not measure yield. Setting `VEG_INDEX=fpar` swaps
VCI for the standardised FPAR anomaly used by JRC ASAP, $S_{\text{veg}}=0.4\,\mathrm{clamp}(-z/2,0,1)$.

**Yield and production.**

$$Y_a = \frac{\mathrm{CPI}}{100}\times Y_m,\qquad
\text{production (t)} = Y_a \times 6.25\ \text{ha per 250 m pixel}.$$

**$Y_m$ is calibrated, not a textbook potential.** `CPI.ym_for(COUNTRY, SEASON)` returns the ceiling
fitted to HarvestStat sub-national yields, target = the median over the available years, least squares
through the origin, tested on a 70/30 split repeated 200 times:

| Country · season | $Y_m$ t/ha | Units | Held-out MAE, calibrated vs default | $r$ |
|---|---|---|---|---|
| Kenya · Long rains | **2.34** | 45 | 0.68 vs 2.26 | 0.57 |
| Kenya · Short rains | **1.44** | 44 | 0.39 vs 1.94 | 0.36 |
| Ethiopia · Meher | **4.14** | 76 | 0.71 vs 1.38 | 0.64 |
| Rwanda · Season A | **2.61** | 30 | 0.37 vs 2.75 | −0.07 |
| Burundi · Season A | **1.88** | 16 | 0.71 vs 3.57 | 0.28 |
| Somalia · Gu | **1.02** | 18 | 0.24 vs 1.58 | 0.34 |
| Uganda · 1st rains | 2.34 | 74 | 1.24 vs 2.90 | −0.14 (provisional) |

Tanzania and South Sudan have no HarvestStat maize yields and fall back to the uncalibrated 6.0 t/ha,
which every country that could be tested shows to be several times too high. Where $r$ is near zero the
ceiling fixes the **level** only: use the map for national and seasonal totals, not to rank districts.

**Expected output.** One line ending in the AOI total production in tonnes. Two sanity checks:

* CPI over maize should mostly sit between **55 and 85** in a normal Kenyan long rains. That is what a
  reported yield of about 1.3 to 1.8 t/ha implies against a 2.34 t/ha ceiling.
* Mean yield should land near **1.5 t/ha** for Kenya long rains, near **3 t/ha** for Ethiopia Meher.
  A mean above 4 t/ha for Kenya means `ym_for` fell through to a default, which happens when `COUNTRY`
  or `SEASON` is spelled differently from the calendar file.

**A CPI of 100 is not a good season, it is a missing stress.** If the whole map reads near 100, check
that the water balance ran: an empty `staged` dictionary makes every stress zero.
"""),

("ee_layer(M, cpi_img", r"""
### Stage 3 · Map

CPI is drawn 0 to 100 and yield 0 to 6 t/ha on the same map so they can be toggled against each other.
They carry identical spatial pattern by construction, because yield is CPI times a constant; the second
layer exists to put the pattern in units a user recognises.

**What to check.** The yield layer should have no values above the country's $Y_m$. If it does, `ym`
was passed as an image with the highland split enabled, which is switched off under the typical-year
calibration.
"""),
]

# ---------------------------------------------------------------- 04 flooding
NOTES["04_flooding_waterlogging.ipynb"] = SETUP + [
PLANTING,

("aeration_stress_index", r"""
### Stage 2 · Excess water: the two wet-side metrics

**Why a separate module.** The WRSI water balance caps soil water at field capacity and throws the rest
away, so **excess rain is invisible to it by construction**. A flooded field and a perfectly watered one
score the same. This notebook adds the wet side, as two metrics that measure different things and have
very different standing.

**Metric 1: SPI-3 wet tail. Validated, and the one to report.**

$$\text{wet} = \mathbf{1}\big[\mathrm{SPI}_3 \ge 1.5\big]$$

The same SPI-3 as the drought side, read at its upper tail. McKee's class for 1.5 and above is *very
wet*. This is a **seasonal, surface** anomaly: it says the three months were far wetter than the 1981 to
2020 normal for that place. It does not say the root zone was saturated.

**Metric 2: aeration stress. Modelled, uncalibrated, indicative only.** An AquaCrop-style daily root-zone
balance. Each day, with rainfall from daily CHIRPS and a fixed crop evapotranspiration of 4 mm per day,

$$W \leftarrow \min\big(\max(W+P-ET,\,0),\ SAT\big),\qquad
W \leftarrow FC + (W-FC)^{+}\,(1-\tau),$$

so gravitational water above field capacity drains at the soil's own rate $\tau$. Field capacity,
saturation and $\tau$ come from SoilGrids texture through Saxton and Rawls. Stress begins at the
anaerobiosis point, halfway from field capacity to saturation:

$$\theta_{\text{aer}}=FC+0.5\,(SAT-FC),\qquad
a=\mathrm{clamp}\!\left(\frac{W-\theta_{\text{aer}}}{SAT-\theta_{\text{aer}}},0,1\right).$$

The daily stress is weighted by growth stage and **accumulated only while the soil stays wet**, resetting
the moment it drains below the anaerobiosis point:

$$r \leftarrow (r + a\,w_s)\cdot\mathbf{1}[W>\theta_{\text{aer}}],
\qquad \mathrm{WL}=100\,\frac{\max_t r_t}{4}.$$

The reset is what separates a well-drained sandy field under heavy storms, which never accumulates, from
a clay field that stays saturated for days.

**The stage weights are reversed from the drought side.** For a deficit, flowering is the critical stage.
For excess water, young maize is the vulnerable one, because of root hypoxia, seed rot, nitrogen loss and
stand loss: $w_{\text{veg}}=1.00$, $w_{\text{flo}}=0.60$, $w_{\text{grf}}=0.35$, following Zaidi et al.
(2004), Ren et al. (2014) and Kaur et al. (2020). There is no FAO-33 equivalent for waterlogging, so
these weights are a first pass awaiting calibration, as are the 4 mm per day evapotranspiration and the
4-day scale that sets 100.

**Expected values.** `spi3_wet` is 0 or 1, and in an average year covers a small share of the area;
whole-region coverage means a genuinely exceptional season, such as the 2023 El Nino short rains.
`waterlog_idx` is 0 to 100 and is **zero over most pixels in most seasons**. That is the expected
result, not a failure. Non-zero values concentrate on heavy soils in the wettest dekads. Because the
scale is uncalibrated, use the ranking between places and not the number itself.

**Do not add these two to the drought layers.** They are a separate hazard with a separate audience.
"""),

("ee_layer(M, wet.updateMask", r"""
### Stage 3 · Map

The two layers answer different questions and should be read separately. **SPI-3 very wet** is the
validated, reportable one: a seasonal rainfall anomaly. **Soil waterlogging** is modelled and
uncalibrated: a root-zone saturation estimate. Where they disagree, the usual explanation is drainage.
A very wet season on a free-draining soil shows the first layer and not the second, and that is the
model working as intended.

Full derivation, references and the calibration that is still outstanding are in
`WATERLOGGING_METHODOLOGY`.
"""),
]
