#!/usr/bin/env python3
"""Per-PRODUCT irrigation exposure grade, for the 41 products that actually exist.

Grading weighs AREA, not just percentage. A state that is 95 % irrigated on 71 ha compromises
nothing; a state that is 31 % irrigated on 491,000 ha compromises 152,000 ha. So a unit counts as
compromised only if it is both substantially irrigated AND holds real area.

    compromised unit : irrigated_pct >= 30 AND area_all_ha >= 1000
    INVALID          : national share >= 40 %          - do not report CPI or yield at all
    materially biased: national >= 10 %, or >= 2 compromised units, or >= 50,000 ha irrigated
    locally biased   : >= 1 compromised unit
    negligible       : none of the above
"""
import os, sys
import pandas as pd

H = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, H)
from products import inventory

NAT = pd.read_csv(f"{H}/spam2020_irrigated_share.csv")
NAT["crop"] = NAT.crop.replace({"teff (via other cereals)": "teff"})
A1 = pd.read_csv(f"{H}/spam2020_irrigated_admin1.csv")
RHO = pd.read_csv(f"{H}/cpi_vs_irrigation.csv")

rows = []
for prod in inventory():
    crop, country, season = prod["crop"], prod["country"], prod["season"]
    n = NAT[(NAT.country == country) & (NAT.crop == crop)]
    a = A1[(A1.country == country) & (A1.crop == crop)]
    nat = float(n.irrigated_pct.iloc[0]) if len(n) else float("nan")
    irr_ha = float(a.area_irr_ha.sum()) if len(a) else float("nan")
    comp = a[(a.irrigated_pct >= 30) & (a.area_all_ha >= 1000)]
    ncomp = len(comp)
    if pd.notna(nat) and nat >= 40:
        g = "INVALID as rainfed"
    elif (pd.notna(nat) and nat >= 10) or ncomp >= 2 or (pd.notna(irr_ha) and irr_ha >= 50000):
        g = "materially biased"
    elif ncomp >= 1:
        g = "locally biased"
    else:
        g = "negligible"
    r = RHO[(RHO.crop == crop) & (RHO.country == country) & (RHO.season == season)]
    rows.append(dict(
        crop=crop, country=country, season=season, stem=prod["stem"],
        national_irr_pct=nat, irr_area_ha=None if pd.isna(irr_ha) else int(irr_ha),
        admin1_max_pct=None if not len(a) else a.irrigated_pct.max(),
        n_compromised_units=ncomp,
        compromised_units="; ".join(f"{x.admin1} {x.irrigated_pct:g}%"
                                    for x in comp.sort_values("area_irr_ha", ascending=False)
                                    .itertuples()) or None,
        rho_cpi=None if not len(r) else r.rho_cpi.iloc[0],
        p_cpi=None if not len(r) else r.p_cpi.iloc[0],
        exposure=g))

d = pd.DataFrame(rows).sort_values(
    ["exposure", "national_irr_pct"],
    key=lambda s: s.map({"INVALID as rainfed": 0, "materially biased": 1, "locally biased": 2,
                         "negligible": 3}) if s.name == "exposure" else -s)
d.to_csv(f"{H}/product_irrigation_exposure.csv", index=False)
show = d[d.exposure != "negligible"]
print("=== products carrying irrigation exposure ===")
print(show[["crop", "country", "season", "national_irr_pct", "irr_area_ha", "admin1_max_pct",
            "n_compromised_units", "rho_cpi", "p_cpi", "exposure"]].to_string(index=False))
print("\n=== compromised admin-1 units, per product ===")
for x in show.itertuples():
    if x.compromised_units:
        print(f"  {x.crop:8s} {x.country:12s} {x.season:11s} -> {x.compromised_units}")
print("\n=== counts ===")
print(d.exposure.value_counts().to_string())
print(f"\ntotal products: {len(d)}")
print(f"written: {H}/product_irrigation_exposure.csv")
