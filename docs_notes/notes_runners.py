# -*- coding: utf-8 -*-
"""Stage notes for the runner and all-country Colab notebooks."""

NOTES = {}

# ------------------------------------------------------------------ run_in_colab
NOTES["run_in_colab.ipynb"] = [

('!pip -q install "earthengine-api', r"""
### Stage 0 · What this notebook is for

**Use this one to launch batch exports, not to explore.** It uploads the pipeline as a zip, calls
`run.py`, and then watches the Earth Engine task queue. Nothing is computed in the notebook itself:
`run.py` submits **batch exports** that run on Google's servers and land in Drive, so you can close the
browser once they are submitted.

For interactive work with maps, use `01_planting_window` through `04_flooding_waterlogging`, which
import the pipeline from Drive instead of uploading a zip.

**Expected output.** Pip installs quietly. Warnings about resolver conflicts are normal.

**A quota point that catches people out.** Colab does not raise your Earth Engine compute quota. Quota
belongs to the **cloud project**, not to the runtime. A heavy WRSI run will be throttled here exactly
as it would anywhere else, and paying for more Colab compute changes nothing.
"""),

("ee.Initialize(project=PROJECT)", r"""
### Stage 1 · Earth Engine sign-in

**Expected output.** `EE ready: ok`.

**Choose the project deliberately.** The **export queue is per project**. `ee-manzikye` has left
batches sitting in READY for hours, including a Somalia WRSI export that had to be cancelled. For any
run that matters, set `PROJECT = "indigo-proxy-484220-q8"`, whose queue has been reliable. Compute is
identical; only the queue differs.
"""),

("files.upload()", r"""
### Stage 2 · Get the code into the runtime

**What runs.** Uploads `planting_pipeline.zip`, unpacks it and changes into it. The upload widget is
a browser control, so this cell will sit and wait until you choose a file.

**Expected output.** `cwd: /content/planting_pipeline` and a file listing that includes `run.py`,
`src`, `config` and the validation CSVs. If `config` is missing, the zip was made from inside the wrong
folder and `run.py` will fail on the crop calendar.

**The alternative, which is usually better.** Keep the folder on Drive and mount it, as the module
notebooks do. A zip is a snapshot: any fix you make later has to be re-zipped and re-uploaded.
"""),

("python run.py --year 2024", r"""
### Stage 3 · Submit the run

**What this stage does.** `run.py` builds the graph for one product and submits Earth Engine batch
exports. Arguments:

| Argument | Effect |
|---|---|
| `--year` | the planting year |
| `--country`, `--crop` | one product. Drop both to submit everything viable for that year |
| `--mask-asset` | a crop-specific mask image. Without it the run falls back to WorldCereal |

**Use `--mask-asset`.** WorldCereal is a single 2021 season and does not separate the crops. The
crop-type masks built by `crop_type_mask_colab.ipynb` are the intended input, for example
`projects/<project>/assets/crop_type_mask/croptype_KE_100m` selecting `mask_maize`. The difference is
not cosmetic: the mask decides which pixels every statistic is computed over.

**Expected output.** One line per submitted task. Submission takes seconds; the exports themselves
take from minutes to hours.

**Three exports per product**, described in stage 5.
"""),

("ee.data.listOperations()", r"""
### Stage 4 · Watch the queue

**What this stage does.** Lists the tasks whose description matches the filter, keeping only the latest
attempt of each name. Re-run the cell to refresh; it does not poll on its own.

**States.** `PENDING → RUNNING → SUCCEEDED`, or `FAILED` / `CANCELLED`. A failure prints its message.

**Change the filter.** It is hard-coded to `"Kenya_maize"`. If you ran another country, nothing will
print and the run will look as though it never started.

**How long is too long.** Minutes in PENDING is normal. **More than about 20 minutes with nothing
moving to RUNNING is a stalled queue, not a slow one.** That has happened repeatedly in `ee-manzikye`.
Cancel the tasks, switch the project, and resubmit; waiting does not clear it.

**Common failures.**

* *Too many pixels* — the AOI or the scale is too large. Export at 250 m, or tile the AOI.
* *Computation timed out* — the graph is too deep for one task, usually from running the whole
  country with the fused green-up. Split by season or by region.
* *Asset not found* — a `--mask-asset` path that does not exist, or one owned by a different project.
"""),
]

