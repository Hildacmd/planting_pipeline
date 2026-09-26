#!/usr/bin/env python3
"""Re-fit the maize yield ceiling Ym on the ICPAC crop-type-mask footprint, against WorldCereal.

Ym is fitted by least squares through the origin of observed yield on CPI, with the admin units
weighted by their MAIZE AREA (`area x crop_area_frac`). Changing the mask changes both terms: CPI is
computed over a different set of pixels, and crop_area_frac is a different fraction. So a Ym fitted
on the WorldCereal footprint does not carry over to a crop-type-mask product - the ceiling and the
footprint are a matched pair.

BOTH footprints are fitted here, at the SAME admin level (L2) with the same units, the same
HarvestStat targets, the same 70/30 x 200 held-out test and the same seed, so the difference is
attributable to the footprint and nothing else.

    python calibrate_ym_ctm.py                 # fit both, print the comparison
    python calibrate_ym_ctm.py --write         # also patch YM_CAL_CTM into src/cpi.py

A NOTE ON COMPARABILITY. The shipped Kenya and Ethiopia ceilings in src/cpi.py were fitted on
WARD/WOREDA (L2 of the risk monitor, admin-3) units read out of risk_app.html. This script fits
every job at admin-2 for both footprints, because the crop-type-mask run has no admin-3 reduce. The
'worldcereal' column here is therefore a CONTROL re-fit at admin-2, not the shipped number, and the
two can differ for that reason alone - which is exactly why the control is computed rather than
compared against the shipped value.
"""
import argparse, os, random, re
import geopandas as gpd, numpy as np, pandas as pd
from shapely import wkt

H = os.path.dirname(os.path.abspath(__file__))
HS = os.path.join(H, "Cropyield-Data", "harveststat")
EQ = "ESRI:54034"                                  # equal-area, for overlap weights

# token, WorldCereal L2 stem, HarvestStat country/season/years/FNID prefix, provisional?
JOBS = [
    ("Kenya_Longrains",  "planting_Kenya_maize_Longrains_2024",
     "Kenya", "Long", range(2015, 2025), False),
    ("Kenya_Shortrains", "planting_Kenya_maize_Shortrains_2024_rainfed",
     "Kenya", "Short", range(2016, 2025), False),
    ("Ethiopia_Meher",   "planting_Ethiopia_maize_Meher_2024_250m",
     "Ethiopia", "Meher", range(2012, 2022), False),
    ("Rwanda_SeasonA",   "newc_Rwanda_SeasonA_2024",  "Rwanda",  "Season A", range(2010, 2018), False),
    ("Burundi_SeasonA",  "newc_Burundi_SeasonA_2024", "Burundi", "Season A", range(2012, 2017), False),
    ("Somalia_Gu",       "newc_Somalia_Gu_2024",      "Somalia", "Gu",       range(2015, 2025), False),
    ("Uganda_1strains",  "newc_Uganda_1strains_2024", "Uganda",  "First",    range(2008, 2010), True),
]
YM_KEY = {"Kenya_Longrains": ("Kenya", "Long rains"), "Kenya_Shortrains": ("Kenya", "Short rains"),
          "Ethiopia_Meher": ("Ethiopia", "Meher"), "Rwanda_SeasonA": ("Rwanda", "Season A"),
          "Burundi_SeasonA": ("Burundi", "Season A"), "Somalia_Gu": ("Somalia", "Gu"),
          "Uganda_1strains": ("Uganda", "1st rains")}


def units(stem):
    f = os.path.join(H, f"{stem}_L2_skill_WKT.csv")
    n = pd.read_csv(f)
    g = gpd.GeoDataFrame(n[["cpi", "crop_area_frac"]],
                         geometry=[wkt.loads(x) for x in n.geometry_wkt], crs="EPSG:4326")
    g = g[g.cpi.notna() & g.crop_area_frac.notna() & (g.crop_area_frac > 0)].copy()
    g["geometry"] = g.geometry.buffer(0)
    return g


