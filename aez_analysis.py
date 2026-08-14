#!/usr/bin/env python3
"""Planting dekad x Agro-Ecological Zone (AEZ) -> maize maturity-class interpretation (LOCAL).

Overlays the estimated planting-dekad raster with Kenya's Jaetzold/Sombroek AEZ polygons and,
per zone, reports the modal/median planting dekad and an INDICATIVE maize maturity class.

Why AEZ -> maturity: the AEZ code encodes a temperature belt (altitude) + a moisture/zone
number (1 humid ... 7 very arid). Together these set the Length of Growing Period (LGP), which
is what determines whether farmers grow long- (late), medium-, or short-cycle (early) maize:
  * Highland/cool belts (TA/UH/LH) + humid zones -> long LGP  -> LATE-maturing (e.g. H614/H629)
  * Midland transitional (UM3-4, LM3-4)          -> medium LGP -> MEDIUM (e.g. H513/H516)
  * Dry lowlands (LM5-6, IL5-7, CL5-6)           -> short LGP  -> EARLY / drought-escaping (Katumani/DH04)
The maturity mapping is a standard first-order convention (Jaetzold & Schmidt, Farm Management
Handbook of Kenya) -- calibrate before operational use.

Run:  python aez_analysis.py --product planting_Kenya_maize_Longrains_2024 --px 4000
"""
import argparse, os, glob, re, csv, datetime as dt
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

AEZ_SHP = "/Users/hildamanzi/AEZ-COUNTRIES/KENYA_AEZ/kenya_aezones.shp"
DEKAD_COLORS = ['#2b83ba', '#80bfab', '#c7e8ad', '#ffffbf', '#fdc980', '#ec6e43', '#d7191c']
MATURITY_ORDER = ["early", "medium", "late"]
MATURITY_COLORS = {"early": "#fdae61", "medium": "#66bd63", "late": "#1a5276",
                   "unclassified": "#dddddd"}
COOL_BELTS = {"TA", "UH", "LH"}


def dekad_label(d):
    d = int(round(d)); m = (d - 1) // 3 + 1; k = (d - 1) % 3 + 1
    return f"{d}·{dt.date(2000, m, 1):%b}"


def parse_aez(code):
    """Return (belt, zone_number) or (None, None) for non-AEZ features (lakes/dams/parks)."""
    code = str(code)
    belts = re.findall(r"[A-Z]{2}", code)
    if not belts or belts[0] not in {"TA", "UH", "LH", "UM", "LM", "IL", "CL"}:
        return None, None
    belt = belts[0]
    nums = re.findall(r"\d+", code)
    if nums:
        zone = max(int(n) for n in nums)          # driest (shortest-LGP) in compound codes
    elif code.rstrip().endswith("O"):
        zone = 0                                   # 'UHO','LHO' = per-humid zone 0
    else:
        zone = None
    return belt, zone


def maturity_class(belt, zone):
    if zone is None:
        return "unclassified"
    if belt in COOL_BELTS:                          # cool highlands: long calendar cycle
        return "late" if zone <= 3 else "medium"
    else:                                           # UM/LM/IL/CL midlands & lowlands
        if zone <= 2:  return "late"
        if zone <= 4:  return "medium"
        return "early"