# ------------------------------------------------------------------ planting_pipeline_colab
NOTES["planting_pipeline_colab.ipynb"] = [

("!pip -q install earthengine-api geemap", r"""
### Stage 0 · What this notebook is

**A single notebook covering all three modules**, for a walkthrough in one sitting. The four numbered
notebooks (`01_planting_window` to `04_flooding_waterlogging`) are the same computations split up, with
more validation in each. Use those for work; use this one to show the whole chain.

**The yield ceiling is the calibrated one.** Sections 2 and 3 call `CPI.ym_for(COUNTRY, SEASON)`, which
returns the ceiling fitted to HarvestStat sub-national yields rather than the uncalibrated 6.0 t/ha
agronomic potential. Both cells print or use the same value, so they cannot drift apart. A country and
season with no calibration falls back to 6.0, or 4.5 for a short season, and the table in Module 3 says
which those are.
"""),

("ee.Authenticate()              # opens a sign-in", r"""
### Stage 0b · Earth Engine

**Expected output.** `EE ready: ok`. The export queue is per project; use
`indigo-proxy-484220-q8` if you intend to export.
"""),

("src modules:", r"""
### Stage 0c · Drive and the pipeline path

**Expected output.** `pipeline on path: ...` followed by the first few `src` module names. The cell
also `chdir`s into the folder, which matters: the crop calendar and coefficients are loaded by the
relative paths `config/season_calendar.csv` and `config/crop_coefficients.yaml`.
"""),

("AOI_TEST  = ee.Geometry.Rectangle", r"""
### Stage 0d · Configuration

**Time is in dekads.** A dekad is a third of a month, numbered 1 to 36 through the year; dekad 9 is 21
to 31 March. Seasons that cross the new year use a global dekad 1 to 72.

**`aoi_run` is the test box by default**, about 380 by 265 km over western and central Kenya. Swap in
`aoi` only after the box runs clean, and expect to move from interactive `getInfo()` calls to batch
exports when you do.

**Season windows.** Kenya long rains dekads 9 to 15, Kenya short rains 28 to 33, Ethiopia Meher 11 to
18, read from `config/season_calendar.csv`.
"""),

("# 1.1  Planting dekad", r"""
### Module 1 · Planting dekad

**Main seasons, cue fusion.** A dekadal fused greenness proxy is built from Sentinel-2 red edge, MODIS
FPAR and Sentinel-1 radar, the radar filling cloud gaps:

$$G_t=\tfrac12\big[\mathrm{unit}(\mathrm{NDRE}_t)+\mathrm{unit}(\mathrm{FPAR}_t)\big],
\qquad G_t \leftarrow \mathrm{unit}(\mathrm{RVI}_t)\ \text{where optical is missing}.$$

Start of season is the first sustained crossing of a quarter of the season amplitude, held within two
dekads of the climatological onset:

$$G_{\text{thr}}=G_{\min}+0.25(G_{\max}-G_{\min}),\qquad
\text{planting}=\mathrm{SOS}-2\ \text{dekads (maize)}.$$

**Short rains, rainfall anchored.** Green-up is too weak, so the FEWS rule is used:
$P_t\ge 25$ mm, $P_{t+1}+P_{t+2}\ge 20$ mm, and $P_t/ET_{0,t}\ge 0.5$.

**Then the 5 + 7 false-start gate**, where it is applied: at least 20 mm in the first 5 days, and no
dry spell longer than 7 days in the following 20.

**Expected values.** Kenya long rains 2024: modal planting dekad **8**, tenth to ninetieth percentile
**7 to 9**. Against farmer reports the estimate carries a bias of **−0.31 dekads** and an MAE of **1.02
dekads**, with **93 %** of counties inside two dekads. Treat one dekad as the noise floor of this
product.
"""),

("# 2.1  GEE risk layers", r"""
### Module 2 · Water balance, stresses and CPI

**The balance, FAO-56 and FAO-33.** Reference evaporation from ERA5-Land by Hargreaves,

$$ET_0=0.0023\,R_a\,(T_{\text{mean}}+17.8)\sqrt{T_{\max}-T_{\min}},$$

crop demand $WR_t=K_{c,t}ET_{0,t}$ with the maize curve $0.30\to1.20\to0.35$ over a 12-dekad cycle,
and a soil bucket that starts empty at planting:

$$AET_t=\min(SW_{t-1}+P_t,\ WR_t),\qquad
SW_t=\min(SW_{t-1}+P_t-AET_t,\ WHC),\qquad
\mathrm{WRSI}=100\frac{\sum AET}{\sum WR}.$$

Rainfall is CHIRPS; water-holding capacity is SoilGrids through Saxton and Rawls over a 1 m root zone.
Water above capacity is discarded, so **this index cannot see waterlogging** — that is the next cell.

**The three stresses.**

$$S_{\text{water}}=\sum_s K_{y,s}\Big(1-\tfrac{AET_s}{WR_s}\Big),\quad K_y=0.4,\,1.5,\,0.5;$$
$$S_{\text{heat}}=\min\Big(1,\,0.06\!\!\sum_{\text{flowering}}\!\!\max(T_{\max}-33,0)\Big);\qquad
S_{\text{veg}}=0.4\,(1-\mathrm{VCI}).$$

$$\mathrm{CPI}=100\,(1-S_{\text{water}})(1-S_{\text{heat}})(1-S_{\text{veg}}).$$

**Expected values.** WRSI at flowering 70 to 100 over maize in a normal Kenyan long rains; below 50 is
the FEWS crop-failure class. CPI mostly 55 to 85. **$S_{\text{heat}}$ will be zero in Kenya and that is
correct**: the 33 °C cap is a dekad-mean, and measured dekad-mean flowering maxima peak at 22.9, 25.9
and 29.3 °C across Kenya's three season regimes.

**The ceiling.** `YM = CPI.ym_for(COUNTRY, SEASON)` is fetched here and reused in Module 3, and the
cell prints it so the value behind the yield map is on the record: Kenya long rains 2.34 t/ha, short
rains 1.44, Ethiopia Meher 4.14.
"""),

("# 2.1b  New monitoring layers", r"""
### Module 2b · The wet side

**SPI-3 wet, validated.** $\mathbf{1}[\mathrm{SPI}_3\ge 1.5]$, McKee's *very wet* class, against the
1981 to 2020 CHIRPS climatology. A seasonal, surface anomaly.

**Aeration stress, modelled and uncalibrated.** A daily root-zone balance from SoilGrids hydrology:
water above field capacity drains at the soil's own rate, stress begins halfway from field capacity to
saturation, and the stage-weighted stress accumulates only while the soil stays wet, resetting whenever
it drains. Stage weights are **reversed** from the deficit side, because young maize is the vulnerable
stage: veg 1.00, flo 0.60, grf 0.35.

**Expected values.** The waterlogging index is **zero over most pixels in most seasons**, which is the
correct answer and not a failure. Use the ranking between places, not the number: the 4 mm per day
evapotranspiration and the 4-day scale that sets 100 are first-pass constants awaiting calibration.
"""),

("# 2.2  SPI-3 meteorological drought", r"""
### Module 2c · SPI-3 drought

Earth Engine has no incomplete gamma function, so SPI uses the Wilson and Hilferty cube-root normal
approximation:

$$a=(\mu/\sigma)^2,\qquad \mathrm{SPI}=\Big[(P_3/\mu)^{1/3}-1+\tfrac{1}{9a}\Big]\sqrt{9a}.$$

**Classes.** −1 moderate drought, −1.5 severe, −2 extreme, and the wet mirror.

**Expected values.** SPI is roughly standard normal by construction, so about **16 % of pixels below
−1 in any year is normal**. A map where nearly everything is below −1, highlands included, is more
likely a CHIRPS gap than a drought.

**What SPI-3 is not.** It is rainfall only. It knows nothing about soil, crop stage or evaporative
demand. When SPI-3 and WRSI disagree, WRSI is the crop-relevant one; SPI-3 is the meteorological
context.
"""),

("# 3.1  Yield & production", r"""
### Module 3 · Yield

$$Y_a=\frac{\mathrm{CPI}}{100}\times Y_m,\qquad
\text{production (t)}=Y_a\times 6.25\ \text{ha per 250 m pixel}.$$

**The ceiling is fetched, not typed.** `CPI.ym_for(COUNTRY, SEASON)` returns the typical-year fit to
HarvestStat sub-national yields, so the notebook follows `src/cpi.py` whenever the calibration is
updated. The uncalibrated 6.0 t/ha it replaced over-predicted reported smallholder yields two- to
sevenfold.

| Country · season | $Y_m$ t/ha | Held-out MAE, calibrated vs uncalibrated |
|---|---|---|
| Kenya · Long rains | 2.34 | 0.68 vs 2.26 |
| Kenya · Short rains | 1.44 | 0.39 vs 1.94 |
| Ethiopia · Meher | 4.14 | 0.71 vs 1.38 |
| Rwanda · Season A | 2.61 | 0.37 vs 2.75 |
| Burundi · Season A | 1.88 | 0.71 vs 3.57 |
| Somalia · Gu | 1.02 | 0.24 vs 1.58 |

**Tanzania and South Sudan still fall back to 6.0**, because HarvestStat holds no maize yields for
either. Every country where the default could be tested shows it to be several times too high, so treat
their yield numbers as unusable in level, whatever this cell prints.

**Expected values with the calibrated ceiling.** Mean yield near **1.5 t/ha** for Kenya long rains and
near **3 t/ha** for Ethiopia Meher. The total production line is marked indicative because it assumes
every masked pixel is fully planted.
"""),
]

