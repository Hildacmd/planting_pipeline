#!/usr/bin/env python3
"""Render the report's maps and charts from the shipped reduce CSVs — no Earth Engine needed.

Every admin-level CSV carries `geometry_wkt` plus the values, so the regional panels are drawn
locally and are guaranteed to show exactly what the products contain.

PLANTING DEKAD USES ONE HUE, DARK TO BRIGHT. A qualitative palette on an ordered quantity invites
the reader to see categories where there is a sequence, and dekad IS a sequence.
"""
import os, sys, warnings
import geopandas as gpd, matplotlib as mpl, numpy as np, pandas as pd
mpl.use("Agg")
import matplotlib.pyplot as plt
from shapely import wkt
warnings.filterwarnings("ignore")

H = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, H); sys.path.insert(0, f"{H}/crop_pipeline/irrigation")
FIG = os.path.join(H, "report", "figs")
os.makedirs(FIG, exist_ok=True)
from products import inventory
plt.rcParams.update({"font.size": 8, "axes.titlesize": 9, "figure.dpi": 150})

DEKAD_LBL = {1: "Jan", 4: "Feb", 7: "Mar", 10: "Apr", 13: "May", 16: "Jun",
             19: "Jul", 22: "Aug", 25: "Sep", 28: "Oct", 31: "Nov", 34: "Dec"}


def gdf(csv):
    d = pd.read_csv(csv)
    if "geometry_wkt" not in d.columns:
        return None
    g = gpd.GeoDataFrame(d, geometry=[wkt.loads(x) for x in d.geometry_wkt], crs="EPSG:4326")
    return g[~g.geometry.is_empty]


def panel(items, col, title, fname, cmap, label, vmin=None, vmax=None, pct=False):
    """One choropleth per product, laid out in a grid."""
    items = [(n, g) for n, g in items if g is not None and col in g.columns
             and g[col].notna().any()]
    if not items:
        return print(f"  [skip] {fname}: no product carries '{col}'")
    n = len(items); ncol = min(4, n); nrow = int(np.ceil(n / ncol))
    # constrained layout reserves space for the suptitle and the colorbar instead of letting them
    # sit on top of the first row; the extra height per row is for the two-line panel titles, which
    # collided with the map above them under the default spacing.
    fig, axes = plt.subplots(nrow, ncol, figsize=(3.2 * ncol, 3.6 * nrow),
                             layout="constrained")
    # country outlines have wildly different aspect ratios, so a tall map in one row can crowd the
    # title of the panel below it. h_pad buys that row separation explicitly.
    fig.get_layout_engine().set(h_pad=0.10, w_pad=0.04, hspace=0.03)
    axes = np.atleast_1d(axes).ravel()
    lo = vmin if vmin is not None else min(g[col].min() for _, g in items)
    hi = vmax if vmax is not None else max(g[col].max() for _, g in items)
    for ax, (name, g) in zip(axes, items):
        g.plot(column=col, ax=ax, cmap=cmap, vmin=lo, vmax=hi, linewidth=0.15,
               edgecolor="#888", missing_kwds={"color": "#eeeeee", "edgecolor": "#cccccc"})
        ax.set_title(name, fontsize=8, pad=7, linespacing=1.2); ax.axis("off")
    for ax in axes[n:]:
        ax.axis("off")
    sm = plt.cm.ScalarMappable(cmap=cmap, norm=plt.Normalize(vmin=lo, vmax=hi))
    cb = fig.colorbar(sm, ax=axes.tolist(), fraction=0.025, pad=0.012, shrink=0.75)
    cb.set_label(label + (" (%)" if pct else ""), fontsize=8)
    cb.ax.tick_params(labelsize=7)
    fig.suptitle(title, fontsize=11)          # constrained layout places it; no manual y
    p = os.path.join(FIG, fname)
    fig.savefig(p)                            # no bbox_inches: it overrides constrained layout
    plt.close(fig)
    print(f"  wrote {fname}  ({n} products)")


