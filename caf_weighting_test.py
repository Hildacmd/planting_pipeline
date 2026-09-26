#!/usr/bin/env python3
"""Which CAF weighting leaves yield/ha least disturbed by a change of crop mask?

Ym is fitted by least squares through the origin of observed yield on CPI. CPI reaches a
HarvestStat unit as a WEIGHTED MEAN of the pipeline admin-2 units that overlap it, and the weight
is currently `overlap_area x crop_area_frac`. crop_area_frac comes from the mask, so the mask
enters yield/ha TWICE: once through CPI itself (which pixels are averaged) and again through the
weight. The second path is avoidable; the first is not.

Four weightings, each fitted on BOTH footprints with everything else held identical:

  caf       overlap_area x crop_area_frac      current - mask-dependent
  area      overlap_area                       geometric only - mask-INdependent
  equal     1 per overlapping admin-2 unit     mask-independent, ignores size
  reported  overlap_area x the HarvestStat unit's own reported crop area share
                                               mask-independent, uses the same source as the target

The diagnostic is |d_ym| BETWEEN footprints: a weighting that leaves yield/ha stable when the mask
changes has isolated the mask's effect to CPI, where it belongs. Skill (r) is reported alongside,
because a weighting that is stable but unskilful is not an improvement.

    python caf_weighting_test.py
"""
import os, random
import geopandas as gpd, numpy as np, pandas as pd
from shapely import wkt

H = os.path.dirname(os.path.abspath(__file__))
HS = os.path.join(H, "Cropyield-Data", "harveststat")
EQ = "ESRI:54034"
JOBS = [("Kenya_Longrains", "planting_Kenya_maize_Longrains_2024", "Kenya", "Long", range(2015, 2025)),
        ("Kenya_Shortrains", "planting_Kenya_maize_Shortrains_2024_rainfed", "Kenya", "Short", range(2016, 2025)),
        ("Ethiopia_Meher", "planting_Ethiopia_maize_Meher_2024_250m", "Ethiopia", "Meher", range(2012, 2022)),
        ("Rwanda_SeasonA", "newc_Rwanda_SeasonA_2024", "Rwanda", "Season A", range(2010, 2018)),
        ("Burundi_SeasonA", "newc_Burundi_SeasonA_2024", "Burundi", "Season A", range(2012, 2017)),
        ("Somalia_Gu", "newc_Somalia_Gu_2024", "Somalia", "Gu", range(2015, 2025)),
        ("Uganda_1strains", "newc_Uganda_1strains_2024", "Uganda", "First", range(2008, 2010))]
SCHEMES = ["caf", "area", "equal", "reported"]


def units(stem):
    n = pd.read_csv(os.path.join(H, f"{stem}_L2_skill_WKT.csv"))
    g = gpd.GeoDataFrame(n[["cpi", "crop_area_frac"]],
                         geometry=[wkt.loads(x) for x in n.geometry_wkt], crs="EPSG:4326")
    g = g[g.cpi.notna() & g.crop_area_frac.notna() & (g.crop_area_frac > 0)].copy()
    g["geometry"] = g.geometry.buffer(0)
    return g


def fit(g, obs, bnd, scheme, rep_area):
    u = bnd[bnd.fnid.isin(obs.index)][["fnid", "geometry"]]
    ov = gpd.overlay(g.to_crs(EQ), u.to_crs(EQ), how="intersection", keep_geom_type=True)
    if not len(ov):
        return None
    if scheme == "caf":
        ov["w"] = ov.area * ov.crop_area_frac
    elif scheme == "area":
        ov["w"] = ov.area
    elif scheme == "equal":
        ov["w"] = 1.0
    else:                                   # reported: geometric share x the unit's reported area
        ov["w"] = ov.area * ov.fnid.map(rep_area).fillna(rep_area.median())
    cpi_u = (ov.groupby("fnid")
               .apply(lambda t: np.average(t.cpi, weights=t.w) if t.w.sum() > 0 else np.nan,
                      include_groups=False).dropna())
    j = pd.concat([obs.rename("obs"), (cpi_u / 100).rename("c")], axis=1).dropna()
    if len(j) < 3:
        return None
    o, c = j.obs.values, j.c.values
    ym = float((o * c).sum() / (c * c).sum())
    rnd = random.Random(42); idx = list(range(len(j))); mae = []
    for _ in range(200):
        rnd.shuffle(idx); k = max(1, int(round(0.7 * len(idx)))); tr, te = idx[:k], idx[k:]
        if not te:
            continue
        ymt = (o[tr] * c[tr]).sum() / (c[tr] ** 2).sum()
        mae.append(np.abs(o[te] - ymt * c[te]).mean())
    return dict(n=len(j), ym=round(ym, 3), mae=round(float(np.mean(mae)), 3),
                r=round(float(np.corrcoef(o, ym * c)[0, 1]), 3))


def main():
    d = pd.read_csv(os.path.join(HS, "hvstat_africa_data_v1.2.csv"), low_memory=False)
    d.columns = [c.lower() for c in d.columns]
    b = gpd.read_file(os.path.join(HS, "hvstat_africa_boundary_v1.2.gpkg"))
    b.columns = [c.lower() for c in b.columns]; b = b.set_geometry("geometry")

    rows = []
    for tok, wc_stem, country, season, years in JOBS:
        y = d[(d["product"] == "Maize") & (d.country == country) & (d.season_name == season)
              & d.harvest_year.isin(years) & d["yield"].notna()]
        obs = y.groupby("fnid")["yield"].median()
        obs = obs[(obs > 0) & (obs <= 8)]
        rep_area = y.groupby("fnid")["area"].median()
        for sch in SCHEMES:
            r = dict(product=tok, scheme=sch)
            for lab, stem in (("wc", wc_stem), ("ctm", f"newcCTM_{tok}_2024")):
                f = fit(units(stem), obs, b, sch, rep_area)
                if f:
                    r.update({f"{lab}_ym": f["ym"], f"{lab}_r": f["r"], f"{lab}_mae": f["mae"],
                              f"{lab}_n": f["n"]})
            if "wc_ym" in r and "ctm_ym" in r:
                r["d_ym_pct"] = round(100 * (r["ctm_ym"] - r["wc_ym"]) / r["wc_ym"], 2)
                r["mean_r"] = round((r["wc_r"] + r["ctm_r"]) / 2, 3)
            rows.append(r)
        print(f"  {tok} done", flush=True)

    o = pd.DataFrame(rows).dropna(subset=["d_ym_pct"])
    o.to_csv(os.path.join(H, "maize_ctm", "caf_weighting_test.csv"), index=False)
    print("\n=== Ym shift between footprints, by weighting scheme (|smaller| = yield/ha better insulated) ===")
    piv = o.pivot(index="product", columns="scheme", values="d_ym_pct")[SCHEMES]
    print(piv.to_string())
    print("\n  median |shift| %:")
    for s in SCHEMES:
        print(f"    {s:9s} {piv[s].abs().median():6.2f}   (max {piv[s].abs().max():6.2f})")
    print("\n=== skill (mean r over the two footprints), by scheme ===")
    pr = o.pivot(index="product", columns="scheme", values="mean_r")[SCHEMES]
    print(pr.to_string())
    print("\n  median r:")
    for s in SCHEMES:
        print(f"    {s:9s} {pr[s].median():6.3f}")
    print("\nwritten: maize_ctm/caf_weighting_test.csv")


if __name__ == "__main__":
    main()
