#!/usr/bin/env python3
"""Add Crop Area Fraction (CAF) to the admin skill tables — the maize share of each unit.

CAF(unit) = detected-maize pixels / total pixels in the unit, computed on the product's own
raster grid (native for 250 m single-file products; a downsampled area-preserving mosaic canvas
for the tiled 10 m Long-rains product, matching admin_skill_local). CAF is a ratio, so it is
resolution/canvas independent and comparable across products.

Merges a `crop_area_frac` column into each existing {product}_L{lvl}_skill_WKT.csv by admin key;
all other statistics are left untouched.
"""
import os, glob
import numpy as np
import pandas as pd
import geopandas as gpd
import rasterio
from rasterio.features import rasterize
from rasterio.transform import from_bounds
from rasterio.warp import reproject, Resampling

DRIVE = os.path.expanduser(
    "~/Library/CloudStorage/GoogleDrive-manzikye@gmail.com/My Drive/planting_outputs")
GADM = {"KEN": "/Users/hildamanzi/Downloads/gadm41_KEN_shp/gadm41_KEN_%d.shp",
        "ETH": "/Users/hildamanzi/ICPAC-WORK/Teff-Crop/gadm41_ETH_shp/gadm41_ETH_%d.shp"}
AUTO_PX = {1: 3500, 2: 5000, 3: 8000}
KEYS = {1: ["name"], 2: ["county", "name"], 3: ["county", "constituency", "name"]}

PRODUCTS = [
    {"base": "planting_Kenya_maize_Longrains_2024", "gadm": "KEN"},
    {"base": "planting_Kenya_maize_Shortrains_2024_250m", "gadm": "KEN"},
    {"base": "planting_Ethiopia_maize_Meher_2024_250m", "gadm": "ETH"},
]


def mosaic(tiles, target_px):
    ls, bs, rs, ts = [], [], [], []; crs = None
    for t in tiles:
        with rasterio.open(t) as ds:
            b = ds.bounds; crs = ds.crs
            ls.append(b.left); bs.append(b.bottom); rs.append(b.right); ts.append(b.top)
    left, bottom, right, top = min(ls), min(bs), max(rs), max(ts)
    W = target_px; H = max(1, int(round(W * (top - bottom) / (right - left))))
    tr = from_bounds(left, bottom, right, top, W, H)
    dest = np.zeros((H, W), "float32")
    for t in tiles:
        with rasterio.open(t) as ds:
            tmp = np.zeros((H, W), "float32")
            reproject(source=rasterio.band(ds, 1), destination=tmp,
                      src_transform=ds.transform, src_crs=ds.crs,
                      dst_transform=tr, dst_crs=crs, resampling=Resampling.nearest)
        dest = np.where(tmp > 0, tmp, dest)
    return dest, tr


def grid_for(base):
    """Return (array, transform) — native for a single file, else a downsampled mosaic."""
    tiled = sorted(glob.glob(os.path.join(DRIVE, base + "-*.tif")))
    if tiled:
        return None  # signal: per-level mosaic (needs level px), handled by caller
    single = sorted(glob.glob(os.path.join(DRIVE, base + ".tif")))
    if not single:
        return "missing"
    with rasterio.open(single[0]) as ds:
        return ds.read(1).astype("float32"), ds.transform


def caf_by_unit(arr, tr, gdf):
    z = rasterize(((g, i + 1) for i, g in enumerate(gdf.geometry)),
                  out_shape=arr.shape, transform=tr, fill=0, dtype="int32")
    out = {}
    for i in range(len(gdf)):
        m = z == (i + 1)
        ntot = int(m.sum())
        if ntot == 0:
            continue
        nval = int(((arr >= 1) & (arr <= 36) & m).sum())
        out[i] = round(nval / ntot, 4)
    return out


def process(cfg):
    base, gk = cfg["base"], cfg["gadm"]
    tiled = sorted(glob.glob(os.path.join(DRIVE, base + "-*.tif")))
    print(f"== {base} ({'tiled 10 m' if tiled else '250 m'}) ==")
    for lvl in (1, 2, 3):
        csv = f"{base}_L{lvl}_skill_WKT.csv"
        if not os.path.exists(csv):
            print(f"  [skip] no {csv}"); continue
        gdf = gpd.read_file(GADM[gk] % lvl).to_crs("EPSG:4326")
        if tiled:
            arr, tr = mosaic(tiled, AUTO_PX[lvl])
        else:
            arr, tr = grid_for(base)
        caf = caf_by_unit(arr, tr, gdf)
        # map GADM row -> key tuple used in the CSV
        gdf["_caf"] = gdf.index.map(lambda i: caf.get(i, np.nan))
        gdf["county"] = gdf["NAME_1"]; gdf["constituency"] = gdf.get("NAME_2")
        gdf["name"] = gdf[f"NAME_{lvl}"]
        key = KEYS[lvl]
        lut = gdf.dropna(subset=["_caf"]).drop_duplicates(key).set_index(key)["_caf"].to_dict()
        df = pd.read_csv(csv)
        def lookup(r):
            k = tuple(r[c] for c in key) if len(key) > 1 else r[key[0]]
            return lut.get(k, np.nan)
        df["crop_area_frac"] = df.apply(lookup, axis=1)
        df.to_csv(csv, index=False)
        n_ok = df["crop_area_frac"].notna().sum()
        print(f"  L{lvl}: CAF added to {n_ok}/{len(df)} units "
              f"(median {np.nanmedian(df['crop_area_frac'])*100:.1f}%)")


if __name__ == "__main__":
    for cfg in PRODUCTS:
        process(cfg)
