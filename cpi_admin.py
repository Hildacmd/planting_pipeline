#!/usr/bin/env python3
"""Merge stage-WRSI/WSI + CPI + yield into the MAIN-season admin tables (Kenya Long rains, Ethiopia
Meher), from their cpi_*.tif rasters. Short rains is handled by swap_shortrains.py.

Adds columns (to each existing {base}_L{lvl}_skill_WKT.csv): wrsi_veg/flo/grf, wsi_veg/flo/grf,
failflo_pct, cpi, yield_tha, total_yield_t, s_water, s_heat, s_veg.
"""
import os, numpy as np, pandas as pd, geopandas as gpd, rasterio
from rasterio.features import rasterize
from rasterio.warp import reproject, Resampling
import caf_add

DRIVE, GADM, KEYS = caf_add.DRIVE, caf_add.GADM, caf_add.KEYS
PIXEL_HA = 6.25
BANDS = ["wrsi_veg", "wrsi_flo", "wrsi_grf", "wsi_veg", "wsi_flo", "wsi_grf",
         "CPI", "yield_tha_x100", "S_water", "S_heat", "S_veg"]
PRODUCTS = [
    {"base": "planting_Kenya_maize_Longrains_2024", "plant": "planting_Kenya_maize_Longrains_2024.tif",
     "cpi": "cpi_Kenya_Longrains_2024.tif", "gadm": "KEN"},
    {"base": "planting_Ethiopia_maize_Meher_2024_250m", "plant": "planting_Ethiopia_maize_Meher_2024_250m.tif",
     "cpi": "cpi_Ethiopia_Meher_2024.tif", "gadm": "ETH"},
]
MINPX = 5


def reproj(src, tr, crs, shp, band=1):
    dst = np.full(shp, np.nan, "float32")
    with rasterio.open(os.path.join(DRIVE, src)) as s:
        reproject(rasterio.band(s, band), dst, src_transform=s.transform, src_crs=s.crs,
                  dst_transform=tr, dst_crs=crs, resampling=Resampling.nearest)
    return dst


for cfg in PRODUCTS:
    if not os.path.exists(os.path.join(DRIVE, cfg["cpi"])):
        print(f"  [skip] {cfg['cpi']} not present yet"); continue
    with rasterio.open(os.path.join(DRIVE, cfg["plant"])) as d:
        plant = d.read(1).astype("float32"); tr = d.transform; crs = d.crs; shp = plant.shape
    with rasterio.open(os.path.join(DRIVE, cfg["cpi"])) as cd:
        cnames = [cd.descriptions[i] for i in range(cd.count)]
    b = {nm: reproj(cfg["cpi"], tr, crs, shp, band=cnames.index(nm) + 1) for nm in BANDS}
    maize = (plant >= 1) & (plant <= 36)
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
        acc = {c: {} for c in ["wrsi_veg", "wrsi_flo", "wrsi_grf", "wsi_veg", "wsi_flo", "wsi_grf",
                               "failflo_pct", "cpi", "yield_tha", "total_yield_t", "s_water", "s_heat", "s_veg"]}
        for i in range(len(gdf)):
            mm = (z == (i + 1)) & maize
            if mm.sum() < MINPX:
                continue
            for src, col in (("wrsi_veg", "wrsi_veg"), ("wrsi_flo", "wrsi_flo"), ("wrsi_grf", "wrsi_grf"),
                             ("wsi_veg", "wsi_veg"), ("wsi_flo", "wsi_flo"), ("wsi_grf", "wsi_grf"),
                             ("CPI", "cpi"), ("S_water", "s_water"), ("S_heat", "s_heat"), ("S_veg", "s_veg")):
                v = b[src][mm]; v = v[(v >= 0) & (v <= 100)]
                if v.size >= MINPX: acc[col][i] = round(float(np.median(v)), 1)
            yv = b["yield_tha_x100"][mm] / 100.0; yv = yv[(yv >= 0) & (yv <= 15)]
            if yv.size >= MINPX:
                acc["yield_tha"][i] = round(float(np.median(yv)), 2)
                acc["total_yield_t"][i] = round(float(np.sum(yv) * PIXEL_HA), 0)
            fv = b["wrsi_flo"][mm]; fv = fv[(fv >= 0) & (fv <= 100)]
            if fv.size >= MINPX: acc["failflo_pct"][i] = round(float((fv < 50).mean() * 100), 1)
        df = pd.read_csv(csv)
        kf = lambda r: (tuple(r[c] for c in key) if len(key) > 1 else r[key[0]])
        for col, med in acc.items():
            gdf["_x"] = gdf.index.map(lambda i: med.get(i, np.nan))
            lut = gdf.dropna(subset=["_x"]).drop_duplicates(key).set_index(key)["_x"].to_dict()
            df[col] = df.apply(lambda r: lut.get(kf(r), np.nan), axis=1)
        df.to_csv(csv, index=False)
        print(f"  L{lvl}: CPI/stage -> {df['cpi'].notna().sum()}/{len(df)} units")
