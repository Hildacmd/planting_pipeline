#!/usr/bin/env python3
"""Generate the Google Colab notebook for the three modules (planting / risk / yield) with an
xclim climate-index track. Run: python build_colab.py  ->  planting_pipeline_colab.ipynb"""
import nbformat as nbf

nb = nbf.v4.new_notebook()
C, M = [], []
cells = []
def md(s): cells.append(nbf.v4.new_markdown_cell(s.strip("\n")))
def co(s): cells.append(nbf.v4.new_code_cell(s.strip("\n")))

md(r"""
# Crop-Specific Maize Monitoring — Colab (GEE × xclim)
**Three modules:** ① Planting window · ② Risk maps · ③ Yield forecast — for the Greater Horn of Africa.

**Architecture (hybrid).** Google Earth Engine is the **spatial engine** (Sentinel-2/1 phenology,
SoilGrids, 250 m aggregation). **xclim** computes the **climate indices** (GDD, SPI-3, dry spells, heat)
from ERA5 + CHIRPS pulled into `xarray` at native climate resolution (~5–28 km). xclim is a *computation*
library (CF-compliant, tested) — the data comes from **public cloud** (ARCO-ERA5 zarr, no key) and GEE.

### Where to start
1. **Put the `planting_pipeline` folder on your Google Drive** (so this notebook can `import src`).
2. Run the cells **top to bottom**. Section 0 authenticates GEE and mounts Drive.
3. Set your **AOI / season / year** in the config cell, then run each module.

> The GEE cells reuse your existing `src/` code. The xclim cells are self-contained.
""")

md("## Section 0 — Setup")

co(r"""
# 0.1  Install dependencies (Colab). ~2-3 min the first time.
!pip -q install earthengine-api geemap xee xclim xarray zarr gcsfs netCDF4 pandas geopandas 2>/dev/null
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
import geemap
COUNTRY   = "Kenya"          # "Kenya" | "Ethiopia"
SEASON    = "Long rains"     # "Long rains" | "Short rains" | "Meher"
YEAR      = 2024
from run import GAUL_NAME
from src import zonal_aggregate as ZA
aoi = ZA.gaul_admin(ee, [GAUL_NAME[COUNTRY]], level=0).geometry()
# a smaller test box speeds up interactive work (central/western Kenya). Comment out to use whole country.
AOI_TEST  = ee.Geometry.Rectangle([34.4, -1.2, 37.8, 1.2])
aoi_run   = AOI_TEST
print(f"{COUNTRY} · {SEASON} · {YEAR}")
Map = geemap.Map(); Map.centerObject(aoi_run, 7); Map
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
    s2 = S2.build_s2_dekadal(ee, aoi_run, YEAR); s1 = S1.build_s1_dekadal(ee, aoi_run, YEAR, orbit="DESCENDING")
    fpar = FZ.add_fpar_dekadal(ee, aoi_run, YEAR)
    g = FZ.build_fused_greenness(ee, s2, s1, fpar)
    ltn = LTN.build_ltn_prior(ee, aoi_run, ss, se)
    sos = FZ.detect_sos(ee, g, mask, ss, se, ltn_sos=ltn, ltn_pad=2)
    planting = PD.sos_to_planting(ee, sos, "maize").toInt16()

# 5+7 false-start gate (green-up seasons; short rains already carries 25/20)
if SEASON != "Short rains":
    ok = WR.dryspell_false_start(ee, aoi_run, planting, YEAR, dk_lo=ss, dk_hi=se+2)
    planting = planting.updateMask(ok)

Map.addLayer(planting.clip(aoi_run), {"min": ss, "max": se+3, "palette": ["440154","3b528b","21908d","5dc863","fde725"]},
             f"Planting dekad — {SEASON}")
Map
""")

md(r"""
## Section 2 — Risk-maps module  *(GEE spatial × xclim climate indices)*
GEE builds the spatial risk layers (WRSI / crop-failure / CPI / excess). **xclim** independently
computes the climate indices (GDD, SPI-3, dry spells) from public-cloud ERA5 + CHIRPS — a tested
cross-check on the hand-rolled GEE versions.
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
Map.addLayer(cpi_img.updateMask(mask).clip(aoi_run), {"min":0,"max":100,"palette":["a50026","fee08b","1a9850"]}, "CPI (GEE)")
Map.addLayer(staged["wrsi_flo"].updateMask(mask).clip(aoi_run), {"min":40,"max":100,"palette":["a50026","fee08b","1a9850"]}, "WRSI @flowering (GEE)")
Map
""")

