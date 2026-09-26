#!/usr/bin/env python3
"""Is the pipeline's reported crop condition ANTI-correlated with irrigation?

For every product, joins its OWN admin-1 CPI to the irrigated share of its OWN crop, and takes
Spearman rho. Negative rho = the units SPAM says are irrigated are the units the pipeline says are
failing, which means CPI is partly measuring irrigation dependence rather than crop condition.
"""
import os, sys
import pandas as pd
from scipy.stats import spearmanr

H = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, H)
from products import inventory

A1 = pd.read_csv(f"{H}/spam2020_irrigated_admin1.csv")
rows = []
for prod in inventory():
    crop, country, season = prod["crop"], prod["country"], prod["season"]
    d = pd.read_csv(prod["csv"])
    i = A1[(A1.country == country) & (A1.crop == crop)][["admin1", "irrigated_pct"]]
    if not len(i) or "cpi" not in d.columns:
        continue
    m = d.merge(i, left_on="name", right_on="admin1", how="inner")
    if len(m) < 4:
        rows.append(dict(crop=crop, country=country, season=season, n=len(m),
                         note="too few matched units")); continue
    wcol = "mean_WRSI" if "mean_WRSI" in m.columns else ("wrsi_grf" if "wrsi_grf" in m else None)
    r = dict(crop=crop, country=country, season=season, n=len(m),
             irr_max_pct=m.irrigated_pct.max(), cpi_range=f"{m.cpi.min():g}-{m.cpi.max():g}")
    if m.irrigated_pct.nunique() < 3:
        r["note"] = "irrigated share near-constant across units"
    elif m.cpi.nunique() < 2:
        r["note"] = f"CPI constant at {m.cpi.iloc[0]:g} - rho undefined"
    else:
        rc, pc = spearmanr(m.cpi, m.irrigated_pct)
        r.update(rho_cpi=round(rc, 3), p_cpi=round(pc, 4))
    if wcol and m.irrigated_pct.nunique() >= 3 and m[wcol].nunique() >= 2:
        rw, pw = spearmanr(m[wcol], m.irrigated_pct)
        r.update(rho_wrsi=round(rw, 3), p_wrsi=round(pw, 4))
    rows.append(r)

d = pd.DataFrame(rows)
d.to_csv(f"{H}/cpi_vs_irrigation.csv", index=False)
cols = ["crop", "country", "season", "n", "irr_max_pct", "rho_cpi", "p_cpi", "rho_wrsi", "p_wrsi",
        "note"]
for c in cols:
    if c not in d.columns:
        d[c] = None
print("=== all products with a testable irrigated gradient ===")
t = d[d.irr_max_pct.notna() & (d.irr_max_pct >= 5)].sort_values("irr_max_pct", ascending=False)
print(t[cols].to_string(index=False))
print("\n=== significant at p < 0.05 ===")
s = d[d.p_cpi.notna() & (d.p_cpi < 0.05)]
print(s[cols].to_string(index=False) if len(s) else "  NONE on CPI")
s2 = d[d.p_wrsi.notna() & (d.p_wrsi < 0.05)]
print("\n=== significant on WRSI at p < 0.05 ===")
print(s2[cols].to_string(index=False) if len(s2) else "  NONE on WRSI")
print(f"\nwritten: {H}/cpi_vs_irrigation.csv")
