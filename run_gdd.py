#!/usr/bin/env python3
"""Kick off the maize GDD phenology clock (thermal branch) for the 2024 seasons.

Reuses the pipeline's in-GEE SOS (cue fusion + LTN-gated detect_sos) as the emergence anchor, then
accumulates GDD (ERA5-Land daily air-T, DEM lapse-corrected) to flowering & maturity dekad.
GDD_maturity seeds at the medium AEZ value (1500 °C·d) for v1 — AEZ-per-pixel seeding and the
EVI-peak calibration are the documented next refinements.

Run:  EE_PROJECT=ee-manzikye python run_gdd.py
"""
import sys, os
sys.path.insert(0, os.path.dirname(__file__))
from src import (utils, s2_preprocess as S2, s1_preprocess as S1,
                 fusion_phenometrics as FZ, ltn as LTN, zonal_aggregate as ZA, gdd_clock as GC)
from run import crop_mask_image, GAUL_NAME

YEAR = 2024
JOBS = [("Kenya", "Long rains"), ("Kenya", "Short rains"), ("Ethiopia", "Meher")]


def main():
    ee = utils.gee_init()
    rows = {(r["country"], r["season"]): r
            for r in utils.viable_products(utils.load_calendar("config/season_calendar.csv"))
            if r["crop"].lower() == "maize"}
    for country, season in JOBS:
        r = rows.get((country, season))
        if not r:
            print(f"  [skip] no calendar row for {country} {season}"); continue
        aoi = ZA.gaul_admin(ee, [GAUL_NAME[country]], level=0).geometry()
        sos_start, sos_end = utils.sos_window_dekads(r["sos_detection_window"])
        s2 = S2.build_s2_dekadal(ee, aoi, YEAR)
        s1 = S1.build_s1_dekadal(ee, aoi, YEAR, orbit="DESCENDING")
        fpar = FZ.add_fpar_dekadal(ee, aoi, YEAR)
        g = FZ.build_fused_greenness(ee, s2, s1, fpar)               # cue fusion (production)
        mask = crop_mask_image(ee, country, "maize", None)
        ltn = LTN.build_ltn_prior(ee, aoi, sos_start, sos_end)
        sos = FZ.detect_sos(ee, g, mask, sos_start, sos_end, ltn_sos=ltn, ltn_pad=2)
        gmat = GC.gdd_maturity_from_aez(ee, aoi)                  # AEZ-per-pixel GDD-to-maturity
        dk_hi = min(36, sos_end + 18)                            # accumulate only through the season
        clock = GC.gdd_clock(ee, aoi, YEAR, sos, gmat, dk_lo=sos_start, dk_hi=dk_hi)
        desc = f"gddclock_{country}_{season.replace(' ', '')}_2024"
        ee.batch.Export.image.toDrive(
            image=clock.clip(aoi), description=desc, folder="planting_outputs",
            region=aoi, scale=250, crs="EPSG:4326", maxPixels=int(1e13)).start()
        print(f"  export started: {desc}  (peak-veg + flowering + grain-fill + maturity + gdd_total)")


if __name__ == "__main__":
    main()
