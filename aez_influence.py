#!/usr/bin/env python3
"""Visualize the AEZ influence on planting dekad — distributions by maturity class and by
altitude belt, plus the moisture-zone gradient. Shows whether planting *timing* actually
shifts with agro-ecology (the maps show it barely does; this quantifies it).

Run: python aez_influence.py --product planting_Kenya_maize_Longrains_2024 \
        --outputs-dir "/path/to/planting_outputs" --px 4000
"""
import argparse, os, glob
import numpy as np
import geopandas as gpd
from rasterio.features import rasterize
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from aez_analysis import mosaic, parse_aez, maturity_class, dekad_label, AEZ_SHP

BELT_ORDER = ["TA", "UH", "LH", "UM", "LM", "IL", "CL"]        # cold/high -> hot/low
BELT_LABEL = {"TA": "TA (alpine)", "UH": "UH (upper highland)", "LH": "LH (lower highland)",
              "UM": "UM (upper midland)", "LM": "LM (lower midland)", "IL": "IL (inner lowland)",
              "CL": "CL (coastal lowland)"}
MAT_ORDER = ["early", "medium", "late"]
MAT_COLOR = {"early": "#fdae61", "medium": "#66bd63", "late": "#1a5276"}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--outputs-dir", default=os.path.expanduser("~/Downloads/planting_outputs"))
    ap.add_argument("--product", default="planting_Kenya_maize_Longrains_2024")
    ap.add_argument("--px", type=int, default=4000)
    ap.add_argument("--out", default=None)
    args = ap.parse_args()

    tiles = sorted(glob.glob(os.path.join(args.outputs_dir, args.product + "-*.tif"))) or \
            sorted(glob.glob(os.path.join(args.outputs_dir, args.product + ".tif")))
    if not tiles:
        print(f"No tiles for {args.product} in {args.outputs_dir}"); return
    arr, tr = mosaic(tiles, args.px)
    H, W = arr.shape

    aez = gpd.read_file(AEZ_SHP).to_crs("EPSG:4326")
    aez["belt"], aez["zone"] = zip(*aez["AEZONE"].map(parse_aez))
    aez["maturity"] = [maturity_class(b, z) for b, z in zip(aez["belt"], aez["zone"])]
    aez = aez[aez["belt"].notna()].copy()
    aez["rid"] = range(1, len(aez) + 1)
    rid_belt = dict(zip(aez["rid"], aez["belt"]))
    rid_zone = dict(zip(aez["rid"], aez["zone"]))
    rid_mat = dict(zip(aez["rid"], aez["maturity"]))
    zones = rasterize(((g, r) for g, r in zip(aez.geometry, aez["rid"])),
                      out_shape=(H, W), transform=tr, fill=0, dtype="int32")

    valid = (arr >= 1) & (arr <= 36) & (zones > 0)
    pv = arr[valid]; rz = zones[valid]
    belt_arr = np.array([rid_belt.get(r, "?") for r in rz])
    zone_arr = np.array([rid_zone.get(r, np.nan) for r in rz], dtype=float)
    mat_arr = np.array([rid_mat.get(r, "unclassified") for r in rz])
    print(f"{args.product}: {pv.size:,} classified maize pixels")

    fig, axes = plt.subplots(1, 3, figsize=(15, 5.6))

    # (A) planting dekad distribution by maturity class
    ax = axes[0]
    data = [pv[mat_arr == m] for m in MAT_ORDER]
    bp = ax.boxplot(data, labels=[m for m in MAT_ORDER], patch_artist=True, showfliers=False,
                    medianprops=dict(color="black"))
    for patch, m in zip(bp["boxes"], MAT_ORDER):
        patch.set_facecolor(MAT_COLOR[m])
    for i, m in enumerate(MAT_ORDER):
        ax.text(i + 1, np.median(pv[mat_arr == m]) + 0.15,
                f"med {int(round(np.median(pv[mat_arr==m])))}", ha="center", fontsize=8)
    ax.set_title("Planting dekad by maturity class", fontsize=11, color="#1a3a5c")
    ax.set_ylabel("planting dekad (1–36)")
    ax.set_yticks(range(int(pv.min()), int(pv.max()) + 1))
    ax.set_yticklabels([dekad_label(d) for d in range(int(pv.min()), int(pv.max()) + 1)], fontsize=7)

    # (B) planting dekad distribution by altitude belt (cold/high -> hot/low)
    ax = axes[1]
    belts = [b for b in BELT_ORDER if (belt_arr == b).sum() > 30]
    data = [pv[belt_arr == b] for b in belts]
    ax.boxplot(data, labels=[b for b in belts], showfliers=False,
               medianprops=dict(color="#c0392b"))
    ax.set_title("Planting dekad by altitude belt\n(cold/high → hot/low)", fontsize=11, color="#1a3a5c")
    ax.set_ylabel("planting dekad (1–36)")
    ax.axhline(np.median(pv), ls="--", lw=0.8, color="grey")
    ax.text(0.5, np.median(pv) + 0.1, f"national median {int(round(np.median(pv)))}", fontsize=7, color="grey")

    # (C) mean planting dekad vs moisture-zone number (dryness gradient)
    ax = axes[2]
    zn = np.arange(0, 8)
    means = [pv[zone_arr == z].mean() if (zone_arr == z).sum() > 30 else np.nan for z in zn]
    stds = [pv[zone_arr == z].std() if (zone_arr == z).sum() > 30 else np.nan for z in zn]
    ax.errorbar(zn, means, yerr=stds, marker="o", capsize=3, color="#2d6a9f")
    ax.set_title("Mean planting dekad vs moisture zone\n(0 humid → 7 very arid)", fontsize=11, color="#1a3a5c")
    ax.set_xlabel("AEZ moisture zone number"); ax.set_ylabel("mean planting dekad")
    ax.grid(alpha=0.3)

    fig.suptitle(f"AEZ influence on maize planting timing — {args.product.replace('_',' ')}",
                 fontsize=12, color="#1a3a5c")
    fig.tight_layout(rect=[0, 0, 1, 0.96])
    out = args.out or f"{args.product}_AEZ_influence.png"
    fig.savefig(out, dpi=200, bbox_inches="tight")
    fig.savefig(out.replace(".png", ".pdf"), bbox_inches="tight")
    plt.close(fig)

    # console takeaway
    print("\nmedian planting dekad by maturity class:")
    for m in MAT_ORDER:
        d = pv[mat_arr == m]
        print(f"  {m:7} median {np.median(d):.1f} ({dekad_label(np.median(d))})  "
              f"IQR {np.percentile(d,25):.0f}-{np.percentile(d,75):.0f}  n={d.size:,}")
    spread = np.median(pv[mat_arr == "early"]) - np.median(pv[mat_arr == "late"])
    print(f"\nearly-vs-late median difference: {spread:+.1f} dekad(s)  "
          f"-> {'negligible' if abs(spread)<1 else 'modest'} timing shift with agro-ecology")
    print(f"saved -> {out}  and  {out.replace('.png','.pdf')}")


if __name__ == "__main__":
    main()
