#!/usr/bin/env python3
"""Aggregate the GDD-clock stage dekads to admin units and merge into the skill WKT tables.

Per admin unit (over the clock's maize pixels): median dekad of each stage transition —
peak-vegetative, flowering, grain-filling, maturity. Adds columns pkv_dekad, flo_dekad,
grf_dekad, mat_dekad to each {base}_L{lvl}_skill_WKT.csv.
"""
import os, numpy as np, pandas as pd, geopandas as gpd, rasterio
from rasterio.features import rasterize
import caf_add  # DRIVE, GADM, KEYS

DRIVE, GADM, KEYS = caf_add.DRIVE, caf_add.GADM, caf_add.KEYS
STAGES = {"peak_vegetative_dekad": "pkv_dekad", "flowering_dekad": "flo_dekad",
          "grain_filling_dekad": "grf_dekad", "maturity_dekad": "mat_dekad"}
PRODUCTS = [
    {"base": "planting_Kenya_maize_Longrains_2024", "clock": "gddclock_Kenya_Longrains_2024 (1).tif", "gadm": "KEN"},
    {"base": "planting_Kenya_maize_Shortrains_2024_250m", "clock": "gddclock_Kenya_Shortrains_2024 (1).tif", "gadm": "KEN"},
    {"base": "planting_Ethiopia_maize_Meher_2024_250m", "clock": "gddclock_Ethiopia_Meher_2024 (1).tif", "gadm": "ETH"},
]


def load(clock):
    with rasterio.open(os.path.join(DRIVE, clock)) as d:
        bands = {d.descriptions[i]: d.read(i + 1).astype("float32") for i in range(d.count)}
        tr, shp = d.transform, (d.height, d.width)
    return bands, tr, shp


for cfg in PRODUCTS:
    bands, tr, shp = load(cfg["clock"])
    print(f"== {cfg['base']} ==")
    for lvl in (1, 2, 3):
        csv = f"{cfg['base']}_L{lvl}_skill_WKT.csv"
        if not os.path.exists(csv):
            print(f"  [skip] {csv}"); continue
        gdf = gpd.read_file(GADM[cfg["gadm"]] % lvl).to_crs("EPSG:4326")
        z = rasterize(((g, i + 1) for i, g in enumerate(gdf.geometry)),
                      out_shape=shp, transform=tr, fill=0, dtype="int32")
        gdf["county"] = gdf["NAME_1"]; gdf["constituency"] = gdf.get("NAME_2"); gdf["name"] = gdf[f"NAME_{lvl}"]
        key = KEYS[lvl]
        df = pd.read_csv(csv)
        kf = lambda r: (tuple(r[c] for c in key) if len(key) > 1 else r[key[0]])
        for src, col in STAGES.items():
            med = {}
            arr = bands[src]
            for i in range(len(gdf)):
                v = arr[z == (i + 1)]; v = v[(v >= 1) & (v <= 36)]
                if v.size >= 5:
                    med[i] = round(float(np.median(v)), 1)
            gdf["_x"] = gdf.index.map(lambda i: med.get(i, np.nan))
            lut = gdf.dropna(subset=["_x"]).drop_duplicates(key).set_index(key)["_x"].to_dict()
            df[col] = df.apply(lambda r: lut.get(kf(r), np.nan), axis=1)
        n = df["flo_dekad"].notna().sum()
        df.to_csv(csv, index=False)
        print(f"  L{lvl}: stages -> {n}/{len(df)} units")
