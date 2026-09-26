#!/usr/bin/env python3
"""Score the three Ethiopia Meher maize calendar arms against HarvestStat.

    arm op      operative, SOS Apr-d2 to Jun-d3
    arm cm4ew   GEOGLAM CM4EW,  SOS May-d3 to Aug-d2
    arm report  Table 2.0,      SOS Jun-d2 to Aug-d3

**Primary metric: Spearman rho between CPI and reported zone yield.** It needs no yield ceiling, so
it cannot be contaminated by a fitted Ym — the trap that produced a false positive in the WHC A/B,
where refitting a ceiling per arm absorbed a level shift and manufactured a win that vanished once
both arms shared one.

Mean absolute error is secondary and is reported with the ceiling **held fixed across all three
arms**, under each arm's own fit in turn, so a result cannot be an artefact of which arm set the
level.

Intervals are a paired bootstrap over the zones, 2000 resamples. Ethiopia Meher has 76 HarvestStat
zones over ten years, the largest sample of any product in the series, which is why this is the one
calendar question in the region a test can plausibly settle.

    EE_PROJECT=ee-manzikye python maize_ctm/score_calendar_ab_ethiopia.py
"""
import itertools, os, sys
import numpy as np, pandas as pd, geopandas as gpd
from scipy import stats

H = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(H)
HS = os.path.join(ROOT, "Cropyield-Data", "harveststat")
YEARS = range(2012, 2022)
MAX_YIELD = 8.0
AEA = ("+proj=aea +lat_1=20 +lat_2=-23 +lat_0=0 +lon_0=25 +x_0=0 +y_0=0 "
       "+datum=WGS84 +units=m +no_defs")
ARMS = ["op", "cm4ew", "report"]
LABEL = {"op": "operative Apr-d2", "cm4ew": "GEOGLAM May-d3", "report": "report Jun-d2"}


def arm_units(arm):
    f = os.path.join(ROOT, f"newcCAL{arm}_Ethiopia_Meher_2024_L2_skill_WKT.csv")
    if not os.path.exists(f):
        return None
    from shapely import wkt
    d = pd.read_csv(f)
    return gpd.GeoDataFrame(d, geometry=d.geometry_wkt.map(wkt.loads), crs="EPSG:4326")


def match(g, units):
    g = g[g.cpi.notna() & g.crop_area_frac.notna() & (g.crop_area_frac > 0)].to_crs(4326)
    ov = gpd.overlay(units[["fnid", "y", "geometry"]],
                     g[["cpi", "crop_area_frac", "geometry"]], how="intersection").to_crs(AEA)
    ov["w"] = ov.area * ov.crop_area_frac
    return (ov.groupby("fnid")[["cpi", "y", "w"]]
              .apply(lambda t: pd.Series({"cpi": np.average(t.cpi, weights=t.w) if t.w.sum() > 0
                                          else np.nan, "y": t.y.iloc[0]}))
              .dropna().reset_index())


def fit_ym(y, c):
    return float((y * c).sum() / max((c * c).sum(), 1e-9))


def loo_mae(y, c, ym):
    return float(np.mean([abs(c[i] * ym - y[i]) for i in range(len(y))]))


def main():
    d = pd.read_csv(os.path.join(HS, "hvstat_africa_data_v1.2.csv"), low_memory=False)
    d.columns = [x.lower() for x in d.columns]
    b = gpd.read_file(os.path.join(HS, "hvstat_africa_boundary_v1.2.gpkg"))
    b.columns = [x.lower() for x in b.columns]
    y = d[(d["product"] == "Maize") & (d.country == "Ethiopia") & (d.season_name == "Meher")
          & d.harvest_year.isin(YEARS) & d["yield"].notna()]
    obs = y.groupby("fnid")["yield"].median().rename("y").reset_index()
    obs = obs[obs.y <= MAX_YIELD]
    units = b.merge(obs, on="fnid").to_crs(4326)
    print(f"HarvestStat Ethiopia Meher maize: {len(units)} zones, {min(YEARS)} to {max(YEARS)}\n")

    m = None
    for arm in ARMS:
        g = arm_units(arm)
        if g is None:
            print(f"  waiting on the reduce for arm '{arm}' "
                  f"(newcCAL{arm}_Ethiopia_Meher_2024_L2_skill_WKT.csv)")
            return
        a = match(g, units).rename(columns={"cpi": f"cpi_{arm}"})
        m = a if m is None else m.merge(a[["fnid", f"cpi_{arm}"]], on="fnid")
    m = m.dropna()
    yv = m.y.values
    C = {a: (m[f"cpi_{a}"] / 100).values for a in ARMS}
    n = len(m)
    print(f"matched on all three arms: {n} zones\n")

    ym = {a: fit_ym(yv, C[a]) for a in ARMS}
    rho = {a: stats.spearmanr(C[a], yv).statistic for a in ARMS}
    r = {a: float(np.corrcoef(C[a], yv)[0, 1]) for a in ARMS}
    print(f"{'arm':<10}{'window':<18}{'rho':>8}{'pearson r':>11}{'Ym fit':>9}"
          + "".join(f"{'MAE|Ym='+a:>13}" for a in ARMS))
    for a in ARMS:
        maes = "".join(f"{loo_mae(yv, C[a], ym[b]):>13.3f}" for b in ARMS)
        print(f"{a:<10}{LABEL[a]:<18}{rho[a]:>8.3f}{r[a]:>11.3f}{ym[a]:>9.2f}{maes}")

    rng = np.random.default_rng(0)
    print("\npaired bootstrap on rho, 2000 resamples:")
    for a, bb in itertools.combinations(ARMS, 2):
        diffs, wins = [], 0
        for _ in range(2000):
            k = rng.integers(0, n, n)
            ra = stats.spearmanr(C[a][k], yv[k]).statistic
            rb = stats.spearmanr(C[bb][k], yv[k]).statistic
            if np.isnan(ra) or np.isnan(rb):
                continue
            diffs.append(ra - rb); wins += ra > rb
        lo, hi = np.percentile(diffs, [2.5, 97.5])
        sig = "SIGNIFICANT" if lo > 0 or hi < 0 else "not separable"
        print(f"  {a:<7} minus {bb:<7} d_rho {np.mean(diffs):+.3f}  "
              f"95% [{lo:+.3f}, {hi:+.3f}]  {a} wins {100*wins/max(len(diffs),1):.0f}%  {sig}")

    out = pd.DataFrame([dict(arm=a, window=LABEL[a], zones=n, rho=round(rho[a], 3),
                             pearson_r=round(r[a], 3), ym_fit=round(ym[a], 2),
                             mae_own_ym=round(loo_mae(yv, C[a], ym[a]), 3)) for a in ARMS])
    p = f"{H}/work/calendar_ab_ethiopia.csv"
    os.makedirs(f"{H}/work", exist_ok=True)
    out.to_csv(p, index=False)
    print(f"\nwritten: {p}")
    print("A rho that falls monotonically as planting is pushed later is evidence FOR the earlier "
          "window; intervals spanning zero mean the calendars cannot be separated on this evidence.")


if __name__ == "__main__":
    main()