# ------------------------------------------------------------------ ALL countries
NOTES["planting_pipeline_ALL_colab.ipynb"] = [

("!pip -q install earthengine-api geemap", r"""
### Stage 0 · What this notebook is

**The operational graph, run interactively.** It calls the same `build_product_image()` used for the
2024 continental asset set, so what you see here is the operational computation clipped to a small
box, not a simplified demo. Every module below reads pieces of **one** result, which is why they are
always internally consistent.

**Expected output.** `installed.`
"""),

("PROJECT=\"ee-manzikye\"", r"""
### Stage 0b · Earth Engine

`EE ready: ok`. Switch to `indigo-proxy-484220-q8` before submitting the continental batch in
section 5; the queue is per project and this one has stalled.
"""),

("PIPE_DIR=\"/content/drive/MyDrive/planting_pipeline\"", r"""
### Stage 0c · Drive

`pipeline on path: ...`. An `AssertionError` means the folder is not on Drive at that path.
"""),

("from run_all_maize_2024 import build_product_image", r"""
### Stage 0d · The product menu

**What this stage does.** Prints every viable maize (country, season) in
`config/season_calendar.csv`, and defines a small demo box per country. Sixteen products across eleven
countries were built for 2024.

**Viability is a judgement recorded in the calendar**, not a guess: a season marked low viability is
one where maize area is negligible or the season cannot be detected reliably. Only High and Medium
appear here.

**Expected output.** A list of pairs such as `Kenya Long rains`, `Ethiopia Meher`, `Somalia Gu`,
`Rwanda Season A`, `Tanzania Msimu`.
"""),

("USE_WHOLE_COUNTRY = False", r"""
### Stage 0e · Pick one product

**What to set.** `COUNTRY`, `SEASON`, and whether to run the real country boundary.

**`USE_WHOLE_COUNTRY = True` is a different order of job.** The demo box returns in seconds to
minutes. A whole country with the fused green-up runs for tens of minutes, and interactive
`getInfo()` calls will start timing out. At that point use the batch scripts in section 5.

**The onset method is chosen for you**, by the calendar. Second and short seasons route to the
rainfall-anchored rule because green-up detection fails there: in Rwanda and Burundi, Season A
green-up returned 64 usable pixels against 3,365 for the rainfall rule.
"""),

("build_product_image(ee, r, kc, soil", r"""
### Stage 1 · Compute the whole product once

**What this stage does.** Runs the entire graph and returns the output image plus every intermediate:
the planting dekad, the staged water balance, the three stresses, CPI and yield. Modules 1 to 3 below
only draw pieces of this.

**Expected output.** The band list, then the onset method that was selected. Bands include
`planting_dekad`, `CPI`, `yield_tha_x100` and, in the rich stack, six WRSI and WSI stage bands.

**Yield is stored times 100 as an integer.** `yield_tha_x100` divided by 100 is tonnes per hectare.
This keeps the asset small; forgetting it is the most common misreading of these assets.

**$Y_m$ here is the calibrated ceiling**, through `CPI.ym_img_for`, unlike the older single-country
notebook which hard-codes 6.0.
"""),

("Planting dekad —", r"""
### Module 1 · Planting window

**What it answers.** For each field, which ten-day period did the crop go in?

**Expected values.** Inside the season window for that country. Kenya long rains: modal dekad 8, with
most area in dekads 7 to 9. Against farmer reports for 2024, bias **−0.31 dekads**, MAE **1.02
dekads**, **93 %** of counties within two dekads at county level and **96 %** of 855 wards at ward
level. One dekad is the noise floor.

**The colour ramp here runs the full 1 to 36**, so a single-season map occupies a narrow slice of it.
That is expected; the module notebooks stretch the ramp to the season window instead.
"""),

("WRSI — flowering", r"""
### Module 2 · Risk monitoring

**What it answers.** Where, and at which growth stage, is the crop under stress?

$$\mathrm{WRSI}=100\frac{\sum_t AET_t}{\sum_t WR_t},\qquad
AET_t=\min(SW_{t-1}+P_t,\,K_{c,t}ET_{0,t}).$$

The three stress layers are drawn as percentages so they can be compared with each other.

**Expected values.**

* **WRSI at flowering** 70 to 100 over maize in a normal season; below 50 is the FEWS crop-failure
  class; 50 to 60 poor, 60 to 80 mediocre, 80 to 95 mild, 95 and above unstressed.
* **$S_{\text{water}}$** carries almost all of the signal. It is the only one of the three with a
  calibrated parameter set behind it, the FAO-33 $K_y$ values.
* **$S_{\text{heat}}$ is zero in the highland seasons and that is correct.** The 33 °C cap is a
  dekad-mean; measured dekad-mean flowering maxima peak at 22.9, 25.9 and 29.3 °C across Kenya's three
  regimes. The term is live for lowland and Sahelian seasons.
* **$S_{\text{veg}}$** is capped at 0.4 by design. It confirms; it does not drive.

**Toggle the stress layers against WRSI.** If $S_{\text{water}}$ is high where WRSI is also high, the
stage weighting is doing the work: a deficit at flowering costs three times what the same deficit costs
during vegetative growth.
"""),

("CPI (0-100)", r"""
### Module 3 · Crop performance index and yield

$$\mathrm{CPI}=100\,(1-S_{\text{water}})(1-S_{\text{heat}})(1-S_{\text{veg}}),
\qquad Y_a=\frac{\mathrm{CPI}}{100}\,Y_m.$$

**$Y_m$ is calibrated, per country and season**, fitted to HarvestStat sub-national yields with the
median year as the target and tested on a 70/30 split repeated 200 times: Kenya 2.34 long rains and
1.44 short rains, Ethiopia 4.14, Rwanda 2.61, Burundi 1.88, Somalia 1.02, Uganda 2.34 provisional.
Tanzania and South Sudan have no HarvestStat maize yields and fall back to 6.0, which every country
that could be tested shows to be several times too high; treat their yields as unusable in level.

**Where $r$ is near zero the ceiling fixes the level, not the ranking.** Rwanda, Burundi and Somalia
are level-only: use their yields for national and seasonal totals, not to rank districts.
"""),

("mean CPI = ", r"""
### Module 3b · The two numbers to check

**Expected values over the demo box.**

| Country · season | Mean CPI | Mean yield t/ha |
|---|---|---|
| Kenya · Long rains | 55 to 85 | about 1.5 |
| Ethiopia · Meher | 60 to 90 | about 3 |
| Somalia · Gu | lower and more variable | about 1 |

**Two failure signatures.** A mean CPI near 100 means the stresses did not compute, usually because the
water balance ran on an empty planting image. A mean yield above 4 t/ha in Kenya means $Y_m$ fell
through to the uncalibrated default, which happens when the country or season string does not match
the calendar exactly.

Remember to divide `yield_tha_x100` by 100, which this cell does for you.
"""),

("aeration_stress_index", r"""
### Module 4 · The wet-side hazard

**Why it is separate.** WRSI caps soil water at field capacity and discards the rest, so excess water
is invisible to it by construction.

**SPI-3 wet, validated**: $\mathbf{1}[\mathrm{SPI}_3\ge1.5]$, a seasonal surface anomaly against 1981
to 2020. **Aeration stress, modelled and uncalibrated**: a daily root-zone balance from SoilGrids and
Saxton-Rawls, where stage-weighted stress accumulates only while the soil stays above the anaerobiosis
point and resets whenever it drains. Stage weights are reversed from the deficit side, veg 1.00, flo
0.60, grf 0.35, because young maize is the vulnerable stage.

**Expected values.** The waterlogging index is **zero over most pixels in most seasons**. Report the
SPI-3 wet layer; use the aeration layer to rank places, never as a calibrated magnitude.
"""),
]

