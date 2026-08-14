#!/usr/bin/env python3
"""Convert a planting/WRSI GeoTIFF into a point CSV with WKT geometry — QGIS-ready.

One row per valid pixel: lon, lat, the band value(s), a dekad label (for planting), and a
POINT WKT column. Load in QGIS via Layer → Add Layer → Add Delimited Text Layer, geometry =
"Well Known Text (WKT)", field = geometry_wkt, CRS = EPSG:4326.

Downsamples on read (--px) so the point count stays manageable; only valid pixels are written.

Run:
  python raster_to_wkt.py --product planting_Kenya_maize_Longrains_2024 --px 2000
  python raster_to_wkt.py --product wrsi_Kenya_maize_Longrains_2024 --px 1200 --kind wrsi
"""
import argparse, os, glob, csv, datetime as dt
import numpy as np
import rasterio
from rasterio.transform import from_bounds, xy
from rasterio.warp import reproject, Resampling


def dekad_label(d):
    d = int(round(d)); m = (d - 1) // 3 + 1
    return f"{d}·{dt.date(2000, m, 1):%b}"


def mosaic(tiles, px, nbands):
    ls, bs, rs, ts = [], [], [], []; crs = None
    for t in tiles:
        with rasterio.open(t) as ds:
            b = ds.bounds; crs = ds.crs
            ls.append(b.left); bs.append(b.bottom); rs.append(b.right); ts.append(b.top)
    left, bottom, right, top = min(ls), min(bs), max(rs), max(ts)
    W = px; H = max(1, int(round(W * (top - bottom) / (right - left))))
    tr = from_bounds(left, bottom, right, top, W, H)
    dest = np.zeros((nbands, H, W), "float32")
    for t in tiles:
        with rasterio.open(t) as ds:
            for bi in range(nbands):
                tmp = np.zeros((H, W), "float32")
                reproject(source=rasterio.band(ds, bi + 1), destination=tmp,
                          src_transform=ds.transform, src_crs=ds.crs,
                          dst_transform=tr, dst_crs=crs, resampling=Resampling.nearest)
                dest[bi] = np.where(tmp != 0, tmp, dest[bi])
    return dest, tr


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--outputs-dir", default="/Users/hildamanzi/ICPAC-WORK/plantingwindow_pipeline/planting_outputs")
    ap.add_argument("--product", default="planting_Kenya_maize_Longrains_2024")
    ap.add_argument("--px", type=int, default=2000, help="grid width (points ~ px x px x maize-fraction)")
    ap.add_argument("--kind", choices=["planting", "wrsi"], default="planting")
    ap.add_argument("--geom", choices=["polygon", "point"], default="polygon",
                    help="polygon = pixel square (4 corners; fills the map); point = pixel centre")
    ap.add_argument("--out", default=None)
    args = ap.parse_args()

    tiles = sorted(glob.glob(os.path.join(args.outputs_dir, args.product + "-*.tif"))) or \
            sorted(glob.glob(os.path.join(args.outputs_dir, args.product + ".tif")))
    if not tiles:
        print(f"No tiles for {args.product} in {args.outputs_dir}"); return
    with rasterio.open(tiles[0]) as ds:
        nbands = ds.count
    bandnames = (["planting_dekad"] if args.kind == "planting"
                 else ["WRSI", "deficit_mm", "wrsi_class"][:nbands])
    print(f"{args.product}: {len(tiles)} tiles, {nbands} band(s) → {bandnames}")

    arr, tr = mosaic(tiles, args.px, nbands)
    H, W = arr.shape[1], arr.shape[2]
    b0 = arr[0]
    if args.kind == "planting":
        valid = (b0 >= 1) & (b0 <= 36)
    else:
        valid = (b0 > 0) & (b0 <= 100)
    rows_idx, cols_idx = np.where(valid)
    print(f"valid pixels: {rows_idx.size:,}")

    hx, hy = abs(tr.a) / 2.0, abs(tr.e) / 2.0        # half pixel size (deg) for the polygon corners
    suffix = "polygons" if args.geom == "polygon" else "points"
    out = args.out or f"{args.product}_{suffix}_WKT.csv"
    with open(out, "w", newline="") as f:
        w = csv.writer(f)
        header = ["lon", "lat"] + bandnames + (["dekad_label"] if args.kind == "planting" else []) + ["geometry_wkt"]
        w.writerow(header)
        xs, ys = xy(tr, rows_idx, cols_idx)          # pixel centres
        xs = np.atleast_1d(xs); ys = np.atleast_1d(ys)
        for k in range(rows_idx.size):
            r, c = rows_idx[k], cols_idx[k]
            vals = [round(float(arr[bi][r, c]), 3) for bi in range(nbands)]
            lon, lat = round(float(xs[k]), 6), round(float(ys[k]), 6)
            extra = [dekad_label(vals[0])] if args.kind == "planting" else []
            if args.geom == "polygon":
                x0, x1 = round(lon - hx, 6), round(lon + hx, 6)
                y0, y1 = round(lat - hy, 6), round(lat + hy, 6)
                wkt = (f"POLYGON (({x0} {y0}, {x1} {y0}, {x1} {y1}, {x0} {y1}, {x0} {y0}))")
            else:
                wkt = f"POINT ({lon} {lat})"
            w.writerow([lon, lat] + vals + extra + [wkt])
    sz = os.path.getsize(out) / 1e6
    print(f"saved -> {os.path.abspath(out)}  ({rows_idx.size:,} points, {sz:.1f} MB)")
    print("QGIS: Add Delimited Text Layer → geometry = WKT, field = geometry_wkt, CRS = EPSG:4326")


if __name__ == "__main__":
    main()
