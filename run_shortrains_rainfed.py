#!/usr/bin/env python3
"""Rainfall-anchored Short-rains planting variant (Kenya maize) — fixes the coverage weakness.

Design (rainfall establishes, green-up confirms):
  1. LTN normal onset — CHIRPS 45-yr climatology, FEWS 25/20 mm + P/PET >= 0.5, searched over the
     short-rains window -> a normal onset dekad on EVERY maize pixel (full coverage).
  2. Year-specific onset — the same rule on actual-2024 CHIRPS.
  3. planting = 2024 onset where it fires, else the 45-yr normal (so no pixel drops out).
Green-up confirmation is applied locally afterwards (blend toward the existing green-up product where
it exists). Rainfall onset = planting trigger, so no emergence offset is subtracted.

Run:  EE_PROJECT=ee-manzikye python run_shortrains_rainfed.py
"""
import sys, os
sys.path.insert(0, os.path.dirname(__file__))
from src import utils, wrsi_feedback as WR, zonal_aggregate as ZA
from run import crop_mask_image, GAUL_NAME

YEAR = 2024
SEARCH = (28, 34)                      # Oct-d1 .. Nov-d3 (broad, so hit-rate vs 28-32 is a real test)
CLIM_YEARS = list(range(1981, 2025))   # 44-yr CHIRPS climatology


def main():
    ee = utils.gee_init()
    aoi = ZA.gaul_admin(ee, [GAUL_NAME["Kenya"]], level=0).geometry()
    chirps24 = WR.chirps_dekadal(ee, aoi, YEAR)
    pet24 = WR.pet_dekadal(ee, aoi, YEAR)
    clim = WR.chirps_clim_dekadal(ee, aoi, range(SEARCH[0], 37), CLIM_YEARS)

    onset24 = WR.wrsi_onset(ee, chirps24, SEARCH[0], SEARCH[1], pet_ic=pet24)      # year-specific
    onsetltn = WR.wrsi_onset(ee, clim, SEARCH[0], SEARCH[1], pet_ic=pet24)         # 44-yr normal
    mask = crop_mask_image(ee, "Kenya", "maize", None)
    planting = onset24.unmask(onsetltn).updateMask(mask).toInt16().rename("planting_dekad")

    desc = "planting_Kenya_maize_Shortrains_2024_rainfed"
    ee.batch.Export.image.toDrive(image=planting.clip(aoi), description=desc,
                                  folder="planting_outputs", region=aoi, scale=250,
                                  crs="EPSG:4326", maxPixels=int(1e13)).start()
    print(f"  export started: {desc}  (2024 onset unmasked by 44-yr LTN normal, maize-masked)")


if __name__ == "__main__":
    main()
