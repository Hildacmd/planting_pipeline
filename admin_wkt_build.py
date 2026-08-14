#!/usr/bin/env python3
"""Generalized LOCAL admin planting-skill + WRSI WKT builder (multi-country, app-ready).

Produces the exact schema the interactive app consumes, for any (product, country, level):
  {product}_L{lvl}_skill_WKT.csv :
     county,name,level,constituency,n_px,modal_dekad,modal_label,mean_dekad,
     p10,p50,p90,hit_rate,bias_dek,mae_dek,geometry_wkt
  {wproduct}_L{lvl}_admin_WKT.csv :
     level,name,county,constituency,n_px,mean_WRSI,mean_deficit_mm,fail_pct,geometry_wkt

Column convention is Kenya-style for all countries: county=NAME_1, constituency=NAME_2,
name=NAME_{level}. The planting raster is a single 250 m GeoTIFF; WRSI is a 3-band raster
(WRSI, deficit_mm, wrsi_class). Rasterize GADM polygons onto the raster grid and reduce.

Run (example):
  python admin_wkt_build.py --product planting_Ethiopia_maize_Meher_2024_250m \
      --wproduct wrsi_Ethiopia_maize_Meher_2024_250m --gadm ETH --win 10 15 --level 1
"""
import argparse, os, glob, csv, datetime as dt
import numpy as np
import geopandas as gpd
import rasterio
from rasterio.features import rasterize

DRIVE = os.path.expanduser(
    "~/Library/CloudStorage/GoogleDrive-manzikye@gmail.com/My Drive/planting_outputs")
GADM = {
    "KEN": "/Users/hildamanzi/Downloads/gadm41_KEN_shp/gadm41_KEN_%d.shp",
    "ETH": "/Users/hildamanzi/ICPAC-WORK/Teff-Crop/gadm41_ETH_shp/gadm41_ETH_%d.shp",
}


def dekad_label(d):
    d = int(round(d)); m = (d - 1) // 3 + 1
    return f"{d}·{dt.date(2000, m, 1):%b}"


def find_tif(product, outputs_dir):
    tiles = sorted(glob.glob(os.path.join(outputs_dir, product + "-*.tif"))) or \
            sorted(glob.glob(os.path.join(outputs_dir, product + ".tif")))
    return tiles[-1] if tiles else None


def zones_for(gdf, ds):
    """Rasterize polygons onto the raster's own grid (native, no resample)."""
    return rasterize(((geom, i + 1) for i, geom in enumerate(gdf.geometry)),
                     out_shape=(ds.height, ds.width), transform=ds.transform,
                     fill=0, dtype="int32")


def keys_for(gdf, i, level):
    row = {"county": gdf["NAME_1"].iloc[i]}
    if level >= 2: row["constituency"] = gdf["NAME_2"].iloc[i]
    row["name"] = gdf[f"NAME_{level}"].iloc[i]
    return row


def build(product, wproduct, gadm_key, win, level, outputs_dir, min_px):
    win_s, win_e = win; centre = (win_s + win_e) / 2.0
    ptif = find_tif(product, outputs_dir)
    if not ptif:
        print(f"  [skip] no planting raster for {product}"); return
    gdf = gpd.read_file(GADM[gadm_key] % level).to_crs("EPSG:4326")

    with rasterio.open(ptif) as ds:
        arr = ds.read(1).astype("float32")
        z = zones_for(gdf, ds)

    # optional WRSI raster (3-band)
    warr = None; wtif = find_tif(wproduct, outputs_dir) if wproduct else None
    if wtif:
        with rasterio.open(wtif) as wds:
            wz = zones_for(gdf, wds)
            wb = [wds.read(b).astype("float32") for b in range(1, wds.count + 1)]
        warr = (wb, wz)

    skill, wrsi = [], []
    for i in range(len(gdf)):
        k = keys_for(gdf, i, level)
        geom_wkt = gdf.geometry.iloc[i].wkt
        v = arr[z == (i + 1)]; v = v[(v >= 1) & (v <= 36)]
        if v.size >= min_px:
            modal = int(np.bincount(v.astype(int)).argmax())
            p10, p50, p90 = np.percentile(v, [10, 50, 90])
            hit = float(((v >= win_s) & (v <= win_e)).mean())
            skill.append({"county": k["county"], "name": k["name"], "level": level,
                          "constituency": k.get("constituency", ""),
                          "n_px": int(v.size), "modal_dekad": modal,
                          "modal_label": dekad_label(modal),
                          "mean_dekad": round(float(v.mean()), 2),
                          "p10": round(float(p10), 1), "p50": round(float(p50), 1),
                          "p90": round(float(p90), 1), "hit_rate": round(hit, 3),
                          "bias_dek": round(float(v.mean() - centre), 2),
                          "mae_dek": round(float(np.abs(v - centre).mean()), 2),
                          "geometry_wkt": geom_wkt})
        if warr is not None:
            wb, wz = warr
            m = wz == (i + 1)
            w0 = wb[0][m]; w0 = w0[np.isfinite(w0) & (w0 >= 0) & (w0 <= 100)]
            if w0.size >= min_px:
                defb = wb[1][m] if len(wb) > 1 else np.array([np.nan])
                defb = defb[np.isfinite(defb)]
                wrsi.append({"level": level, "name": k["name"], "county": k["county"],
                             "constituency": k.get("constituency", ""),
                             "n_px": int(w0.size),
                             "mean_WRSI": round(float(w0.mean()), 1),
                             "mean_deficit_mm": round(float(defb.mean()), 1) if defb.size else "",
                             "fail_pct": round(float((w0 < 50).mean() * 100), 1),
                             "geometry_wkt": geom_wkt})

    def dump(rows, cols, path):
        with open(path, "w", newline="") as f:
            w = csv.DictWriter(f, fieldnames=cols); w.writeheader(); w.writerows(rows)
        print(f"  wrote {path}  ({len(rows)} units)")

    dump(skill,
         ["county", "name", "level", "constituency", "n_px", "modal_dekad", "modal_label",
          "mean_dekad", "p10", "p50", "p90", "hit_rate", "bias_dek", "mae_dek", "geometry_wkt"],
         f"{product}_L{level}_skill_WKT.csv")
    if warr is not None:
        dump(wrsi,
             ["level", "name", "county", "constituency", "n_px", "mean_WRSI",
              "mean_deficit_mm", "fail_pct", "geometry_wkt"],
             f"{wproduct}_L{level}_admin_WKT.csv")
    if skill:
        allv = arr[(arr >= 1) & (arr <= 36)]
        print(f"  L{level}: {len(skill)}/{len(gdf)} units | national modal="
              f"{int(np.bincount(allv.astype(int)).argmax())} hit%="
              f"{((allv>=win_s)&(allv<=win_e)).mean()*100:.1f}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--product", required=True)
    ap.add_argument("--wproduct", default=None)
    ap.add_argument("--gadm", required=True, choices=list(GADM))
    ap.add_argument("--win", type=int, nargs=2, required=True)
    ap.add_argument("--level", type=int, choices=[1, 2, 3], default=None,
                    help="omit to build all three levels")
    ap.add_argument("--outputs-dir", default=DRIVE)
    ap.add_argument("--min-px", type=int, default=8)
    a = ap.parse_args()
    levels = [a.level] if a.level else [1, 2, 3]
    for lv in levels:
        build(a.product, a.wproduct, a.gadm, a.win, lv, a.outputs_dir, a.min_px)


if __name__ == "__main__":
    main()
