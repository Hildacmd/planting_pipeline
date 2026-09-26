#!/usr/bin/env python3
"""Score DMP-derived yield against observed AND against the CPI water-balance yield.

Three series per zone:
  obs        HarvestStat county/region mean, or ward crop-cut median
  cpi_yield  the pipeline's own product: arm-B CPI (production SoilGrids bucket) x ym_for()
  dmp_yield  seasonal dry matter x F_ABOVEGROUND x HARVEST_INDEX / (1 - moisture)

Because raw DM (kg/ha) is exported, the last conversion is done HERE — so harvest index and
above-ground fraction can be retuned without touching Earth Engine. The script also back-solves
the harvest index that WOULD reproduce the observations, which is the honest way to read a
biomass product: if the implied HI is far outside the agronomic 0.30-0.55 range, the mismatch is
not in HI, it is in the mask or the biomass itself.
"""
import csv, os, glob, sys, re
import numpy as np
from scipy import stats
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from src.kenya_gaul_counties import DISTRICT_TO_COUNTY, DROP, norm_county
from src.cpi import ym_for
from src import dmp_yield as DMP

HERE = os.path.dirname(os.path.abspath(__file__))
CY = os.path.join(HERE, "Cropyield-Data")
DRIVE = os.path.expanduser("~/Google Drive/My Drive/planting_outputs")
def norm(s): return re.sub(r"[^a-z0-9]", "", str(s).lower())
ET_ALIAS = {norm("Southern Nations, Nationalities and Peoples"): norm("SNNPR"),
            norm("Southern Nations"): norm("SNNPR"),
            norm("Benshangul-Gumaz"): norm("Benishangul Gumuz"),
            norm("Gambela Peoples"): norm("Gambela"), norm("Harari People"): norm("Harari")}


def find(pat):
    h = [f for d in (CY, DRIVE) for f in glob.glob(os.path.join(d, pat))]
    return max(h, key=os.path.getmtime) if h else None


def wavg(path, key, bands, rollup=False):
    acc = {}
    for r in csv.DictReader(open(path)):
        z = " ".join(str(r[key]).strip().split())
        if z in DROP: continue
        if rollup:
            z = DISTRICT_TO_COUNTY.get(z)
            if z is None: continue
        t = acc.setdefault(z, {b: [0.0, 0.0] for b in bands})
        for b in bands:
            try: v, n = float(r[f"{b}_mean"]), float(r[f"{b}_count"])
            except (ValueError, KeyError, TypeError): continue
            if n > 0: t[b][0] += v*n; t[b][1] += n
    return {z: {b: (s/n if n else None) for b, (s, n) in t.items()} for z, t in acc.items()}


def obs_county(fn):
    return {norm_county(r["admin_1"]): float(r["obs_mean"])
            for r in csv.DictReader(open(os.path.join(CY, fn))) if r.get("obs_mean")}


def obs_ward(year):
    return {r["GID_3"]: (float(r["obs_median_tha"]), f'{r["county"]}/{r["ward"]}')
            for r in csv.DictReader(open(os.path.join(CY, "ward_validation_joined.csv")))
            if r.get("GID_3") and r.get("obs_median_tha") and int(r["year"]) == year}


def skill(name, obs, pred):
    e = pred - obs
    r = np.corrcoef(pred, obs)[0, 1] if len(obs) > 2 else float("nan")
    rho = stats.spearmanr(pred, obs).statistic if len(obs) > 2 else float("nan")
    print(f"    {name:<12}{np.abs(e).mean():>8.3f}{e.mean():>+9.3f}{np.median(pred):>9.3f}"
          f"{r:>+8.2f}{rho:>+9.2f}")


VAR = [("ke_long",     "dmp_yield_ke_long_modis_2024*.csv",  "county", ("Kenya","Long rains"),
        "harveststat_obs_KE_Long.csv",  "whc_ab_KE_Long_2024_L2*.csv"),
       ("ke_short",    "dmp_yield_ke_short_modis_2024*.csv", "county", ("Kenya","Short rains"),
        "harveststat_obs_KE_Short.csv", "whc_ab_KE_Short_2024_short_county*.csv"),
       ("ke_ward_2021","dmp_yield_ke_ward_2021_modis_2021*.csv","ward", ("Kenya","Short rains"),
        None, "whc_ab_KE_Short_2021_short_ward*.csv"),
       ("ke_ward_2022","dmp_yield_ke_ward_2022_modis_2022*.csv","ward", ("Kenya","Short rains"),
        None, "whc_ab_KE_Short_2022_short_ward*.csv"),
       ("et_meher",    "dmp_yield_et_meher_modis_2024*.csv", "region", ("Ethiopia","Meher"),
        "harveststat_obs_ET_Meher.csv", "whc_ab_ET_Meher_2024*.csv")]

