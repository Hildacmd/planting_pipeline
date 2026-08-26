#!/usr/bin/env python3
"""Fused Canopy Condition Index (FCCI) — within-season peak fused greenness (NDRE+FPAR+SAR), 0-100,
masked to maize. Absolute (no multi-year baseline), so it dodges the short-archive problem. A 10-20 m,
cloud-proof vegetation cross-check on the water-balance WRSI. Exported at 250 m for admin roll-up.

Run:  EE_PROJECT=ee-manzikye python run_fcci.py            # -> Drive
      TO_ASSET=1 EE_PROJECT=ee-manzikye python run_fcci.py # -> EE assets
"""
import sys, os
sys.path.insert(0, os.path.dirname(__file__))
from src import (utils, s2_preprocess as S2, s1_preprocess as S1, fusion_phenometrics as FZ,
                 zonal_aggregate as ZA)
from run import crop_mask_image, GAUL_NAME

YEAR = 2024
S1_ORBIT = "ASCENDING"                       # S1B gone (2022) -> ASCENDING has coverage over Kenya
JOBS = [("Kenya", "Long rains", "Kenya_Longrains", 12),
        ("Ethiopia", "Meher", "Ethiopia_Meher", 12),
        ("Kenya", "Short rains", "Kenya_Shortrains", 9)]


def main():
    ee = utils.gee_init()
    rows = {(r["country"], r["season"]): r for r in utils.viable_products(utils.load_calendar("config/season_calendar.csv"))
            if r["crop"].lower() == "maize"}
    for country, season, tag, lgp in JOBS:
        r = rows.get((country, season))
        if not r:
            print(f"  [skip] no calendar row for {country} {season}"); continue
        aoi = ZA.gaul_admin(ee, [GAUL_NAME[country]], level=0).geometry()
        ss, se = utils.sos_window_dekads(r["sos_detection_window"])
        s2 = S2.build_s2_dekadal(ee, aoi, YEAR)
        s1 = S1.build_s1_dekadal(ee, aoi, YEAR, orbit=S1_ORBIT)
        fpar = FZ.add_fpar_dekadal(ee, aoi, YEAR)
        g = FZ.build_fused_greenness(ee, s2, s1, fpar)
        mask = crop_mask_image(ee, country, "maize", None)
        fcci = FZ.fused_condition(ee, g, mask, ss, se, lgp=lgp).toInt16()
        desc = f"fcci_{tag}_2024"
        if os.environ.get("TO_ASSET"):
            ee.batch.Export.image.toAsset(image=fcci.clip(aoi), description=desc,
                assetId=f"projects/ee-manzikye/assets/{desc}", region=aoi, scale=250, maxPixels=int(1e13)).start()
        else:
            ee.batch.Export.image.toDrive(image=fcci.clip(aoi), description=desc, folder="planting_outputs",
                region=aoi, scale=250, crs="EPSG:4326", maxPixels=int(1e13)).start()
        print(f"  export started: {desc}  ({'asset' if os.environ.get('TO_ASSET') else 'drive'}; peak fused greenness 0-100)")


if __name__ == "__main__":
    main()
