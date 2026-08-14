#!/usr/bin/env python3
"""Refresh ONLY the whole-season WRSI admin tables for the main seasons, from the spatial-WHC WRSI
rasters — without touching the skill CSVs (preserves their CAF/GDD/CPI/viability columns) and without
re-reading the 351 MB 10 m planting raster.

Writes {wproduct}_L{lvl}_admin_WKT.csv with columns matching admin_wkt_build:
    level, name, county, constituency, n_px, mean_WRSI, mean_deficit_mm, fail_pct, geometry_wkt
app_data.py merges these (mean_WRSI->wrsi, mean_deficit_mm->def, fail_pct->fail).

Run:  python wrsi_admin_refresh.py
"""
import os, glob, csv, numpy as np, geopandas as gpd, rasterio
from rasterio.features import rasterize
import caf_add

DRIVE, GADM = caf_add.DRIVE, caf_add.GADM
MINPX = 8
PRODUCTS = [
    {"wproduct": "wrsi_Kenya_maize_Longrains_2024",      "gadm": "KEN"},
    {"wproduct": "wrsi_Ethiopia_maize_Meher_2024_250m",  "gadm": "ETH"},
]
COLS = ["level", "name", "county", "constituency", "n_px",
        "mean_WRSI", "mean_deficit_mm", "fail_pct", "geometry_wkt"]


def newest(base):
    """Newest-by-mtime among base.tif and 'base (N).tif' (works around Drive duplicate names)."""
    v = glob.glob(os.path.join(DRIVE, base + ".tif")) + glob.glob(os.path.join(DRIVE, base + " (*).tif"))
    return max(v, key=os.path.getmtime) if v else None


def keys_for(gdf, i, lvl):
    r = {"county": gdf["NAME_1"].iloc[i]}
    if lvl >= 2:
        r["constituency"] = gdf["NAME_2"].iloc[i]
    r["name"] = gdf[f"NAME_{lvl}"].iloc[i]
    return r


for cfg in PRODUCTS:
    tif = newest(cfg["wproduct"])
    if not tif:
        print(f"  [skip] no raster for {cfg['wproduct']}"); continue
    with rasterio.open(tif) as wds:
        wb = [wds.read(b).astype("float32") for b in range(1, wds.count + 1)]
        tr, shp, rcrs = wds.transform, (wds.height, wds.width), wds.crs
    print(f"== {cfg['wproduct']}  ({len(wb)} bands, {shp[1]}x{shp[0]}, {rcrs}) <- {os.path.basename(tif)} ==")
    for lvl in (1, 2, 3):
        gdf = gpd.read_file(GADM[cfg["gadm"]] % lvl).to_crs("EPSG:4326")  # keys + wkt (display) in 4326
        gdf_r = gdf.to_crs(rcrs)                                          # rasterize in the RASTER's CRS
        z = rasterize(((g, i + 1) for i, g in enumerate(gdf_r.geometry)),
                      out_shape=shp, transform=tr, fill=0, dtype="int32")   # native grid, no resample
        rows = []
        for i in range(len(gdf)):
            m = z == (i + 1)
            w0 = wb[0][m]; w0 = w0[np.isfinite(w0) & (w0 >= 0) & (w0 <= 100)]
            if w0.size < MINPX:
                continue
            defb = wb[1][m] if len(wb) > 1 else np.array([np.nan]); defb = defb[np.isfinite(defb)]
            k = keys_for(gdf, i, lvl)
            rows.append({"level": lvl, "name": k["name"], "county": k["county"],
                         "constituency": k.get("constituency", ""), "n_px": int(w0.size),
                         "mean_WRSI": round(float(w0.mean()), 1),
                         "mean_deficit_mm": round(float(defb.mean()), 1) if defb.size else "",
                         "fail_pct": round(float((w0 < 50).mean() * 100), 1),
                         "geometry_wkt": gdf.geometry.iloc[i].wkt})
        out = f"{cfg['wproduct']}_L{lvl}_admin_WKT.csv"
        with open(out, "w", newline="") as f:
            w = csv.DictWriter(f, fieldnames=COLS); w.writeheader(); w.writerows(rows)
        med = np.median([r["mean_WRSI"] for r in rows]) if rows else float("nan")
        print(f"  L{lvl}: {len(rows)} units  median WRSI={med:.1f}  -> {out}")
