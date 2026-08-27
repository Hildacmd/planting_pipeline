#!/usr/bin/env python3
"""Generate the Google Colab notebook for the three modules (planting / risk / yield) with an
GEE-only. Run: python build_colab.py  ->  planting_pipeline_colab.ipynb"""
import nbformat as nbf

nb = nbf.v4.new_notebook()
C, M = [], []
cells = []
def md(s): cells.append(nbf.v4.new_markdown_cell(s.strip("\n")))
def co(s): cells.append(nbf.v4.new_code_cell(s.strip("\n")))

md(r"""
# Crop-Specific Maize Monitoring — Colab (Google Earth Engine)
**Three modules:** ① Planting window · ② Risk maps · ③ Yield forecast — for the Greater Horn of Africa.

**Architecture (hybrid).** Google Earth Engine is the **spatial engine** (Sentinel-2/1 phenology,
SoilGrids, 250 m aggregation), all in the Earth Engine Python API. Each module reuses your existing `src/` code.
For separate, single-purpose notebooks see `01_planting_window` / `02_risk_monitoring` / `03_cpi_yield` / `04_flooding_waterlogging`.

### Where to start
1. **Put the `planting_pipeline` folder on your Google Drive** (so this notebook can `import src`).
2. Run the cells **top to bottom**. Section 0 authenticates GEE and mounts Drive.
3. Set your **AOI / season / year** in the config cell, then run each module.

> All cells reuse your existing `src/` code from Drive.
""")

md("## Section 0 — Setup")

co(r"""
# 0.1  Install dependencies (Colab). ~2-3 min the first time.
!pip -q install earthengine-api folium pandas geopandas 2>/dev/null
print("installed.")
""")

co(r"""
# 0.2  Authenticate + initialise Earth Engine  (use the account that owns project 'ee-manzikye')
import ee
PROJECT = "ee-manzikye"            # <-- your GEE cloud project
try:
    ee.Initialize(project=PROJECT)
except Exception:
    ee.Authenticate()              # opens a sign-in; paste the token
    ee.Initialize(project=PROJECT)
print("EE ready:", ee.String("ok").getInfo())
""")

co(r"""
# 0.3  Mount Google Drive and point at the pipeline folder (so we can import src/)
from google.colab import drive
drive.mount("/content/drive")
import sys, os
PIPE_DIR = "/content/drive/MyDrive/planting_pipeline"   # <-- adjust if you put it elsewhere
assert os.path.isdir(PIPE_DIR), f"Upload the planting_pipeline folder to Drive; not found at {PIPE_DIR}"
sys.path.insert(0, PIPE_DIR)
os.chdir(PIPE_DIR)                 # so relative config/ paths resolve
print("pipeline on path:", PIPE_DIR, "| src modules:", os.listdir("src")[:6], "...")
""")

co(r"""
# 0.4  Configuration — choose the country / season / year and an AOI
COUNTRY   = "Kenya"          # "Kenya" | "Ethiopia"
SEASON    = "Long rains"     # "Long rains" | "Short rains" | "Meher"
YEAR      = 2024
S1_ORBIT  = "ASCENDING"      # Sentinel-1B is gone (2022) -> ASCENDING has coverage over Kenya; try "DESCENDING" elsewhere
from run import GAUL_NAME
from src import zonal_aggregate as ZA
aoi = ZA.gaul_admin(ee, [GAUL_NAME[COUNTRY]], level=0).geometry()
# a smaller test box speeds up interactive work (central/western Kenya). Use `aoi` for the whole country.
AOI_TEST  = ee.Geometry.Rectangle([34.4, -1.2, 37.8, 1.2])
aoi_run   = AOI_TEST

# --- robust map display: raw folium + Earth Engine tile URLs (no geemap map -> avoids the xyz_to_folium bug) ---
import folium
def ee_layer(fmap, image, vis, name):
    mid = ee.Image(image).getMapId(vis)
    folium.TileLayer(mid["tile_fetcher"].url_format, attr="Google Earth Engine",
                     name=name, overlay=True, control=True).add_to(fmap)
def new_map(zoom=7):
    c = aoi_run.centroid(1).coordinates().getInfo()          # [lon, lat]
    return folium.Map(location=[c[1], c[0]], zoom_start=zoom, tiles="CartoDB positron")
print(f"{COUNTRY} · {SEASON} · {YEAR}  ·  S1 orbit {S1_ORBIT}")
""")

md(r"""
## Section 1 — Planting-window module  *(GEE)*
Cue fusion (Sentinel-2 red-edge NDRE + FPAR + SAR) → green-up SOS for the main seasons, or the
rainfall-anchored onset (CHIRPS 25/20 mm + P/PET) for the short rains, then the inception-report
**5 + 7 false-start gate** (`DRYSPELL_GATE`).
""")

