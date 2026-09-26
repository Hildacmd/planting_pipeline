#!/usr/bin/env python3
"""Is the pipeline's reported crop condition ANTI-correlated with irrigation?

If the admin units SPAM says are irrigated are the same units the rainfed balance reports as
failing, then for those products CPI is measuring irrigation dependence rather than crop condition.
Spearman rho over admin-1 units, per product.
"""
import os
import pandas as pd
from scipy.stats import spearmanr

H = os.path.dirname(os.path.abspath(__file__))
P = os.path.dirname(os.path.dirname(H))
IRR = pd.read_csv(f"{H}/spam2020_irrigated_admin1.csv")
PRODUCTS = [("newcM_Sudan_Kharif_2024", "Sudan", "maize", "maize Kharif"),
            ("newcS_Sudan_Kharif_2024", "Sudan", "sorghum", "sorghum Kharif"),
            ("newcW_Sudan_Shitwi_2024", "Sudan", "wheat", "wheat Shitwi"),
            ("newc_Somalia_Gu_2024", "Somalia", "maize", "maize Gu"),
            ("newc_Somalia_Deyr_2024", "Somalia", "maize", "maize Deyr"),
            ("newcS_Somalia_Gu_2024", "Somalia", "sorghum", "sorghum Gu"),
            ("newcS_Somalia_Deyr_2024", "Somalia", "sorghum", "sorghum Deyr"),
            ("newcS_South_Sudan_Main_2024", "South_Sudan", "sorghum", "sorghum Main")]

print(f"{'product':28s} {'n':>3s} {'rho(CPI,irr%)':>14s} {'p':>7s} {'rho(WRSI,irr%)':>15s}"
      f" {'irr max%':>9s}")
print("-" * 82)
rows = []
for stem, country, crop, label in PRODUCTS:
    f = f"{P}/{stem}_L1_skill_WKT.csv"
    if not os.path.exists(f):
        print(f"{country} {label:20s}  -- no L1 CSV"); continue
    d = pd.read_csv(f)
    i = IRR[(IRR.country == country) & (IRR.crop == crop)][["admin1", "irrigated_pct"]]
    m = d.merge(i, left_on="name", right_on="admin1", how="inner")
    if len(m) < 4 or m.irrigated_pct.nunique() < 3:
        print(f"{country} {label:20s} {len(m):3d}   too few/constant units"); continue
    rc, pc = spearmanr(m.cpi, m.irrigated_pct)
    wcol = "mean_WRSI" if "mean_WRSI" in m.columns else "wrsi_grf"
    rw, _ = spearmanr(m[wcol], m.irrigated_pct)
    print(f"{country+' '+label:28s} {len(m):3d} {rc:14.3f} {pc:7.3f} {rw:15.3f}"
          f" {m.irrigated_pct.max():9.1f}")
    rows.append(dict(country=country, product=label, n=len(m), rho_cpi=round(rc, 3),
                     p_cpi=round(pc, 4), rho_wrsi=round(rw, 3),
                     max_irrigated_pct=m.irrigated_pct.max()))
pd.DataFrame(rows).to_csv(f"{H}/cpi_vs_irrigation.csv", index=False)
print(f"\nNegative rho = the units SPAM calls irrigated are the units the pipeline calls failing.")
print(f"written: {H}/cpi_vs_irrigation.csv")
