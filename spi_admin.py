#!/usr/bin/env python3
"""Aggregate SPI-3 to admin units over the maize area, and merge into the skill WKT tables.

Per admin unit (maize pixels only, from the 250 m planting raster):
  spi3_dry_pct = % of maize area with SPI-3 <= -1  (ASAP-classable drought fraction)
  spi3_mean    = mean SPI-3 over the maize area
SPI-3 (~5.5 km CHIRPS) is reprojected onto the planting grid (nearest) before overlay.
"""
import os, numpy as np, pandas as pd, geopandas as gpd, rasterio
from rasterio.features import rasterize
from rasterio.warp import reproject, Resampling
import caf_add  # DRIVE, GADM, KEYS

DRIVE, GADM, KEYS = caf_add.DRIVE, caf_add.GADM, caf_add.KEYS
PRODUCTS = [
    {"base": "planting_Kenya_maize_Longrains_2024",
     "plant": "planting_Kenya_maize_Longrains_2024.tif", "spi": "spi3_Kenya_Longrains_2024.tif", "gadm": "KEN"},
    {"base": "planting_Kenya_maize_Shortrains_2024_250m",
     "plant": "planting_Kenya_maize_Shortrains_2024_250m.tif", "spi": "spi3_Kenya_Shortrains_2024.tif", "gadm": "KEN"},
    {"base": "planting_Ethiopia_maize_Meher_2024_250m",
     "plant": "planting_Ethiopia_maize_Meher_2024_250m.tif", "spi": "spi3_Ethiopia_Meher_2024.tif", "gadm": "ETH"},
]


def load(plant, spi):
    with rasterio.open(os.path.join(DRIVE, plant)) as p:
        parr = p.read(1).astype("float32"); tr = p.transform; crs = p.crs; shp = parr.shape
    dst = np.full(shp, np.nan, "float32")
    with rasterio.open(os.path.join(DRIVE, spi)) as s:
        reproject(rasterio.band(s, 1), dst, src_transform=s.transform, src_crs=s.crs,
                  dst_transform=tr, dst_crs=crs, resampling=Resampling.nearest)
    return parr, dst, tr


for cfg in PRODUCTS:
    parr, spi, tr = load(cfg["plant"], cfg["spi"])
    maize = (parr >= 1) & (parr <= 36)
    print(f"== {cfg['base']} ==")
    for lvl in (1, 2, 3):
        csv = f"{cfg['base']}_L{lvl}_skill_WKT.csv"
        if not os.path.exists(csv):
            print(f"  [skip] {csv}"); continue
        gdf = gpd.read_file(GADM[cfg["gadm"]] % lvl).to_crs("EPSG:4326")
        z = rasterize(((g, i + 1) for i, g in enumerate(gdf.geometry)),
                      out_shape=parr.shape, transform=tr, fill=0, dtype="int32")
        dry, mean = {}, {}
        for i in range(len(gdf)):
            m = (z == (i + 1)) & maize
            sv = spi[m]; sv = sv[np.isfinite(sv)]
            if sv.size >= 5:
                dry[i] = round(float((sv <= -1).mean() * 100), 1)
                mean[i] = round(float(sv.mean()), 2)
        gdf["county"] = gdf["NAME_1"]; gdf["constituency"] = gdf.get("NAME_2"); gdf["name"] = gdf[f"NAME_{lvl}"]
        key = KEYS[lvl]
        gdf["_d"] = gdf.index.map(lambda i: dry.get(i, np.nan))
        gdf["_m"] = gdf.index.map(lambda i: mean.get(i, np.nan))
        ld = gdf.dropna(subset=["_d"]).drop_duplicates(key).set_index(key)["_d"].to_dict()
        lm = gdf.dropna(subset=["_m"]).drop_duplicates(key).set_index(key)["_m"].to_dict()
        df = pd.read_csv(csv)
        kf = lambda r: (tuple(r[c] for c in key) if len(key) > 1 else r[key[0]])
        df["spi3_dry_pct"] = df.apply(lambda r: ld.get(kf(r), np.nan), axis=1)
        df["spi3_mean"] = df.apply(lambda r: lm.get(kf(r), np.nan), axis=1)
        df.to_csv(csv, index=False)
        n = df["spi3_dry_pct"].notna().sum()
        print(f"  L{lvl}: SPI-3 -> {n}/{len(df)} units (mean SPI {np.nanmean(df['spi3_mean']):+.2f})")
