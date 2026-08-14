#!/usr/bin/env python3
"""WRSI choropleths at GADM level 1/2/3 (county / constituency / ward) — mean WRSI, deficit,
and % crop area failing (class<=2) per admin unit. Local; from the WRSI GeoTIFF. Outputs a
2-page PDF per level + a CSV with WKT for QGIS.

Run: python wrsi_admin_maps.py --product wrsi_Kenya_maize_Longrains_2024 --level 1
"""
import argparse, os, glob, csv
import numpy as np
import geopandas as gpd
import rasterio
from rasterio.features import rasterize
from rasterio.transform import from_bounds
from rasterio.warp import reproject, Resampling
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.backends.backend_pdf import PdfPages

GADM = "/Users/hildamanzi/Downloads/gadm41_KEN_shp/gadm41_KEN_%d.shp"
AUTO_PX = {1: 2500, 2: 3500, 3: 5000}


def mosaic(tiles, px, nb):
    ls, bs, rs, ts = [], [], [], []; crs = None
    for t in tiles:
        with rasterio.open(t) as ds:
            b = ds.bounds; crs = ds.crs
            ls.append(b.left); bs.append(b.bottom); rs.append(b.right); ts.append(b.top)
    left, bottom, right, top = min(ls), min(bs), max(rs), max(ts)
    W = px; H = max(1, int(round(W * (top - bottom) / (right - left))))
    tr = from_bounds(left, bottom, right, top, W, H)
    dest = np.zeros((nb, H, W), "float32")
    for t in tiles:
        with rasterio.open(t) as ds:
            for bi in range(nb):
                tmp = np.zeros((H, W), "float32")
                reproject(source=rasterio.band(ds, bi + 1), destination=tmp,
                          src_transform=ds.transform, src_crs=ds.crs,
                          dst_transform=tr, dst_crs=crs, resampling=Resampling.nearest)
                dest[bi] = np.where(tmp != 0, tmp, dest[bi])
    return dest, tr


def choropleth(pdf, gdf, col, title, cmap, vmin, vmax, cbar_label, reverse_good=False):
    fig, ax = plt.subplots(figsize=(8.27, 9.5))
    gdf.plot(column=col, cmap=cmap, ax=ax, vmin=vmin, vmax=vmax, legend=True,
             edgecolor="#555", linewidth=0.15, missing_kwds={"color": "#eeeeee"},
             legend_kwds={"label": cbar_label, "shrink": 0.6})
    ax.set_title(title, fontsize=11, color="#1a3a5c"); ax.set_axis_off()
    pdf.savefig(fig, bbox_inches="tight"); plt.close(fig)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--outputs-dir",
        default="/Users/hildamanzi/Library/CloudStorage/GoogleDrive-manzikye@gmail.com/My Drive/planting_outputs")
    ap.add_argument("--product", default="wrsi_Kenya_maize_Longrains_2024")
    ap.add_argument("--level", type=int, choices=[1, 2, 3], default=1)
    ap.add_argument("--px", type=int, default=None)
    ap.add_argument("--min-px", type=int, default=8)
    args = ap.parse_args()

    tiles = sorted(glob.glob(os.path.join(args.outputs_dir, args.product + "-*.tif"))) or \
            sorted(glob.glob(os.path.join(args.outputs_dir, args.product + ".tif")))
    if not tiles:
        print(f"No tiles for {args.product}"); return
    px = args.px or AUTO_PX[args.level]
    with rasterio.open(tiles[0]) as ds:
        nb = ds.count
    arr, tr = mosaic(tiles, px, nb)          # bands: WRSI, deficit_mm, wrsi_class
    H, W = arr.shape[1], arr.shape[2]
    wrsi, defi = arr[0], (arr[1] if nb > 1 else arr[0] * 0)
    cls = arr[2] if nb > 2 else np.where(wrsi >= 80, 5, np.where(wrsi >= 50, 3, 1))

    gdf = gpd.read_file(GADM % args.level).to_crs("EPSG:4326")
    namecol = f"NAME_{args.level}"
    zones = rasterize(((g, i + 1) for i, g in enumerate(gdf.geometry)),
                      out_shape=(H, W), transform=tr, fill=0, dtype="int32")
    recs, wrsi_by, fail_by = [], {}, {}
    for i in range(len(gdf)):
        m = (zones == (i + 1)) & (wrsi > 0) & (wrsi <= 100)
        n = int(m.sum())
        if n < args.min_px:
            continue
        mw = float(wrsi[m].mean()); md = float(defi[m].mean())
        fail = float((cls[m] <= 2).mean())
        wrsi_by[i] = mw; fail_by[i] = fail * 100
        row = {"level": args.level, "name": gdf[namecol].iloc[i], "county": gdf["NAME_1"].iloc[i]}
        if args.level >= 2: row["constituency"] = gdf["NAME_2"].iloc[i]
        row.update(n_px=n, mean_WRSI=round(mw, 1), mean_deficit_mm=round(md, 1),
                   fail_pct=round(fail * 100, 1), geometry_wkt=gdf.geometry.iloc[i].wkt)
        recs.append(row)
    recs.sort(key=lambda r: r["mean_WRSI"])

    base = f"{args.product}_L{args.level}_admin"
    with open(base + "_WKT.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(recs[0].keys())); w.writeheader(); w.writerows(recs)
    gdf["mean_WRSI"] = gdf.index.map(lambda i: wrsi_by.get(i, np.nan))
    gdf["fail_pct"] = gdf.index.map(lambda i: fail_by.get(i, np.nan))
    lvl = {1: "county", 2: "constituency", 3: "ward"}[args.level]
    with PdfPages(base + ".pdf") as pdf:
        choropleth(pdf, gdf, "mean_WRSI", f"Mean WRSI by {lvl} — {args.product.replace('_',' ')}",
                   "RdYlGn", 0, 100, "mean WRSI (0 fail → 100 satisfied)")
        choropleth(pdf, gdf, "fail_pct", f"Crop-failure risk by {lvl} (% area WRSI class ≤ 2)",
                   "Reds", 0, 100, "% crop area failing")
    print(f"  L{args.level}: {len(recs)} units | saved {base}.pdf + {base}_WKT.csv")


if __name__ == "__main__":
    main()
