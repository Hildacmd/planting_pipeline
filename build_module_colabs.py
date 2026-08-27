#!/usr/bin/env python3
"""Generate four clean, GEE-only Colab notebooks (no xclim), one per module:
  01_planting_window · 02_risk_monitoring · 03_cpi_yield · 04_flooding_waterlogging
Each shares a compact setup (auth, Drive import of src/, folium map helper) and runs its module.
Run:  python build_module_colabs.py
"""
import nbformat as nbf

def md(s): return nbf.v4.new_markdown_cell(s.strip("\n"))
def co(s): return nbf.v4.new_code_cell(s.strip("\n"))

def setup(title, blurb):
    return [
        md(f"# {title}\n{blurb}\n\n**Where to start:** put the `planting_pipeline` folder on your Google Drive, "
           "run the cells top-to-bottom, and approve the Drive-mount and Earth-Engine sign-in prompts."),
        md("## Setup"),
        co("!pip -q install earthengine-api folium pandas geopandas 2>/dev/null\nprint('installed.')"),
        co('import ee\nPROJECT="ee-manzikye"\ntry:\n    ee.Initialize(project=PROJECT)\nexcept Exception:\n'
           '    ee.Authenticate(); ee.Initialize(project=PROJECT)\nprint("EE ready:", ee.String("ok").getInfo())'),
        co('from google.colab import drive; drive.mount("/content/drive")\nimport sys, os\n'
           'PIPE_DIR="/content/drive/MyDrive/planting_pipeline"   # adjust if needed\n'
           'assert os.path.isdir(PIPE_DIR), f"Upload planting_pipeline to Drive; not at {PIPE_DIR}"\n'
           'sys.path.insert(0, PIPE_DIR); os.chdir(PIPE_DIR)\nprint("pipeline on path:", PIPE_DIR)'),
        co('# --- config + robust folium map (EE tile URLs; no geemap) ---\n'
           'COUNTRY="Kenya"      # "Kenya" | "Ethiopia"\nSEASON ="Long rains" # "Long rains" | "Short rains" | "Meher"\n'
           'YEAR=2024\nS1_ORBIT="ASCENDING"   # S1B gone (2022) -> ASCENDING has coverage over Kenya\n'
           'from run import GAUL_NAME\nfrom src import zonal_aggregate as ZA\n'
           'aoi = ZA.gaul_admin(ee, [GAUL_NAME[COUNTRY]], level=0).geometry()\n'
           'aoi_run = ee.Geometry.Rectangle([34.4,-1.2,37.8,1.2])   # fast test box; use `aoi` for whole country\n'
           'import folium\n'
           'def ee_layer(fmap,image,vis,name):\n'
           '    m=ee.Image(image).getMapId(vis)\n'
           '    folium.TileLayer(m["tile_fetcher"].url_format,attr="Google Earth Engine",name=name,overlay=True,control=True).add_to(fmap)\n'
           'def new_map(zoom=7):\n'
           '    c=aoi_run.centroid(1).coordinates().getInfo(); return folium.Map(location=[c[1],c[0]],zoom_start=zoom,tiles="CartoDB positron")\n'
           'print(f"{COUNTRY} · {SEASON} · {YEAR} · S1 {S1_ORBIT}")'),
    ]

PLANTING_CORE = (
    "# --- planting dekad (onset) — cue-fusion green-up (main seasons) or rainfall onset (short rains) ---\n"
    "from src import (utils, s2_preprocess as S2, s1_preprocess as S1, fusion_phenometrics as FZ,\n"
    "                 ltn as LTN, planting_date as PD, wrsi_feedback as WR)\n"
    "from run import crop_mask_image\n"
    "kc, soil = utils.load_crop_coeffs()\n"
    "rows={(r['country'],r['season']):r for r in utils.viable_products(utils.load_calendar('config/season_calendar.csv')) if r['crop'].lower()=='maize'}\n"
    "r=rows[(COUNTRY,SEASON)]; ss,se=utils.sos_window_dekads(r['sos_detection_window']); mask=crop_mask_image(ee,COUNTRY,'maize',None)\n"
    "if SEASON=='Short rains':\n"
    "    pet=WR.pet_dekadal(ee,aoi_run,YEAR); ch=WR.chirps_dekadal(ee,aoi_run,YEAR)\n"
    "    planting=WR.wrsi_onset(ee,ch,ss,se,pet_ic=pet).updateMask(mask).toInt16()\n"
    "else:\n"
    "    s2=S2.build_s2_dekadal(ee,aoi_run,YEAR); s1=S1.build_s1_dekadal(ee,aoi_run,YEAR,orbit=S1_ORBIT); fpar=FZ.add_fpar_dekadal(ee,aoi_run,YEAR)\n"
    "    g=FZ.build_fused_greenness(ee,s2,s1,fpar); ltn=LTN.build_ltn_prior(ee,aoi_run,ss,se)\n"
    "    sos=FZ.detect_sos(ee,g,mask,ss,se,ltn_sos=ltn,ltn_pad=2); planting=PD.sos_to_planting(ee,sos,'maize').toInt16()\n"
    "print('planting dekad computed for', COUNTRY, SEASON)"
)
MED = "mz=kc['maize']; d_veg=mz['L_ini']+mz['L_dev']; d_flo=d_veg+mz['L_mid']; lgp=mz['LGP_dekads']"

