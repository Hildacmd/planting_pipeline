#!/usr/bin/env python3
"""Excess / waterlogging diagnostics for the Kenya SHORT rains (250 m). Excess is independent of the
onset method, so it applies here too (OND short rains can flood hard — e.g. the 2023 El Niño season).
No 5+7 false-start band (short rains uses the 25/20 mm three-dekad rule for that).

Bands: waterlog_idx (0-100, stage-weighted, establishment-worst), spi3_wet (0/1, SPI-3 >= +1.5).
Rainfall-onset planting (early/short-duration maize), year-wrapping into 2025 for grain-fill.

Run:  EE_PROJECT=ee-manzikye python run_excess_shortrains.py
      TO_ASSET=1 EE_PROJECT=ee-manzikye python run_excess_shortrains.py
"""
import sys, os
sys.path.insert(0, os.path.dirname(__file__))
from src import utils, wrsi_feedback as WR, zonal_aggregate as ZA, excess as EX, soil as SOIL
from run import crop_mask_image, GAUL_NAME

YEAR = 2024
SEARCH = (28, 34)
CLIM_YEARS = list(range(1981, 2025))
EARLY = {"d_veg": 5, "d_flo": 7, "lgp": 9}          # short-duration maize stage ends (dekads)
SPI_END = 12                                        # SPI-3 ending December (OND short rains)


def main():
    ee = utils.gee_init()
    aoi = ZA.gaul_admin(ee, [GAUL_NAME["Kenya"]], level=0).geometry()
    pet = WR.pet_dekadal(ee, aoi, YEAR)
    ch = WR.chirps_dekadal(ee, aoi, YEAR)
    clim = WR.chirps_clim_dekadal(ee, aoi, range(SEARCH[0], 37), CLIM_YEARS)
    onset = WR.wrsi_onset(ee, ch, *SEARCH, pet_ic=pet).unmask(WR.wrsi_onset(ee, clim, *SEARCH, pet_ic=pet))
    mask = crop_mask_image(ee, "Kenya", "maize", None)
    planting = onset.updateMask(mask).toInt16()

    hy = SOIL.build_hydro_mm(ee, root_depth_cm=100)
    wl  = EX.aeration_stress_index(ee, aoi, planting, YEAR, EARLY["d_veg"], EARLY["d_flo"], EARLY["lgp"], *SEARCH,
                                   hy["FC_mm"], hy["SAT_mm"], hy["tau"])
    wet = EX.spi3_wet(ee, aoi, YEAR, SPI_END).rename("spi3_wet")
    out = ee.Image.cat([wl, wet]).updateMask(mask).updateMask(planting.mask()).toInt16().rename(["waterlog_idx", "spi3_wet"])

    desc = "onsetexcess_Kenya_Shortrains_2024"
    if os.environ.get("TO_ASSET"):
        ee.batch.Export.image.toAsset(image=out.clip(aoi), description=desc,
            assetId=f"projects/ee-manzikye/assets/{desc}", region=aoi, scale=250, maxPixels=int(1e13)).start()
    else:
        ee.batch.Export.image.toDrive(image=out.clip(aoi), description=desc, folder="planting_outputs",
            region=aoi, scale=250, crs="EPSG:4326", maxPixels=int(1e13)).start()
    print(f"  export started: {desc}  ({'asset' if os.environ.get('TO_ASSET') else 'drive'}; waterlog + spi_wet, short rains)")


if __name__ == "__main__":
    main()
