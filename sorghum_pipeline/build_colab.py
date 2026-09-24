#!/usr/bin/env python3
"""Generate sorghum_pipeline_colab.ipynb: the sorghum workflow end to end, documented.

    python sorghum_pipeline/build_colab.py

The notebook is generated rather than hand-edited so the documentation cannot drift away from the
code it describes. Edit this file, re-run it, and the notebook is rebuilt.
"""
import json, os

H = os.path.dirname(os.path.abspath(__file__))
cells = []


def md(t):
    lines = t.strip("\n").split("\n")
    cells.append({"cell_type": "markdown", "metadata": {},
                  "source": [l + "\n" for l in lines[:-1]] + [lines[-1]]})


def code(t):
    lines = t.strip("\n").split("\n")
    cells.append({"cell_type": "code", "metadata": {}, "execution_count": None, "outputs": [],
                  "source": [l + "\n" for l in lines[:-1]] + [lines[-1]]})


md(r"""
# Sorghum monitoring pipeline — ICPAC / FSRP-AF

Planting window, water balance, crop performance index and yield for **sorghum** across ten ICPAC
Member States, 2024.

**Why sorghum needs its own pipeline rather than the maize one run over a sorghum mask.** Sorghum
is the second cereal of the region by area and the first in its drylands: the crop-type masks place
**6.32 Mha in Sudan**, 1.84 Mha in Ethiopia and 0.57 Mha in Tanzania, against 1.54 Mha of maize in
the whole of Kenya. It is grown where the rains are least reliable, which is where anticipatory
action is needed and where a maize-shaped product helps least. Four things differ, and each is
sourced rather than inherited:

| | Maize | Sorghum | Source |
|---|---|---|---|
| Season calendar | `config/season_calendar.csv` | **Inception Report Table 2.0** | report pp. 16-17 |
| Cycle length | fixed 12 dekads | **9 to 18**, per product | report planting to harvest |
| Kc curve | 0.30 → 1.20 → 0.35 | **0.30 → 1.05 → 0.55** | FAO-56 Tables 11, 12 |
| Rooting depth | 1.0 m | **1.5 m** | FAO-56 Table 22 |
| FAO-33 Ky veg/flo/grf | 0.4 / **1.5** / 0.5 | 0.2 / **0.55** / 0.45 | FAO-33 Table 24 |
| Heat cap at flowering | 33 °C | **36 °C** | Prasad et al. 2008, 2015 |
| Crop mask | WorldCereal maize | **ICPAC crop-type mask** | this project |

**The Ky row is the substantive one.** Sorghum's total yield-response factor is 0.9 against maize's
1.25, and its flowering weight is 0.55 against 1.50. A water deficit at flowering costs maize
nearly three times what it costs sorghum. Scored with maize factors, a sorghum crop would be
declared failed in seasons it comes through — the failure mode that matters most, because sorghum
is grown precisely where the rains fail.

**The mask row would fail silently.** WorldCereal has no sorghum class, and `run.crop_mask_image`
falls through to the temporary-crops extent, which is all cropland, for any crop that is not maize.
A sorghum run left on the default would compute over every field in the country and label the
result sorghum. `ctm_mask.crop_mask` raises instead of falling back.

**Where this sits in the Inception Report.** Section 3.1 sets out a three-tier strategy for the
sorghum, millet and teff crop-type gap. Tier 1, a MapSPAM area-fraction prior over a cropland mask,
is "the operational default from day one and the benchmark for all later work". The ICPAC
crop-type mask **is** Tier 1, built stronger than the report assumed: SPAM shares over a
four-lineage, sixteen-source-year cropland vote, reweighted by suitability and satellite evidence
and calibrated to sub-national statistics, at 100 m rather than SPAM's 9 km. Tier 2, label
acquisition, has produced nothing, so Tier 3 is correctly not attempted.
""")

md("## 0 — Setup")

code(r"""
!pip -q install earthengine-api geemap pandas geopandas rasterio scipy 2>/dev/null
print("installed.")
""")

code(r"""
import ee
PROJECT = "ee-manzikye"      # compute and exports run here; the masks are READ from another project
try:
    ee.Initialize(project=PROJECT)
except Exception:
    ee.Authenticate(); ee.Initialize(project=PROJECT)
print("EE ready:", ee.String("ok").getInfo())
""")

code(r"""
from google.colab import drive; drive.mount("/content/drive")
import sys, os
PIPE_DIR = "/content/drive/MyDrive/planting_pipeline"
assert os.path.isdir(PIPE_DIR), f"Upload planting_pipeline to Drive; not at {PIPE_DIR}"
sys.path.insert(0, PIPE_DIR); sys.path.insert(0, f"{PIPE_DIR}/sorghum_pipeline")
os.chdir(PIPE_DIR)
print("pipeline on path:", PIPE_DIR)
""")

