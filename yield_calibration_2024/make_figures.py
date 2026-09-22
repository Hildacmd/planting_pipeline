"""Figures for YIELD_CALIBRATION_2024: predicted vs reported yield per country, and test error before/after."""
import os, numpy as np, pandas as pd, matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
H = os.path.dirname(os.path.abspath(__file__)); CY = os.path.join(os.path.dirname(H), "Cropyield-Data")
plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 8, "axes.spines.top": False, "axes.spines.right": False})
loc = pd.read_csv(os.path.join(CY, "ym_calibration_local_units.csv"))
panels = []
for f, t, lvl in [("app:ke_long", "Kenya · Long rains", "counties"), ("app:ke_short", "Kenya · Short rains", "counties"),
                  ("app:et_meher", "Ethiopia · Meher", "zones"), ("Rwanda_SeasonA", "Rwanda · Season A", "districts"),
                  ("Burundi_SeasonA", "Burundi · Season A", "provinces"), ("Somalia_Gu", "Somalia · Gu", "districts"),
                  ("Uganda_1strains", "Uganda · 1st rains (provisional)", "districts")]:
    x = loc[loc.file == f]; panels.append((t, x.obs, x.pred_cal, x.pred_default, lvl))
fig, axs = plt.subplots(2, 4, figsize=(11, 6.0))
for ax, (t, o, pc, pd6, lvl) in zip(axs.flat, panels):
    hi = float(max(o.max(), pc.max()) * 1.1)
    ax.plot([0, hi], [0, hi], ls="--", lw=0.8, color="#888888")
    ax.scatter(o, pd6, s=12, color="#c9c8c2", label="default ceiling", zorder=2)
    ax.scatter(o, pc, s=14, color="#2f6b4f", label="calibrated", zorder=3)
    r = np.corrcoef(o, pc)[0, 1] if len(o) > 2 else np.nan
    mae = np.abs(o - pc).mean()
    ax.set_title(f"{t}\nn = {len(o)} {lvl} · MAE {mae:.2f} t/ha · r = {r:.2f}", fontsize=8, linespacing=1.5)
    ax.set_xlim(0, hi); ax.set_ylim(0, max(hi, float(pd6.max()) * 1.05))
    ax.set_xlabel("reported yield (t/ha)"); ax.set_ylabel("predicted (t/ha)")
axs.flat[-1].axis("off")
h, l = axs.flat[0].get_legend_handles_labels()
axs.flat[-1].legend(h, l, loc="center", frameon=False, fontsize=9, title="Model yield with…")
fig.tight_layout(); fig.savefig(os.path.join(H, "fig1_predicted_vs_reported.png"), dpi=200); plt.close(fig)

# test error before / after (held-out units)
l = pd.read_csv(os.path.join(CY, "ym_calibration_local.csv"))
names = {"app:ke_long": "Kenya LR", "app:ke_short": "Kenya SR", "app:et_meher": "Ethiopia", "Rwanda_SeasonA": "Rwanda",
         "Burundi_SeasonA": "Burundi", "Somalia_Gu": "Somalia", "Uganda_1strains": "Uganda*"}
rows = [(names[r.file], r.test_mae_default, r.test_mae_cal) for r in l.itertuples()]
fig, ax = plt.subplots(figsize=(7, 2.8))
y = np.arange(len(rows))
ax.barh(y + 0.19, [r[1] for r in rows], 0.36, color="#c9c8c2", label="default ceiling (6.0; 4.5 short rains)")
ax.barh(y - 0.19, [r[2] for r in rows], 0.36, color="#2f6b4f", label="calibrated")
for i, r in enumerate(rows):
    ax.text(r[1] + 0.04, i + 0.19, f"{r[1]:.2f}", va="center", fontsize=7); ax.text(r[2] + 0.04, i - 0.19, f"{r[2]:.2f}", va="center", fontsize=7)
ax.set_yticks(y); ax.set_yticklabels([r[0] for r in rows]); ax.invert_yaxis()
ax.set_xlabel("mean absolute error on held-out units (t/ha)")
ax.legend(frameon=False, loc="lower center", bbox_to_anchor=(0.5, 1.02), ncol=2, fontsize=7.5)
ax.set_xlim(0, max(r[1] for r in rows) * 1.12)
fig.tight_layout(); fig.savefig(os.path.join(H, "fig2_test_error.png"), dpi=200); plt.close(fig)
print("figures written")
