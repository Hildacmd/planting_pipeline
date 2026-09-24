#!/usr/bin/env python3
"""Generate ONE comprehensive Colab notebook covering ALL GHA countries and ALL FOUR modules,
with a plain-language explanation before each module. GEE-only (no xclim); reuses your src/ code
and run_all_maize_2024.build_product_image so every country/season (incl. rainfall-anchored short
seasons and cross-year main seasons like Tanzania Msimu) is handled by the SAME validated graph.

Run:  python build_colab_all.py   ->  planting_pipeline_ALL_colab.ipynb
"""
import nbformat as nbf

def md(s): return nbf.v4.new_markdown_cell(s.strip("\n"))
def co(s): return nbf.v4.new_code_cell(s.strip("\n"))

cells = []

cells.append(md(r"""
# Crop-Specific Maize Monitoring — Greater Horn of Africa (all countries, all modules)
### One Colab notebook · Google Earth Engine · 11 countries · 2024

This notebook runs the **as-built ICPAC planting pipeline** for **any country and season** in the
Greater Horn of Africa, one module at a time, with a short explanation before each. It reuses the
exact `src/` code and the `build_product_image()` graph that produced the 2024 continental asset set,
so the demo here is the same computation as the operational run — only clipped to a small fast test box.

**The four modules**
1. **Planting window** — when the crop went in (onset), per pixel.
2. **Risk monitoring** — staged water balance (WRSI) and the water / heat / vegetation stresses.
3. **CPI & yield** — the Crop Performance Index and the calibrated yield estimate.
4. **Flooding / waterlogging** — the wet-side hazard the WRSI cannot see.

**Countries & seasons (2024):** Kenya (Long, Short) · Ethiopia (Meher, Belg) · Somalia (Gu, Deyr) ·
Uganda (1st, 2nd) · Rwanda (A, B) · Burundi (A, B) · Tanzania (Masika, Msimu, Vuli) · South Sudan (Main).

### How to run
1. Put the whole **`planting_pipeline`** folder on your Google Drive (so `import src` works).
2. Run the cells **top to bottom**. Section 0 signs you into Earth Engine and mounts Drive.
3. In the **config cell**, set `COUNTRY` and `SEASON` from the printed list, then run each module.

> Every module reuses your `src/` code from Drive. Maps use **geemap** with the native Earth Engine
> Layers panel (toggle + opacity), so no Google Maps API key is needed.
"""))

# ---------------- Section 0 · Setup ----------------
cells.append(md("## Section 0 — Setup (Earth Engine + Drive)"))
cells.append(co("!pip -q install earthengine-api geemap pandas geopandas 2>/dev/null\nprint('installed.')"))
cells.append(co(
'import ee\nPROJECT="ee-manzikye"   # <-- your Earth Engine cloud project\n'
'try:\n    ee.Initialize(project=PROJECT)\nexcept Exception:\n'
'    ee.Authenticate(); ee.Initialize(project=PROJECT)\nprint("EE ready:", ee.String("ok").getInfo())'))
cells.append(co(
'from google.colab import drive; drive.mount("/content/drive")\nimport sys, os\n'
'PIPE_DIR="/content/drive/MyDrive/planting_pipeline"   # adjust if your folder is elsewhere\n'
'assert os.path.isdir(PIPE_DIR), f"Upload planting_pipeline to Drive; not found at {PIPE_DIR}"\n'
'sys.path.insert(0, PIPE_DIR); os.chdir(PIPE_DIR)\nprint("pipeline on path:", PIPE_DIR)'))

