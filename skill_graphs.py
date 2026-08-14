#!/usr/bin/env python3
"""Skill-strength graphs from the admin skill CSVs (county/constituency/ward).

Panels:
  A. County hit-rate, ranked (how well each county matches the FEWS/FAO calendar window)
  B. Ward-level hit-rate distribution (histogram) — spread of skill across the maize belt
  C. Bias distribution (dekads early/late vs window centre)
  D. Hit-rate vs bias scatter (county), point size ~ maize area

Run: python skill_graphs.py --product planting_Kenya_maize_Longrains_2024 --win 8 12
"""
import argparse, os
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.cm import ScalarMappable
from matplotlib.colors import Normalize


def load(product, level):
    p = f"{product}_L{level}_skill.csv"
    return pd.read_csv(p) if os.path.exists(p) else None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--product", default="planting_Kenya_maize_Longrains_2024")
    ap.add_argument("--win", type=int, nargs=2, default=[8, 12])
    ap.add_argument("--out", default=None)
    args = ap.parse_args()
    ws, we = args.win

    L1, L2, L3 = load(args.product, 1), load(args.product, 2), load(args.product, 3)
    if L1 is None:
        print("Need at least the level-1 skill CSV (run admin_skill_local.py first)."); return
    finest = L3 if L3 is not None else (L2 if L2 is not None else L1)

    # national pixel-weighted skill
    nat_hit = np.average(finest["hit_rate"], weights=finest["n_px"])
    nat_bias = np.average(finest["bias_dek"], weights=finest["n_px"])
    nat_mae = np.average(finest["mae_dek"], weights=finest["n_px"])

    fig, axes = plt.subplots(2, 2, figsize=(14, 10))
    cmap = plt.get_cmap("RdYlGn")

    # A. ranked county hit-rate
    ax = axes[0, 0]
    d = L1.sort_values("hit_rate")
    colors = cmap(Normalize(0, 1)(d["hit_rate"]))
    ax.barh(d["name"], d["hit_rate"] * 100, color=colors, edgecolor="#444", linewidth=0.3)
    ax.set_title("A · County calendar hit-rate (ranked)", fontsize=12, color="#1a3a5c")
    ax.set_xlabel("% maize pixels planting inside calendar window"); ax.set_xlim(0, 100)
    ax.tick_params(axis="y", labelsize=6)
    ax.axvline(nat_hit * 100, ls="--", color="black", lw=1)
    ax.text(nat_hit * 100 - 1, 0.5, f"national {nat_hit*100:.0f}%", rotation=90,
            fontsize=7, ha="right", va="bottom")

    # B. ward-level hit-rate distribution
    ax = axes[0, 1]
    lvl_name = {"1": "county", "2": "constituency", "3": "ward"}[str(finest is L3 and 3 or (finest is L2 and 2 or 1))]
    ax.hist(finest["hit_rate"] * 100, bins=20, color="#2d6a9f", edgecolor="white")
    ax.axvline(nat_hit * 100, ls="--", color="#c0392b", lw=1.2, label=f"national {nat_hit*100:.0f}%")
    ax.set_title(f"B · Hit-rate distribution across {lvl_name}s (n={len(finest)})",
                 fontsize=12, color="#1a3a5c")
    ax.set_xlabel("calendar hit-rate (%)"); ax.set_ylabel(f"number of {lvl_name}s"); ax.legend()

    # C. bias distribution
    ax = axes[1, 0]
    ax.hist(finest["bias_dek"], bins=25, color="#8e7cc3", edgecolor="white")
    ax.axvline(0, color="black", lw=1, label="on calendar centre")
    ax.axvline(nat_bias, ls="--", color="#c0392b", lw=1.2, label=f"national bias {nat_bias:+.2f}")
    ax.set_title(f"C · Planting-date bias ({lvl_name}s)", fontsize=12, color="#1a3a5c")
    ax.set_xlabel("bias (dekads):  − earlier   |   later +"); ax.set_ylabel(f"number of {lvl_name}s"); ax.legend()

    # D. hit-rate vs bias scatter (county), size ~ area
    ax = axes[1, 1]
    sizes = 20 + 380 * (L1["n_px"] / L1["n_px"].max())
    sc = ax.scatter(L1["bias_dek"], L1["hit_rate"] * 100, s=sizes,
                    c=L1["hit_rate"], cmap=cmap, vmin=0, vmax=1, edgecolor="#333", linewidth=0.4, alpha=0.85)
    for _, r in L1.sort_values("hit_rate").head(4).iterrows():
        ax.annotate(r["name"], (r["bias_dek"], r["hit_rate"] * 100), fontsize=7,
                    xytext=(3, 3), textcoords="offset points")
    ax.axvline(0, color="grey", lw=0.7)
    ax.set_title("D · County hit-rate vs bias (size ~ maize area)", fontsize=12, color="#1a3a5c")
    ax.set_xlabel("bias (dekads)"); ax.set_ylabel("hit-rate (%)")

    fig.suptitle(f"Planting-window skill vs FEWS/FAO calendar (dekads {ws}–{we}) — "
                 f"{args.product.replace('_',' ')}\n"
                 f"national: hit {nat_hit*100:.1f}%   bias {nat_bias:+.2f} dek   MAE {nat_mae:.2f} dek",
                 fontsize=13, color="#1a3a5c")
    fig.tight_layout(rect=[0, 0, 1, 0.94])
    out = args.out or f"{args.product}_skill_graphs.png"
    fig.savefig(out, dpi=200, bbox_inches="tight")
    fig.savefig(out.replace(".png", ".pdf"), bbox_inches="tight")
    plt.close(fig)
    print(f"national skill: hit {nat_hit*100:.1f}%  bias {nat_bias:+.2f}  MAE {nat_mae:.2f}")
    print(f"saved -> {out}  and  {out.replace('.png','.pdf')}")


if __name__ == "__main__":
    main()
