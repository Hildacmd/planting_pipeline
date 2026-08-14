#!/usr/bin/env python3
"""Admin-level planting statistics + skill vs FEWS/FAO calendar, computed LOCALLY.

Rasterizes GADM Kenya admin polygons (level 1 county / 2 constituency / 3 ward) onto the
same grid as the downsampled planting mosaic and reduces per unit. No Earth Engine -> not
affected by the GEE quota. Outputs a CSV and a 2-page PDF: modal-dekad choropleth + calendar
hit-rate choropleth.

Run:
  python admin_skill_local.py --level 1 --product planting_Kenya_maize_Longrains_2024 --win 8 12
  python admin_skill_local.py --level 2
  python admin_skill_local.py --level 3 --px 8000
"""
import argparse, os, glob, csv, datetime as dt
import numpy as np
import geopandas as gpd
import rasterio
from rasterio.features import rasterize
from rasterio.transform import from_bounds
from rasterio.warp import reproject, Resampling
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.colors import ListedColormap, BoundaryNorm
from matplotlib.backends.backend_pdf import PdfPages

GADM = "/Users/hildamanzi/Downloads/gadm41_KEN_shp/gadm41_KEN_%d.shp"
DEKAD_COLORS = ['#2b83ba', '#80bfab', '#c7e8ad', '#ffffbf', '#fdc980', '#ec6e43', '#d7191c']
AUTO_PX = {1: 3500, 2: 5000, 3: 8000}


def dekad_label(d):
    d = int(round(d)); m = (d - 1) // 3 + 1
    return f"{d}·{dt.date(2000, m, 1):%b}"


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


