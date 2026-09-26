#!/usr/bin/env python3
"""Fill a tier-2 column at admin-1 by rolling its admin-2 values up, area-weighted.

Some admin-1 reduces cannot be computed directly: Sudan millet FCCI fails with "User memory limit
exceeded" at every scale and batch size the retry ladder tries, because FCCI rebuilds the S2/S1/FPAR
fusion and Sudan's states are enormous. It is not contention - it fails the same way running alone.
The admin-2 reduce over the same country succeeds (43/43 localities), because the polygons are small.

FCCI, SPI-3 and deficit are all area-mean quantities, so the admin-1 value IS the crop-area-weighted
mean of its admin-2 units. Rolling up is therefore the correct definition rather than a substitute
for it - PROVIDED the admin-2 units cover the state. This records that: it writes a companion
`<col>_source` column marking every value as `direct` or `rollup_L2`, refuses any admin-1 unit whose
children are missing, and prints the coverage so a thin rollup is visible rather than silent.

    python tier2_rollup.py newcM_Sudan_Kharif_2024 --col fcci
    python tier2_rollup.py newcM_Sudan_Kharif_2024 --col fcci --apply
"""
import argparse
import numpy as np, pandas as pd


def rollup(stem, col, apply=False):
    f1, f2 = f"{stem}_L1_skill_WKT.csv", f"{stem}_L2_skill_WKT.csv"
    d1, d2 = pd.read_csv(f1), pd.read_csv(f2)
    if col not in d2.columns or d2[col].notna().sum() == 0:
        return print(f"  L2 has no {col} to roll up — nothing to do")
    have1 = d1[col].notna().sum() if col in d1.columns else 0
    print(f"  L1 {col}: {have1}/{len(d1)} direct · L2 {col}: {d2[col].notna().sum()}/{len(d2)}")

    # crop-area weight: pixels x crop fraction. Falls back to pixel count, then to equal weights.
    w = pd.Series(1.0, index=d2.index)
    if "n_px" in d2.columns:
        w = d2["n_px"].astype(float).fillna(0)
        if "crop_area_frac" in d2.columns:
            w = w * d2["crop_area_frac"].astype(float).fillna(0)
    if w.sum() <= 0:
        w = pd.Series(1.0, index=d2.index)
    d2 = d2.assign(_w=w)

    ok = d2[d2[col].notna() & (d2._w > 0)]
    g = (ok.groupby("county")
           .apply(lambda x: np.average(x[col].astype(float), weights=x._w), include_groups=False)
           .rename(col + "_rollup").reset_index())

    # refuse a parent whose children are incomplete - a partial rollup is a wrong number
    cnt = d2.groupby("county")[col].agg(["size", "count"]).reset_index()
    partial = set(cnt[cnt["size"] != cnt["count"]].county)
    if partial:
        print(f"  ! {len(partial)} parent(s) have admin-2 units missing {col}; not rolled up: "
              f"{', '.join(sorted(partial))}")
        g = g[~g.county.isin(partial)]

    m = d1.merge(g, left_on="name", right_on="county", how="left")
    src = pd.Series("direct", index=d1.index).where(
        d1[col].notna() if col in d1.columns else False, other=None)
    fill = m[col + "_rollup"]
    if col not in d1.columns:
        d1[col] = np.nan
    take = d1[col].isna() & fill.notna()
    print(f"  would fill {int(take.sum())} of {int(d1[col].isna().sum())} empty L1 rows by rollup")
    unmatched = sorted(set(g.county) - set(d1["name"]))
    if unmatched:
        print(f"  ! {len(unmatched)} L2 parent(s) match no L1 row: {', '.join(unmatched)}")
    if not apply:
        print("  (dry run — add --apply)")
        return
    d1.loc[take, col] = fill[take].round(1)
    d1[col + "_source"] = np.where(take, "rollup_L2", np.where(d1[col].notna(), "direct", None))
    d1.to_csv(f1, index=False)
    print(f"  wrote {f1}: {col} now {d1[col].notna().sum()}/{len(d1)} "
          f"({int(take.sum())} by rollup, marked in {col}_source)")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("stem"); ap.add_argument("--col", default="fcci")
    ap.add_argument("--apply", action="store_true")
    a = ap.parse_args()
    print(f"== {a.stem} · {a.col} ==")
    rollup(a.stem, a.col, a.apply)
