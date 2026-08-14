#!/usr/bin/env python3
"""Aggregate the onset false-start (5+7) + excess/waterlogging diagnostics to admin units and merge
into the green-up-season skill tables (Kenya Long rains, Ethiopia Meher).

Adds columns to each {base}_L{lvl}_skill_WKT.csv:
  false_start_pct  % of green-up-onset maize area the 5+7 gate rejects (deficit false start)
  waterlog_idx     mean stage-weighted waterlogging index (0-100)
  waterlog_pct     % of maize area with waterlog_idx >= 25 (Watch-level, ASAP-style)
  spi_wet_pct      % of maize area with SPI-3 >= +1.5 (very wet)
"""
import os, glob, numpy as np, pandas as pd, geopandas as gpd, rasterio
from rasterio.features import rasterize
import caf_add

DRIVE, GADM, KEYS = caf_add.DRIVE, caf_add.GADM, caf_add.KEYS
BANDS = ["false_start", "waterlog_idx", "spi3_wet", "onset_acc_mm"]
WATERLOG_AFFECTED = 25          # waterlog_idx >= this = "affected" (Watch threshold)
MINPX = 5
PRODUCTS = [
    {"base": "planting_Kenya_maize_Longrains_2024",         "diag": "onsetexcess_Kenya_Longrains_2024", "gadm": "KEN"},
    {"base": "planting_Ethiopia_maize_Meher_2024_250m",     "diag": "onsetexcess_Ethiopia_Meher_2024",  "gadm": "ETH"},
    {"base": "planting_Kenya_maize_Shortrains_2024_rainfed", "diag": "onsetexcess_Kenya_Shortrains_2024", "gadm": "KEN"},  # excess only (no 5+7)
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
    tif = newest(cfg["diag"])
    if not tif:
        print(f"  [skip] no raster {cfg['diag']}"); continue
    with rasterio.open(tif) as ds:
        names = [ds.descriptions[i] or (BANDS[i] if i < len(BANDS) else f"b{i}") for i in range(ds.count)]
        b = {names[i]: ds.read(i + 1, masked=True).astype("float32") for i in range(ds.count)}
        tr, shp, rcrs = ds.transform, (ds.height, ds.width), ds.crs
    valid = ~b["waterlog_idx"].mask                                      # always-present footprint (excess bands)
    has_fs = "false_start" in b                                          # false-start absent for short rains
    print(f"== {cfg['base']}  <- {os.path.basename(tif)} ({rcrs}) ==")
    for lvl in (1, 2, 3):
        csv = f"{cfg['base']}_L{lvl}_skill_WKT.csv"
        if not os.path.exists(csv):
            print(f"  [skip] {csv}"); continue
        gdf = gpd.read_file(GADM[cfg["gadm"]] % lvl).to_crs(rcrs)
        z = rasterize(((g, i + 1) for i, g in enumerate(gdf.geometry)), out_shape=shp, transform=tr, fill=0, dtype="int32")
        gdf["county"] = gdf["NAME_1"]; gdf["constituency"] = gdf.get("NAME_2"); gdf["name"] = gdf[f"NAME_{lvl}"]
        acc = {c: {} for c in ["false_start_pct", "waterlog_idx", "waterlog_pct", "spi_wet_pct"]}
        for i in range(len(gdf)):
            m = (z == (i + 1)) & valid
            n = int(m.sum())
            if n < MINPX:
                continue
            wl = np.asarray(b["waterlog_idx"][m]); sw = np.asarray(b["spi3_wet"][m])
            if has_fs:
                fs = np.asarray(b["false_start"][m]); acc["false_start_pct"][i] = round(float(fs.mean()) * 100, 1)
            acc["waterlog_idx"][i]    = round(float(wl.mean()), 1)
            acc["waterlog_pct"][i]    = round(float((wl >= WATERLOG_AFFECTED).mean()) * 100, 1)
            acc["spi_wet_pct"][i]     = round(float(sw.mean()) * 100, 1)
        df = pd.read_csv(csv)
        kf = lambda r: (tuple(r[c] for c in KEYS[lvl]) if len(KEYS[lvl]) > 1 else r[KEYS[lvl][0]])
        for col, med in acc.items():
            gdf["_x"] = gdf.index.map(lambda i: med.get(i, np.nan))
            lut = gdf.dropna(subset=["_x"]).drop_duplicates(KEYS[lvl]).set_index(KEYS[lvl])["_x"].to_dict()
            df[col] = df.apply(lambda r: lut.get(kf(r), np.nan), axis=1)
        df.to_csv(csv, index=False)
        nfs = int(df["false_start_pct"].notna().sum()) if has_fs else 0
        fsmsg = f"median false-start {np.nanmedian(df['false_start_pct']):.1f}% · " if has_fs and nfs else ""
        print(f"  L{lvl}: excess -> {int(df['waterlog_idx'].notna().sum())}/{len(df)} units "
              f"({fsmsg}median wet {np.nanmedian(df['spi_wet_pct']):.1f}% · median waterlog-idx {np.nanmedian(df['waterlog_idx']):.1f})")