md(r"""
## 1 — The crop calendar

**Primary source: the Inception Report, Table 2.0** (pp. 16-17), which gives the rainfall regime,
main seasons, planting months and harvest months per country, using the season names FEWS NET and
the GEOGLAM Crop Monitor use operationally — which is also what HarvestStat reports against, so the
calibration matching is direct.

    planting window = the report's planting months, as whole dekads
    SOS window      = planting start + 1 dekad .. planting end + 3 dekads
    cycle           = mid-harvest minus mid-planting, in dekads, clamped to 9 .. 18

The SOS rule is the one the maize calendar already uses: green-up follows planting by about a
dekad, and the tail allows for the late end of a staggered planting front.

**GEOGLAM CM4EW v1.3 is carried alongside as a second arm, not discarded.** Its shapefile holds a
*sorghum-specific* calendar where Table 2.0 gives one generalised calendar per country covering
every crop it monitors. They **disagree for six of the nine products CM4EW covers**, by three
dekads for Kenya, Eritrea, Uganda and South Sudan's second season. Both arms were run and scored
(Section 7).
""")

code(r"""
!python sorghum_pipeline/build_calendar.py
""")

code(r"""
import pandas as pd
cal = pd.read_csv("sorghum_pipeline/config/season_calendar_sorghum.csv")
display(cal[["country","season","indicative_planting_window","sos_detection_window",
             "cycle_dekads","crop_viability","cm4ew_planting_window","cm4ew_agreement",
             "mapped_area_Mha"]])
""")

md(r"""
## 2 — The crop mask

From the ICPAC crop-type mask series, band `mask_sorghum`. Ten countries carry a sorghum band;
Djibouti has none, because SPAM 2020 places 47 ha of sorghum in the whole country.

**Two rules for using it.** The binary mask turns a whole 100 m cell on once sorghum reaches 10 %
of it, so region-wide it covers about **2.4 times** the ground the crop occupies (23.33 Mha of mask
over 9.91 Mha of crop). That is the right behaviour for a computation stratum and the wrong number
for an area. For area, use `frac_sorghum` with the pixel-area raster:

    area (ha) = sum( frac_sorghum / 100 × pixel_area_ha )

never a pixel count. A 0.0009° cell is 1.004 ha at the equator and 0.955 ha at 18 °N, so counting
pixels is wrong twice over.
""")

code(r"""
import ctm_mask as CTM
import sorghum_params as P
for c in ["Sudan", "Ethiopia", "Kenya", "Somalia", "Eritrea"]:
    print(f"{c:<10} {CTM.asset(c):<70} sorghum mapped {CTM.AREA_MHA.get((c,'sorghum'))} Mha")
print("\nFAO-33 Ky (sorghum):", P.SORGHUM_KY, " vs maize {'veg':0.4,'flo':1.5,'grf':0.5}")
print("FAO-56 Kc          :", {k: P.SORGHUM_KC[k] for k in ("Kc_ini","Kc_mid","Kc_end","root_depth_m")})
print("heat cap           :", P.SORGHUM_HEAT_TCAP, "C (maize 33)")
""")

md(r"""
## 3 — One product, interactively

`build_product_image` runs the whole graph for one calendar row and returns the output image plus
every intermediate, so the modules below all read one internally consistent result.

**The chain.** Main seasons use the fused green-up: Sentinel-2 red edge and MODIS FPAR combined
into a dekadal greenness proxy, gap-filled by the Sentinel-1 radar vegetation index, with start of
season the first sustained crossing of a quarter of the season amplitude, held within two dekads of
the climatological onset. Planting is SOS minus two dekads. Second and short seasons use the FEWS
rainfall rule instead, because green-up detection is unreliable there.

Then the FAO-56 water balance from each pixel's own planting dekad, over a **1.5 m** root zone,
with the Kc curve rescaled to that product's cycle length; the three stresses; and

$$\mathrm{CPI}=100\,(1-S_{\text{water}})(1-S_{\text{heat}})(1-S_{\text{veg}}),\qquad
Y_a=\frac{\mathrm{CPI}}{100}\,Y_m.$$
""")

