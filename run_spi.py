#!/usr/bin/env python3
"""Kick off SPI-3 (3-month Standardized Precipitation Index) GEE exports for the 2024 seasons.

One SPI-3 raster per season, ending in the month that closes that season's rains, vs the
CHIRPS 1981-2020 climatology (Wilson-Hilferty gamma approximation, src/spi.py):
  Kenya Long rains  -> SPI-3 ending May   (MAM)
  Kenya Short rains -> SPI-3 ending Dec   (OND)
  Ethiopia Meher    -> SPI-3 ending Sep   (JAS, Kiremt core)

Run:  EE_PROJECT=ee-manzikye python run_spi.py
"""
import sys, os
sys.path.insert(0, os.path.dirname(__file__))
from src import utils, zonal_aggregate as ZA, spi as SPI

GAUL_NAME = {"Kenya": "Kenya", "Ethiopia": "Ethiopia"}
JOBS = [("Kenya", "Longrains", 5), ("Kenya", "Shortrains", 12), ("Ethiopia", "Meher", 9)]


def main():
    ee = utils.gee_init()
    for country, season, end_month in JOBS:
        aoi = ZA.gaul_admin(ee, [GAUL_NAME[country]], level=0).geometry()
        img = SPI.spi3(ee, aoi, 2024, end_month).clip(aoi)
        desc = f"spi3_{country}_{season}_2024"
        ee.batch.Export.image.toDrive(
            image=img, description=desc, folder="planting_outputs",
            region=aoi, scale=5566, crs="EPSG:4326", maxPixels=int(1e13)).start()
        print(f"  export started: {desc}  (SPI-3 ending month {end_month}, ~5.5 km CHIRPS)")


if __name__ == "__main__":
    main()