co(r"""
# 1.1  Planting dekad for the chosen season
from src import (utils, s2_preprocess as S2, s1_preprocess as S1, fusion_phenometrics as FZ,
                 ltn as LTN, planting_date as PD, wrsi_feedback as WR)
from run import crop_mask_image
kc, soil = utils.load_crop_coeffs()
rows = {(r["country"], r["season"]): r for r in utils.viable_products(utils.load_calendar("config/season_calendar.csv"))
        if r["crop"].lower() == "maize"}
r  = rows[(COUNTRY, SEASON)]
ss, se = utils.sos_window_dekads(r["sos_detection_window"])
mask = crop_mask_image(ee, COUNTRY, "maize", None)

if SEASON == "Short rains":                       # rainfall-anchored onset
    pet = WR.pet_dekadal(ee, aoi_run, YEAR); ch = WR.chirps_dekadal(ee, aoi_run, YEAR)
    planting = WR.wrsi_onset(ee, ch, ss, se, pet_ic=pet).updateMask(mask).toInt16()
else:                                             # green-up cue fusion
    s2 = S2.build_s2_dekadal(ee, aoi_run, YEAR); s1 = S1.build_s1_dekadal(ee, aoi_run, YEAR, orbit=S1_ORBIT)
    fpar = FZ.add_fpar_dekadal(ee, aoi_run, YEAR)
    g = FZ.build_fused_greenness(ee, s2, s1, fpar)
    ltn = LTN.build_ltn_prior(ee, aoi_run, ss, se)
    sos = FZ.detect_sos(ee, g, mask, ss, se, ltn_sos=ltn, ltn_pad=2)
    planting = PD.sos_to_planting(ee, sos, "maize").toInt16()

# 5+7 false-start gate (green-up seasons; short rains already carries 25/20)
if SEASON != "Short rains":
    ok = WR.dryspell_false_start(ee, aoi_run, planting, YEAR, dk_lo=ss, dk_hi=se+2)
    planting = planting.updateMask(ok)

# quick sanity: how many valid maize pixels?  (>0 => a product exists)
print("valid maize pixels:",
      planting.reduceRegion(ee.Reducer.count(), aoi_run, 250, maxPixels=int(1e13)).get("planting_dekad").getInfo())
M = new_map()
ee_layer(M, planting.clip(aoi_run), {"min": ss, "max": se+3, "palette": ["440154","3b528b","21908d","5dc863","fde725"]},
         f"Planting dekad — {SEASON}")
folium.LayerControl().add_to(M); M
""")

md(r"""
## Section 2 — Risk-maps module  *(GEE)*
GEE builds the spatial risk layers — staged **WRSI / WSI / crop-failure**, **CPI**, the
**excess / waterlogging** metrics, **fused canopy condition (FCCI)**, and **SPI-3** drought — masked to maize.
""")

co(r"""
# 2.1  GEE risk layers — staged WRSI/WSI + CPI + excess (SPI-3 wet) for the season
from src.wrsi_waterbalance import run_wrsi_staged
from src import cpi as CPI, soil as SOIL, spi as SPI, excess as EX
whc = SOIL.get_whc(ee, aoi_run, soil, root_depth_cm=int(kc["maize"].get("root_depth_m",1.0)*100))
staged = run_wrsi_staged(ee, aoi_run, YEAR, planting, "maize", kc, soil, ss, se, whc_img=whc)
Sw = CPI.s_water(ee, staged); Sh = CPI.s_heat(ee, aoi_run, YEAR, planting, kc["maize"]["L_ini"]+kc["maize"]["L_dev"],
                                              kc["maize"]["L_ini"]+kc["maize"]["L_dev"]+kc["maize"]["L_mid"], ss, se)
Sv = CPI.s_veg(ee, aoi_run, YEAR, ss, se)
cpi_img, yld = CPI.cpi(ee, Sw, Sh, Sv, ym=6.0)
M = new_map()
ee_layer(M, cpi_img.updateMask(mask).clip(aoi_run), {"min":0,"max":100,"palette":["a50026","fee08b","1a9850"]}, "CPI (GEE)")
ee_layer(M, staged["wrsi_flo"].updateMask(mask).clip(aoi_run), {"min":40,"max":100,"palette":["a50026","fee08b","1a9850"]}, "WRSI @flowering (GEE)")
folium.LayerControl().add_to(M); M
""")

