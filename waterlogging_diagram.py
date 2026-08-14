#!/usr/bin/env python3
"""Render the excess-rain / waterlogging workflow (two complementary metrics)."""
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch

INK, SOFT = "#1c2b22", "#5a655c"
C = {"in": ("#eaf2ec", "#2f7d4f"), "anom": ("#eaf0f6", "#2f5d8a"),
     "soil": ("#f6ecdd", "#b0702a"), "out": ("#e9eaee", "#3a3f52")}
fig, ax = plt.subplots(figsize=(10.6, 11.2)); ax.set_xlim(0, 100); ax.set_ylim(0, 100); ax.axis("off")
ax.text(50, 98.6, "Excess-Rain / Waterlogging — two complementary wet-side metrics",
        ha="center", va="top", fontsize=12, fontweight="bold", color=INK)


def box(x, y, w, h, t, b, k, ts=9.4, bs=7.8):
    fc, ec = C[k]
    ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.5,rounding_size=1.5", fc=fc, ec=ec, lw=1.5))
    ax.text(x + w / 2, y + h - 1.9, t, ha="center", va="top", fontsize=ts, fontweight="bold", color=INK)
    if b: ax.text(x + w / 2, y + h - 4.4, b, ha="center", va="top", fontsize=bs, color=SOFT)


def arr(x1, y1, x2, y2, col=INK, lab="", dashed=False):
    ax.add_patch(FancyArrowPatch((x1, y1), (x2, y2), arrowstyle="-|>", mutation_scale=13, lw=1.4,
                                 color=col, shrinkA=2, shrinkB=2, linestyle="--" if dashed else "-"))
    if lab: ax.text((x1 + x2) / 2 + 1.2, (y1 + y2) / 2, lab, fontsize=7.0, color=col, style="italic", va="center")


# inputs
box(2, 86, 30, 10, "CHIRPS daily rain", "gauge-satellite (~5.5 km)", "in")
box(35, 86, 30, 10, "SoilGrids texture", "sand/clay/SOC → Saxton–Rawls\nFC · SAT · Ksat", "in", bs=7.4)
box(68, 86, 30, 10, "Planting + GDD stages", "onset dekad · veg/flo/grf\n· WorldCereal maize", "in", bs=7.4)

# --- two branches ---
box(3, 62, 44, 15, "① Surface / seasonal anomaly — SPI-3 wet tail",
    "3-month CHIRPS vs 1981–2020 (gamma)\nSPI-3 ≥ +1.5 = very wet\nVALIDATED (2024 floods) · anomaly-based", "anom", ts=9.0, bs=7.8)
arr(14, 86, 16, 77)

box(53, 55, 45, 22, "② Root-zone soil waterlogging — AquaCrop aeration",
    "DAILY balance: W = f(rain − ET), capped at SAT,\n"
    "water above FC drains at τ (soil Ksat)\n"
    "aer = clamp((W − thr)/(SAT − thr), 0, 1)\n"
    "thr = anaerobiosis pt (½ FC→SAT)\n"
    "idx = 100·peak CONSECUTIVE stage-weighted aer\n"
    "MODELLED · UNCALIBRATED (first-pass)", "soil", ts=9.0, bs=7.6)
arr(50, 86, 66, 77); arr(83, 86, 80, 77)

# stage weighting note
box(53, 43, 45, 9, "Stage weighting — establishment-worst",
    "veg 1.0 · flo 0.6 · grf 0.35   (Zaidi 2004; Ren 2014; Kaur 2020)", "soil", bs=7.6)
arr(75, 55, 75, 52)

# ASAP aggregation
box(20, 27, 60, 9, "③ ASAP admin aggregation (% of maize area affected)",
    "Watch ≥ 25 % · Alert ≥ 50 % · Critical ≥ 75 %   [Rembold 2019]", "out", bs=7.8)
arr(25, 62, 40, 36, lab="% wet"); arr(70, 43, 60, 36, lab="% waterlogged")

# outputs
box(8, 10, 40, 10, "Excess-wet risk (SPI-3)", "surface/seasonal · VALIDATED", "out")
box(52, 10, 42, 10, "Soil-waterlogging risk", "root-zone · MODELLED, uncalibrated", "out")
arr(34, 27, 26, 20); arr(66, 27, 74, 20)
ax.text(50, 6.5, "Two DIFFERENT hazards: SPI-3 = surface/seasonal anomalous wet · aeration = root-zone soil saturation",
        ha="center", va="top", fontsize=8.0, color=SOFT, style="italic")

fig.savefig("waterlogging_diagram.png", dpi=200, bbox_inches="tight")
fig.savefig("waterlogging_diagram.pdf", bbox_inches="tight")
print("saved waterlogging_diagram.png")
