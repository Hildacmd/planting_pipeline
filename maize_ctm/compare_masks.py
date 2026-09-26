#!/usr/bin/env python3
"""WorldCereal vs the ICPAC crop-type mask: what changed, and does it matter?

The shipped 2024 maize products (`newc_*`, `planting_*`) are computed inside the ESA WorldCereal
2021 maize layer. The `newcCTM_*` products are the SAME 16 products with the SAME water balance,
stresses, Ky, heat cap and yield ceiling - only the set of pixels changed. Any difference is
therefore attributable to the mask alone.

This reports three things, because they answer different questions:

  1. LEVEL    does the mask move CPI / yield / stress up or down, and by how much?
  2. PATTERN  does it re-rank the admin units? Spearman rho between the two rankings. A high rho
              with a level shift means the mask changes the number but not the story; a low rho
              means it changes which units look worst, which is what an early-warning product is
              actually for.
  3. FOOTPRINT `caf_wc` vs `caf_ctm` - the crop-area fraction each mask assigns to the unit.

A WARNING ABOUT THE FOOTPRINT COLUMNS. `crop_area_frac` is computed at REDUCE time, not stored in
the raster, so it reflects whatever mask the reducer was told to measure over - not necessarily the
mask the product was computed in. Until 26 Sep 2026 `reduce_newcountries._crop_mask` hard-coded
WorldCereal for every maize product, so both sides of this comparison carried the identical
WorldCereal fraction and the footprint columns were silently meaningless (they agreed to four
decimals for all 13 products, which is the giveaway). `--caf-source` now defaults to following the
product's own mask. **If caf_wc and caf_ctm are identical, the CSVs predate that fix: re-reduce the
cpiCTMX_ products before reading the footprint columns.** The level and pattern results above do not
depend on CAF and were unaffected.

A mask change that only moves the level can be absorbed by re-fitting Ym. One that re-ranks units
cannot, and it is the one that matters.

    python maize_ctm/compare_masks.py
    python maize_ctm/compare_masks.py --col cpi --out maize_ctm/mask_comparison.csv
"""
import argparse, glob, os, sys
import numpy as np, pandas as pd
from scipy.stats import spearmanr, wilcoxon

H = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(H)

# WorldCereal stem -> crop-type-mask stem, for the same product
PAIRS = [("newc_Uganda_1strains_2024",   "newcCTM_Uganda_1strains_2024"),
         ("newc_Uganda_2ndrains_2024",   "newcCTM_Uganda_2ndrains_2024"),
         ("newc_Rwanda_SeasonA_2024",    "newcCTM_Rwanda_SeasonA_2024"),
         ("newc_Rwanda_SeasonB_2024",    "newcCTM_Rwanda_SeasonB_2024"),
         ("newc_Tanzania_Msimu_2024",    "newcCTM_Tanzania_Msimu_2024"),
         ("newc_Tanzania_Vuli_2024",     "newcCTM_Tanzania_Vuli_2024"),
         ("newc_Tanzania_Masika_2024",   "newcCTM_Tanzania_Masika_2024"),
         ("newc_Burundi_SeasonA_2024",   "newcCTM_Burundi_SeasonA_2024"),
         ("newc_Burundi_SeasonB_2024",   "newcCTM_Burundi_SeasonB_2024"),
         ("newc_Somalia_Gu_2024",        "newcCTM_Somalia_Gu_2024"),
         ("newc_Somalia_Deyr_2024",      "newcCTM_Somalia_Deyr_2024"),
         ("newc_SouthSudan_Main_2024",   "newcCTM_SouthSudan_Main_2024"),
         ("newc_Ethiopia_Belg_2024",     "newcCTM_Ethiopia_Belg_2024"),
         ("planting_Ethiopia_maize_Meher_2024_250m",  "newcCTM_Ethiopia_Meher_2024"),
         ("planting_Kenya_maize_Longrains_2024",      "newcCTM_Kenya_Longrains_2024"),
         ("planting_Kenya_maize_Shortrains_2024_250m", "newcCTM_Kenya_Shortrains_2024")]


def load(stem, lvl):
    f = f"{ROOT}/{stem}_L{lvl}_skill_WKT.csv"
    if not os.path.exists(f):
        return None
    d = pd.read_csv(f)
    return d if "name" in d.columns else None


