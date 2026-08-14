#!/usr/bin/env python3
"""Last Viable Planting Date (LVPD) dekad for the Kenya short rains — climatological planning guide.

LVPD = latest dekad you can PLANT and still have short-duration (early) maize MATURE before the
reliable moisture ends:
    LGP_end = last dekad the CHIRPS 44-yr LTN P/PET ≥ 0.5 (season, year-wrap aware)
    LVPD    = LGP_end + RESIDUAL_SOIL − EARLY_CYCLE
             (residual ≈ 3 dekads of stored soil water; early maize cycle ≈ 9 dekads)
This is the *climatological* late edge of the window (a "plant no later than" guide), complementary to
the 2024-specific WRSI viability %. Exported as lvpd_dekad, maize-masked.

Run:  EE_PROJECT=ee-manzikye python run_lvpd.py
"""
import sys, os
sys.path.insert(0, os.path.dirname(__file__))
from src import utils, wrsi_feedback as WR, zonal_aggregate as ZA
from run import crop_mask_image, GAUL_NAME
from src.utils import dekad_to_start_date

YEAR = 2024
CLIM_YEARS = list(range(1981, 2025))
RESIDUAL = 3          # dekads of usable stored soil water after the rains
EARLY_CYCLE = 9       # short-duration maize ≈ 85-90 days


def main():
    ee = utils.gee_init()
    aoi = ZA.gaul_admin(ee, [GAUL_NAME["Kenya"]], level=0).geometry()
    pet = WR.pet_dekadal(ee, aoi, YEAR)

    def clim_P(dk):
        imgs = []
        for y in CLIM_YEARS:
            yy = y if dk <= 36 else y + 1
            cdk = dk if dk <= 36 else dk - 36
            s = ee.Date(dekad_to_start_date(yy, cdk).isoformat())
            imgs.append(ee.ImageCollection("UCSB-CHG/CHIRPS/DAILY").filterBounds(aoi)
                          .filterDate(s, s.advance(10, "day")).sum())
        return ee.ImageCollection(imgs).mean()

    def petd(dk):
        return ee.Image(pet.filter(ee.Filter.eq("dekad", dk if dk <= 36 else dk - 36)).first()).select("ET0")

    lgp_end = ee.Image(0)
    for dk in range(28, 43):                                   # Oct-d1 .. next-year Jun
        ok = clim_P(dk).divide(petd(dk).max(1e-3)).gte(0.5)
        lgp_end = lgp_end.where(ok, dk)
    lvpd = lgp_end.add(RESIDUAL).subtract(EARLY_CYCLE).rename("lvpd_dekad")
    mask = crop_mask_image(ee, "Kenya", "maize", None)
    out = lvpd.updateMask(mask).toInt16()

    desc = "lvpd_Kenya_maize_Shortrains_2024"
    ee.batch.Export.image.toDrive(image=out.clip(aoi), description=desc, folder="planting_outputs",
                                  region=aoi, scale=250, crs="EPSG:4326", maxPixels=int(1e13)).start()
    print(f"  export started: {desc}  (LGP_end + {RESIDUAL} − {EARLY_CYCLE}; climatological last-viable-planting dekad)")


if __name__ == "__main__":
    main()
