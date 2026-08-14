#!/usr/bin/env python3
"""AEZ x WRSI overlay — water satisfaction by agro-ecological zone and maize maturity class.

Crosses the WRSI water-balance raster with Kenya's AEZ polygons: mean WRSI + crop-failure %
per AEZ zone, and pixel-weighted mean WRSI by maturity class (early/medium/late). Answers
"do the early/medium/late-maturing maize zones differ in water satisfaction?"

Run: python aez_wrsi.py --product wrsi_Kenya_maize_Longrains_2024 --px 3000
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
from aez_analysis import parse_aez, maturity_class, AEZ_SHP, MATURITY_ORDER, MATURITY_COLORS


def mosaic(tiles, px, bands):
    ls, bs, rs, ts = [], [], [], []; crs = None
    for t in tiles:
        with rasterio.open(t) as ds:
            b = ds.bounds; crs = ds.crs
            ls.append(b.left); bs.append(b.bottom); rs.append(b.right); ts.append(b.top)
    left, bottom, right, top = min(ls), min(bs), max(rs), max(ts)
    W = px; H = max(1, int(round(W * (top - bottom) / (right - left))))
    tr = from_bounds(left, bottom, right, top, W, H)
    out = {}
    for bi in bands:
        dest = np.zeros((H, W), "float32")
        for t in tiles:
            with rasterio.open(t) as ds:
                if bi > ds.count: continue
                tmp = np.zeros((H, W), "float32")
                reproject(source=rasterio.band(ds, bi), destination=tmp,
                          src_transform=ds.transform, src_crs=ds.crs,
                          dst_transform=tr, dst_crs=crs, resampling=Resampling.nearest)
            dest = np.where(tmp != 0, tmp, dest)
        out[bi] = dest
    return out, tr


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--outputs-dir",
        default="/Users/hildamanzi/Library/CloudStorage/GoogleDrive-manzikye@gmail.com/My Drive/planting_outputs")
    ap.add_argument("--product", default="wrsi_Kenya_maize_Longrains_2024")
    ap.add_argument("--px", type=int, default=3000)
    ap.add_argument("--min-px", type=int, default=15)
    args = ap.parse_args()

    tiles = sorted(glob.glob(os.path.join(args.outputs_dir, args.product + "-*.tif"))) or \
            sorted(glob.glob(os.path.join(args.outputs_dir, args.product + ".tif")))
    if not tiles:
        print(f"No tiles for {args.product}"); return
    with rasterio.open(tiles[0]) as ds:
        nb = ds.count
    bands = mosaic(tiles, args.px, [1] + ([3] if nb >= 3 else []))
    b, tr = bands
    wrsi = b[1]; cls = b.get(3, np.where(wrsi >= 80, 5, np.where(wrsi >= 50, 3, 1)))
    H, W = wrsi.shape

    aez = gpd.read_file(AEZ_SHP).to_crs("EPSG:4326")
    aez["belt"], aez["zone"] = zip(*aez["AEZONE"].map(parse_aez))
    aez["maturity"] = [maturity_class(x, z) for x, z in zip(aez["belt"], aez["zone"])]
    aez = aez[aez["belt"].notna()].copy()
    codes = sorted(aez["AEZONE"].unique().tolist())
    cid = {c: i + 1 for i, c in enumerate(codes)}
    aez["cid"] = aez["AEZONE"].map(cid)
    zones = rasterize(((g, i) for g, i in zip(aez.geometry, aez["cid"])),
                      out_shape=(H, W), transform=tr, fill=0, dtype="int32")
    meta = aez.drop_duplicates("AEZONE").set_index("AEZONE")

    recs = []
    for c in codes:
        m = (zones == cid[c]) & (wrsi > 0) & (wrsi <= 100)
        n = int(m.sum())
        if n < args.min_px: continue
        recs.append(dict(aez=c, maturity=meta.loc[c, "maturity"], n_px=n,
                         mean_WRSI=round(float(wrsi[m].mean()), 1),
                         fail_pct=round(float((cls[m] <= 2).mean()) * 100, 1)))
    with open(f"{args.product}_AEZ_WRSI.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(recs[0].keys())); w.writeheader(); w.writerows(recs)

    # per-maturity pixel-weighted
    print(f"{args.product}  —  WRSI by maize maturity class")
    matstats = {}
    for mc in MATURITY_ORDER:
        rr = [r for r in recs if r["maturity"] == mc]
        if not rr: continue
        tot = sum(r["n_px"] for r in rr)
        mw = sum(r["mean_WRSI"] * r["n_px"] for r in rr) / tot
        mf = sum(r["fail_pct"] * r["n_px"] for r in rr) / tot
        matstats[mc] = (mw, mf, tot)
        print(f"  {mc.upper():7} mean WRSI {mw:5.1f} | failure {mf:4.1f}% | {tot:,} px")

    # figure: (A) WRSI choropleth by AEZ, (B) bar WRSI+failure by maturity
    wrsi_by = {r["aez"]: r["mean_WRSI"] for r in recs}
    aez_d = aez.dissolve("AEZONE").reset_index(); aez_d["mean_WRSI"] = aez_d["AEZONE"].map(wrsi_by)
    with PdfPages(f"{args.product}_AEZ_WRSI.pdf") as pdf:
        fig, ax = plt.subplots(figsize=(8.27, 9.5))
        aez_d.plot(column="mean_WRSI", cmap="RdYlGn", vmin=0, vmax=100, ax=ax, legend=True,
                   edgecolor="#555", linewidth=0.2, missing_kwds={"color": "#eee"},
                   legend_kwds={"label": "mean WRSI", "shrink": 0.6})
        ax.set_title(f"Mean WRSI by AEZ — {args.product.replace('_',' ')}", fontsize=11, color="#1a3a5c")
        ax.set_axis_off(); pdf.savefig(fig, bbox_inches="tight"); plt.close(fig)

        fig, ax = plt.subplots(figsize=(8, 5.5))
        mcs = [m for m in MATURITY_ORDER if m in matstats]
        x = np.arange(len(mcs)); wsi = [matstats[m][0] for m in mcs]; fl = [matstats[m][1] for m in mcs]
        ax.bar(x - 0.2, wsi, 0.4, color=[MATURITY_COLORS[m] for m in mcs], label="mean WRSI")
        ax.bar(x + 0.2, fl, 0.4, color=[MATURITY_COLORS[m] for m in mcs], alpha=0.45, hatch="//", label="failure %")
        for i, m in enumerate(mcs):
            ax.text(i - 0.2, wsi[i] + 1, f"{wsi[i]:.0f}", ha="center", fontsize=9)
            ax.text(i + 0.2, fl[i] + 1, f"{fl[i]:.0f}", ha="center", fontsize=9)
        ax.set_xticks(x); ax.set_xticklabels([m + f"\n({matstats[m][2]:,} px)" for m in mcs])
        ax.set_ylabel("value"); ax.set_ylim(0, 105); ax.legend(fontsize=9)
        ax.set_title("Water satisfaction by maize maturity class\n(WRSI vs crop-failure %, AEZ-derived)",
                     fontsize=11, color="#1a3a5c")
        pdf.savefig(fig, bbox_inches="tight"); plt.close(fig)
    print(f"saved {args.product}_AEZ_WRSI.pdf + .csv")


if __name__ == "__main__":
    main()
