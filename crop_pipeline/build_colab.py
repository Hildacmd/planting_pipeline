#!/usr/bin/env python3
"""Generate crop_pipeline_colab.ipynb: wheat, teff and millet end to end, documented.

    python crop_pipeline/build_colab.py

Generated rather than hand-edited, so the documentation cannot drift from the code it describes.
Edit this file, re-run it, and the notebook is rebuilt. Parameter tables are read from the
parameter modules at BUILD time, so a changed Kc or Ky appears here without anyone retyping it.
"""
import json, os, sys

H = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(H)
sys.path.insert(0, ROOT); sys.path.insert(0, H)
from params import get                                        # noqa: E402
import irrigation_exposure as IRR                             # noqa: E402

cells = []


def md(t):
    lines = t.strip("\n").split("\n")
    cells.append({"cell_type": "markdown", "metadata": {},
                  "source": [l + "\n" for l in lines[:-1]] + [lines[-1]]})


def code(t):
    lines = t.strip("\n").split("\n")
    cells.append({"cell_type": "code", "metadata": {}, "execution_count": None, "outputs": [],
                  "source": [l + "\n" for l in lines[:-1]] + [lines[-1]]})


def param_row(crop):
    p = get(crop)
    k, y = p.KC, p.KY
    return (f"| **{crop}** | {k['Kc_ini']} → {k['Kc_mid']} → {k['Kc_end']} | {k['LGP_dekads']} | "
            f"{k['root_depth_m']} m | {y['veg']} / **{y['flo']}** / {y['grf']} | {p.HEAT_TCAP:.0f} °C | "
            f"{p.YM_DEFAULT} |")


md(r"""
# Wheat, teff and millet — ICPAC / FSRP-AF

Planting window, water balance, crop performance index and yield for **wheat, teff and millet**,
2024. Seven products: wheat in Ethiopia, Kenya, Sudan and Tanzania; teff in Ethiopia; millet in
Sudan and Eritrea.

These three crops complete the regional cereal set alongside maize and sorghum. They are built on
the **ICPAC crop-type mask**, which is the only route to them: ESA WorldCereal has no millet or teff
class at all (Van Tricht et al. 2023), and `run.crop_mask_image` would silently return the
*temporary-crops* extent — all cropland — for any non-maize crop. `ctm_mask.crop_mask()` **raises**
instead of falling back, so a missing band is a visible error rather than a product quietly computed
over the wrong stratum.
""")

md(f"""
## Parameters, read from the parameter modules at build time

| crop | Kc ini → mid → end | cycle (dekads) | rooting depth | FAO-33 Ky veg/flo/grf | heat cap | Ym fallback |
|---|---|---|---|---|---|---|
{param_row("wheat")}
{param_row("teff")}
{param_row("millet")}

**Read the asterisks in the parameter modules.** FAO-33 (Doorenbos & Kassam 1979) tabulates neither
teff nor pearl millet, so their flowering Ky values are **first-pass analogues** taken from the
closest documented small-grain cereal. That is the honest state of the science for these crops, and
it sets how the output may be used: a wrong Ky biases CPI in a way calibration cannot detect,
because the fitted Ym absorbs the level and leaves the spatial pattern wrong.

Three things follow from the table:

- **Teff has the shortest cycle (9 dekads) and the shallowest roots (0.6 m)** in the whole pipeline.
  The 0.6 m rooting depth is why a dedicated 60 cm WHC asset was built: water-holding capacity is
  **not linear in depth**, so the 100 cm asset cannot be rescaled. At an Ethiopian highland site the
  60 cm asset gives 79 mm against the 100 cm asset's 128 mm — using the wrong one would overstate
  teff's available water by about 60 %.
- **Millet has the lowest Ky and the highest heat cap (38 °C)** — it is the most drought- and
  heat-tolerant cereal here, grown where nothing else ripens.
- **Wheat has the lowest heat cap (31 °C)** and the highest Kc_mid (1.15): it is the cool-season
  crop of the set and aborts grain at temperatures maize tolerates.
""")

