#!/usr/bin/env python3
"""Regime-aware Kenya SHORT-RAINS planting dekad (PROVISIONAL, opt-in). The western/Rift bimodal
counties plant their second season Aug-Sep (some Jul-Aug), far earlier than the eastern/coastal
Oct-Nov window; a single national window (dk 28-34) pins them all to dk28. This routes each county
through its regime's detection window (config/ond_regime_windows.csv + Cropyield-Data/ond_regimes.csv)
and re-reduces the planting distribution to admin, updating only the planting columns of the
ke_short skill CSVs. Evidence & caveats: KENYA_SEASON_REGIMES.md sec 7 (held-out significant only at
the boundary, n=16; ~39% of mapped western short-rains area may be the standing long-rains crop).

  EE_PROJECT=ee-manzikye python run_shortrains_regime.py [--levels 1,2,3] [--test]
"""
import sys, os, csv, argparse, ee, warnings, pandas as pd, geopandas as gpd
warnings.simplefilter("ignore")
sys.path.insert(0, os.path.dirname(__file__))
ee.Initialize(project=os.environ.get("EE_PROJECT", "ee-manzikye"))
from src import wrsi_feedback as WR
from run import crop_mask_image, GAUL_NAME
import reduce_newcountries as R1

YEAR = 2024
CLIM_YEARS = range(1981, 2025)
EARLY_WIN = (24, 29)   # Aug-d3 .. Oct-d2  (western/Rift)
LATE_WIN = (28, 33)    # Oct-d1 .. Nov-d3  (eastern/coastal)
BASE = "planting_Kenya_maize_Shortrains_2024_rainfed"
# GADM county name (NAME_1) normalisation to match ond_regimes.csv
ALIAS = {"Elgeyo-Marakwet": "Elgeiyo Marakwet", "Homa Bay": "Homabay", "Muranga": "Murang'a",
         "Murang'A": "Murang'a", "Tharaka-Nithi": "Tharaka Nithi", "Taita Taveta": "Taita Taveta",
         "Nairobi": "Nairobi"}


def early_counties():
    rows = list(csv.DictReader(open("Cropyield-Data/ond_regimes.csv")))
    return {r["county"].strip() for r in rows if r["ond_regime"].startswith("early")}


def regime_planting(ee, aoi, mask):
    """planting_dekad: early-window onset over early counties, late-window elsewhere."""
    ch = WR.chirps_dekadal(ee, aoi, YEAR); pet = WR.pet_dekadal(ee, aoi, YEAR)
    def onset(win):
        clim = WR.chirps_clim_dekadal(ee, aoi, range(win[0], 37), CLIM_YEARS)
        return WR.wrsi_onset(ee, ch, win[0], win[1], pet_ic=pet).unmask(
               WR.wrsi_onset(ee, clim, win[0], win[1], pet_ic=pet))
    o_early, o_late = onset(EARLY_WIN), onset(LATE_WIN)
    # regime mask: 1 over early counties (GADM Kenya L1)
    g = gpd.read_file("/Users/hildamanzi/ICPAC-WORK/ADMIN-boundaries/gadm41_KEN.gpkg", layer="ADM_ADM_1")
    ecs = early_counties()
    g["reg"] = g["NAME_1"].map(lambda n: 1 if (ALIAS.get(n, n) in ecs) else 0)
    eg = g[g["reg"] == 1].reset_index(drop=True); eg["_id"] = eg.index
    early_fc = R1.gdf_to_ee(eg[["_id", "geometry"]])
    early_img = ee.Image(0).paint(early_fc, 1).gt(0)
    planting = o_late.where(early_img, o_early).updateMask(mask).toInt16().rename("planting_dekad")
    return planting, g, ecs


def reduce_levels(planting, levels, test=False):
    KEYS = {1: ["name"], 2: ["county", "name"], 3: ["county", "constituency", "name"]}
    for lvl in levels:
        csvf = f"{BASE}_L{lvl}_skill_WKT.csv"
        if not os.path.exists(csvf):
            print(f"  [skip] {csvf}"); continue
        df = pd.read_csv(csvf)
        gcol = "geometry_wkt"
        from shapely import wkt as _wkt
        gdf = gpd.GeoDataFrame(df, geometry=df[gcol].map(_wkt.loads), crs="EPSG:4326")
        red = ee.Reducer.mode().combine(ee.Reducer.percentile([10, 50, 90]), "", True) \
                .combine(ee.Reducer.mean(), "", True).combine(ee.Reducer.count(), "", True)
        rows = gdf.head(6) if test else gdf
        got = 0
        for idx, r in rows.iterrows():
            geom = ee.Geometry(r.geometry.__geo_interface__)
            try:
                p = planting.reduceRegion(red, geom, scale=250, maxPixels=int(1e10), bestEffort=True).getInfo()
            except Exception:
                p = {}
            md = p.get("planting_dekad_mode")
            if md is None:
                continue
            df.at[idx, "modal_dekad"] = int(round(md))
            if p.get("planting_dekad_mean") is not None: df.at[idx, "mean_dekad"] = round(p["planting_dekad_mean"], 2)
            for q in (10, 50, 90):
                v = p.get(f"planting_dekad_p{q}")
                if v is not None: df.at[idx, f"p{q}"] = round(v)
            got += 1
        if not test:
            df.to_csv(csvf, index=False)
        print(f"  L{lvl}: updated {got}/{len(rows)} units{' (TEST, not written)' if test else ''} -> {csvf}")
        if test:
            wc = [c for c in ["Kakamega", "Bungoma", "Trans Nzoia", "Uasin Gishu", "Kitui", "Makueni"] if c in set(rows["name"])]
            print("   sample:", df[df["name"].isin(wc)][["name", "modal_dekad", "mean_dekad"]].to_dict("records"))


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--levels", default="1"); ap.add_argument("--test", action="store_true")
    a = ap.parse_args()
    aoi = __import__("src.zonal_aggregate", fromlist=["gaul_admin"]).gaul_admin(ee, [GAUL_NAME["Kenya"]], level=0).geometry()
    mask = crop_mask_image(ee, "Kenya", "maize", None)
    planting, g, ecs = regime_planting(ee, aoi, mask)
    print(f"early (western/Rift) counties: {len(ecs)} | windows early={EARLY_WIN} late={LATE_WIN}")
    reduce_levels(planting, [int(x) for x in a.levels.split(",")], test=a.test)


if __name__ == "__main__":
    main()
