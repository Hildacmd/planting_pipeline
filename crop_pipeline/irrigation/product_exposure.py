#!/usr/bin/env python3
"""Per-PRODUCT irrigation exposure: joins every calendar row in the pipeline to its country-crop
irrigated share, and grades it. This is the table the methodology note reports."""
import os
import pandas as pd

H = os.path.dirname(os.path.abspath(__file__))
P = os.path.dirname(os.path.dirname(H))
SH = pd.read_csv(f"{H}/spam2020_irrigated_share.csv")
A1 = pd.read_csv(f"{H}/spam2020_irrigated_admin1.csv")
CROPMAP = {"teff": "teff (via other cereals)"}

cal = []
for f, crop_col in [("crop_pipeline/config/season_calendar_wtm.csv", "crop"),
                    ("sorghum_pipeline/config/season_calendar_sorghum.csv", "crop"),
                    ("config/season_calendar.csv", "crop")]:
    d = pd.read_csv(f"{P}/{f}")
    d = d[d["indicative_planting_window"].astype(str).str.strip().ne("-")]
    d["crop"] = d[crop_col].str.lower()
    src = "maize" if f.endswith("season_calendar.csv") else ("sorghum" if "sorghum" in f else "wtm")
    # the root calendar is the maize pipeline's; only its Maize rows are built as products
    if src == "maize":
        d = d[d.crop == "maize"]
    cal.append(d[["country", "crop", "season"]].assign(pipeline=src))
cal = pd.concat(cal).drop_duplicates()
cal["ckey"] = cal.country.str.replace(" ", "_")

sh = SH.copy(); sh["ckey"] = sh.country
sh["crop"] = sh.crop.replace({v: k for k, v in CROPMAP.items()})
m = cal.merge(sh[["ckey", "crop", "irrigated_pct", "area_all_ha", "area_irrigated_ha"]],
              on=["ckey", "crop"], how="left")
mx = (A1.assign(ckey=A1.country).groupby(["ckey", "crop"]).irrigated_pct.max()
      .rename("admin1_max_pct").reset_index())
m = m.merge(mx, on=["ckey", "crop"], how="left")


def grade(r):
    n, a = r.irrigated_pct, r.admin1_max_pct
    if pd.isna(n):
        return "unknown"
    if n >= 40:
        return "INVALID as rainfed"
    if n >= 10 or (pd.notna(a) and a >= 50):
        return "materially biased"
    if n >= 2 or (pd.notna(a) and a >= 20):
        return "locally biased"
    return "negligible"


m["exposure"] = m.apply(grade, axis=1)
m = m.sort_values(["irrigated_pct", "country"], ascending=[False, True])
m.to_csv(f"{H}/product_irrigation_exposure.csv", index=False)
print(m[["country", "crop", "season", "irrigated_pct", "admin1_max_pct",
         "exposure"]].to_string(index=False))
print("\n=== product counts by exposure grade ===")
print(m.exposure.value_counts().to_string())
print(f"\ntotal products: {len(m)}")
print(f"written: {H}/product_irrigation_exposure.csv")