# ---------------- Config / country picker ----------------
cells.append(md(r"""
### Configure country & season
The pipeline knows every viable maize season from `config/season_calendar.csv`. The cell below prints
the full menu, then you pick one. Each country has a small **test box** so the demo runs in seconds;
set `USE_WHOLE_COUNTRY=True` to run the real AOI (slower). The onset method (green-up vs rainfall) and
any cross-year handling are chosen automatically by the calendar, exactly as in the operational run.
"""))
cells.append(co(
'from src import utils\n'
'from run_all_maize_2024 import build_product_image, YEAR\n'
'from run import GAUL_NAME\nfrom src import zonal_aggregate as ZA\n'
'kc, soil = utils.load_crop_coeffs()\n'
'ROWS = {(r["country"], r["season"]): r for r in\n'
'        utils.viable_products(utils.load_calendar("config/season_calendar.csv"))\n'
'        if r["crop"].lower() == "maize"}\n'
'print("Available (country, season) products:")\n'
'for (c, s) in ROWS: print(f"   {c:12s} {s}")\n'
'\n'
'# small representative demo boxes [west,south,east,north] (maize belts); fallback = country bounds\n'
'TEST_BOX = {\n'
'  "Kenya":       [34.4,-1.2,37.8,1.2],   "Ethiopia":  [37.0,7.0,39.5,9.5],\n'
'  "Somalia":     [42.0,1.5,44.5,3.5],    "Uganda":    [30.5,0.2,33.5,2.2],\n'
'  "Rwanda":      [29.2,-2.4,30.6,-1.3],  "Burundi":   [29.2,-3.9,30.5,-2.8],\n'
'  "Tanzania":    [34.0,-6.5,36.5,-4.5],  "South Sudan":[30.0,4.0,33.0,7.0],\n'
'}'))
cells.append(co(
'# >>> EDIT THESE TWO <<<\n'
'COUNTRY = "Kenya"        # e.g. "Tanzania"\n'
'SEASON  = "Long rains"   # must match one printed above for this country, e.g. "Msimu"\n'
'USE_WHOLE_COUNTRY = False # True = real AOI (slow); False = fast test box\n'
'\n'
'assert (COUNTRY, SEASON) in ROWS, f"{(COUNTRY, SEASON)} not in the menu above"\n'
'r = ROWS[(COUNTRY, SEASON)]\n'
'if USE_WHOLE_COUNTRY:\n'
'    gname = GAUL_NAME.get(COUNTRY) or GAUL_NAME.get(COUNTRY.replace(" ", "_"), COUNTRY)\n'
'    aoi_run = ZA.gaul_admin(ee, [gname], level=0).geometry()\n'
'else:\n'
'    aoi_run = ee.Geometry.Rectangle(TEST_BOX.get(COUNTRY, [34.4,-1.2,37.8,1.2]))\n'
'\n'
'import geemap\n'
'try:\n'
'    from google.colab import output; output.enable_custom_widget_manager()\n'
'except Exception:\n'
'    pass\n'
'def new_map(zoom=7):\n'
'    m = geemap.Map(add_google_map=False, basemap="SATELLITE"); m.centerObject(aoi_run, zoom); return m\n'
'def ee_layer(m, image, vis, name, shown=True, opacity=1.0):\n'
'    m.addLayer(ee.Image(image), vis, name, shown, opacity); return m\n'
'print(f"Selected: {COUNTRY} · {SEASON} · {YEAR}  ·  onset window dekads = {r[\'sos_detection_window\']}")'))

# ---------------- One compute for modules 1-3 ----------------
cells.append(md(r"""
### Compute the product once (feeds Modules 1–3)
`build_product_image()` runs the whole graph for the selected country/season and returns the output
image plus every intermediate (`planting`, staged WRSI, the three stresses, CPI, yield). Modules 1–3
below just visualise pieces of this one result — so they are always internally consistent.
"""))
cells.append(co(
'out, aoi_run, M3 = build_product_image(ee, r, kc, soil, aoi=aoi_run, rich=True)\n'
'planting = M3["planting"]; staged = M3["staged"]\n'
'Sw, Sh, Sv = M3["Sw"], M3["Sh"], M3["Sv"]; cpi_img, yld = M3["cpi"], M3["yld"]; mask = M3["mask"]\n'
'print("computed:", out.bandNames().getInfo())\nprint("onset method:", M3["onset_method"])'))

# ---------------- Module 1 · Planting window ----------------
cells.append(md(r"""
## Module 1 — Planting window (onset)

**What it answers:** *for each field, which 10-day period (dekad) did the crop go in?*

**How it works.** For **main seasons** the onset is a **cue-fusion green-up**: Sentinel-2 red-edge
(NDRE) is the primary signal, MODIS FPAR confirms canopy build-up, and Sentinel-1 SAR fills cloud
gaps. The first sustained green-up crossing inside the season window is the start-of-season (SOS);
a crop-specific offset (maize 2 dekads, wheat/teff 1) converts SOS to the **planting dekad**. For
**short / second seasons** green-up is too weak, so onset is **rainfall-anchored** (CHIRPS onset:
25 mm in a dekad with ≥20 mm follow-on, and P/PET support). **Cross-year seasons** (e.g. Tanzania
Msimu, Dec→Feb) are built from the prior year with the dekads wrapped past 36.

*Dekad 1 = 1–10 Jan … dekad 36 = 21–31 Dec. Higher = later planting.*
"""))
cells.append(co(
'M = new_map()\n'
'ee_layer(M, planting.clip(aoi_run), {"min":1,"max":36,\n'
'         "palette":["08306b","08519c","2171b5","4292c6","6baed6","9ecae1","c6dbef"]}, f"Planting dekad — {COUNTRY} {SEASON}")\n'
'M'))

