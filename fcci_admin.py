#!/usr/bin/env python3
"""Aggregate the Fused Canopy Condition Index (FCCI) to admin units and merge a `fcci` column into
each season's skill CSV (mean peak fused greenness over the unit's maize pixels)."""
import os, glob, numpy as np, pandas as pd, geopandas as gpd, rasterio
from rasterio.features import rasterize
import caf_add

DRIVE, GADM, KEYS = caf_add.DRIVE, caf_add.GADM, caf_add.KEYS
MINPX = 5
PRODUCTS = [
    {"base": "planting_Kenya_maize_Longrains_2024",          "fcci": "fcci_Kenya_Longrains_2024",  "gadm": "KEN"},
    {"base": "planting_Ethiopia_maize_Meher_2024_250m",      "fcci": "fcci_Ethiopia_Meher_2024",   "gadm": "ETH"},
    {"base": "planting_Kenya_maize_Shortrains_2024_rainfed", "fcci": "fcci_Kenya_Shortrains_2024", "gadm": "KEN"},
]

def newest(base):
    v = glob.glob(os.path.join(DRIVE, base + ".tif")) + glob.glob(os.path.join(DRIVE, base + " (*).tif"))
    return max(v, key=os.path.getmtime) if v else None

def keys_for(gdf, i, lvl):
    r = {"county": gdf["NAME_1"].iloc[i]}
    if lvl >= 2: r["constituency"] = gdf["NAME_2"].iloc[i]
    r["name"] = gdf[f"NAME_{lvl}"].iloc[i]
    return r

for cfg in PRODUCTS:
    tif = newest(cfg["fcci"])
    if not tif:
        print(f"  [skip] {cfg['fcci']} not present yet"); continue
    with rasterio.open(tif) as ds:
        arr = ds.read(1).astype("float32"); tr, shp, rcrs = ds.transform, (ds.height, ds.width), ds.crs
    valid = np.isfinite(arr) & (arr > 0) & (arr <= 100)          # maize canopy footprint (peak-G > 0)
    print(f"== {cfg['base']}  <- {os.path.basename(tif)} ({rcrs}) ==")
    for lvl in (1, 2, 3):
        csv = f"{cfg['base']}_L{lvl}_skill_WKT.csv"
        if not os.path.exists(csv):
            print(f"  [skip] {csv}"); continue
        gdf = gpd.read_file(GADM[cfg["gadm"]] % lvl).to_crs(rcrs)
        z = rasterize(((g, i + 1) for i, g in enumerate(gdf.geometry)), out_shape=shp, transform=tr, fill=0, dtype="int32")
        gdf["county"] = gdf["NAME_1"]; gdf["constituency"] = gdf.get("NAME_2"); gdf["name"] = gdf[f"NAME_{lvl}"]
        acc = {}
        for i in range(len(gdf)):
            m = (z == (i + 1)) & valid
            if int(m.sum()) >= MINPX:
                acc[i] = round(float(arr[m].mean()), 1)
        df = pd.read_csv(csv)
        kf = lambda r: (tuple(r[c] for c in KEYS[lvl]) if len(KEYS[lvl]) > 1 else r[KEYS[lvl][0]])
        gdf["_x"] = gdf.index.map(lambda i: acc.get(i, np.nan))
        lut = gdf.dropna(subset=["_x"]).drop_duplicates(KEYS[lvl]).set_index(KEYS[lvl])["_x"].to_dict()
        df["fcci"] = df.apply(lambda r: lut.get(kf(r), np.nan), axis=1)
        df.to_csv(csv, index=False)
        print(f"  L{lvl}: FCCI -> {df['fcci'].notna().sum()}/{len(df)} units (median {np.nanmedian(df['fcci']):.0f})")