# ------------------------------------------------------------------ Kenya local workflow
NOTES["planting_pipeline_kenya.ipynb"] = [

("PIPELINE_DIR = ", r"""
### Stage 0 · Configuration, and what is different about this notebook

**This is the local workflow, not a Colab notebook.** Paths are absolute to a laptop. Only stage 1
touches Earth Engine; stages 2 to 5 run from the exported GeoTIFFs with rasterio and matplotlib, so
they are unaffected by Earth Engine quota and can be re-run freely.

| Setting | Meaning |
|---|---|
| `PRODUCT` | the export name the later stages look for |
| `CAL_WIN` | the FEWS and FAO indicative planting window, in dekads, that skill is scored against |
| `AEZ_SHP` | Kenya's Jaetzold and Sombroek agro-ecological zones |

**`CAL_WIN = (8, 12)`** is dekad 8 to 12, that is 11 March to 30 April. Skill is the share of maize
area whose estimated planting dekad falls inside it. Change it with the season: short rains 28 to 32,
Ethiopia Meher 10 to 15.
"""),

("python run.py --year {YEAR}", r"""
### Stage 1 · Submit the Earth Engine exports

**What this stage does.** Submits the planting, WRSI and zonal exports for the product. This is the
only quota-gated stage. Comment it out once the exports exist.

**Three outputs per product**, landing in Drive under `planting_outputs/`:

* `planting_<country>_<crop>_<season>_<year>` — per-pixel planting dekad, GeoTIFF
* `wrsi_<...>` — WRSI, deficit in mm, and the crop-performance class
* `<...>_zonal` — admin-1 modal, p10, p50 and p90 planting dekad, CSV

**Expected time.** Minutes to hours. The monitor cell below refreshes on demand; more than about 20
minutes with nothing entering RUNNING means a stalled queue rather than a slow one.
"""),

("render_maps_pdf.py", r"""
### Stage 2 · Local maps

**What this stage does.** Renders the exported tiles into a styled PDF, downsampling on read so a
32,000 by 32,000 tile does not exhaust memory, then previews the last page inline.

**Expected output.** `Planting_Maps.pdf` and an inline preview. A preview that is almost entirely
blank means the GeoTIFF is a shard rather than the mosaic; check that the export finished and that all
shards were downloaded.
"""),

("admin_skill_local.py", r"""
### Stage 3 · Administrative statistics and calendar skill

**What this stage does.** Aggregates the planting dekad to three levels — 1 county, 2 constituency,
3 ward — and scores each unit against the calendar window. Each level writes a CSV and a two-page PDF:
the modal planting dekad, and the calendar hit rate.

**Definitions.** Hit rate is the share of maize area inside `CAL_WIN`; bias is the mean signed
difference in dekads, positive being later than the calendar.

**Expected values, Kenya long rains 2024, level 2, 253 constituencies.** Modal dekad **8**, mean **8.05**,
p10 **7.3**, p90 **8.8**, mean hit rate **0.73**, mean bias **−1.95 dekads**, mean absolute error
**2.01 dekads** against the calendar window.

**The negative bias is a property of the calendar, not an error in the estimate.** The indicative
window opens at Mar-d2 while most western farmers plant in Mar-d1 to Mar-d3. Against **farmer-reported**
dates rather than the calendar, the same product carries a bias of only **−0.31 dekads** and an MAE of
**1.02 dekads**, with 93 % of counties within two dekads. When you report accuracy, report the farmer
comparison and say which one you used.
"""),

("aez_analysis.py", r"""
### Stage 4 · Agro-ecological zone and maturity class

**What this stage does.** Overlays the planting dekad with Kenya's agro-ecological zones. The zone
code, a temperature belt and a moisture zone, sets the length of growing period, which in turn implies
an early, medium or late-maturing maize variety.

**Read page 2, not page 1.** Planting **timing** is nearly uniform across zones, because the long-rains
onset is regional. It is the **maturity class** that varies by zone. The dekad map therefore looks
flat, and that flatness is the finding.

**A caveat worth carrying.** A growing-degree-day clock, tested against this fixed-length assumption,
puts the long-rains highland growing period out by about 68 days. The maturity classes here come from
the zone table, not from a thermal-time model, and should be treated as indicative.
"""),

("skill_graphs.py", r"""
### Stage 5 · Skill graphs

**What this stage does.** Breaks the skill down: ranked county hit rate, the ward-level distribution,
the bias, and a scatter of estimated against observed. Stage 3 must have run first.

**What to look for.** A wide spread in county hit rate with no geographic pattern is noise. A block of
low-skill counties that share a season regime is a real finding, and the usual cause is a calendar
window that does not fit that regime; Kenya has three regimes, not one, and 39.4 % of the mapped
short-rains area is in fact the standing long-rains crop. See `KENYA_SEASON_REGIMES.md`.
"""),

("aez_influence.py", r"""
### Stage 5b · How much the zone actually moves planting

Boxplots of planting dekad by maturity class and altitude belt. The expected result is **overlapping
boxes**: zones differ in how long the crop takes, not in when it goes in. A strong separation here
would contradict stage 4 and would be worth investigating before it is reported.
"""),

("skill_across_outputs.py", r"""
### Stage 5c · Compare products against each other

**What this stage does.** Scores every `*_stats.csv` in the stats folder, each against its own calendar
window, so seasons and products can be ranked.

**How to read it.** A season with a wide or badly placed calendar window scores low even when the
estimate is good, because the window is the yardstick. Use this to find which **window** needs
revisiting, then confirm with farmer data before changing the estimate.
"""),
]
