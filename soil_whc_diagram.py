#!/usr/bin/env python3
"""Render the soil water-holding-capacity workflow (SoilGrids texture + Saxton-Rawls -> WHC)."""
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch

INK, SOFT = "#1c2b22", "#5a655c"
C = {"in": ("#eaf2ec", "#2f7d4f"), "ptf": ("#eaf0f6", "#2f5d8a"),
     "der": ("#f6ecdd", "#b0702a"), "out": ("#e9eaee", "#3a3f52")}
fig, ax = plt.subplots(figsize=(10.4, 10.6)); ax.set_xlim(0, 100); ax.set_ylim(0, 100); ax.axis("off")
ax.text(50, 98.5, "Soil Water-Holding Capacity — SoilGrids texture + Saxton–Rawls (2006) pedotransfer",
        ha="center", va="top", fontsize=11.6, fontweight="bold", color=INK)


def box(x, y, w, h, t, b, k, ts=9.4, bs=7.8):
    fc, ec = C[k]
    ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.5,rounding_size=1.5", fc=fc, ec=ec, lw=1.5))
    ax.text(x + w / 2, y + h - 1.9, t, ha="center", va="top", fontsize=ts, fontweight="bold", color=INK)
    if b: ax.text(x + w / 2, y + h - 4.3, b, ha="center", va="top", fontsize=bs, color=SOFT)


def arr(x1, y1, x2, y2, col=INK, lab="", dashed=False):
    ax.add_patch(FancyArrowPatch((x1, y1), (x2, y2), arrowstyle="-|>", mutation_scale=13, lw=1.4,
                                 color=col, shrinkA=2, shrinkB=2, linestyle="--" if dashed else "-"))
    if lab: ax.text((x1 + x2) / 2 + 1.2, (y1 + y2) / 2, lab, fontsize=7.0, color=col, style="italic", va="center")


# --- inputs: ISRIC SoilGrids MEASURED properties (hosted on GEE, read server-side) ---
box(2, 86, 29, 10, "Sand  (g/kg)", "SoilGrids 2.0\nsand_mean · 6 depths", "in")
box(35.5, 86, 29, 10, "Clay  (g/kg)", "SoilGrids 2.0\nclay_mean · 6 depths", "in")
box(69, 86, 29, 10, "SOC  (dg/kg)", "SoilGrids 2.0\nsoc_mean → OM% ×1.724", "in")
ax.text(50, 84.3, "ISRIC-measured texture — read from GEE (projects/soilgrids-isric/…), never copied to disk",
        ha="center", va="top", fontsize=7.3, color=SOFT, style="italic")

# --- Saxton-Rawls pedotransfer ---
box(12, 63, 76, 15, "① Saxton–Rawls (2006) pedotransfer  —  DERIVED here, not downloaded",
    "θ₁₅₀₀ (wilting)  = f(Sa, Cl, OM)   → WP\n"
    "θ₃₃   (field cap) = g(Sa, Cl, OM)  → FC\n"
    "(ISRIC publishes no ready FC/WP layer — standard practice is to derive them from texture)",
    "ptf", ts=9.2, bs=8.0)
arr(16, 86, 22, 78); arr(50, 86, 50, 78); arr(84, 86, 78, 78)

# --- AWC ---
box(20, 46, 60, 9, "② Available water per layer",
    "AWC(z) = FC(z) − WP(z)   [vol fraction]", "der", bs=8.2)
arr(50, 63, 50, 55)

# --- depth integration ---
box(20, 29, 60, 9, "③ Root-zone integration",
    "WHC (mm) = Σ_layers AWC(z) · thickness(z),  clipped at FAO-56 rooting depth (maize 1.0 m)", "der", bs=7.8)
arr(50, 46, 50, 38)

# --- output + static note ---
box(8, 10, 45, 10, "WHC (mm) — spatial", "into the WRSI/WSI/CPI\nwater balance (SW capped at WHC)", "out")
box(58, 10, 36, 10, "STATIC → materialize once", "export_whc_to_asset →\nwhc_asset; no per-run recompute", "out", bs=7.6)
arr(38, 29, 30, 20); arr(62, 29, 74, 20, dashed=True, lab="one-time")
arr(53, 15, 58, 15, dashed=True)

fig.savefig("soil_whc_diagram.png", dpi=200, bbox_inches="tight")
fig.savefig("soil_whc_diagram.pdf", bbox_inches="tight")
print("saved soil_whc_diagram.png")
