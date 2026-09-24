#!/usr/bin/env python3
"""Score the two sorghum crop calendars against HarvestStat, arm A vs arm B.

    arm A  Inception Report Table 2.0              assets sorghum_*
    arm B  GEOGLAM CM4EW v1.3, sorghum-specific    assets sorghumB_*

The arms differ in exactly one thing, the calendar: the planting window and the cycle length.
The SOS rule, the mask, the coefficients, the Ky values and the heat cap are identical, so any
difference in skill is attributable to the calendar.

**Metrics, and why these ones.**

1. **Spearman rho between CPI and reported sorghum yield, across reporting units.** This is the
   primary metric and it needs **no yield ceiling at all**, so it cannot be contaminated by a
   fitted Ym. It answers the question that matters: does the calendar put the water balance in
   the right part of the season, so that the index ranks districts the way the harvest did?

2. **Leave-one-out MAE with the ceiling held FIXED across the arms.** Refitting Ym per arm
   absorbs a level shift by construction and manufactures false positives; the WHC A/B in this
   project produced exactly one apparent win that vanished when the ceiling was shared. Three
   regimes are reported - a ceiling fitted on arm A, one fitted on arm B, and the shipped
   default - so a result cannot be an artefact of which arm set the level.

3. **Paired bootstrap** over units, 2000 resamples, giving the share of resamples in which each
   arm wins and a confidence interval on the difference. With 20 to 76 units a point estimate
   on its own means very little.

    python sorghum_pipeline/score_calendar_ab.py
    python sorghum_pipeline/score_calendar_ab.py --resamples 5000

Reads the zonal CSVs written by `zonal_sorghum.py` for both arms; writes
`work/calendar_ab_scores.csv` and `work/calendar_ab_units.csv`.
"""
import argparse, os, sys
import numpy as np, pandas as pd, geopandas as gpd
from scipy import stats

H = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(H)
sys.path.insert(0, H)
import sorghum_params as P                                          # noqa: E402

HS = os.path.join(ROOT, "Cropyield-Data", "harveststat")
DRIVE = os.environ.get("CTM_LOCAL_DRIVE", os.path.expanduser(
    "~/Library/CloudStorage/GoogleDrive-manzikye@gmail.com/My Drive/planting_outputs"))
YEAR = 2024
MAX_YIELD = 6.0

# products where the two calendars differ AND HarvestStat holds sorghum yields.
# (country, season, HarvestStat country, HarvestStat season, years)
JOBS = [
    ("Ethiopia",    "Meher",      "Ethiopia",    "Meher",  range(2012, 2022)),
    ("Kenya",       "Long rains", "Kenya",       "Long",   range(2015, 2017)),
    ("Uganda",      "1st rains",  "Uganda",      "First",  range(2009, 2010)),
    ("South_Sudan", "Main",       "South Sudan", "Main",   range(1990, 2011)),
]
# Eritrea Kremti and South Sudan 2nd also differ between the arms but cannot be scored:
# Eritrea is absent from HarvestStat entirely, and no second-season sorghum series exists.


def zonal(prefix, country, season):
    tok = f"{country}_{season}_{YEAR}".replace(" ", "")
    for d in (DRIVE, f"{H}/work"):
        p = os.path.join(d, f"{prefix}_{tok}_L2.csv")
        if os.path.exists(p):
            return gpd.read_file(p)
    return None


def match(g, units):
    """Aggregate admin-2 CPI onto the HarvestStat units, weighted by sorghum area."""
    g = g[g.cpi.notna() & g.crop_area_frac.notna() & (g.crop_area_frac > 0)].to_crs(4326)
    ov = gpd.overlay(units[["fnid", "y", "geometry"]],
                     g[["cpi", "crop_area_frac", "geometry"]], how="intersection")
    ov["w"] = ov.area * ov.crop_area_frac
    out = (ov.groupby("fnid")
             .apply(lambda t: pd.Series({"cpi": np.average(t.cpi, weights=t.w) if t.w.sum() > 0
                                         else np.nan, "y": t.y.iloc[0]}))
             .dropna().reset_index())
    return out


def fit_ym(y, c):
    return float((y * c).sum() / max((c * c).sum(), 1e-9))


