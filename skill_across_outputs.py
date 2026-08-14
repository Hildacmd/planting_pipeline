#!/usr/bin/env python3
"""Compare planting-window skill ACROSS different pipeline outputs (seasons / products).

Reads every `*_stats.csv` produced by stats.py (pixel-based skill per GAUL admin-1, each scored
against that product's own FEWS/FAO calendar window) and plots skill side by side, so you can
see which output is stronger. Metrics: hit-rate, bias (dekads), MAE (dekads), detection fraction.

Run: python skill_across_outputs.py --stats-dir "/path/to/planting_outputs"
"""
import argparse, os, glob, re
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

SEASON_COLOR = {"Longrains": "#2d6a9f", "Shortrains": "#e07b00"}


def label_of(fname):
    m = re.search(r"planting_([A-Za-z]+)_([a-z]+)_([A-Za-z]+)_(\d{4})_stats", fname)
    if not m: return os.path.basename(fname), "?"
    country, crop, season, year = m.groups()
    return f"{crop.title()} · {season} · {year}", season


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--stats-dir",
        default="/Users/hildamanzi/Library/CloudStorage/GoogleDrive-manzikye@gmail.com/My Drive/planting_outputs")
    ap.add_argument("--out", default="skill_across_outputs.png")
    args = ap.parse_args()

    files = sorted(glob.glob(os.path.join(args.stats_dir, "*_stats.csv")))
    files = [f for f in files if "national" not in os.path.basename(f)]
    if not files:
        print(f"No *_stats.csv in {args.stats_dir}"); return

    outs = []
    for f in files:
        df = pd.read_csv(f)
        if not {"hit", "bias", "abserr", "count"} <= set(df.columns):
            continue
        df = df[df["count"] > 0].copy()
        w = df["count"]
        outs.append(dict(
            label=label_of(f)[0], season=label_of(f)[1], df=df,
            hit=np.average(df["hit"], weights=w),
            bias=np.average(df["bias"], weights=w),
            mae=np.average(df["abserr"], weights=w),
            det=np.average(df["detected"], weights=w) if "detected" in df else np.nan,
            n=int(w.sum())))
    if not outs:
        print("No stats.csv had skill columns."); return
    print("outputs compared:")
    for o in outs:
        print(f"  {o['label']:28} hit {o['hit']*100:5.1f}%  bias {o['bias']:+.2f}  "
              f"MAE {o['mae']:.2f}  detected {o['det']*100:4.1f}%  n={o['n']:,}")

    labels = [o["label"] for o in outs]
    colors = [SEASON_COLOR.get(o["season"], "#666") for o in outs]
    x = np.arange(len(outs))

    fig, axes = plt.subplots(2, 2, figsize=(14, 10))

    # A. national hit-rate + detection per output
    ax = axes[0, 0]
    ax.bar(x - 0.2, [o["hit"] * 100 for o in outs], 0.4, color=colors, label="calendar hit-rate")
    ax.bar(x + 0.2, [o["det"] * 100 for o in outs], 0.4, color=colors, alpha=0.45,
           hatch="//", label="signal-detected %")
    ax.set_xticks(x); ax.set_xticklabels(labels, fontsize=9)
    ax.set_ylabel("%"); ax.set_ylim(0, 100)
    ax.set_title("A · Hit-rate & detection by output", fontsize=12, color="#1a3a5c")
    for i, o in enumerate(outs):
        ax.text(i - 0.2, o["hit"] * 100 + 1, f"{o['hit']*100:.0f}", ha="center", fontsize=8)
    ax.legend(fontsize=8)

    # B. bias & MAE per output
    ax = axes[0, 1]
    ax.bar(x - 0.2, [o["bias"] for o in outs], 0.4, color=colors, label="bias (dekads)")
    ax.bar(x + 0.2, [o["mae"] for o in outs], 0.4, color=colors, alpha=0.45, hatch="//",
           label="MAE (dekads)")
    ax.axhline(0, color="black", lw=0.8)
    ax.set_xticks(x); ax.set_xticklabels(labels, fontsize=9)
    ax.set_ylabel("dekads (− earlier / + later)")
    ax.set_title("B · Bias & MAE by output", fontsize=12, color="#1a3a5c")
    ax.legend(fontsize=8)

    # C. per-province hit-rate, grouped by output
    ax = axes[1, 0]
    provinces = sorted(set().union(*[set(o["df"]["ADM1_NAME"]) for o in outs]))
    xp = np.arange(len(provinces)); wd = 0.8 / len(outs)
    for k, o in enumerate(outs):
        m = dict(zip(o["df"]["ADM1_NAME"], o["df"]["hit"] * 100))
        ax.bar(xp + k * wd - 0.4 + wd / 2, [m.get(p, 0) for p in provinces], wd,
               color=SEASON_COLOR.get(o["season"], "#666"), label=o["label"])
    ax.set_xticks(xp); ax.set_xticklabels(provinces, rotation=40, ha="right", fontsize=8)
    ax.set_ylabel("hit-rate (%)"); ax.set_ylim(0, 100)
    ax.set_title("C · Hit-rate by admin-1 (GAUL), per output", fontsize=12, color="#1a3a5c")
    ax.legend(fontsize=8)

    # D. bias by province, grouped by output
    ax = axes[1, 1]
    for k, o in enumerate(outs):
        m = dict(zip(o["df"]["ADM1_NAME"], o["df"]["bias"]))
        ax.bar(xp + k * wd - 0.4 + wd / 2, [m.get(p, np.nan) for p in provinces], wd,
               color=SEASON_COLOR.get(o["season"], "#666"), label=o["label"])
    ax.axhline(0, color="black", lw=0.8)
    ax.set_xticks(xp); ax.set_xticklabels(provinces, rotation=40, ha="right", fontsize=8)
    ax.set_ylabel("bias (dekads)")
    ax.set_title("D · Bias by admin-1 (GAUL), per output", fontsize=12, color="#1a3a5c")
    ax.legend(fontsize=8)

    fig.suptitle("Planting-window skill strength across outputs — Kenya maize 2024\n"
                 "(pixel-based, each season scored vs its own FEWS/FAO calendar window)",
                 fontsize=13, color="#1a3a5c")
    fig.tight_layout(rect=[0, 0, 1, 0.94])
    fig.savefig(args.out, dpi=200, bbox_inches="tight")
    fig.savefig(args.out.replace(".png", ".pdf"), bbox_inches="tight")
    plt.close(fig)
    print(f"saved -> {args.out}  and  {args.out.replace('.png','.pdf')}")


if __name__ == "__main__":
    main()