code(r"""
import csv
import run_all_sorghum as R
from src import utils
kc, soil = utils.load_crop_coeffs()

COUNTRY, SEASON = "Sudan", "Kharif"          # <-- edit
row = next(r for r in csv.DictReader(open(R.CALENDARS["report"][0]))
           if r["country"] == COUNTRY and r["season"] == SEASON)
aoi = ee.Geometry.Rectangle([32.5, 12.0, 36.0, 15.0])    # fast test box; None = whole country
out, aoi, M3 = R.build_product_image(ee, row, soil, aoi=aoi, rich=True)
print("bands:", out.bandNames().getInfo())
print("onset:", M3["onset_method"], "| cycle", M3["kc"]["LGP_dekads"], "dekads",
      "| Ym", P.ym_for(COUNTRY, SEASON), "t/ha",
      "(calibrated)" if P.is_calibrated(COUNTRY, SEASON) else "(UNCALIBRATED)")
""")

code(r"""
import geemap
m = geemap.Map(center=[13.5, 34.0], zoom=7); m.add_basemap("HYBRID")
# planting dekad: ONE hue, dark (early) to light (late). A planting date is an ordered quantity with
# no meaningful midpoint, so a multi-hue or diverging ramp would invite reading the colours as
# categories.
BLUES = ["08306b","08519c","2171b5","4292c6","6baed6","9ecae1","c6dbef"]
RYG = ["a50026","fee08b","1a9850"]
ss, se = M3["ss"], M3["se"]
m.addLayer(M3["planting"], {"min": ss-2, "max": se, "palette": BLUES}, "Planting dekad")
m.addLayer(M3["cpi"], {"min": 0, "max": 100, "palette": RYG}, "CPI", False)
m.addLayer(M3["staged"]["wrsi_flo"], {"min": 40, "max": 100, "palette": RYG}, "WRSI @ flowering", False)
m
""")

md(r"""
## 4 — Submit the batch

Dry run first. Nothing is exported without `--submit`.

**Use `--rich`.** The reducer that feeds the apps needs `planting_dekad` and the six WRSI and WSI
stage bands, which only the rich export carries. The first submission of this pipeline was made
without it and had to be redone.

Assets land as `sorghumX_<Country>_<Season>_2024`. Arm B, the GEOGLAM calendar, goes to
`sorghumBX_*` and is restricted to the products that can actually be validated.
""")

code(r"""
!python sorghum_pipeline/run_all_sorghum.py --stage high --rich
# EE_PROJECT=ee-manzikye python sorghum_pipeline/run_all_sorghum.py --stage high --rich --submit
# EE_PROJECT=ee-manzikye python sorghum_pipeline/run_all_sorghum.py --calendar cm4ew --differing-only --rich --submit
""")

md(r"""
## 5 — Reduce to administrative units

The same reducer the maize products use, with a different asset and output prefix, so the CSV
schema the apps consume cannot drift between crops. Geometry and names come from the local GADM 4.1
GeoPackages; the statistics come from `reduceRegions` over the asset.
""")

code(r"""
!EE_PROJECT=ee-manzikye python reduce_newcountries.py --asset-prefix sorghumX --out-prefix newcS --project ee-manzikye
""")

md(r"""
## 6 — Fit the yield ceiling

$$Y_m=\frac{\sum y\,c}{\sum c^{2}},\qquad c=\mathrm{CPI}/100$$

The admin-2 CPI is aggregated onto the HarvestStat reporting units by polygon overlap, **weighted
by the sorghum area in each overlap** and measured in an **equal-area projection**, so a district
that is 2 % sorghum cannot count the same as one that is 60 %. The target is the **median over the
available years**, a typical year, which is robust to one bad season and applies to any season.
Skill is out of sample: 70/30 splits repeated 200 times.

**Read `r` before using a ceiling.** A calibrated level with `r` near zero means the map has the
average right but cannot tell which unit yielded more.
""")

code(r"""
!python sorghum_pipeline/calibrate_ym_sorghum.py
# add --write to patch YM_CAL_SORGHUM in sorghum_params.py
""")

md(r"""
### Result

| Country · season | $Y_m$ t/ha | Units | Held-out MAE, fitted vs default | $r$ | Status |
|---|---|---|---|---|---|
| Ethiopia Meher | 2.60 | 64 | 0.43 vs 0.52 | 0.21 | level only |
| **Kenya Long rains** | **1.41** | 27 | **0.27 vs 1.16** | **0.54** | **level and pattern** |
| Uganda 1st rains | 1.31 | 47 | 0.67 vs 1.45 | −0.02 | level only |
| Somalia Gu | 0.41 | 12 | 0.16 vs 1.52 | 0.36 | level, weak pattern |
| Somalia Deyr | 0.87 | 12 | 0.21 vs 0.26 | −0.04 | level only |
| Sudan Kharif | 0.80 | 16 | 0.27 vs 1.08 | −0.14 | level only |

South Sudan has 2 HarvestStat units, too few to fit. **Tanzania and Eritrea have no sorghum yields
in HarvestStat at all** and keep the uncalibrated default; their yield layers are hatched in the
atlas so they cannot be read as calibrated.
""")

