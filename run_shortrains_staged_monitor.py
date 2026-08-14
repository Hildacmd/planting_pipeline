#!/usr/bin/env python3
"""Dekadal, stage-resolved WRSI / WSI / crop-failure monitor — Kenya short-rains maize.

For each maize pixel, the FAO-56/33 water balance is run from the rainfall onset with a running WRSI,
and snapshotted at the end of the three growth stages (vegetative · flowering · grain-fill). Emits:
  wrsi_veg/flo/grf  — running WRSI at each stage end (0-100; <50 = crop failure at that stage)
  wsi_veg/flo/grf   — worst dekadal water stress within each stage (0-100)
Short-duration (early) maize; wraps into 2025 for grain-fill.

Run:  EE_PROJECT=ee-manzikye python run_shortrains_staged_monitor.py
"""
import sys, os
sys.path.insert(0, os.path.dirname(__file__))
from src import utils, wrsi_feedback as WR, zonal_aggregate as ZA, soil as SOIL
from src.wrsi_waterbalance import run_wrsi_staged
from run import crop_mask_image, GAUL_NAME

YEAR = 2024
SEARCH = (28, 34)
CLIM_YEARS = list(range(1981, 2025))
EARLY = {"LGP_dekads": 9, "L_ini": 2, "L_dev": 3, "L_mid": 2, "L_late": 2}


def main():
    ee = utils.gee_init()
    aoi = ZA.gaul_admin(ee, [GAUL_NAME["Kenya"]], level=0).geometry()
    kc, soil = utils.load_crop_coeffs()
    kc["maize_early"] = {**kc["maize"], **EARLY}
    pet = WR.pet_dekadal(ee, aoi, YEAR)
    ch = WR.chirps_dekadal(ee, aoi, YEAR)
    clim = WR.chirps_clim_dekadal(ee, aoi, range(SEARCH[0], 37), CLIM_YEARS)
    onset = WR.wrsi_onset(ee, ch, *SEARCH, pet_ic=pet).unmask(WR.wrsi_onset(ee, clim, *SEARCH, pet_ic=pet))
    mask = crop_mask_image(ee, "Kenya", "maize", None)
    planting = onset.updateMask(mask).toInt16()

    whc = SOIL.get_whc(ee, aoi, soil, root_depth_cm=int(kc["maize"].get("root_depth_m", 1.0) * 100))
    st = run_wrsi_staged(ee, aoi, YEAR, planting, "maize_early", kc, soil, *SEARCH, whc_img=whc)
    out = ee.Image.cat([st["wrsi_veg"], st["wrsi_flo"], st["wrsi_grf"],
                        st["wsi_veg"], st["wsi_flo"], st["wsi_grf"]]).toInt16()
    desc = "stagemonitor_Kenya_maize_Shortrains_2024"
    if os.environ.get("TO_ASSET"):
        ee.batch.Export.image.toAsset(image=out.clip(aoi), description=desc,
            assetId=f"projects/ee-manzikye/assets/{desc}", region=aoi, scale=250,
            maxPixels=int(1e13)).start()
    else:
        ee.batch.Export.image.toDrive(image=out.clip(aoi), description=desc, folder="planting_outputs",
            region=aoi, scale=250, crs="EPSG:4326", maxPixels=int(1e13)).start()
    print(f"  export started: {desc}  ({'asset' if os.environ.get('TO_ASSET') else 'drive'}; running WRSI + max WSI per stage)")


if __name__ == "__main__":
    main()
