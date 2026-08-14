#!/usr/bin/env python3
"""GDD phenology clock for the Kenya SHORT RAINS — rainfall-anchored + year-wrapping.

Fixes the two reasons the short-rains stages were empty:
  1. anchor on the RAINFALL onset (full coverage), not the sparse green-up SOS;
  2. WRAP accumulation into the next year — short rains plant in Oct (dekad ~28-32) and mature in
     Feb-Mar of the following year (dekad > 36), which the within-year clock truncated.

Emergence anchor = rainfall onset + 1 dekad. Stage dekads may exceed 36 (e.g. 46 = dekad 10 of the
next year). Thermal branch, AEZ-seeded GDD_maturity.

Run:  EE_PROJECT=ee-manzikye python run_gdd_shortrains_rainfed.py
"""
import sys, os
sys.path.insert(0, os.path.dirname(__file__))
from src import utils, wrsi_feedback as WR, zonal_aggregate as ZA, gdd_clock as GC
from run import crop_mask_image, GAUL_NAME

YEAR = 2024
SEARCH = (28, 34)
CLIM_YEARS = list(range(1981, 2025))


def main():
    ee = utils.gee_init()
    aoi = ZA.gaul_admin(ee, [GAUL_NAME["Kenya"]], level=0).geometry()
    chirps24 = WR.chirps_dekadal(ee, aoi, YEAR)
    pet24 = WR.pet_dekadal(ee, aoi, YEAR)
    clim = WR.chirps_clim_dekadal(ee, aoi, range(SEARCH[0], 37), CLIM_YEARS)
    onset = WR.wrsi_onset(ee, chirps24, *SEARCH, pet_ic=pet24).unmask(
            WR.wrsi_onset(ee, clim, *SEARCH, pet_ic=pet24))              # rainfall onset, full coverage
    mask = crop_mask_image(ee, "Kenya", "maize", None)
    sos = onset.add(1).updateMask(mask)                                  # emergence ≈ onset + 1 dekad
    gmat = GC.gdd_maturity_from_aez(ee, aoi)
    clock = GC.gdd_clock(ee, aoi, YEAR, sos, gmat, dk_lo=28, dk_hi=52)   # wrap through ~Jun next year

    desc = "gddclock_Kenya_Shortrains_2024_rainfed"
    ee.batch.Export.image.toDrive(image=clock.clip(aoi), description=desc,
                                  folder="planting_outputs", region=aoi, scale=250,
                                  crs="EPSG:4326", maxPixels=int(1e13)).start()
    print(f"  export started: {desc}  (rainfall-anchored, year-wrapping; stage dekads may be >36)")


if __name__ == "__main__":
    main()