def maps_by_crop():
    inv = inventory()
    for crop in ("maize", "sorghum", "wheat", "teff", "millet"):
        items = []
        for p in [x for x in inv if x["crop"] == crop]:
            g = gdf(p["csv"])
            items.append((f"{p['country'].replace('_',' ')}\n{p['season']}", g))
        # planting dekad — ONE hue, dark to bright
        panel(items, "modal_dekad", f"{crop.capitalize()} — modal planting dekad, 2024",
              f"map_planting_{crop}.png", "viridis", "dekad of year (1-36)", 1, 36)
        panel(items, "cpi", f"{crop.capitalize()} — Crop Performance Index, 2024",
              f"map_cpi_{crop}.png", "RdYlGn", "CPI", 0, 100)
        panel(items, "fail_pct", f"{crop.capitalize()} — crop-failure risk (ASAP), 2024",
              f"map_risk_{crop}.png", "OrRd", "% of crop area in failure", 0, 100)
        panel(items, "yield_tha", f"{crop.capitalize()} — estimated yield, 2024",
              f"map_yield_{crop}.png", "YlGn", "t/ha")
        panel(items, "mean_deficit_mm", f"{crop.capitalize()} — season water deficit, 2024",
              f"map_deficit_{crop}.png", "magma_r", "mm", 0, 400)


def more_maps():
    """Tier-2 and stage layers, all from the same current CSVs."""
    inv = inventory()
    for crop in ("maize", "sorghum", "wheat", "teff", "millet"):
        items = []
        for p in [x for x in inv if x["crop"] == crop]:
            items.append((f"{p['country'].replace('_',' ')}\n{p['season']}", gdf(p["csv"])))
        panel(items, "spi3_mean", f"{crop.capitalize()} — SPI-3 at end of season, 2024",
              f"map_spi_{crop}.png", "BrBG", "SPI-3 (z)", -2.5, 2.5)
        panel(items, "fcci", f"{crop.capitalize()} — fused canopy condition (FCCI), 2024",
              f"map_fcci_{crop}.png", "YlGn", "FCCI", 0, 100)
        panel(items, "crop_viable_pct", f"{crop.capitalize()} — planted before the last viable date, 2024",
              f"map_viable_{crop}.png", "PuBuGn", "% of crop area viable", 0, 100)
        panel(items, "wrsi_flo", f"{crop.capitalize()} — WRSI at flowering (the critical stage), 2024",
              f"map_wrsiflo_{crop}.png", "RdYlBu", "WRSI", 0, 100)


def chart_stress_decomposition():
    """Which stress actually drives CPI, per product. CPI = 100(1-Sw)(1-Sh)(1-Sv)."""
    rows = []
    for p in inventory():
        d = pd.read_csv(p["csv"])
        if not {"s_water", "s_heat", "s_veg"} <= set(d.columns):
            continue
        w = d["n_px"].fillna(0) * d["crop_area_frac"].fillna(0)
        if w.sum() <= 0:
            w = pd.Series(1.0, index=d.index)
        rows.append(dict(product=f"{p['crop'][:3]} {p['country'].replace('_',' ')} {p['season']}",
                         crop=p["crop"],
                         **{k: float(np.average(d[k].fillna(0), weights=w))
                            for k in ("s_water", "s_heat", "s_veg")}))
    d = pd.DataFrame(rows).sort_values("s_water")
    fig, ax = plt.subplots(figsize=(7.4, 0.26 * len(d) + 1.2))
    y = np.arange(len(d))
    ax.barh(y, d.s_water, color="#2b8cbe", label="S_water (FAO-33 Ky-weighted)")
    ax.barh(y, d.s_heat, left=d.s_water, color="#e34a33", label="S_heat (flowering)")
    ax.barh(y, d.s_veg, left=d.s_water + d.s_heat, color="#31a354", label="S_veg (VCI/zFPAR)")
    ax.set_yticks(y); ax.set_yticklabels(d["product"], fontsize=6.5)
    ax.set_xlabel("three INDEPENDENT stresses, each 0-100, stacked for comparison\n(the total is not a percentage; CPI = 100(1-Sw)(1-Sh)(1-Sv))")
    ax.set_title("What actually drives CPI in each product\n"
                 "water stress dominates almost everywhere — which is why irrigation matters",
                 fontsize=9)
    ax.legend(fontsize=7, loc="lower right", frameon=False)
    fig.tight_layout(); fig.savefig(os.path.join(FIG, "chart_stress_decomposition.png"))
    plt.close(fig); print("  wrote chart_stress_decomposition.png")