NOTEBOOKS = {}

# ---------- 01 · Planting window ----------
NOTEBOOKS["01_planting_window"] = setup(
    "Module 1 — Planting Window (maize, GHA)",
    "Estimates the **planting dekad** per maize pixel: cue-fusion green-up (Sentinel-2 NDRE + S1 SAR + FPAR) for the "
    "main seasons, or CHIRPS rainfall onset (25/20 mm) for the short rains, then the inception-report **5+7 false-start gate**.") + [
    md("## Planting-window estimation"),
    co(PLANTING_CORE),
    co("# 5+7 false-start gate (green-up seasons; short rains already carries the 25/20 mm rule)\n"
       "if SEASON!='Short rains':\n"
       "    ok=WR.dryspell_false_start(ee,aoi_run,planting,YEAR,dk_lo=ss,dk_hi=se+2); planting=planting.updateMask(ok)\n"
       "print('valid maize pixels:', planting.reduceRegion(ee.Reducer.count(),aoi_run,250,maxPixels=int(1e13)).get('planting_dekad').getInfo())"),
    co("M=new_map()\nee_layer(M, planting.clip(aoi_run), {'min':ss,'max':se+3,'palette':['440154','3b528b','21908d','5dc863','fde725']}, f'Planting dekad — {SEASON}')\n"
       "folium.LayerControl().add_to(M); M"),
    md("*Higher dekad = later planting. Export with `ee.batch.Export.image.toDrive(...)`; see `run.py` for batch runs.*"),
]

# ---------- 02 · Risk monitoring ----------
NOTEBOOKS["02_risk_monitoring"] = setup(
    "Module 2 — Risk Monitoring (maize, GHA)",
    "Stage-resolved **WRSI / WSI / crop-failure** water-balance monitoring (FAO-56/33) plus **SPI-3** meteorological "
    "drought — anchored on the planting dekad, masked to maize.") + [
    md("## Planting (onset anchor)"), co(PLANTING_CORE),
    co("# --- staged WRSI/WSI + SPI-3 ---\n"
       "from src.wrsi_waterbalance import run_wrsi_staged\nfrom src import cpi as CPI, soil as SOIL, spi as SPI\n" + MED + "\n"
       "whc=SOIL.get_whc(ee,aoi_run,soil,root_depth_cm=int(mz.get('root_depth_m',1.0)*100))\n"
       "staged=run_wrsi_staged(ee,aoi_run,YEAR,planting,'maize',kc,soil,ss,se,whc_img=whc)\n"
       "failflo=staged['wrsi_flo'].lt(50)                       # crop-failure at flowering (<50)\n"
       "spi3=SPI.spi3(ee,aoi_run,YEAR,end_month=5 if SEASON=='Long rains' else (9 if SEASON=='Meher' else 12))\n"
       "print('risk layers computed')"),
    co("# --- Fused Canopy Condition Index (FCCI) — peak fused greenness (NDRE+FPAR+SAR), a vegetation cross-check on WRSI ---\n"
       "from src import s2_preprocess as S2, s1_preprocess as S1, fusion_phenometrics as FZ\n"
       "_s2=S2.build_s2_dekadal(ee,aoi_run,YEAR); _s1=S1.build_s1_dekadal(ee,aoi_run,YEAR,orbit=S1_ORBIT); _fp=FZ.add_fpar_dekadal(ee,aoi_run,YEAR)\n"
       "fcci=FZ.fused_condition(ee, FZ.build_fused_greenness(ee,_s2,_s1,_fp), mask, ss, se, lgp=lgp)\n"
       "print('FCCI computed (0-100; higher = more vigorous canopy)')"),
    co("M=new_map()\n"
       "ee_layer(M, staged['wrsi_flo'].updateMask(mask).clip(aoi_run), {'min':40,'max':100,'palette':['a50026','fee08b','1a9850']}, 'WRSI @flowering')\n"
       "ee_layer(M, failflo.updateMask(mask).clip(aoi_run), {'min':0,'max':1,'palette':['ffffff','a50026']}, 'Crop-failure @ flowering')\n"
       "ee_layer(M, spi3.updateMask(mask).clip(aoi_run), {'min':-2,'max':2,'palette':['a50026','fee08b','ffffff','abd9e9','4575b4']}, 'SPI-3 (drought/wet)')\n"
       "ee_layer(M, fcci.clip(aoi_run), {'min':0,'max':100,'palette':['a50026','fee08b','1a9850']}, 'Canopy condition (fused, FCCI)')\n"
       "folium.LayerControl().add_to(M); M"),
    md("*WRSI < 50 = crop failure · SPI-3 ≤ −1 = drought · FCCI = 10–20 m cloud-proof canopy-vigour cross-check. Admin roll-up: `cpi_admin.py`, `spi_admin.py`, `fcci_admin.py`.*"),
]

