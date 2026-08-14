#!/usr/bin/env python3
"""Short-rains planting with a VARIETY-ADAPTIVE WRSI viability gate (Kenya maize).

Rainfall onset gives full coverage; a pixel is KEPT only if EARLY (~90-day) maize planted at that
onset achieves WRSI >= 50. Early is the shortest-that-fits variety, so it is the most permissive gate —
a pixel is dropped only if *even* early maize fails, which structurally avoids removing viable pixels
(a farmer would simply plant a short-duration variety). Pixels that fail are flagged non-viable.

Output bands: planting_dekad (viable only) · wrsi_early · viable (0/1 over all maize).
Run:  EE_PROJECT=ee-manzikye python run_shortrains_gated.py
"""
import sys, os
sys.path.insert(0, os.path.dirname(__file__))
from src import utils, wrsi_feedback as WR, zonal_aggregate as ZA, soil as SOIL
from run import crop_mask_image, GAUL_NAME

YEAR = 2024
SEARCH = (28, 34)
CLIM_YEARS = list(range(1981, 2025))
WRSI_MIN = 50                      # FEWS "not crop-failure" threshold
EARLY = {"LGP_dekads": 9, "L_ini": 2, "L_dev": 3, "L_mid": 2, "L_late": 2}   # ~85-90 day maize


def main():
    ee = utils.gee_init()
    aoi = ZA.gaul_admin(ee, [GAUL_NAME["Kenya"]], level=0).geometry()
    kc_cfg, soil_cfg = utils.load_crop_coeffs()
    kc_cfg["maize_early"] = {**kc_cfg["maize"], **EARLY}                     # short-duration variety
    pet = WR.pet_dekadal(ee, aoi, YEAR)
    chirps = WR.chirps_dekadal(ee, aoi, YEAR)
    clim = WR.chirps_clim_dekadal(ee, aoi, range(SEARCH[0], 37), CLIM_YEARS)
    onset = WR.wrsi_onset(ee, chirps, *SEARCH, pet_ic=pet).unmask(
            WR.wrsi_onset(ee, clim, *SEARCH, pet_ic=pet))
    mask = crop_mask_image(ee, "Kenya", "maize", None)
    planting = onset.updateMask(mask)

    whc = SOIL.get_whc(ee, aoi, soil_cfg, root_depth_cm=int(kc_cfg["maize"].get("root_depth_m", 1.0) * 100))
    wrsi_e = WR.run_wrsi(ee, aoi, YEAR, planting, "maize_early", kc_cfg, soil_cfg, *SEARCH, whc_img=whc)["WRSI"]
    viable = wrsi_e.gte(WRSI_MIN)
    gated = planting.updateMask(viable).toInt16().rename("planting_dekad")
    out = (gated.addBands(wrsi_e.toInt16().rename("wrsi_early"))
                .addBands(viable.unmask(0).updateMask(mask).toInt16().rename("viable")))

    desc = "planting_Kenya_maize_Shortrains_2024_rainfed_gated"
    ee.batch.Export.image.toDrive(image=out.clip(aoi), description=desc,
                                  folder="planting_outputs", region=aoi, scale=250,
                                  crs="EPSG:4326", maxPixels=int(1e13)).start()
    print(f"  export started: {desc}  (early-variety WRSI>=50 gate; bands: planting_dekad, wrsi_early, viable)")


if __name__ == "__main__":
    main()
