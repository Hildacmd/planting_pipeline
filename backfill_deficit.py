#!/usr/bin/env python3
"""Backfill mean_deficit_mm into the new-country skill CSVs using PER-POLYGON reduceRegion.
The water-balance deficit graph is heavy, so reduceRegions (per FeatureCollection) starves under the
GEE free-tier throttle and returns null; a single reduceRegion per admin polygon is light and works
(just slow). One country at a time; writes each CSV as it finishes so progress is durable.

  EE_PROJECT=ee-manzikye python backfill_deficit.py [Product ...]
"""
import sys, os, ee, warnings, pandas as pd
warnings.simplefilter("ignore")
sys.path.insert(0, os.path.dirname(__file__))
ee.Initialize(project=os.environ.get("EE_PROJECT", "ee-manzikye"))
import reduce_newcountries_tier2 as T2, reduce_newcountries as R1
from run import crop_mask_image

MISSING = ["Somalia_Gu", "Somalia_Deyr", "SouthSudan_Main", "Ethiopia_Belg",
           "Tanzania_Vuli", "Tanzania_Msimu", "Tanzania_Masika"]


def backfill(tok):
    c, s = T2.TOK2CS[tok]; ctok = tok.split("_")[0]
    asset = f"projects/ee-manzikye/assets/cpiX_{tok}_2024"
    try:
        ee.data.getAsset(asset)
    except Exception:
        print(f"  [skip] no asset {tok}"); return
    img = ee.Image(asset); planting = img.select("planting_dekad")
    print(f"== {tok} ==", flush=True)
    for lvl in (1, 2):
        g = R1.admin_gdf(ctok, lvl)
        aoi = ee.Geometry(g.unary_union.__geo_interface__).bounds()
        mask = crop_mask_image(ee, c, "maize", None)
        d = T2.metric_images(tok, aoi, mask, planting, {"def"})["deficit"]
        csvf = f"newc_{tok}_2024_L{lvl}_skill_WKT.csv"
        df = pd.read_csv(csvf)
        gi = g.set_index("_id")
        key2id = {(gi.loc[i, "name"], gi.loc[i, "county"]): i for i in gi.index}
        if "mean_deficit_mm" not in df.columns:
            df["mean_deficit_mm"] = None
        got = 0
        for idx, r in df.iterrows():
            aid = key2id.get((r["name"], r.get("county") if pd.notna(r.get("county")) else ""))
            if aid is None:
                continue
            geom = ee.Geometry(gi.loc[aid, "geometry"].__geo_interface__)
            try:
                v = d.reduceRegion(ee.Reducer.mean(), geom, scale=250, maxPixels=int(1e10),
                                   bestEffort=True).getInfo().get("deficit_mm")
            except Exception:
                v = None
            if v is not None:
                df.at[idx, "mean_deficit_mm"] = round(v, 1); got += 1
        df.to_csv(csvf, index=False)
        print(f"  L{lvl}: {got}/{len(df)} deficit -> {csvf}", flush=True)


if __name__ == "__main__":
    for p in (sys.argv[1:] or MISSING):
        backfill(p)
    print("DONE", flush=True)