def mosaic(tiles, px):
    ls, bs, rs, ts = [], [], [], []; crs = None
    for t in tiles:
        with rasterio.open(t) as ds:
            b = ds.bounds; crs = ds.crs
            ls.append(b.left); bs.append(b.bottom); rs.append(b.right); ts.append(b.top)
    left, bottom, right, top = min(ls), min(bs), max(rs), max(ts)
    W = px; H = max(1, int(round(W * (top - bottom) / (right - left))))
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


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--outputs-dir", default=os.path.expanduser("~/Downloads/planting_outputs"))
    ap.add_argument("--product", default="planting_Kenya_maize_Longrains_2024")
    ap.add_argument("--px", type=int, default=4000)
    ap.add_argument("--min-px", type=int, default=15)
    args = ap.parse_args()

    tiles = sorted(glob.glob(os.path.join(args.outputs_dir, args.product + "-*.tif"))) or \
            sorted(glob.glob(os.path.join(args.outputs_dir, args.product + ".tif")))
    if not tiles:
        print(f"No tiles for {args.product}"); return
    print(f"{args.product}: {len(tiles)} tiles | AEZ overlay @ {args.px}px")

    arr, tr = mosaic(tiles, args.px)
    H, W = arr.shape
    aez = gpd.read_file(AEZ_SHP).to_crs("EPSG:4326")
    aez["belt"], aez["zone"] = zip(*aez["AEZONE"].map(parse_aez))
    aez["maturity"] = [maturity_class(b, z) for b, z in zip(aez["belt"], aez["zone"])]

    # dissolve to unique zone codes for rasterizing/labelling
    codes = sorted(aez["AEZONE"].dropna().unique().tolist())
    code_id = {c: i + 1 for i, c in enumerate(codes)}
    aez["cid"] = aez["AEZONE"].map(code_id)
    zones = rasterize(((geom, cid) for geom, cid in zip(aez.geometry, aez["cid"])),
                      out_shape=(H, W), transform=tr, fill=0, dtype="int32")

    # per-zone-code stats
    meta = aez.drop_duplicates("AEZONE").set_index("AEZONE")
    recs = []
    for c in codes:
        cid = code_id[c]
        v = arr[zones == cid]; v = v[(v >= 1) & (v <= 36)]
        belt, zone = meta.loc[c, "belt"], meta.loc[c, "zone"]
        mat = meta.loc[c, "maturity"]
        if belt is None or v.size < args.min_px:
            continue
        modal = int(np.bincount(v.astype(int)).argmax())
        p10, p50, p90 = np.percentile(v, [10, 50, 90])
        recs.append(dict(aez=c, belt=belt, zone=zone, maturity_class=mat,
                         n_px=int(v.size), modal_dekad=modal, modal_label=dekad_label(modal),
                         p10=round(float(p10), 1), median=round(float(p50), 1),
                         p90=round(float(p90), 1), mean_dekad=round(float(v.mean()), 2)))
    recs.sort(key=lambda r: (MATURITY_ORDER.index(r["maturity_class"])
                             if r["maturity_class"] in MATURITY_ORDER else 9, -r["n_px"]))

    base = f"{args.product}_AEZ_maturity"
    with open(base + ".csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(recs[0].keys())); w.writeheader(); w.writerows(recs)

    # console summary grouped by maturity class
    print(f"\n{'AEZ':10}{'belt':5}{'zone':>5}{'maturity':>10}{'px':>9}{'modal':>12}{'median':>10}")
    for r in recs:
        print(f"{r['aez'][:10]:10}{r['belt']:5}{str(r['zone']):>5}{r['maturity_class']:>10}"
              f"{r['n_px']:9d}{r['modal_label']:>12}{dekad_label(r['median']):>10}")
    print("\n--- by maturity class (pixel-weighted) ---")
    for mc in MATURITY_ORDER:
        rr = [r for r in recs if r["maturity_class"] == mc]
        if not rr: continue
        tot = sum(r["n_px"] for r in rr)
        wmod = sum(r["modal_dekad"] * r["n_px"] for r in rr) / tot
        zones_in = sorted({r["aez"] for r in rr})
        print(f"{mc.upper():7} | {tot:>9,} px | wtd modal ~ {dekad_label(wmod)} | "
              f"{len(rr)} zones e.g. {', '.join(zones_in[:6])}")

    # maps: (1) modal dekad per AEZ, (2) maturity-class map
    modal_by = {r["aez"]: r["modal_dekad"] for r in recs}
    aez_d = aez.dissolve("AEZONE").reset_index()
    aez_d["modal_dekad"] = aez_d["AEZONE"].map(modal_by)
    aez_d["maturity"] = aez_d["AEZONE"].map({r["aez"]: r["maturity_class"] for r in recs})
    md = [r["modal_dekad"] for r in recs]; dmin, dmax = int(min(md)), int(max(md))
    idx = np.linspace(0, len(DEKAD_COLORS) - 1, dmax - dmin + 1).round().astype(int)
    cmap = ListedColormap([DEKAD_COLORS[i] for i in idx])
    norm = BoundaryNorm(np.arange(dmin - 0.5, dmax + 1.5, 1), cmap.N)

    with PdfPages(base + ".pdf") as pdf:
        fig, ax = plt.subplots(figsize=(8.27, 9.5))
        aez_d.plot(column="modal_dekad", cmap=cmap, norm=norm, ax=ax,
                   edgecolor="#666", linewidth=0.2, missing_kwds={"color": "#eee"})
        sm = plt.cm.ScalarMappable(cmap=cmap, norm=norm)
        cb = fig.colorbar(sm, ax=ax, fraction=0.04, pad=0.02, ticks=range(dmin, dmax + 1))
        cb.ax.set_yticklabels([dekad_label(d) for d in range(dmin, dmax + 1)])
        cb.set_label("Modal planting dekad (1–36 · month-dekad)")
        ax.set_title(f"Modal planting dekad by AEZ — {args.product.replace('_',' ')}",
                     fontsize=11, color="#1a3a5c"); ax.set_axis_off()
        pdf.savefig(fig, bbox_inches="tight"); plt.close(fig)

        fig, ax = plt.subplots(figsize=(8.27, 9.5))
        from matplotlib.patches import Patch
        handles = []
        for mc in MATURITY_ORDER + ["unclassified"]:
            sub = aez_d[aez_d["maturity"] == mc]
            if len(sub):
                sub.plot(ax=ax, color=MATURITY_COLORS[mc], edgecolor="#666", linewidth=0.2)
                handles.append(Patch(facecolor=MATURITY_COLORS[mc], edgecolor="#666",
                                     label=f"{mc} ({len(sub)} zones)"))
        ax.legend(handles=handles, title="Indicative maize maturity", loc="lower right", fontsize=8)
        ax.set_title("Indicative maize maturity class by AEZ\n"
                     "(from altitude belt + moisture zone → length of growing period)",
                     fontsize=11, color="#1a3a5c"); ax.set_axis_off()
        pdf.savefig(fig, bbox_inches="tight"); plt.close(fig)
    print(f"\nsaved -> {base}.csv  and  {base}.pdf")


if __name__ == "__main__":
    main()
