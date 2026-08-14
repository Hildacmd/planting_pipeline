#!/usr/bin/env python3
"""Skill-strength MAPS for all planting outputs (both seasons) — hit-rate, bias, MAE choropleths.

Reads the stats.csv exports (pixel-based skill vs the FEWS/FAO calendar, per GAUL admin-1, with
embedded geometry) and renders a season x metric grid of choropleths. Local; no GEE.

Run: python skill_maps.py
"""
import argparse, os, json, glob
import pandas as pd
import geopandas as gpd
from shapely.geometry import shape
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt


def load(path):
    df = pd.read_csv(path)
    df = df[df["count"] > 0].copy()
    geom = [shape(json.loads(g)) for g in df[".geo"]]
    return gpd.GeoDataFrame(df, geometry=geom, crs="EPSG:4326")


def newest(drive, season):
    fs = sorted(glob.glob(os.path.join(drive, f"planting_Kenya_maize_{season}_2024_stats*.csv")),
                key=os.path.getmtime)
    return fs[-1] if fs else None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--drive",
        default="/Users/hildamanzi/Library/CloudStorage/GoogleDrive-manzikye@gmail.com/My Drive/planting_outputs")
    ap.add_argument("--out", default="skill_maps_all_outputs.png")
    args = ap.parse_args()

    seasons = [("Long rains", "Longrains"), ("Short rains", "Shortrains")]
    metrics = [("hit", "Calendar hit-rate (%)", "RdYlGn", 0, 100, lambda v: v * 100),
               ("bias", "Bias (dekads: − early / + late)", "RdBu_r", -3, 3, lambda v: v),
               ("abserr", "MAE (dekads)", "YlOrRd", 0, 3, lambda v: v)]

    fig, axes = plt.subplots(len(seasons), len(metrics), figsize=(15, 9))
    for r, (slabel, stag) in enumerate(seasons):
        f = newest(args.drive, stag)
        gdf = load(f) if f else None
        for c, (col, title, cmap, vmin, vmax, fn) in enumerate(metrics):
            ax = axes[r, c]
            if gdf is not None:
                gdf = gdf.copy(); gdf["_plot"] = gdf[col].map(fn)
                gdf.plot(column="_plot", cmap=cmap, vmin=vmin, vmax=vmax, ax=ax, legend=True,
                         edgecolor="#555", linewidth=0.3, legend_kwds={"shrink": 0.55})
            ax.set_axis_off()
            if r == 0: ax.set_title(title, fontsize=10.5, color="#1a3a5c")
            if c == 0: ax.text(-0.06, 0.5, slabel, transform=ax.transAxes, rotation=90,
                               va="center", ha="center", fontsize=12, fontweight="bold", color="#1a3a5c")
    fig.suptitle("Planting-window skill strength by output — Kenya maize 2024 (admin-1, vs FEWS/FAO calendar)",
                 fontsize=13, color="#1a3a5c")
    fig.tight_layout(rect=[0.02, 0, 1, 0.96])
    fig.savefig(args.out, dpi=185, bbox_inches="tight")
    fig.savefig(args.out.replace(".png", ".pdf"), bbox_inches="tight")
    print(f"saved {args.out}")


if __name__ == "__main__":
    main()
