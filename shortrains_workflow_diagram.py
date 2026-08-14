#!/usr/bin/env python3
"""Render the short-rains rainfall-anchored + LVPD + year-wrap-GDD pipeline as a flowchart PNG/PDF."""
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch

INK, SOFT = "#1c2b22", "#5a655c"
C_IN, C_INB = "#eaf2ec", "#2f7d4f"       # inputs (green)
C_ST, C_STB = "#eaf0f6", "#2f5d8a"       # stages (blue)
C_LV, C_LVB = "#f6ecdd", "#b0702a"       # LVPD/gate (amber)
C_GD, C_GDB = "#efeaf5", "#6b4e9a"       # GDD clock (purple)
C_OUT, C_OUTB = "#e9eaee", "#3a3f52"     # outputs (slate)

fig, ax = plt.subplots(figsize=(9.6, 12.4))
ax.set_xlim(0, 100); ax.set_ylim(0, 130); ax.axis("off")


def box(x, y, w, h, title, body, fill, edge, tsize=10.5, bsize=8.6):
    ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.6,rounding_size=1.6",
                                fc=fill, ec=edge, lw=1.6))
    ax.text(x + w/2, y + h - 2.4, title, ha="center", va="top", fontsize=tsize,
            fontweight="bold", color=INK)
    if body:
        ax.text(x + w/2, y + h - 5.6, body, ha="center", va="top", fontsize=bsize, color=SOFT)


def arrow(x1, y1, x2, y2, label="", col=INK):
    ax.add_patch(FancyArrowPatch((x1, y1), (x2, y2), arrowstyle="-|>", mutation_scale=15,
                                 lw=1.5, color=col, shrinkA=2, shrinkB=2))
    if label:
        ax.text((x1+x2)/2 + 2.5, (y1+y2)/2, label, ha="left", va="center", fontsize=7.8,
                color=col, style="italic")


ax.text(50, 128, "Short-Rains Planting Pipeline (Kenya maize) — rainfall-anchored · LVPD-gated · year-wrapping GDD",
        ha="center", va="top", fontsize=12.5, fontweight="bold", color=INK)

# --- Inputs row ---
box(1,   116, 23, 8, "CHIRPS 44-yr LTN", "1981–2024 climatology", C_IN, C_INB, tsize=9.4, bsize=8.0)
box(25.5,116, 17, 8, "CHIRPS 2024", "actual-year rain", C_IN, C_INB, tsize=9.4, bsize=8.0)
box(44,  116, 26, 8, "ERA5-Land T + DEM", "temperature · lapse", C_IN, C_INB, tsize=9.4, bsize=8.0)
box(71.5,116, 27, 8, "AEZ + maize mask", "early/med/late · WorldCereal", C_IN, C_INB, tsize=9.4, bsize=7.6)

# --- Stage 1: onset ---
box(14, 100, 72, 9, "① FEWS onset rule",
    "P₀ ≥ 25 mm  AND  P₁+P₂ ≥ 20 mm   AND   P / PET ≥ 0.5", C_ST, C_STB)
arrow(12, 116, 30, 109)   # LTN -> onset
arrow(34, 116, 45, 109)   # 2024 -> onset

# --- Stage 2: establish (rainfall-anchored) ---
box(10, 84, 80, 10, "② Establish planting window — rainfall-anchored",
    "planting = 2024 onset,  else 44-yr LTN normal  →  FULL COVERAGE (96%)\n"
    "green-up NOT used (612 px, ~1.9 dekads early-biased)", C_ST, C_STB, bsize=8.2)
arrow(50, 100, 50, 94)

# --- Stage 3: LVPD viability gate ---
box(6, 64, 88, 12, "③ LVPD viability gate — variety-adaptive WRSI",
    "keep pixel IF  early-variety (~90 d) maize planted at onset  →  WRSI ≥ 50\n"
    "early = shortest-that-fits → most permissive → never removes a viable pixel\n"
    "outputs: viable planting (99.3%) · LVPD dekad · non-viable / dry-zone flag (0.7%)",
    C_LV, C_LVB, bsize=8.0)
arrow(50, 84, 50, 76)
arrow(57, 116, 80, 76, col=C_LVB)   # ERA5/DEM+soil feed WRSI (right side)

# --- Stage 4: GDD clock (branch) ---
box(6, 44, 88, 12, "④ GDD phenology clock — rainfall anchor · year-wrapping",
    "anchor = onset + 1 dekad (emergence) · ERA5 T (DEM-lapsed) · AEZ-seeded GDD_maturity\n"
    "accumulate ACROSS the year boundary (dekads > 36)\n"
    "peak-veg → flowering (~Jan) → grain-fill → maturity (~Mar, next year)",
    C_GD, C_GDB, bsize=8.0)
arrow(50, 64, 50, 56)
arrow(85, 116, 86, 56, col=C_GDB)   # AEZ feeds GDD

# --- Outputs ---
box(10, 24, 80, 11, "⑤ Admin aggregation (L1 / L2 / L3)",
    "planting dekad · LVPD dekad · viability % · SPI-3 drought · WRSI · CAF · flowering/maturity\n"
    "median for dekads · mean for fractions", C_OUT, C_OUTB, bsize=8.2)
arrow(50, 44, 50, 35)

box(16, 8, 30, 10, "Interactive apps", "Planting Explorer · Risk Monitor", C_OUT, C_OUTB)
box(54, 8, 30, 10, "QGIS / WKT + PDF", "pixel & admin polygons", C_OUT, C_OUTB)
arrow(40, 24, 31, 18); arrow(60, 24, 69, 18)

fig.tight_layout()
fig.savefig("WORKFLOW_SHORTRAINS_diagram.png", dpi=200, bbox_inches="tight")
fig.savefig("WORKFLOW_SHORTRAINS_diagram.pdf", bbox_inches="tight")
print("saved WORKFLOW_SHORTRAINS_diagram.png / .pdf")