# ---------------- Module 2 · Risk monitoring ----------------
cells.append(md(r"""
## Module 2 — Risk monitoring (staged WRSI + stresses)

**What it answers:** *where and at which growth stage is the crop under stress?*

**How it works.** From the planting dekad we run a **FAO-56/33 water balance** (WRSI) forward through
three stages — **vegetative → flowering → grain-fill** — using ERA5-Land ET₀ (Hargreaves), CHIRPS
rainfall, and SoilGrids water-holding capacity. Each stage yields a running **WRSI** (100 = no water
limitation) and a **water-stress index (WSI)**. Flowering is weighted most heavily (FAO-33 Ky = 1.5),
because water or heat stress there costs the most yield. Alongside water we compute:
- **Heat stress** — heat-degree-dekads above a maize threshold, concentrated at flowering (pollen sterility).
- **Vegetation stress** — a down-weighted VCI / FPAR-anomaly confirmation of canopy condition.

The layers below are on a **0–100** scale (stresses: higher = worse; WRSI: higher = better).
"""))
cells.append(co(
'M = new_map()\n'
'ee_layer(M, staged["wrsi_flo"].clip(aoi_run), {"min":0,"max":100,"palette":["d73027","fee08b","1a9850"]}, "WRSI — flowering (100=no stress)")\n'
'ee_layer(M, Sw.multiply(100).clip(aoi_run), {"min":0,"max":100,"palette":["ffffff","fdae61","d73027"]}, "Water stress S_water (%)", False)\n'
'ee_layer(M, Sh.multiply(100).clip(aoi_run), {"min":0,"max":100,"palette":["ffffff","fdae61","d73027"]}, "Heat stress S_heat (%)", False)\n'
'ee_layer(M, Sv.multiply(100).clip(aoi_run), {"min":0,"max":100,"palette":["ffffff","fdae61","d73027"]}, "Vegetation stress S_veg (%)", False)\n'
'M   # toggle layers in the Layers panel'))

# ---------------- Module 3 · CPI & yield ----------------
cells.append(md(r"""
## Module 3 — Crop Performance Index & yield

**What it answers:** *how good is the season, and how much maize per hectare?*

**How it works.** The three stresses combine **multiplicatively** (AquaCrop-style) into a single
**Crop Performance Index**:

$$\text{CPI} = 100\,(1-S_{water})(1-S_{heat})(1-S_{veg})$$

CPI is the fraction of the attainable ceiling the crop is on track to reach. Yield is then
$\text{yield} = (\text{CPI}/100)\times Y_m$, where **Yₘ is an attainable-ceiling** calibrated
against **HarvestStat Africa** official statistics (least-squares through origin, 70/30 train/test).
Yₘ is **AEZ-aware** where it helps: in Kenya's Long rains the cool **highland** (≥ 1800 m) carries a
higher ceiling (3.2 t/ha) than the rest (2.1 t/ha), because the highland edge is *potential*, not
water timing. Uncalibrated countries fall back to season defaults (6.0 t/ha main, 4.5 short).
"""))
cells.append(co(
'M = new_map()\n'
'ee_layer(M, cpi_img.clip(aoi_run), {"min":0,"max":100,"palette":["d73027","fee08b","1a9850"]}, "CPI (0-100)")\n'
'ee_layer(M, yld.clip(aoi_run), {"min":0,"max":6,"palette":["ffffcc","c2e699","78c679","238443"]}, "Yield (t/ha)", False)\n'
'M'))
cells.append(co(
'# quick numbers over the test box (mean CPI / mean yield)\n'
'stats = out.select(["CPI","yield_tha_x100"]).reduceRegion(\n'
'    ee.Reducer.mean(), aoi_run, scale=250, maxPixels=int(1e10), bestEffort=True).getInfo()\n'
'print(f"{COUNTRY} {SEASON}:  mean CPI = {stats.get(\'CPI\'):.1f}   mean yield = {stats.get(\'yield_tha_x100\')/100:.2f} t/ha")'))