def fit(g, obs, bnd):
    """Ym by least squares through the origin, maize-area-weighted onto HarvestStat units."""
    u = bnd[bnd.fnid.isin(obs.index)][["fnid", "geometry"]]
    ov = gpd.overlay(g.to_crs(EQ), u.to_crs(EQ), how="intersection", keep_geom_type=True)
    if not len(ov):
        return None
    ov["w"] = ov.area * ov.crop_area_frac
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
    r = float(np.corrcoef(o, ym * c)[0, 1]) if len(j) > 2 else np.nan
    return dict(n=len(j), ym=round(ym, 2), mae=round(float(np.mean(mae)), 2),
                r=round(r, 2), cpi_med=round(float(np.median(c * 100)), 1))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--write", action="store_true")
    a = ap.parse_args()

    d = pd.read_csv(os.path.join(HS, "hvstat_africa_data_v1.2.csv"), low_memory=False)
    d.columns = [c.lower() for c in d.columns]
    b = gpd.read_file(os.path.join(HS, "hvstat_africa_boundary_v1.2.gpkg"))
    b.columns = [c.lower() for c in b.columns]; b = b.set_geometry("geometry")

    rows = []
    for tok, wc_stem, country, season, years, prov in JOBS:
        y = d[(d["product"] == "Maize") & (d.country == country) & (d.season_name == season)
              & d.harvest_year.isin(years) & d["yield"].notna()]
        obs = y.groupby("fnid")["yield"].median()
        obs = obs[(obs > 0) & (obs <= 8)]
        r = dict(product=tok, country=country, season=season, n_hs=len(obs), provisional=prov)
        for lab, stem in (("wc", wc_stem), ("ctm", f"newcCTM_{tok}_2024")):
            try:
                f = fit(units(stem), obs, b)
            except Exception as e:
                f = None; print(f"  [{tok} {lab}] {type(e).__name__}: {str(e)[:70]}")
            if f:
                r.update({f"{lab}_n": f["n"], f"{lab}_ym": f["ym"], f"{lab}_mae": f["mae"],
                          f"{lab}_r": f["r"], f"{lab}_cpi": f["cpi_med"]})
        if "wc_ym" in r and "ctm_ym" in r:
            r["d_ym"] = round(r["ctm_ym"] - r["wc_ym"], 2)
            r["d_ym_pct"] = round(100 * (r["ctm_ym"] - r["wc_ym"]) / r["wc_ym"], 1)
            r["d_mae"] = round(r["ctm_mae"] - r["wc_mae"], 2)
        rows.append(r)
        print(f"  fitted {tok}", flush=True)

    out = pd.DataFrame(rows)
    out.to_csv(os.path.join(H, "maize_ctm", "ym_refit_ctm.csv"), index=False)
    cols = [c for c in ("product", "n_hs", "wc_n", "wc_ym", "wc_mae", "wc_r",
                        "ctm_n", "ctm_ym", "ctm_mae", "ctm_r", "d_ym", "d_ym_pct", "d_mae",
                        "provisional") if c in out.columns]
    print("\n=== Ym re-fit: WorldCereal vs ICPAC crop-type mask, both at admin-2 ===")
    print(out[cols].to_string(index=False))

    ok = out.dropna(subset=["d_ym"]) if "d_ym" in out.columns else out.iloc[0:0]
    if len(ok):
        print(f"\n=== over {len(ok)} fitted products ===")
        print(f"  Ym change   : median {ok.d_ym_pct.median():+.1f} % "
              f"(range {ok.d_ym_pct.min():+.1f} % to {ok.d_ym_pct.max():+.1f} %)")
        print(f"  held-out MAE: median change {ok.d_mae.median():+.2f} t/ha "
              f"({int((ok.d_mae < 0).sum())} of {len(ok)} improve)")
        better = ok[ok.d_mae < 0]
        if len(better):
            print("  crop-type mask fits BETTER for: " + ", ".join(better["product"]))
        worse = ok[ok.d_mae > 0]
        if len(worse):
            print("  WorldCereal fits better for    : " + ", ".join(worse["product"]))

    if a.write and len(ok):
        p = os.path.join(H, "src", "cpi.py")
        s = open(p).read()
        block = ("# Ym fitted on the ICPAC CROP-TYPE-MASK footprint (calibrate_ym_ctm.py). Use ONLY\n"
                 "# with the cpiCTMX_/newcCTM_ products - a ceiling and a footprint are a matched\n"
                 "# pair, because the mask changes both CPI and the crop-area weights it is fitted\n"
                 "# against. Do NOT apply these to the WorldCereal products in YM_CAL above.\n"
                 "YM_CAL_CTM = {\n")
        for r in ok.itertuples():
            co, se = YM_KEY[r.product]
            block += (f'    ("{co}", "{se}"): {r.ctm_ym:.2f},   # n{int(r.ctm_n)} '
                      f'MAE {r.ctm_mae} vs wc {r.wc_mae}  r {r.ctm_r}'
                      f'{"  PROVISIONAL" if r.provisional else ""}\n')
        block += "}\n"
        if "YM_CAL_CTM" in s:
            s = re.sub(r"(?ms)^# Ym fitted on the ICPAC CROP-TYPE-MASK.*?^\}\n", block, s)
        else:
            s = s.replace("YM_MAIN_DEFAULT", block + "\nYM_MAIN_DEFAULT", 1)
        open(p, "w").write(s)
        print(f"\nwrote YM_CAL_CTM ({len(ok)} ceilings) into src/cpi.py")
    print(f"\nwritten: maize_ctm/ym_refit_ctm.csv")


if __name__ == "__main__":
    main()