def chart_planting_windows():
    """p10-p90 planting spread per product, from the current reduce CSVs."""
    rows = []
    for p in inventory():
        d = pd.read_csv(p["csv"])
        if not {"p10", "p50", "p90"} <= set(d.columns) or d.p50.isna().all():
            continue
        rows.append(dict(product=f"{p['crop'][:3]} {p['country'].replace('_',' ')} {p['season']}",
                         crop=p["crop"], p10=d.p10.median(), p50=d.p50.median(), p90=d.p90.median()))
    d = pd.DataFrame(rows).sort_values("p50")
    col = {"maize": "#2c7fb8", "sorghum": "#d95f0e", "wheat": "#756bb1",
           "teff": "#31a354", "millet": "#c51b8a"}
    fig, ax = plt.subplots(figsize=(7.4, 0.26 * len(d) + 1.2))
    y = np.arange(len(d))
    for i, r in enumerate(d.itertuples()):
        ax.plot([r.p10, r.p90], [i, i], color=col[r.crop], lw=3, alpha=0.5, solid_capstyle="round")
        ax.plot(r.p50, i, "o", color=col[r.crop], ms=4)
    ax.set_yticks(y); ax.set_yticklabels(d["product"], fontsize=6.5)
    ax.set_xlim(0, 37); ax.set_xticks(sorted(DEKAD_LBL)); ax.set_xticklabels(
        [DEKAD_LBL[k] for k in sorted(DEKAD_LBL)], fontsize=7)
    ax.set_xlabel("dekad of year")
    ax.set_title("Detected planting window per product — median p10 to p90, dot = p50",
                 fontsize=9)
    from matplotlib.patches import Patch
    ax.legend(handles=[Patch(color=v, label=k) for k, v in col.items()], fontsize=7,
              loc="lower right", frameon=False)
    fig.tight_layout(); fig.savefig(os.path.join(FIG, "chart_planting_windows.png"))
    plt.close(fig); print("  wrote chart_planting_windows.png")


def chart_coverage():
    """The country x crop matrix the crop-type mask permits, and what was built."""
    import ctm_mask as CTM
    from crop_coverage import is_dropped
    inv = inventory()
    built = {(p["country"], p["crop"]) for p in inv}
    crops = ["maize", "sorghum", "wheat", "teff", "millet"]
    cos = sorted(CTM.PROFILES)
    M = np.zeros((len(cos), len(crops)))
    for i, co in enumerate(cos):
        for j, cr in enumerate(crops):
            M[i, j] = (3 if (co, cr) in built else
                       1 if is_dropped(cr, co) else
                       2 if CTM.has(co, cr) else 0)
    fig, ax = plt.subplots(figsize=(5.2, 0.34 * len(cos) + 1.6))
    cm = mpl.colors.ListedColormap(["#f0f0f0", "#fdae6b", "#bdd7e7", "#2171b5"])
    ax.imshow(M, cmap=cm, vmin=0, vmax=3, aspect="auto")
    ax.set_xticks(range(len(crops))); ax.set_xticklabels(crops, fontsize=8)
    ax.set_yticks(range(len(cos))); ax.set_yticklabels([c.replace("_", " ") for c in cos], fontsize=8)
    for i in range(len(cos)):
        for j in range(len(crops)):
            t = {0: "", 1: "dropped", 2: "mask only", 3: "built"}[int(M[i, j])]
            ax.text(j, i, t, ha="center", va="center", fontsize=6,
                    color="white" if M[i, j] == 3 else "#333")
    ax.set_title("What the crop-type mask permits, and what was built\n"
                 "the mask decides which crops run in which country", fontsize=9)
    fig.tight_layout(); fig.savefig(os.path.join(FIG, "chart_coverage.png"))
    plt.close(fig); print("  wrote chart_coverage.png")


