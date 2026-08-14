#!/usr/bin/env python3
"""One-time materialization of the STATIC soil water-holding capacity (WHC, mm) for the GHA.

Builds WHC from SoilGrids texture + Saxton-Rawls (src/soil.py) over Kenya + Ethiopia at the maize
root depth, and exports it ONCE to an Earth Engine asset (and optionally a Drive GeoTIFF). After the
asset task finishes, set  soil.whc_asset  in config/crop_coefficients.yaml to the asset id below —
every run then just loads it (no per-run recompute, no re-download).

Run:  EE_PROJECT=ee-manzikye python run_export_whc.py            # asset only
      EE_PROJECT=ee-manzikye python run_export_whc.py --drive    # also a GeoTIFF to Drive
"""
import sys, os, argparse
sys.path.insert(0, os.path.dirname(__file__))
from src import utils, zonal_aggregate as ZA, soil as SOIL
from run import GAUL_NAME

ASSET_ID = "projects/ee-manzikye/assets/whc_saxton_soilgrids_gha_250m"
COUNTRIES = ["Kenya", "Ethiopia"]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--drive", action="store_true", help="also export a GeoTIFF to Drive")
    ap.add_argument("--asset", default=ASSET_ID, help="target EE asset id")
    args = ap.parse_args()

    ee = utils.gee_init()
    kc, soil = utils.load_crop_coeffs()
    rd_cm = int(kc["maize"].get("root_depth_m", 1.0) * 100)
    region = ZA.gaul_admin(ee, [GAUL_NAME[c] for c in COUNTRIES], level=0).geometry().bounds()

    whc = SOIL.build_whc_saxton_mm(ee, root_depth_cm=rd_cm, min_whc_mm=soil.get("min_whc_mm", 25))
    SOIL.export_whc_to_asset(ee, whc, region, args.asset, scale=250)
    print(f"  asset export started -> {args.asset}  (root {rd_cm} cm, GHA bounds, 250 m)")
    if args.drive:
        SOIL.export_whc_to_drive(ee, whc, region, folder="planting_outputs",
                                 name="WHC_saxton_soilgrids_gha_250m", scale=250)
        print("  drive GeoTIFF export started -> planting_outputs/WHC_saxton_soilgrids_gha_250m.tif")
    print(f"\n  When the ASSET task completes, set in config/crop_coefficients.yaml:\n"
          f"      soil.whc_asset: \"{args.asset}\"\n"
          f"  (runs then load it directly; nothing recomputes per run).")


if __name__ == "__main__":
    main()
