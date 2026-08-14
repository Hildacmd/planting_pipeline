#!/usr/bin/env python3
"""Render the Risk-Monitoring and CPI pipeline flowcharts (PNG/PDF) for the methodology docs."""
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch

INK, SOFT = "#1c2b22", "#5a655c"
C = {"in": ("#eaf2ec", "#2f7d4f"), "wat": ("#eaf0f6", "#2f5d8a"), "dry": ("#f6ecdd", "#b0702a"),
     "veg": ("#e9f3e6", "#3f7d34"), "heat": ("#f7e9e6", "#b0442a"), "stage": ("#efeaf5", "#6b4e9a"),
     "out": ("#e9eaee", "#3a3f52")}


def canvas(w, h, title):
    fig, ax = plt.subplots(figsize=(w, h)); ax.set_xlim(0, 100); ax.set_ylim(0, 100); ax.axis("off")
    ax.text(50, 98.5, title, ha="center", va="top", fontsize=12.5, fontweight="bold", color=INK)
    return fig, ax


def box(ax, x, y, w, h, title, body, kind, ts=9.6, bs=7.9):
    fc, ec = C[kind]
    ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.5,rounding_size=1.5", fc=fc, ec=ec, lw=1.5))
    ax.text(x + w / 2, y + h - 2.0, title, ha="center", va="top", fontsize=ts, fontweight="bold", color=INK)
    if body:
        ax.text(x + w / 2, y + h - 4.6, body, ha="center", va="top", fontsize=bs, color=SOFT)


def arr(ax, x1, y1, x2, y2, col=INK, lab=""):
    ax.add_patch(FancyArrowPatch((x1, y1), (x2, y2), arrowstyle="-|>", mutation_scale=13, lw=1.4,
                                 color=col, shrinkA=2, shrinkB=2))
    if lab:
        ax.text((x1 + x2) / 2 + 1.5, (y1 + y2) / 2, lab, fontsize=7, color=col, style="italic", va="center")


# ============ 1. RISK MONITORING PIPELINE ============
fig, ax = canvas(10.5, 12.6, "In-Season Maize Risk-Monitoring Pipeline (ASAP-style, stage-weighted)")
# inputs
box(ax, 1, 88, 17, 8, "CHIRPS daily", "rainfall (1981–)", "in")
box(ax, 20, 88, 16, 8, "ERA5-Land", "Tmax/Tmin, ET₀", "in")
box(ax, 38, 88, 17, 8, "MODIS / S2", "NDVI", "in")
box(ax, 57, 88, 20, 8, "Planting + GDD clock", "SOS · stage dekads", "in")
box(ax, 79, 88, 19, 8, "WorldCereal", "maize mask (CAF)", "in")
# indicators row
box(ax, 1, 66, 30, 14, "WATER — FAO-56/33 balance",
    "running WRSI (0–100) · WSI dekadal stress\ndeficit (mm) · crop-failure (WRSI<50)\nstage snapshots: veg / flo / grf", "wat", bs=7.6)
box(ax, 33, 66, 20, 14, "DROUGHT — SPI-3",
    "3-mo CHIRPS, gamma\n(Wilson–Hilferty)\n≤ −1 mod · ≤ −1.5 sev", "dry", bs=7.6)
box(ax, 55, 66, 20, 14, "VEGETATION — VCI",
    "NDVI scaled to\nhistorical min–max\n(condition confirm)", "veg", bs=7.6)
box(ax, 77, 66, 21, 14, "HEAT",
    "Tmax > 33 °C\nheat-degree-dekads\nat flowering", "heat", bs=7.6)
for x in (16, 43, 65, 87):
    arr(ax, x, 88, x, 80)
# stage weighting
box(ax, 20, 51, 60, 9, "Stage weighting — FAO-33 Ky (from the GDD clock)",
    "vegetative 0.4 · flowering 1.5 (critical) · grain-fill 0.5 — anomalies weighted by stage", "stage")
for x in (16, 43, 65, 87):
    arr(ax, x, 66, 50, 60, col=C["stage"][1])
# ASAP
box(ax, 12, 34, 76, 10, "ASAP admin aggregation — % of maize area affected (CAF denominator)",
    "Watch ≥ 25%  ·  Alert ≥ 50%  ·  Critical ≥ 75%   (persistence ≥ 2 dekads)", "out")
arr(ax, 50, 51, 50, 44)
# outputs
box(ax, 20, 16, 60, 10, "Risk Monitor (L1 / L2 / L3)",
    "crop-failure (season & @ flowering) · SPI-3 drought · WRSI · deficit\nstage WRSI/WSI · CPI · yield · viability/LVPD (short rains)", "out", bs=7.6)
arr(ax, 50, 34, 50, 26)
fig.savefig("risk_monitoring_diagram.png", dpi=200, bbox_inches="tight")
fig.savefig("risk_monitoring_diagram.pdf", bbox_inches="tight"); plt.close(fig)
print("saved risk_monitoring_diagram.png")

# ============ 2. CPI PIPELINE ============
fig, ax = canvas(10.2, 11.6, "Crop Performance Index (CPI) — multi-stress multiplicative stacking")
box(ax, 2, 88, 30, 8, "Staged water balance", "per-stage AET / WR", "wat")
box(ax, 35, 88, 28, 8, "ERA5-Land Tmax", "flowering heat", "heat")
box(ax, 66, 88, 32, 8, "MODIS NDVI + climatology", "VCI", "veg")
# stresses
box(ax, 2, 68, 30, 13, "S_water  (FAO-33)",
    "Σ Ky·(1 − AETₛ/WRₛ)\nclamp [0,1]", "wat", bs=8.0)
box(ax, 35, 68, 28, 13, "S_heat",
    "HEAT_K · Σ max(0, Tmax−33)\nover flowering", "heat", bs=8.0)
box(ax, 66, 68, 32, 13, "S_veg",
    "VEG_W · (1 − VCI)\n(down-weighted)", "veg", bs=8.0)
arr(ax, 17, 88, 17, 81); arr(ax, 49, 88, 49, 81); arr(ax, 82, 88, 82, 81)
# combine
box(ax, 14, 48, 72, 11, "Multiplicative stacking (AquaCrop logic)",
    "Ya/Ym = (1 − S_water) · (1 − S_heat) · (1 − S_veg)\nCPI = 100 · Ya/Ym", "stage", bs=8.4)
for x in (17, 49, 82):
    arr(ax, x, 68, 50, 59, col=C["stage"][1])
# yield
box(ax, 8, 30, 40, 10, "Estimated yield",
    "yield (t/ha) = CPI/100 · Ym\n(Ym reference — calibrate)", "out", bs=8.0)
box(ax, 52, 30, 40, 10, "Total production",
    "yield × maize area (ha)\n250 m px = 6.25 ha", "out", bs=8.0)
arr(ax, 40, 48, 28, 40); arr(ax, 60, 48, 72, 40)
# outputs
box(ax, 22, 12, 56, 9, "Admin aggregation → Risk Monitor",
    "CPI · yield t/ha · total production · stress split (water/heat/veg)", "out", bs=7.8)
arr(ax, 28, 30, 45, 21); arr(ax, 72, 30, 55, 21)
fig.savefig("cpi_diagram.png", dpi=200, bbox_inches="tight")
fig.savefig("cpi_diagram.pdf", bbox_inches="tight"); plt.close(fig)
print("saved cpi_diagram.png")