md(r"""
## Setup

Mount Drive, install Earth Engine, authenticate. `EE_PROJECT` must be your own Earth Engine cloud
project — quota is per project.
""")
code(r"""
from google.colab import drive
drive.mount('/content/drive')

%pip -q install earthengine-api geemap geopandas rasterio
import os, sys
ROOT = '/content/drive/MyDrive/planting_pipeline'
os.chdir(ROOT); sys.path.insert(0, ROOT)
os.environ['EE_PROJECT'] = 'ee-manzikye'      # <- your project

import ee
ee.Authenticate()
ee.Initialize(project=os.environ['EE_PROJECT'])
print('Earth Engine ready:', ee.String('ok').getInfo())
""")

md(r"""
## 1. Build the season calendar

Seven products from the Inception Report windows plus GEOGLAM CM4EW where the report is silent. The
`crop_calendar_source` column records which, per row, so a partner can see the provenance of every
window rather than trusting one blanket statement.
""")
code(r"""
!python crop_pipeline/build_calendar.py
import pandas as pd
cal = pd.read_csv('crop_pipeline/config/season_calendar_wtm.csv')
cal[['country','crop','season','indicative_planting_window','sos_detection_window','crop_calendar_source']]
""")

md(r"""
## 2. What will run, and why

**The crop-type mask decides which crops run in which country.** A calendar row for a country whose
mask carries no band for that crop cannot be computed, and is dropped at *planning* time with the
reason printed, rather than raising mid-build. Run the coverage report first — it should always end
`0 unexplained`.
""")
code(r"""
!python crop_coverage.py
""")

md(r"""
## 3. Submit the products

`--rich` exports `planting_dekad` and the six WRSI/WSI stage bands as well as CPI and yield. **Use
it if the products are to reach the apps** — the reducer that feeds `pw_app.html` and `risk_app.html`
needs those bands.

Each asset is stamped with its parameters, its calendar source, its onset method and its
**irrigation exposure**, so a reader can tell from the asset alone whether a low CPI there is crop
condition or unmet irrigation demand.
""")
code(r"""
!python crop_pipeline/run_all_crop.py --crop wtm                  # dry run: prints the plan
# !EE_PROJECT=ee-manzikye python crop_pipeline/run_all_crop.py --crop wtm --submit --rich
""")

md(r"""
### Sudan's Shitwi wheat — the one product that cannot work rainfed

Sudan's wheat is **98.4 % irrigated**: scheme-grown winter wheat on the Nile and the Gezira, sown in
November in the dry season. Two things break:

1. **Onset cannot be detected.** The CHIRPS 25/20 mm rule needs 25 mm in a dekad and Sudan gets
   essentially none in November. The first run produced an asset with 10,478 wheat-mask pixels and
   **zero valid ones**. The workaround fixes the planting dekad at the start of the calendar's
   indicative window, because planting on a scheme is scheduled, not rain-driven.
2. **The water balance then returns CPI 0 everywhere**, including the Gezira — arithmetically
   correct and agronomically meaningless, because `Wb = SW + P` credits rainfall and nothing else.

So the product is **excluded from the apps and the Atlas**, while its asset and CSV are kept: the
deficit *is* the irrigation requirement, which is a useful number under a different name. The
exclusion is driven by the exposure grade, not a hardcoded country, so any future majority-irrigated
product is caught automatically.
""")
code(r"""
import irrigation_exposure as IRR
for c, crop in (('Sudan','wheat'), ('Sudan','millet'), ('Ethiopia','wheat'),
                ('Ethiopia','teff'), ('Kenya','wheat'), ('Tanzania','wheat'), ('Eritrea','millet')):
    r = IRR.record(c, crop)
    print(f"{c:9s} {crop:7s} {r['grade']:20s} {r['national_irr_pct']:5.1f}% national"
          + (f"   affected: {r['compromised_units']}" if r['compromised_units'] else ""))
""")