def chart_ym_skill():
    import re
    rows = []
    for m in re.finditer(r'#\s+(\w[\w ]+?)\s+(Long rains|Short rains|Meher|Season A|1st rains)\s+'
                         r'([\d.]+)\s+\d{4}-\d{2},\s*n(\d+)\s+[\d.]+ vs [\d.]+\s+r\s+(-?[\d.]+)',
                         open(f"{H}/src/cpi.py").read()):
        rows.append(("maize", f"{m.group(1).strip()} {m.group(2)}", float(m.group(5))))
    for crop, f in (("sorghum", "sorghum_pipeline/sorghum_params.py"),
                    ("wheat", "crop_pipeline/params/wheat.py"),
                    ("teff", "crop_pipeline/params/teff.py"),
                    ("millet", "crop_pipeline/params/millet.py")):
        blk = open(f"{H}/{f}").read().split("YM_CAL_CTM")[0]
        for m in re.finditer(r'\("([^"]+)",\s*"([^"]+)"\):\s*[\d.]+,?\s*#.*?\br\s+(-?[\d.]+)', blk):
            rows.append((crop, f"{m.group(1)} {m.group(2)}", float(m.group(3))))
    d = pd.DataFrame(rows, columns=["crop", "product", "r"]).sort_values("r")
    col = {"maize": "#2c7fb8", "sorghum": "#d95f0e", "wheat": "#756bb1",
           "teff": "#31a354", "millet": "#c51b8a"}
    fig, ax = plt.subplots(figsize=(7.2, 0.26 * len(d) + 1.2))
    ax.barh(range(len(d)), d.r, color=[col[c] for c in d.crop], height=0.72)
    ax.set_yticks(range(len(d))); ax.set_yticklabels(d["product"], fontsize=7)
    ax.axvline(0, color="k", lw=0.8); ax.axvline(0.4, color="#666", lw=0.8, ls="--")
    ax.set_xlabel("r (predicted vs reported yield)")
    ax.set_title("Yield-pattern skill of every fitted ceiling\n"
                 "left of 0 = the model ranks units BACKWARDS; dashed line = usable (r = 0.4)",
                 fontsize=9)
    from matplotlib.patches import Patch
    ax.legend(handles=[Patch(color=v, label=k) for k, v in col.items()],
              fontsize=7, loc="lower right", frameon=False)
    fig.tight_layout(); fig.savefig(os.path.join(FIG, "chart_ym_skill.png")); plt.close(fig)
    print("  wrote chart_ym_skill.png")


def chart_dmp():
    fs = [(os.path.join(H, "maize_ctm", f"dmp_rank_test_{s}.csv"), s) for s in ("anti", "control")]
    fs = [(f, s) for f, s in fs if os.path.exists(f)]
    if not fs:
        f0 = os.path.join(H, "maize_ctm", "dmp_rank_test.csv")
        if os.path.exists(f0):
            fs = [(f0, "anti")]
    if not fs:
        return print("  [skip] chart_dmp: no results")
    fig, axes = plt.subplots(1, len(fs), figsize=(5.2 * len(fs), 3.6), squeeze=False)
    for ax, (f, s) in zip(axes[0], fs):
        d = pd.read_csv(f)
        y = np.arange(len(d))
        ax.errorbar(d.d_rho, y, xerr=[d.d_rho - d.ci_lo, d.ci_hi - d.d_rho],
                    fmt="o", ms=4, color="#2c7fb8", ecolor="#9ecae1", capsize=2)
        ax.axvline(0, color="k", lw=0.8)
        ax.set_yticks(y); ax.set_yticklabels(d["product"], fontsize=7)
        ax.set_xlabel(r"$\Delta\rho$  (DMP − CPI)")
        ax.set_title(("Products where CPI ranks BACKWARDS" if s == "anti"
                      else "Control: products where CPI already ranks"), fontsize=9)
    fig.suptitle("DMP as a ranking covariate, paired bootstrap 95 % CI", fontsize=10)
    fig.tight_layout(); fig.savefig(os.path.join(FIG, "chart_dmp_rank.png")); plt.close(fig)
    print("  wrote chart_dmp_rank.png")