co(r"""
# 2.1b  New monitoring layers — waterlogging (AquaCrop aeration) · SPI-3 wet · fused canopy condition (FCCI)
from src import excess as EX
hy = SOIL.build_hydro_mm(ee, root_depth_cm=100)                       # FC/SAT/tau from SoilGrids+Saxton
mz = kc["maize"]; d_veg=mz["L_ini"]+mz["L_dev"]; d_flo=d_veg+mz["L_mid"]; lgp=mz["LGP_dekads"]
wl  = EX.aeration_stress_index(ee, aoi_run, planting, YEAR, d_veg, d_flo, lgp, ss, se, hy["FC_mm"], hy["SAT_mm"], hy["tau"])
wet = EX.spi3_wet(ee, aoi_run, YEAR, end_month=5)                     # SPI-3 wet anomaly (>=+1.5)
M = new_map()
ee_layer(M, wl.updateMask(mask).clip(aoi_run),  {"min":0,"max":40,"palette":["f7fbff","6baed6","08306b"]}, "Soil waterlogging — modelled")
ee_layer(M, wet.updateMask(mask).clip(aoi_run), {"min":0,"max":1,"palette":["ffffff","3690c0"]}, "SPI-3 very wet (excess)")
if SEASON != "Short rains":                                          # FCCI = peak fused greenness (green-up seasons)
    fcci = FZ.fused_condition(ee, g, mask, ss, se, lgp=lgp)
    ee_layer(M, fcci.clip(aoi_run), {"min":0,"max":100,"palette":["a50026","fee08b","1a9850"]}, "Canopy condition (fused 10-20 m)")
folium.LayerControl().add_to(M); M
""")

co(r"""
# 2.2  SPI-3 meteorological drought (pure GEE, src/spi.py) — the drought layer
from src import spi as SPI
end_m = 5 if SEASON=='Long rains' else (9 if SEASON=='Meher' else 12)
spi3 = SPI.spi3(ee, aoi_run, YEAR, end_month=end_m)
M = new_map()
ee_layer(M, spi3.updateMask(mask).clip(aoi_run), {"min":-2,"max":2,"palette":["a50026","fee08b","ffffff","abd9e9","4575b4"]}, "SPI-3 (drought −/+ wet)")
folium.LayerControl().add_to(M); M
""")

md(r"""
## Section 3 — Yield-forecast module  *(GEE)*
Yield-gap framing: **yield (t/ha) = CPI/100 × Ym**, then × harvested area for production. Aggregated
to admin units. Ym is a reference potential — calibrate against observed yields (KALRO / HarvestStat).
""")

co(r"""
# 3.1  Yield & production from the CPI computed in Section 2
YM = 6.0                                        # reference potential (t/ha); short rains ~4.5
yield_tha = cpi_img.divide(100).multiply(YM).rename("yield_tha")
PIXEL_HA  = 6.25                                # 250 m pixel
M = new_map()
ee_layer(M, yield_tha.updateMask(mask).clip(aoi_run), {"min":0,"max":6,"palette":["ffffcc","78c679","006837"]}, "Yield t/ha (GEE)")
folium.LayerControl().add_to(M)

# total production over the AOI
tot = yield_tha.updateMask(mask).multiply(PIXEL_HA).reduceRegion(ee.Reducer.sum(), aoi_run, 250, maxPixels=int(1e13))
print("AOI total production (t, indicative):", tot.get("yield_tha").getInfo())
M
""")

md(r"""
## Section 4 — Notes, caveats, next steps
- **Indices:** SPI-3, GDD, WRSI are computed pure-GEE (`src/spi.py`, `src/gdd_clock.py`, `src/wrsi_waterbalance.py`); this line is
  pipeline's pure-GEE versions (`src/spi.py`, `src/gdd_clock.py`). They use the same definitions but a
  different engine/resolution — expect close, not identical, values.
- **Resolution:** CHIRPS ~5.5 km and ERA5-Land ~9-11 km climate content on the 250 m grid — admin-scale,
  coarse for the 250 m grid — the GEE spatial layers stay authoritative for mapping.
- **Excess / waterlogging:** the aeration model (`src/excess.py`) is soil-water-based and *uncalibrated*;
  cross-check with the SPI-3-wet anomaly. See `WATERLOGGING_METHODOLOGY`.
- **Scale up:** swap `aoi_run = AOI_TEST` for the full-country `aoi`, and export with
  `ee.batch.Export.image.toDrive(...)` (batch) rather than interactive — see the `run_*.py` scripts.
- **Calibration:** Ym, CPI stress params, and the aeration parameters need observed-yield / crop-cut
  calibration before operational use.
""")

nb["cells"] = cells
nb["metadata"] = {"colab": {"provenance": [], "toc_visible": True},
                  "kernelspec": {"name": "python3", "display_name": "Python 3"},
                  "language_info": {"name": "python"}}
nbf.write(nb, "planting_pipeline_colab.ipynb")
print("wrote planting_pipeline_colab.ipynb  (", len(cells), "cells )")