# ---------- 03 · CPI + yield ----------
NOTEBOOKS["03_cpi_yield"] = setup(
    "Module 3 — Crop Performance Index & Yield (maize, GHA)",
    "**CPI** = multi-stress multiplicative stacking (water × heat × vegetation), stage-weighted; then "
    "**yield (t/ha) = CPI/100 × Ym** and **production** = yield × area (250 m pixel = 6.25 ha).") + [
    md("## Planting (onset anchor)"), co(PLANTING_CORE),
    co("# --- CPI + yield ---\n"
       "from src.wrsi_waterbalance import run_wrsi_staged\nfrom src import cpi as CPI, soil as SOIL\n" + MED + "\n"
       "YM=4.5 if SEASON=='Short rains' else 6.0\n"
       "whc=SOIL.get_whc(ee,aoi_run,soil,root_depth_cm=int(mz.get('root_depth_m',1.0)*100))\n"
       "staged=run_wrsi_staged(ee,aoi_run,YEAR,planting,'maize',kc,soil,ss,se,whc_img=whc)\n"
       "Sw=CPI.s_water(ee,staged); Sh=CPI.s_heat(ee,aoi_run,YEAR,planting,d_veg,d_flo,ss,se); Sv=CPI.s_veg(ee,aoi_run,YEAR,ss,se)\n"
       "cpi_img,yld=CPI.cpi(ee,Sw,Sh,Sv,ym=YM)\n"
       "PIXEL_HA=6.25; production=yld.multiply(PIXEL_HA)\n"
       "tot=yld.updateMask(mask).multiply(PIXEL_HA).reduceRegion(ee.Reducer.sum(),aoi_run,250,maxPixels=int(1e13)).get('yield_tha').getInfo()\n"
       "print('CPI + yield computed · AOI total production (t, indicative):', round(tot))"),
    co("M=new_map()\n"
       "ee_layer(M, cpi_img.updateMask(mask).clip(aoi_run), {'min':0,'max':100,'palette':['a50026','fee08b','1a9850']}, 'CPI (0-100)')\n"
       "ee_layer(M, yld.updateMask(mask).clip(aoi_run), {'min':0,'max':6,'palette':['ffffcc','78c679','006837']}, 'Yield (t/ha)')\n"
       "folium.LayerControl().add_to(M); M"),
    md("*Ym is a **reference** potential — calibrate against observed yields (KALRO / HarvestStat). See `CPI_METHODOLOGY`, `YIELD_ESTIMATION_METHODOLOGY`.*"),
]

# ---------- 04 · Flooding / waterlogging ----------
NOTEBOOKS["04_flooding_waterlogging"] = setup(
    "Module 4 — Flooding / Waterlogging (maize, GHA)",
    "The **wet-side** hazard WRSI can't see. Two metrics: **SPI-3 wet anomaly** (validated, surface/seasonal excess) and "
    "the **AquaCrop aeration-stress** soil-water model (root-zone water above field capacity, from SoilGrids/Saxton — modelled, uncalibrated).") + [
    md("## Planting (onset anchor)"), co(PLANTING_CORE),
    co("# --- excess / waterlogging ---\n"
       "from src import excess as EX, soil as SOIL\n" + MED + "\n"
       "wet=EX.spi3_wet(ee,aoi_run,YEAR,end_month=5 if SEASON=='Long rains' else (9 if SEASON=='Meher' else 12))\n"
       "hy=SOIL.build_hydro_mm(ee,root_depth_cm=100)   # FC/SAT/tau from SoilGrids + Saxton-Rawls\n"
       "wl=EX.aeration_stress_index(ee,aoi_run,planting,YEAR,d_veg,d_flo,lgp,ss,se,hy['FC_mm'],hy['SAT_mm'],hy['tau'])\n"
       "print('excess/waterlogging computed')"),
    co("M=new_map()\n"
       "ee_layer(M, wet.updateMask(mask).clip(aoi_run), {'min':0,'max':1,'palette':['ffffff','3690c0']}, 'SPI-3 very wet (excess, validated)')\n"
       "ee_layer(M, wl.updateMask(mask).clip(aoi_run), {'min':0,'max':40,'palette':['f7fbff','6baed6','08306b']}, 'Soil waterlogging (modelled, uncal.)')\n"
       "folium.LayerControl().add_to(M); M"),
    md("*SPI-3 wet = **surface/seasonal** anomaly (validated); aeration = **root-zone** soil saturation (modelled, needs calibration) — "
       "two different hazards. See `WATERLOGGING_METHODOLOGY`.*"),
]

for name, cells in NOTEBOOKS.items():
    nb = nbf.v4.new_notebook(); nb["cells"] = cells
    nb["metadata"] = {"colab": {"provenance": [], "toc_visible": True},
                      "kernelspec": {"name": "python3", "display_name": "Python 3"}, "language_info": {"name": "python"}}
    nbf.write(nb, f"{name}.ipynb")
    print(f"wrote {name}.ipynb ({len(cells)} cells)")