# ---------------- Module 4 · Flooding / waterlogging ----------------
cells.append(md(r"""
## Module 4 — Flooding / waterlogging (the wet-side hazard)

**What it answers:** *where is there too much water — the risk WRSI cannot see?*

WRSI only measures **deficit**; it saturates at 100 and is blind to excess. Two complementary metrics
cover the wet side:
- **SPI-3 wet anomaly** (validated) — a 3-month standardized-precipitation surplus flags surface /
  seasonal excess rainfall.
- **Soil aeration-stress index** (modelled, uncalibrated) — days the root zone sits above field
  capacity toward saturation during the crop cycle, from a SoilGrids + Saxton-Rawls hydrology.

Blue = wetter / more waterlogged. Read these together with the crop mask.
"""))
cells.append(co(
'from src import excess as EX, soil as SOIL\n'
'mz = kc["maize"]; d_veg = mz["L_ini"]+mz["L_dev"]; d_flo = d_veg+mz["L_mid"]; lgp = mz["LGP_dekads"]\n'
'ss, se = utils.sos_window_dekads(r["sos_detection_window"])\n'
'end_m = 5 if SEASON=="Long rains" else (9 if SEASON=="Meher" else 12)\n'
'wet = EX.spi3_wet(ee, aoi_run, YEAR, end_month=end_m)\n'
'hy = SOIL.build_hydro_mm(ee, root_depth_cm=100)   # FC/SAT/tau from SoilGrids + Saxton-Rawls\n'
'wl = EX.aeration_stress_index(ee, aoi_run, planting, YEAR, d_veg, d_flo, lgp, ss, se%36 or se, hy["FC_mm"], hy["SAT_mm"], hy["tau"])\n'
'print("excess / waterlogging computed")'))
cells.append(co(
'M = new_map()\n'
'ee_layer(M, wet.updateMask(mask).clip(aoi_run), {"min":0,"max":1,"palette":["ffffff","3690c0"]}, "SPI-3 very wet (excess, validated)")\n'
'ee_layer(M, wl.updateMask(mask).clip(aoi_run), {"min":0,"max":40,"palette":["f7fbff","6baed6","08306b"]}, "Soil waterlogging (modelled, uncal.)", False)\n'
'M'))

# ---------------- Section 5 · reproduce all countries ----------------
cells.append(md(r"""
## Section 5 — Reproduce the whole continent (batch)

The single-country cells above are for exploration. The **operational continental run** is driven by
two scripts (run them from a machine with the repo, not cell-by-cell — they submit Earth Engine batch
**asset exports** that run server-side for hours):

```bash
# 1) submit every viable 2024 maize product as a 250 m CPI/yield asset (cpi_<Country>_<Season>_2024)
EE_PROJECT=ee-manzikye python run_all_maize_2024.py --stage all --submit

# 1b) OR the richer stack (planting_dekad + 6 WRSI/WSI stage bands) that feeds the app panels
EE_PROJECT=ee-manzikye python run_all_maize_2024.py --stage all --rich --submit

# 2) calibrate the yield ceiling Ym against HarvestStat (70/30) and print paste-ready values
EE_PROJECT=ee-manzikye python calibrate_ym_all.py

# 3) watch the batch until it settles
EE_PROJECT=ee-manzikye python poll_tasks.py --watch 300
```

Onset is chosen per season automatically (green-up for main seasons, rainfall-anchored for short /
second seasons); cross-year seasons (e.g. Tanzania Msimu) are wrapped past dekad 36. Skip-guards mean
re-running only submits products that are not already an asset or in flight. See the accompanying
**ALL_COUNTRIES_2024 documentation** for datasets, algorithms step-by-step, the A/B tests, and how the
gaps were filled.
"""))

nb = nbf.v4.new_notebook()
nb.cells = cells
nb.metadata = {"colab": {"provenance": [], "toc_visible": True},
               "kernelspec": {"name": "python3", "display_name": "Python 3"}}
OUT = "planting_pipeline_ALL_colab.ipynb"
nbf.write(nb, OUT)
print(f"wrote {OUT} — {len(cells)} cells")