def choropleth(pdf, gdf, col, title, cmap, norm=None, vmin=None, vmax=None,
               cbar_ticks=None, cbar_labels=None, cbar_label=""):
    fig, ax = plt.subplots(figsize=(8.27, 9.5))
    plot_kw = dict(column=col, cmap=cmap, ax=ax, edgecolor="#555", linewidth=0.15,
                   missing_kwds={"color": "#eeeeee"})
    if norm is not None: plot_kw["norm"] = norm
    else: plot_kw["vmin"], plot_kw["vmax"] = vmin, vmax
    gdf.plot(**plot_kw)
    sm = plt.cm.ScalarMappable(cmap=cmap, norm=norm if norm is not None
                               else plt.Normalize(vmin, vmax))
    cb = fig.colorbar(sm, ax=ax, fraction=0.04, pad=0.02, ticks=cbar_ticks)
    if cbar_labels is not None: cb.ax.set_yticklabels(cbar_labels)
    cb.set_label(cbar_label)
    ax.set_title(title, fontsize=11, color="#1a3a5c"); ax.set_axis_off()
    pdf.savefig(fig, bbox_inches="tight"); plt.close(fig)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--outputs-dir", default=os.path.expanduser("~/Downloads/planting_outputs"))
    ap.add_argument("--product", default="planting_Kenya_maize_Longrains_2024")
    ap.add_argument("--level", type=int, choices=[1, 2, 3], default=1)
    ap.add_argument("--win", type=int, nargs=2, metavar=("START", "END"), default=[8, 12])
    ap.add_argument("--px", type=int, default=None)
    ap.add_argument("--min-px", type=int, default=15, help="min valid pixels for a unit to count")
    args = ap.parse_args()

    win_s, win_e = args.win; centre = (win_s + win_e) / 2.0
    px = args.px or AUTO_PX[args.level]
    tiles = sorted(glob.glob(os.path.join(args.outputs_dir, args.product + "-*.tif"))) or \
            sorted(glob.glob(os.path.join(args.outputs_dir, args.product + ".tif")))
    if not tiles:
        print(f"No tiles for {args.product} in {args.outputs_dir}"); return
    print(f"{args.product} | admin level {args.level} | window dekads {win_s}-{win_e} "
          f"(centre {centre:g}) | canvas {px}px")

    arr, tr = mosaic(tiles, px)
    H, W = arr.shape
    gdf = gpd.read_file(GADM % args.level)
    namecol = f"NAME_{args.level}"
    zones = rasterize(((geom, i + 1) for i, geom in enumerate(gdf.geometry)),
                      out_shape=(H, W), transform=tr, fill=0, dtype="int32")

    modal_by, hit_by, recs = {}, {}, []
    for i in range(len(gdf)):
        v = arr[zones == (i + 1)]; v = v[(v >= 1) & (v <= 36)]
        if v.size < args.min_px:
            continue
        modal = int(np.bincount(v.astype(int)).argmax())
        p10, p50, p90 = np.percentile(v, [10, 50, 90])
        hit = float(((v >= win_s) & (v <= win_e)).mean())
        row = {"level": args.level, "name": gdf[namecol].iloc[i],
               "county": gdf["NAME_1"].iloc[i]}
        if args.level >= 2: row["constituency"] = gdf["NAME_2"].iloc[i]
        row.update(n_px=int(v.size), modal_dekad=modal, modal_label=dekad_label(modal),
                   mean_dekad=round(float(v.mean()), 2),
                   p10=round(float(p10), 1), p50=round(float(p50), 1), p90=round(float(p90), 1),
                   hit_rate=round(hit, 3), bias_dek=round(float(v.mean() - centre), 2),
                   mae_dek=round(float(np.abs(v - centre).mean()), 2))
        recs.append(row); modal_by[i] = modal; hit_by[i] = hit
    recs.sort(key=lambda r: r["hit_rate"], reverse=True)

    base = f"{args.product}_L{args.level}_skill"
    out_csv, out_pdf = base + ".csv", base + ".pdf"
    with open(out_csv, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(recs[0].keys())); w.writeheader(); w.writerows(recs)

    allv = arr[(arr >= 1) & (arr <= 36)]
    nat_modal = int(np.bincount(allv.astype(int)).argmax())
    print(f"  units with maize signal: {len(recs)} / {len(gdf)}")
    print(f"  NATIONAL modal={nat_modal} ({dekad_label(nat_modal)})  mean={allv.mean():.2f}  "
          f"hit%={((allv>=win_s)&(allv<=win_e)).mean()*100:.1f}  bias={allv.mean()-centre:+.2f}  "
          f"MAE={np.abs(allv-centre).mean():.2f}")
    print(f"  saved -> {out_csv}")

    # choropleths
    gdf["modal_dekad"] = gdf.index.map(lambda i: modal_by.get(i, np.nan))
    gdf["hit_rate"] = gdf.index.map(lambda i: hit_by.get(i, np.nan))
    md = [r["modal_dekad"] for r in recs]
    dmin, dmax = int(min(md)), int(max(md))
    idx = np.linspace(0, len(DEKAD_COLORS) - 1, dmax - dmin + 1).round().astype(int)
    cmap = ListedColormap([DEKAD_COLORS[i] for i in idx])
    norm = BoundaryNorm(np.arange(dmin - 0.5, dmax + 1.5, 1), cmap.N)
    lvl_name = {1: "county", 2: "constituency", 3: "ward"}[args.level]
    with PdfPages(out_pdf) as pdf:
        choropleth(pdf, gdf, "modal_dekad",
                   f"Modal planting dekad by {lvl_name} — {args.product.replace('_',' ')}",
                   cmap, norm=norm, cbar_ticks=range(dmin, dmax + 1),
                   cbar_labels=[dekad_label(d) for d in range(dmin, dmax + 1)],
                   cbar_label="Most common planting dekad (1–36 · month-dekad)")
        choropleth(pdf, gdf, "hit_rate",
                   f"Calendar hit-rate by {lvl_name} "
                   f"(window {dekad_label(win_s)} – {dekad_label(win_e)})",
                   "RdYlGn", vmin=0, vmax=1, cbar_ticks=[0, .25, .5, .75, 1],
                   cbar_label="Share of maize pixels inside calendar window")
    print(f"  saved -> {out_pdf}")


if __name__ == "__main__":
    main()
