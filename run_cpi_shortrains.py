#!/usr/bin/env python3
"""Crop Performance Index (CPI) + yield for Kenya short-rains maize — multi-stress multiplicative.

CPI = 100·(1−S_water)(1−S_heat)(1−S_veg), stage-weighted (FAO-33 Ky). Yield (t/ha) = CPI/100 · Ym.
Bands exported: CPI, yield_tha, S_water, S_heat, S_veg (stresses as %). Early (short-duration) maize.

Run:  EE_PROJECT=ee-manzikye python run_cpi_shortrains.py
"""
import sys, os
sys.path.insert(0, os.path.dirname(__file__))
from src import utils, wrsi_feedback as WR, zonal_aggregate as ZA, cpi as CPI, soil as SOIL
from src.wrsi_waterbalance import run_wrsi_staged
from run import crop_mask_image, GAUL_NAME

YEAR = 2024
SEARCH = (28, 34)
VEG_INDEX = os.environ.get("VEG_INDEX", "ndvi")  # 'ndvi' (VCI) | 'fpar' (zFPAR, ASAP-aligned)
CLIM_YEARS = list(range(1981, 2025))
EARLY = {"LGP_dekads": 9, "L_ini": 2, "L_dev": 3, "L_mid": 2, "L_late": 2}
D_VEG, D_FLO = EARLY["L_ini"] + EARLY["L_dev"], EARLY["L_ini"] + EARLY["L_dev"] + EARLY["L_mid"]  # 5, 7


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
    staged = run_wrsi_staged(ee, aoi, YEAR, planting, "maize_early", kc, soil, *SEARCH, whc_img=whc)
    Sw = CPI.s_water(ee, staged)
    Sh = CPI.s_heat(ee, aoi, YEAR, planting, D_VEG, D_FLO, *SEARCH)
    Sv = CPI.s_veg(ee, aoi, YEAR, *SEARCH, source=VEG_INDEX)
    cpi_img, yld = CPI.cpi(ee, Sw, Sh, Sv)

    out = ee.Image.cat([cpi_img, yld.multiply(100),                       # yield ×100 -> integer t/ha·100
                        Sw.multiply(100), Sh.multiply(100), Sv.multiply(100)]).updateMask(mask).toInt16()
    out = out.rename(["CPI", "yield_tha_x100", "S_water", "S_heat", "S_veg"])
    desc = "cpi_Kenya_maize_Shortrains_2024"
    if os.environ.get("TO_ASSET"):
        ee.batch.Export.image.toAsset(image=out.clip(aoi), description=desc,
            assetId=f"projects/ee-manzikye/assets/{desc}", region=aoi, scale=250,
            maxPixels=int(1e13)).start()
    else:
        ee.batch.Export.image.toDrive(image=out.clip(aoi), description=desc, folder="planting_outputs",
            region=aoi, scale=250, crs="EPSG:4326", maxPixels=int(1e13)).start()
    print(f"  export started: {desc}  ({'asset' if os.environ.get('TO_ASSET') else 'drive'}; CPI, yield, stresses)")


if __name__ == "__main__":
    main()