def compare(col, lvl):
    rows = []
    for wc_stem, ctm_stem in PAIRS:
        a, b = load(wc_stem, lvl), load(ctm_stem, lvl)
        if a is None or b is None:
            rows.append(dict(product=ctm_stem, note="missing " +
                             ("WorldCereal" if a is None else "crop-type-mask") + " CSV"))
            continue
        if col not in a.columns or col not in b.columns:
            rows.append(dict(product=ctm_stem, note=f"no '{col}' column")); continue
        m = a[["name", col] + [c for c in ("crop_area_frac", "n_px") if c in a.columns]].merge(
            b[["name", col] + [c for c in ("crop_area_frac", "n_px") if c in b.columns]],
            on="name", suffixes=("_wc", "_ctm"))
        m = m.dropna(subset=[f"{col}_wc", f"{col}_ctm"])
        if len(m) < 4:
            rows.append(dict(product=ctm_stem, n=len(m), note="too few matched units")); continue
        wc, ctm = m[f"{col}_wc"].astype(float), m[f"{col}_ctm"].astype(float)
        d = ctm - wc
        r = dict(product=ctm_stem.replace("newcCTM_", "").replace("_2024", ""), n=len(m),
                 wc_mean=round(wc.mean(), 2), ctm_mean=round(ctm.mean(), 2),
                 delta_mean=round(d.mean(), 2),
                 delta_abs_med=round(d.abs().median(), 2))
        if wc.nunique() > 2 and ctm.nunique() > 2:
            rho, p = spearmanr(wc, ctm)
            r["rho_rank"] = round(rho, 3); r["p_rho"] = round(p, 4)
        if d.abs().sum() > 0 and len(m) >= 6:
            try:
                r["p_shift"] = round(wilcoxon(wc, ctm).pvalue, 4)   # is the level shift real?
            except ValueError:
                pass
        for s, lab in (("_wc", "caf_wc"), ("_ctm", "caf_ctm")):
            c = f"crop_area_frac{s}"
            if c in m.columns:
                r[lab] = round(float(m[c].astype(float).mean()), 4)
        rows.append(r)
    return pd.DataFrame(rows)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--col", default="cpi")
    ap.add_argument("--level", type=int, default=1)
    ap.add_argument("--out", default=f"{H}/mask_comparison.csv")
    a = ap.parse_args()

    print(f"=== WorldCereal vs ICPAC crop-type mask · '{a.col}' at admin-{a.level} ===")
    print("Same balance, same parameters, same Ym. Only the mask differs.\n")
    d = compare(a.col, a.level)
    cols = [c for c in ("product", "n", "wc_mean", "ctm_mean", "delta_mean", "delta_abs_med",
                        "rho_rank", "p_rho", "p_shift", "caf_wc", "caf_ctm", "note")
            if c in d.columns]
    print(d[cols].to_string(index=False))
    d.to_csv(a.out, index=False)

    if {"caf_wc", "caf_ctm"} <= set(d.columns):
        both = d.dropna(subset=["caf_wc", "caf_ctm"])
        if len(both) and (both.caf_wc == both.caf_ctm).all():
            print("\n  !! caf_wc == caf_ctm for every product — the footprint columns are NOT")
            print("     measuring the two masks. These CSVs predate the --caf-source fix; re-reduce")
            print("     the cpiCTMX_ products. Level and pattern below are unaffected.")

    ok = d[d.get("rho_rank").notna()] if "rho_rank" in d.columns else d.iloc[0:0]
    if len(ok):
        print(f"\n=== verdict over {len(ok)} comparable products ===")
        print(f"  level   : mean change in {a.col} = {ok.delta_mean.mean():+.2f} "
              f"(median |change| per unit {ok.delta_abs_med.median():.2f})")
        print(f"  pattern : Spearman rho between the two rankings, median {ok.rho_rank.median():.3f}"
              f"  (range {ok.rho_rank.min():.3f} to {ok.rho_rank.max():.3f})")
        reranked = ok[ok.rho_rank < 0.8]
        if len(reranked):
            print(f"  RE-RANKED (rho < 0.8) in {len(reranked)} product(s) — the mask changes which "
                  f"units look worst, which re-fitting Ym cannot absorb:")
            for x in reranked.itertuples():
                print(f"      {x.product:26s} rho {x.rho_rank:.3f}  n {x.n}")
        else:
            print("  no product re-ranked below rho 0.8 — the mask moves the level, not the story,")
            print("  so the change is absorbable by re-fitting Ym.")
    print(f"\nwritten: {a.out}")


if __name__ == "__main__":
    main()