md(r"""
## 4. Reduce to admin units

Turns the 250 m rasters into the admin-level tables everything downstream reads — the apps, the
Atlas, the Ym calibration, the report. `crop_area_frac` is measured over the **same mask the product
was computed in**; a weight and a footprint that disagree corrupt the yield fit and the Atlas
thresholds alike.
""")
code(r"""
!EE_PROJECT=ee-manzikye python -u reduce_newcountries_tier2.py --crop wheat  --metrics spi,def,lvpd,fcci
!EE_PROJECT=ee-manzikye python -u reduce_newcountries_tier2.py --crop teff   --metrics spi,def,lvpd,fcci
!EE_PROJECT=ee-manzikye python -u reduce_newcountries_tier2.py --crop millet --metrics spi,def,lvpd,fcci
""")

md(r"""
**If an admin-1 reduce fails where admin-2 succeeded**, roll it up rather than leaving a hole. FCCI,
SPI-3 and deficit are area-mean quantities, so the admin-1 value *is* the crop-area-weighted mean of
its admin-2 units — this is the definition, not a substitute for it. Sudan millet FCCI needs this:
it fails with *User memory limit exceeded* at every scale because FCCI rebuilds the S2/S1/FPAR fusion
and Sudan's states are enormous. The rollup refuses any parent whose children are incomplete and
marks every value `direct` or `rollup_L2` in a companion column.
""")
code(r"""
!python tier2_rollup.py newcM_Sudan_Kharif_2024 --col fcci --apply
""")

md(r"""
## 5. Calibrate the yield ceiling

Ym is fitted by least squares through the origin of reported yield on CPI against HarvestStat
Africa v1.2, weighted by crop area, 70/30 split repeated 200 times.

**Report CPI, not yield, until this has run** — and read the `r` in the fitted comment before
reporting yield at all. Of the 23 ceilings fitted across the whole pipeline, 8 have **r < 0**: they
set a plausible average and then order the admin units *backwards*. Wheat's two fitted ceilings sit
at r = 0.07 (Kenya) and 0.15 (Ethiopia) — level only, no usable ranking. Teff is r = 0.33 and
Sudan millet r = 0.24: weak.
""")
code(r"""
!python crop_pipeline/calibrate_ym.py
# !python crop_pipeline/calibrate_ym.py --write     # patches YM_CAL in crop_pipeline/params/<crop>.py
""")

md(r"""
## 6. Apps, Atlas and the report

`app_data.py` rebuilds the product JSON, `embed_app_data.py` injects it into both apps. Products
graded `INVALID as rainfed` are excluded automatically; everything else with exposure gets a banner.
""")
code(r"""
!python app_data.py && python embed_app_data.py
!python build_crop_dossiers.py                 # per-crop dossiers, .md + .docx + .html
!python report/make_figures.py && python report/build_report.py
""")

md(r"""
## What to check before believing an output

| check | what good looks like |
|---|---|
| `crop_coverage.py` | ends `0 unexplained` |
| asset property `ym_calibrated` | `True`, else report CPI not yield |
| asset property `irrigation_exposure` | `negligible`, else read §7.3 of the workflow report |
| fitted `r` in the params comment | ≥ 0.4 to rank units; < 0 means the ranking is inverted |
| `crop_area_frac` source | the same mask the product was computed in |
| tier-2 columns | non-null count equals the unit count at both levels |

**Known gaps for these three crops**, stated so they are not rediscovered: teff and millet Ky are
first-pass analogues; Eritrea millet and Tanzania wheat have no fitted ceiling and run on fallbacks;
Sudan wheat cannot be calibrated at all while CPI is 0 everywhere; and MapSPAM 2020 predates
Ethiopia's irrigated-wheat expansion, so Ethiopia wheat's `negligible` grade is an as-of-2020 prior
and probably understates it.
""")

nb = {"cells": cells,
      "metadata": {"kernelspec": {"display_name": "Python 3", "name": "python3"},
                   "language_info": {"name": "python"}, "colab": {"provenance": []}},
      "nbformat": 4, "nbformat_minor": 0}
out = os.path.join(H, "crop_pipeline_colab.ipynb")
json.dump(nb, open(out, "w"), indent=1)
nmd = sum(1 for c in cells if c["cell_type"] == "markdown")
print(f"{out}  ({len(cells)} cells: {nmd} markdown, {len(cells) - nmd} code)")