for tag, pat, zone, cs, obsfn, cpipat in VAR:
    print("\n" + "=" * 78)
    p = find(pat)
    if not p:
        print(f"{tag}: DMP export not present yet"); continue
    key = {"county": "ADM2_NAME", "region": "NAME_1", "ward": "GID_3"}[zone]
    dmp = wavg(p, key, ["DM_kg_ha", "dmp_yield_tha"], rollup=(zone == "county"))
    cpip = find(cpipat)
    cpi = wavg(cpip, key, ["cpi_B"], rollup=(zone == "county")) if cpip else {}
    ymv = ym_for(*cs)

    rows = []
    if zone == "ward":
        year = 2021 if "2021" in tag else 2022
        ob = obs_ward(year)
        for g, (o, nm) in ob.items():
            d = dmp.get(g); c = cpi.get(g)
            if not d or d["DM_kg_ha"] is None: continue
            rows.append((nm, o, d["DM_kg_ha"], d["dmp_yield_tha"],
                         (c["cpi_B"]/100*ymv) if c and c.get("cpi_B") is not None else np.nan))
    else:
        ob = obs_county(obsfn) if zone == "county" else None
        if zone == "region":
            ob = {norm(k): v for k, v in
                  {r["admin_1"]: float(r["obs_mean"]) for r in
                   csv.DictReader(open(os.path.join(CY, obsfn))) if r.get("obs_mean")}.items()}
        for z, d in dmp.items():
            if d["DM_kg_ha"] is None: continue
            k = norm_county(z) if zone == "county" else ET_ALIAS.get(norm(z), norm(z))
            if k not in ob: continue
            c = cpi.get(z)
            rows.append((z, ob[k], d["DM_kg_ha"], d["dmp_yield_tha"],
                         (c["cpi_B"]/100*ymv) if c and c.get("cpi_B") is not None else np.nan))

    SCORES = globals().setdefault('SCORES', [])
    if len(rows) < 3:
        print(f"{tag}: only {len(rows)} matched zones — not scored"); continue
    names = [r[0] for r in rows]
    obs = np.array([r[1] for r in rows]); DM = np.array([r[2] for r in rows])
    dy = np.array([r[3] for r in rows]);  cy = np.array([r[4] for r in rows])
    print(f"{tag.upper()}   n = {len(rows)}   (MODIS stand-in for Copernicus DMP)")
    print(f"  seasonal dry matter: mean {DM.mean():,.0f} kg DM/ha  (median {np.median(DM):,.0f})")
    print(f"  observed yield     : mean {obs.mean():.2f} t/ha")
    print(f"    {'series':<12}{'MAE':>8}{'bias':>9}{'median':>9}{'r':>8}{'spearman':>9}")
    skill("dmp_yield", obs, dy)
    if np.isfinite(cy).sum() > 2:
        m = np.isfinite(cy)
        skill("cpi_yield", obs[m], cy[m])
    # back-solve the harvest index implied by the observations
    denom = DM * DMP.F_ABOVEGROUND / (1 - DMP.GRAIN_MOISTURE) / 1000.0
    hi_implied = float(np.sum(denom * obs) / np.sum(denom ** 2))
    print(f"  harvest index used {DMP.HARVEST_INDEX:.2f}  ->  implied by observations "
          f"{hi_implied:.3f}   (agronomic range ~0.30-0.55)")
    print(f"  over-prediction factor at HI={DMP.HARVEST_INDEX:.2f}: {dy.mean()/obs.mean():.1f}x")

    # --- capture, so report/build_report.py reads these numbers rather than anyone retyping them
    def _sk(o, p):
        from scipy import stats as _st
        e = p - o
        return (float(np.abs(e).mean()), float(e.mean()),
                float(np.corrcoef(o, p)[0, 1]), float(_st.spearmanr(o, p).statistic))
    _m = np.isfinite(cy)
    _d = _sk(obs, dy)
    _c = _sk(obs[_m], cy[_m]) if _m.sum() > 2 else (np.nan,) * 4
    SCORES.append(dict(frame=tag.upper(), n=len(rows),
                       dm_mean=round(float(DM.mean())), obs_mean=round(float(obs.mean()), 2),
                       dmp_mae=round(_d[0], 3), dmp_bias=round(_d[1], 3),
                       dmp_r=round(_d[2], 2), dmp_rho=round(_d[3], 2),
                       cpi_mae=round(_c[0], 3), cpi_bias=round(_c[1], 3),
                       cpi_r=round(_c[2], 2), cpi_rho=round(_c[3], 2),
                       hi_implied=round(hi_implied, 3),
                       overpred=round(float(dy.mean() / obs.mean()), 1)))


# ---------------------------------------------------------------------------------------------
# Write the frame-by-frame statistics. The report's Kenya DMP section reads this file, so the
# numbers there are the ones this script actually produced.
try:
    import pandas as _pd
    if globals().get("SCORES"):
        _out = os.path.join(CY, "dmp_score_summary.csv")
        _pd.DataFrame(SCORES).to_csv(_out, index=False)
        print(f"\nwritten: {_out}  ({len(SCORES)} frames)")
except Exception as _e:
    print(f"[warn] summary not written: {_e}")