md(r"""
## 7 — Which calendar? The A/B

Both calendars were run and scored against HarvestStat. The arms differ in **exactly one thing**:
arm B takes CM4EW's planting window and cycle, but its SOS window is re-derived with arm A's rule.
Deriving each arm's SOS by its own source's rule would have made Sudan and Somalia differ too,
although their planting windows agree exactly, and any result would then have been partly an
artefact of the rule.

The primary metric is the **Spearman correlation between CPI and reported yield**, which needs no
yield ceiling and so cannot be contaminated by a fitted $Y_m$. Mean absolute error is secondary,
with the ceiling **held fixed across the arms** — refitting per arm absorbs a level shift by
construction, which is how the WHC A/B in this project produced a win that vanished once both arms
shared a ceiling.
""")

code(r"""
!python sorghum_pipeline/score_calendar_ab.py
""")

md(r"""
### Result: no difference, and a more important finding underneath it

| Product | ρ arm A | ρ arm B | Δρ | 95 % interval | Verdict |
|---|---|---|---|---|---|
| Ethiopia Meher (n 64) | 0.032 | −0.012 | −0.044 | [−0.279, 0.187] | no difference |
| Kenya Long rains (n 27) | **0.592** | 0.546 | −0.046 | [−0.187, 0.073] | no difference |
| Uganda 1st rains (n 47) | **−0.196** | −0.202 | −0.007 | [−0.293, 0.274] | no difference |

Arm A is nominally ahead in all three, but **every interval spans zero**. The report's calendar
stands on the grounds of not being beaten, not of winning, and the three-dekad disagreements with
GEOGLAM remain a question for national partners that this test cannot close.

**The finding that matters more.** Only Kenya has real rank skill. **Uganda ranks districts
backwards**, ρ −0.20 under both calendars, which is worse than no information. Ethiopia is flat at
ρ ≈ 0.03, and the asset diagnostics say why: Ethiopian Meher sorghum runs at **WRSI 99 with
S_water 1.3 %**, so the water balance carries almost no signal and CPI is driven by the vegetation
term alone. Read Ethiopian and Ugandan sorghum CPI as a level, not a ranking.
""")

md(r"""
## 8 — Into the apps and the atlas

`app_data.py` registers all 18 sorghum products and builds only those whose reduce CSV exists, so
the apps never receive an empty product. The atlas sorghum risk layers are rasterised from the same
admin CSVs, with no further Earth Engine work.
""")

code(r"""
!python app_data.py && python embed_app_data.py
!python crop_type_mask/atlas/build_risk_sorghum.py
""")

md(r"""
## 9 — What is still open

1. **Nine of eighteen products are not yet run** — the Medium and Low viability seasons (Kenya
   short rains, Uganda 2nd, Rwanda, Burundi, Tanzania Masika, Ethiopia Belg, South Sudan 2nd).
2. **Tier 2 labels.** Every improvement beyond the current Tier 1 mask is gated on field labels,
   and none have been secured anywhere in the region.
3. **No independent field validation of sorghum planting dates.** The maize estimate is tested
   against farmer records for Kenya 2024 (MAE 1.02 dekads); nothing equivalent exists for sorghum.
   Collecting sorghum planting dates is the highest-value field activity available.
4. **Two parameters carried over from maize** with no sorghum source: the 2-dekad emergence offset
   and the 0.06 heat loss per heat-degree-dekad. Both are marked `FIRST PASS` in the code.
5. **The photothermal clock** the Inception Report reserves for photoperiod-sensitive landraces
   (§3.3.3) is not implemented, and it matters most exactly where the sorghum is: Sudan, South
   Sudan and Ethiopia.
6. **The cropland base still binds.** Sudan's map holds 6.32 of 7.48 Mha of reported sorghum, and
   the shortfall sits in the Darfur and Kordofan sand sheets the global cropland products miss.
""")

nb = {"cells": cells, "metadata": {"kernelspec": {"display_name": "Python 3", "name": "python3"},
      "language_info": {"name": "python"}, "colab": {"provenance": []}},
      "nbformat": 4, "nbformat_minor": 0}
out = f"{H}/sorghum_pipeline_colab.ipynb"
json.dump(nb, open(out, "w"), indent=1, ensure_ascii=False)
open(out, "a").write("\n")
print(f"{out}  ({len(cells)} cells: "
      f"{sum(1 for c in cells if c['cell_type']=='markdown')} markdown, "
      f"{sum(1 for c in cells if c['cell_type']=='code')} code)")