def loo_mae(y, c, ym_fixed=None):
    """Leave-one-out MAE. With ym_fixed the ceiling is not refit, which is the honest comparison."""
    e = []
    for i in range(len(y)):
        k = np.ones(len(y), bool); k[i] = False
        ym = ym_fixed if ym_fixed is not None else fit_ym(y[k], c[k])
        e.append(abs(c[i] * ym - y[i]))
    return float(np.mean(e))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--resamples", type=int, default=2000)
    a = ap.parse_args()

    d = pd.read_csv(os.path.join(HS, "hvstat_africa_data_v1.2.csv"), low_memory=False)
    d.columns = [c.lower() for c in d.columns]
    b = gpd.read_file(os.path.join(HS, "hvstat_africa_boundary_v1.2.gpkg"))
    b.columns = [c.lower() for c in b.columns]

    rows, allunits = [], []
    for country, season, hsc, hss, years in JOBS:
        gA, gB = zonal("sorghum", country, season), zonal("sorghumB", country, season)
        if gA is None or gB is None:
            rows.append(dict(country=country, season=season,
                             status=f"waiting on {'A' if gA is None else ''}"
                                    f"{'B' if gB is None else ''} zonal export"))
            continue
        y = d[(d["product"] == "Sorghum") & (d.country == hsc) & (d.season_name == hss)
              & d.harvest_year.isin(years) & d["yield"].notna()]
        obs = y.groupby("fnid")["yield"].median().rename("y").reset_index()
        obs = obs[obs.y <= MAX_YIELD]
        units = b.merge(obs, on="fnid").to_crs(4326)
        mA, mB = match(gA, units), match(gB, units)
        m = mA.merge(mB, on="fnid", suffixes=("_A", "_B"))      # paired: same units both arms
        m = m[m.y_A.notna()]
        if len(m) < 6:
            rows.append(dict(country=country, season=season, units=len(m),
                             status="too few matched units")); continue

        yv = m.y_A.values
        cA, cB = (m.cpi_A / 100).values, (m.cpi_B / 100).values
        rA = stats.spearmanr(cA, yv).statistic
        rB = stats.spearmanr(cB, yv).statistic
        ymA, ymB = fit_ym(yv, cA), fit_ym(yv, cB)
        dflt = P.ym_for(country, season)
        res = {}
        for name, ym in (("fit_A", ymA), ("fit_B", ymB), ("default", dflt)):
            res[name] = (loo_mae(yv, cA, ym), loo_mae(yv, cB, ym))

        rng = np.random.default_rng(0)
        wins, diffs = 0, []
        n = len(m)
        for _ in range(a.resamples):
            k = rng.integers(0, n, n)
            ra = stats.spearmanr(cA[k], yv[k]).statistic
            rb = stats.spearmanr(cB[k], yv[k]).statistic
            if np.isnan(ra) or np.isnan(rb):
                continue
            diffs.append(rb - ra); wins += rb > ra
        lo, hi = np.percentile(diffs, [2.5, 97.5]) if diffs else (np.nan, np.nan)

        rows.append(dict(
            country=country, season=season, units=n, years=f"{min(years)}-{max(years)}",
            rho_A=round(rA, 3), rho_B=round(rB, 3), d_rho=round(rB - rA, 3),
            ci_lo=round(lo, 3), ci_hi=round(hi, 3),
            B_wins_pct=round(100 * wins / max(len(diffs), 1)),
            ym_fit_A=round(ymA, 2), ym_fit_B=round(ymB, 2),
            mae_A_fixedA=round(res["fit_A"][0], 3), mae_B_fixedA=round(res["fit_A"][1], 3),
            mae_A_fixedB=round(res["fit_B"][0], 3), mae_B_fixedB=round(res["fit_B"][1], 3),
            verdict=("B (GEOGLAM)" if lo > 0 else "A (report)" if hi < 0 else "no difference"),
            status="scored"))
        m["country"], m["season"] = country, season
        allunits.append(m)

    out = pd.DataFrame(rows)
    out.to_csv(f"{H}/work/calendar_ab_scores.csv", index=False)
    if allunits:
        pd.concat(allunits, ignore_index=True).to_csv(f"{H}/work/calendar_ab_units.csv", index=False)
    print(out.to_string(index=False))
    if "verdict" in out:
        print("\nPrimary metric is Spearman rho of CPI against reported yield: it needs no yield "
              "ceiling, so it cannot be contaminated by a fitted Ym.")
        print("A confidence interval that spans zero means the two calendars cannot be separated "
              "on this evidence, whatever the point estimate says.")


if __name__ == "__main__":
    main()
