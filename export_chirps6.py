#!/usr/bin/env python3
"""Export the 6-day observed CHIRPS precipitation sum over Kenya (the observed half of the
FEWS 6-obs/4-forecast running dekad). Small raster (~0.05 deg) -> Drive, quick to download.

Then blend with the Open-Meteo forecast:
  python openmeteo_forecast.py --blend --chirps6 chirps_6day.tif --forecast om_forecast_kenya.tif --out dekad_precip.tif

Run:
  EE_PROJECT=ee-manzikye python export_chirps6.py --end 2026-07-29 --days 6
"""
import argparse, sys, os
sys.path.insert(0, os.path.dirname(__file__))
from src import utils, zonal_aggregate as ZA


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--end", required=True, help="end date (exclusive), YYYY-MM-DD = start of the forecast window")
    ap.add_argument("--days", type=int, default=6, help="observed days before --end")
    ap.add_argument("--country", default="Kenya")
    ap.add_argument("--out-desc", default="chirps_6day")
    ap.add_argument("--scale", type=int, default=5566, help="CHIRPS native ~0.05 deg = 5566 m")
    args = ap.parse_args()

    ee = utils.gee_init()
    aoi = ZA.gaul_admin(ee, [args.country], level=0).geometry()
    end = ee.Date(args.end); start = end.advance(-args.days, "day")
    chirps6 = (ee.ImageCollection("UCSB-CHG/CHIRPS/DAILY").filterBounds(aoi)
                 .filterDate(start, end).select("precipitation").sum().rename("P").clip(aoi))
    ee.batch.Export.image.toDrive(
        image=chirps6.toFloat(), description=args.out_desc, folder="planting_outputs",
        region=aoi, scale=args.scale, maxPixels=1e12, fileFormat="GeoTIFF").start()
    print(f"export started: {args.out_desc} = CHIRPS sum {args.days}d ending {args.end} "
          f"({args.country}, ~{args.scale} m) -> Drive/planting_outputs")


if __name__ == "__main__":
    main()