co(r"""
# 2.2  xclim climate track A — GDD from public-cloud ERA5 (ARCO-ERA5 zarr on GCS, no API key)
#      NOTE: ARCO-ERA5 is ERA5 (~0.25 deg / 28 km), coarser than ERA5-Land (~9 km) — fine for a climate index.
import xarray as xr, numpy as np, xclim
from xclim.indicators.atmos import growing_degree_days

ARCO = "gs://gcp-public-data-arco-era5/ar/1959-2022-full_37-1h-0p25deg-chunk-1.zarr-v2"
bb = aoi_run.bounds().coordinates().get(0).getInfo()          # AOI bounds -> lat/lon slice
lons = [p[0] for p in bb]; lats = [p[1] for p in bb]
lo0, lo1, la0, la1 = min(lons), max(lons), min(lats), max(lats)

ds = xr.open_zarr(ARCO, chunks={"time": 48}, storage_options={"token": "anon"})
t2m = (ds["2m_temperature"]
       .sel(time=slice(f"{YEAR}-01-01", f"{YEAR}-12-31"))
       .sel(latitude=slice(la1, la0), longitude=slice(lo0 % 360, lo1 % 360)))   # ERA5 lat descending, lon 0-360
tas = (t2m.resample(time="1D").mean() - 273.15)               # daily mean, K -> degC
tas.attrs["units"] = "degC"; tas = tas.rename("tas")
gdd = growing_degree_days(tas=tas, thresh="10 degC", freq="YS").compute()       # xclim GDD (base 10 C)
print("xclim GDD (base 10C), area mean for", YEAR, ":", float(gdd.mean().values), "degree-days")
gdd.mean(dim="time").plot(cmap="YlOrRd"); import matplotlib.pyplot as plt; plt.title("xclim GDD — ERA5"); plt.show()
""")

co(r"""
# 2.3  xclim climate track B — SPI-3 and max consecutive dry days from CHIRPS (pulled from GEE via xee)
import xee
from xclim.indices import standardized_precipitation_index, maximum_consecutive_dry_days
chirps_ic = (ee.ImageCollection("UCSB-CHG/CHIRPS/DAILY")
             .filterDate(f"{YEAR-2}-01-01", f"{YEAR}-12-31").filterBounds(aoi_run).select("precipitation"))
dsp = xr.open_dataset(chirps_ic, engine="ee", geometry=aoi_run, scale=0.05)      # ~5.5 km CHIRPS -> xarray
pr = dsp["precipitation"].transpose("time", "lat", "lon")
pr.attrs["units"] = "mm/d"; pr = pr.rename("pr")

# max consecutive dry days (daily; per month)
mcdd = maximum_consecutive_dry_days(pr, thresh="1 mm/day", freq="MS").compute()
# SPI-3 (3-month window) vs the record's own calibration
pr_mon = pr.resample(time="MS").sum(); pr_mon.attrs["units"] = "mm"
spi3 = standardized_precipitation_index(pr_mon, freq="MS", window=3, dist="gamma", method="APP").compute()
print("xclim SPI-3 last month, area mean:", float(spi3.isel(time=-1).mean().values))
spi3.isel(time=-1).plot(cmap="BrBG", vmin=-2, vmax=2); import matplotlib.pyplot as plt; plt.title("xclim SPI-3 (CHIRPS)"); plt.show()
# (compare to the pipeline's pure-GEE SPI-3 in src/spi.py — same definition, different engine)
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
Map.addLayer(yield_tha.updateMask(mask).clip(aoi_run), {"min":0,"max":6,"palette":["ffffcc","78c679","006837"]}, "Yield t/ha (GEE)")

# admin-1 medians (yield) + total production over the AOI
adm1 = ZA.gaul_admin(ee, [GAUL_NAME[COUNTRY]], level=1)
stats = yield_tha.updateMask(mask).reduceRegions(adm1, ee.Reducer.median(), scale=250).filterBounds(aoi_run)
tot = yield_tha.updateMask(mask).multiply(PIXEL_HA).reduceRegion(ee.Reducer.sum(), aoi_run, 250, maxPixels=int(1e13))
print("AOI total production (t, indicative):", tot.get("yield_tha").getInfo())
Map
""")

md(r"""
## Section 4 — Notes, caveats, next steps
- **xclim vs GEE indices:** SPI-3 and GDD here (xclim, native ERA5/CHIRPS) are a *cross-check* on the
  pipeline's pure-GEE versions (`src/spi.py`, `src/gdd_clock.py`). They use the same definitions but a
  different engine/resolution — expect close, not identical, values.
- **Resolution:** ARCO-ERA5 is ~28 km (vs ERA5-Land ~9 km); CHIRPS ~5.5 km. Fine for climate indices,
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
