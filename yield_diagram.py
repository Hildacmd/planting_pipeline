#!/usr/bin/env python3
"""Render the yield-estimation workflow flowchart (PNG/PDF)."""
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch

INK, SOFT = "#1c2b22", "#5a655c"
C = {"in": ("#eaf2ec", "#2f7d4f"), "core": ("#eaf0f6", "#2f5d8a"), "cal": ("#f6ecdd", "#b0702a"),
     "out": ("#e9eaee", "#3a3f52")}
fig, ax = plt.subplots(figsize=(10.2, 11.0)); ax.set_xlim(0, 100); ax.set_ylim(0, 100); ax.axis("off")
ax.text(50, 98.5, "Maize Yield-Estimation Workflow — CPI × potential yield, area-scaled, calibrated",
        ha="center", va="top", fontsize=12, fontweight="bold", color=INK)


def box(x, y, w, h, t, b, k, ts=9.6, bs=8.0):
    fc, ec = C[k]
    ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.5,rounding_size=1.5", fc=fc, ec=ec, lw=1.5))
    ax.text(x + w / 2, y + h - 2.0, t, ha="center", va="top", fontsize=ts, fontweight="bold", color=INK)
    if b: ax.text(x + w / 2, y + h - 4.6, b, ha="center", va="top", fontsize=bs, color=SOFT)


def arr(x1, y1, x2, y2, col=INK, lab="", dashed=False):
    ax.add_patch(FancyArrowPatch((x1, y1), (x2, y2), arrowstyle="-|>", mutation_scale=13, lw=1.4,
                                 color=col, shrinkA=2, shrinkB=2, linestyle="--" if dashed else "-"))
    if lab: ax.text((x1 + x2) / 2 + 1.5, (y1 + y2) / 2, lab, fontsize=7.2, color=col, style="italic", va="center")


# inputs
box(1, 86, 30, 9, "CPI  (relative yield)", "multi-stress = Ya/Ym\nwater × heat × vegetation", "in", bs=7.6)
box(34, 86, 31, 9, "Ym  (potential yield)", "GYGA water-limited / agronomic\nby variety & zone", "in", bs=7.6)
box(68, 86, 30, 9, "Harvested area", "maize mask × pixel\n(250 m px = 6.25 ha)", "in", bs=7.6)
# actual yield
box(14, 66, 46, 10, "① Actual yield per hectare",
    "Ya (t/ha) = (CPI / 100) · Ym\n= (1 − ΣₛKy(1−AETₛ/WRₛ))(1−S_heat)(1−S_veg) · Ym", "core", bs=8.0)
arr(16, 86, 30, 76); arr(49, 86, 44, 76)
# total production
box(20, 47, 40, 9, "② Total production",
    "P (t) = Σ_pixels  Ya · pixel_area_ha", "core", bs=8.2)
arr(37, 66, 40, 56); arr(83, 86, 55, 56, lab="area")
# calibration
box(66, 47, 32, 20, "③ Calibration & validation",
    "regress estimated vs OBSERVED\nyields (KALRO · FAO/GIEWS ·\nHarvestStat) → tune Ym and\nthe stress parameters\n(Ky, HEAT_K, VEG_W)", "cal", bs=7.7)
arr(60, 68, 66, 63, lab="")
arr(74, 47, 45, 71, col=C["cal"][1], dashed=True, lab="feedback")
# admin
box(18, 28, 44, 9, "④ Admin aggregation (L1/L2/L3)",
    "median yield (t/ha) · Σ production (t)", "out", bs=8.0)
arr(40, 47, 40, 37)
# outputs
box(10, 10, 34, 9, "Yield map (t/ha)", "per admin unit", "out")
box(50, 10, 34, 9, "Production (t / kt)", "per admin unit", "out")
arr(34, 28, 27, 19); arr(47, 28, 67, 19)
fig.savefig("yield_estimation_diagram.png", dpi=200, bbox_inches="tight")
fig.savefig("yield_estimation_diagram.pdf", bbox_inches="tight")
print("saved yield_estimation_diagram.png")