def chart_irrigation():
    f = os.path.join(H, "crop_pipeline", "irrigation", "spam2020_irrigated_admin1.csv")
    if not os.path.exists(f):
        return print("  [skip] chart_irrigation")
    d = pd.read_csv(f)
    d = d[d.area_all_ha >= 1000].nlargest(22, "irrigated_pct")
    d["lab"] = d.country.str.replace("_", " ") + " " + d.crop + " — " + d.admin1
    fig, ax = plt.subplots(figsize=(7.2, 0.28 * len(d) + 1.0))
    ax.barh(range(len(d)), d.irrigated_pct[::-1], color="#3182bd", height=0.72)
    ax.set_yticks(range(len(d))); ax.set_yticklabels(d.lab[::-1], fontsize=7)
    ax.axvline(30, color="#d95f0e", ls="--", lw=1)
    ax.set_xlabel("% of the crop's physical area under irrigation (SPAM 2020)")
    ax.set_title("Where the rainfed water balance is reading irrigation demand as crop stress\n"
                 "dashed line = the 30 % threshold at which a unit counts as compromised",
                 fontsize=9)
    fig.tight_layout(); fig.savefig(os.path.join(FIG, "chart_irrigation.png")); plt.close(fig)
    print("  wrote chart_irrigation.png")


def targeted_pre(d):
    return (d["sample"].str.startswith("targeted") if "sample" in d.columns
            else pd.Series(False, index=d.index))


def chart_dmp_kenya():
    """The Kenya DMP assessment: ranking skill, and the implied harvest index that limits it."""
    p = os.path.join(H, "Cropyield-Data", "dmp_score_summary.csv")
    if not os.path.exists(p):
        return print("  [skip] chart_dmp_kenya: run dmp_score.py first")
    d = pd.read_csv(p)
    fig, (a1, a2) = plt.subplots(1, 2, figsize=(10.2, 3.9))
    y = np.arange(len(d)); h = 0.36
    a1.barh(y + h / 2, d.dmp_rho, h, color="#2c7fb8", label="DMP")
    a1.barh(y - h / 2, d.cpi_rho, h, color="#bdbdbd", label="CPI")
    a1.axvline(0, color="k", lw=0.8)
    lbl = [f + ("  (targeted)" if t else "") for f, t in zip(d.frame, targeted_pre(d))]
    a1.set_yticks(y); a1.set_yticklabels(lbl, fontsize=8)
    a1.set_xlabel(r"Spearman $\rho$ against observed yield")
    a1.set_title("Ranking skill: DMP vs CPI", fontsize=9)
    a1.legend(fontsize=7, frameon=False, loc="lower right")
    targeted = d["sample"].str.startswith("targeted") if "sample" in d.columns else \
        pd.Series(False, index=d.index)
    a2.barh(y, d.hi_implied, 0.6,
            color=np.where(targeted, "#bdbdbd",
                           np.where((d.hi_implied >= 0.30) & (d.hi_implied <= 0.55),
                                    "#31a354", "#d95f0e")))
    a2.axvspan(0.30, 0.55, color="#31a354", alpha=0.12)
    a2.axvline(0.45, color="k", ls="--", lw=0.9)
    a2.set_yticks(y); a2.set_yticklabels([])
    a2.set_xlabel("harvest index implied by the observations")
    a2.set_title("Implied harvest index\n"
                 "green band = agronomic 0.30-0.55; GREY = targeted ASAL drought sample,\n"
                 "where a near-zero harvest forces the implied HI down whatever the model does",
                 fontsize=8.5)
    for i, (hi, ov) in enumerate(zip(d.hi_implied, d.overpred)):
        a2.text(max(hi, 0.02) + 0.012, i, f"{ov:.1f}x", va="center", fontsize=7.5)
    fig.suptitle("Kenya DMP assessment - MODIS GPP stand-in for Copernicus DMP", fontsize=10)
    fig.tight_layout(); fig.savefig(os.path.join(FIG, "chart_dmp_kenya.png")); plt.close(fig)
    print("  wrote chart_dmp_kenya.png")


