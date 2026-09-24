#!/usr/bin/env python3
"""Reduce a sorghum CPI asset to admin-2 units and export it as a CSV with geometry.

This is the bridge between the Earth Engine products and the local Ym calibration. For each
GAUL level-2 unit it writes the sorghum-area-weighted mean CPI and the unit's sorghum area
fraction, which the calibration then uses as the overlap weight.

**The weight matters.** A district that is 2 % sorghum and one that is 60 % sorghum must not
count equally when a ceiling is fitted, and an unweighted mean CPI over a large arid district
is dominated by land that grows nothing.

    EE_PROJECT=indigo-proxy-484220-q8 python sorghum_pipeline/zonal_sorghum.py               # arm A, all finished
    EE_PROJECT=... python sorghum_pipeline/zonal_sorghum.py --arm B                          # arm B (CM4EW calendar)
    EE_PROJECT=... python sorghum_pipeline/zonal_sorghum.py Sudan_Kharif Ethiopia_Meher      # named products

Exports land in Drive/planting_outputs as `sorghum[B]_<Country>_<Season>_<YEAR>_L2.csv`.
"""
import csv, os, sys

H = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(H)
sys.path.insert(0, ROOT); sys.path.insert(0, H)

import ee                                              # noqa: E402
import sorghum_params as P                             # noqa: E402
from src import utils, zonal_aggregate as ZA           # noqa: E402
from run import GAUL_NAME                              # noqa: E402

YEAR = 2024
PROJ = f"projects/{os.environ.get('EE_PROJECT', 'indigo-proxy-484220-q8')}/assets"
FOLDER = "planting_outputs"


PREFIX = "sorghum"        # set to "sorghumB" by --arm B


def products():
    with open(f"{H}/config/season_calendar_sorghum.csv") as f:
        return [(r["country"], r["season"]) for r in csv.DictReader(f)]


def export(country, season, year=YEAR):
    tok = f"{country}_{season}_{year}".replace(" ", "")
    asset = f"{PROJ}/{PREFIX}_{tok}"
    img = ee.Image(asset)
    gname = GAUL_NAME.get(country) or GAUL_NAME.get(country.replace("_", " "), country)
    adm = ZA.gaul_admin(ee, [gname], level=2)

    frac = P.crop_fraction(ee, country).unmask(0).divide(100)      # sorghum share of the cell
    cpi = img.select("CPI").toFloat()
    stack = ee.Image.cat([cpi.multiply(frac).rename("cpi_w"), frac.rename("w")]).toFloat()

    # sum(CPI x frac) and sum(frac) per unit, at 250 m
    fc = stack.reduceRegions(collection=adm, reducer=ee.Reducer.sum(), scale=250)

    def attach(f):
        w = ee.Number(f.get("w"))
        cells = ee.Number(f.area(1000)).divide(1e4)                 # unit area in ha
        return f.set({
            "cpi": ee.Number(f.get("cpi_w")).divide(w.max(1e-9)),   # area-weighted mean CPI
            "sorghum_ha": w.multiply(6.25),                         # 250 m cell = 6.25 ha
            "crop_area_frac": w.multiply(6.25).divide(cells.max(1e-9)),
        }).setGeometry(f.geometry(1000))

    fc = fc.map(attach)
    t = ee.batch.Export.table.toDrive(
        collection=fc, description=f"sorghum_{tok}_L2", folder=FOLDER,
        fileNamePrefix=f"sorghum_{tok}_L2", fileFormat="CSV")
    t.start()
    print(f"started  sorghum_{tok}_L2   {t.id}", flush=True)


def main():
    global PREFIX
    args = sys.argv[1:]
    if "--arm" in args:
        i = args.index("--arm")
        PREFIX = "sorghumB" if args[i + 1].upper() == "B" else "sorghum"
        del args[i:i + 2]
    utils.gee_init()
    want = args
    for country, season in products():
        tok = f"{country}_{season}".replace(" ", "")
        if want and tok not in [w.replace(" ", "") for w in want]:
            continue
        try:
            ee.data.getAsset(f"{PROJ}/{PREFIX}_{tok}_{YEAR}")
        except Exception:
            print(f"skip (no asset yet): {PREFIX}_{tok}_{YEAR}"); continue
        export(country, season)


if __name__ == "__main__":
    main()
