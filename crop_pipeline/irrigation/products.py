#!/usr/bin/env python3
"""The REAL product inventory, enumerated from the reduce CSVs on disk.

Driven by the files rather than by the calendars, because the calendars list country-crop-season
rows that were never built (config/season_calendar.csv carries a Sudan Maize Kharif row; no Sudan
maize product exists). The prefix fixes the crop and must match app_data.py exactly:

    planting_ = maize (Kenya, Ethiopia)   newc_  = maize     newcS_ = sorghum
    newcW_    = wheat                     newcT_ = teff      newcM_ = millet
"""
import glob, os, re

P = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
PREFIX_CROP = [("newcS_", "sorghum"), ("newcW_", "wheat"), ("newcT_", "teff"),
               ("newcM_", "millet"), ("newc_", "maize")]     # longest first: newc_ must come last
COUNTRIES = ["South_Sudan", "SouthSudan", "South Sudan", "Ethiopia", "Tanzania", "Somalia", "Burundi",
             "Eritrea", "Rwanda", "Uganda", "Sudan", "Kenya", "Djibouti"]


def _split(token):
    for c in COUNTRIES:                                   # longest match first (South_Sudan vs Sudan)
        if token == c or token.startswith(c + "_"):
            return c.replace("SouthSudan", "South_Sudan").replace(" ", "_"), token[len(c):].strip("_")
    return token, ""


def inventory():
    """[{crop, country, season, stem, csv}] for every product with an L1 reduce CSV."""
    out = []
    for f in sorted(glob.glob(f"{P}/*_L1_skill_WKT.csv")):
        b = os.path.basename(f)
        stem = b[:-len("_L1_skill_WKT.csv")]
        if stem.startswith("planting_"):                  # planting_<Country>_maize_<Season>_<year>...
            m = re.match(r"planting_([A-Za-z_]+?)_maize_([A-Za-z]+)_(\d{4})", stem)
            if not m:
                continue
            if "_250m" in stem and stem.replace("_250m", "") + "_L1_skill_WKT.csv" in os.listdir(P):
                pass                                      # keep both; deduped by (crop,country,season)
            out.append(dict(crop="maize", country=m.group(1), season=m.group(2), stem=stem, csv=f))
            continue
        for pfx, crop in PREFIX_CROP:
            if stem.startswith(pfx):
                tok = stem[len(pfx):]
                tok = re.sub(r"_\d{4}$", "", tok)
                country, season = _split(tok)
                out.append(dict(crop=crop, country=country, season=season, stem=stem, csv=f))
                break
    # one entry per (crop, country, season) — prefer the plainest stem (no _250m/_rainfed suffix)
    best = {}
    for r in out:
        k = (r["crop"], r["country"], r["season"])
        if k not in best or len(r["stem"]) < len(best[k]["stem"]):
            best[k] = r
    return sorted(best.values(), key=lambda r: (r["crop"], r["country"], r["season"]))


if __name__ == "__main__":
    inv = inventory()
    from collections import Counter
    print(f"{len(inv)} products")
    for c, n in sorted(Counter(r['crop'] for r in inv).items()):
        print(f"  {c:8s} {n}")
    print()
    for r in inv:
        print(f"  {r['crop']:8s} {r['country']:12s} {r['season']:12s} {r['stem']}")