def chart_dmp_levels():
    """Implied harvest index across every representative admin-scale frame - the level test."""
    p = os.path.join(H, "Cropyield-Data", "dmp_levels_summary.csv")
    if not os.path.exists(p):
        return print("  [skip] chart_dmp_levels: run dmp_levels.py first")
    d = pd.read_csv(p).sort_values("hi_implied")
    lab = d.crop.str[:3] + " " + d["product"].str.replace("_", " ")
    fig, (a1, a2) = plt.subplots(1, 2, figsize=(10.4, 0.34 * len(d) + 2.0),
                                 gridspec_kw={"width_ratios": [1.25, 1]})
    y = np.arange(len(d))
    a1.axvspan(0.30, 0.55, color="#31a354", alpha=0.14, label="agronomic 0.30-0.55")
    a1.barh(y, d.hi_implied, 0.66, color=np.where(d.hi_in_range, "#31a354", "#d95f0e"))
    a1.axvline(0.45, color="k", ls="--", lw=0.9, label="0.45 assumed")
    a1.set_yticks(y); a1.set_yticklabels(lab, fontsize=7.5)
    a1.set_xlabel("harvest index implied by observed yield")
    a1.set_title(f"Implied HI: inside the band in only "
                 f"{int(d.hi_in_range.sum())} of {len(d)} frames", fontsize=9)
    a1.legend(fontsize=7, frameon=False, loc="lower right")
    a2.barh(y, d.overpred, 0.66, color="#756bb1")
    a2.axvline(1.0, color="k", lw=0.9)
    a2.set_yticks(y); a2.set_yticklabels([])
    a2.set_xlabel("DMP-derived yield / observed")
    a2.set_title(f"Over-prediction: median {d.overpred.median():.2f}x", fontsize=9)
    fig.suptitle("Can DMP carry a level? Every representative admin-scale frame", fontsize=10)
    fig.tight_layout(); fig.savefig(os.path.join(FIG, "chart_dmp_levels.png")); plt.close(fig)
    print("  wrote chart_dmp_levels.png")


def chart_mask():
    f = os.path.join(H, "maize_ctm", "mask_comparison.csv")
    if not os.path.exists(f):
        return print("  [skip] chart_mask")
    d = pd.read_csv(f).dropna(subset=["rho_rank"])
    fig, (a1, a2) = plt.subplots(1, 2, figsize=(9.6, 3.6))
    y = np.arange(len(d))
    a1.barh(y, d.rho_rank, color=np.where(d.rho_rank < 0.8, "#d95f0e", "#2c7fb8"), height=0.7)
    a1.axvline(0.8, color="k", ls="--", lw=0.9)
    a1.set_yticks(y); a1.set_yticklabels(d["product"], fontsize=7)
    a1.set_xlabel(r"Spearman $\rho$ between the two admin rankings")
    a1.set_title("Does the mask re-rank the units?\nleft of the line = yes", fontsize=9)
    a2.barh(y, d.delta_mean, color="#756bb1", height=0.7)
    a2.axvline(0, color="k", lw=0.8)
    a2.set_yticks(y); a2.set_yticklabels([]); a2.set_xlabel("mean change in CPI")
    a2.set_title("and does it move the level?", fontsize=9)
    fig.suptitle("ESA WorldCereal vs ICPAC crop-type mask — same balance, same parameters",
                 fontsize=10)
    fig.tight_layout(); fig.savefig(os.path.join(FIG, "chart_mask_comparison.png")); plt.close(fig)
    print("  wrote chart_mask_comparison.png")


if __name__ == "__main__":
    print("maps by crop:"); maps_by_crop(); more_maps()
    print("charts:"); chart_coverage(); chart_planting_windows()
    chart_stress_decomposition(); chart_ym_skill(); chart_dmp()
    chart_irrigation(); chart_mask(); chart_dmp_kenya(); chart_dmp_levels()
    print(f"\nfigures in {FIG}")
