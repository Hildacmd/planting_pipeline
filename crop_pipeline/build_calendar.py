#!/usr/bin/env python3
"""Season calendars for wheat, teff and millet, restricted to what the crop-type masks support.

A product needs BOTH a crop-type mask band and a parseable season window. Where those disagree the
mask wins, because a calendar row without a mask cannot be computed at all.

  wheat   `config/season_calendar.csv` already carries wheat rows; the mask covers 6 countries
  teff    the same, Ethiopia only
  millet  NO calendar rows exist. Built here from GEOGLAM CM4EW `Millet 1` where it monitors the
          country, and from Inception Report Table 2.0 otherwise.

GEOGLAM's window is carried alongside in `cm4ew_*` for every crop, as for sorghum, so a
disagreement is visible rather than silently resolved.

    python crop_pipeline/build_calendar.py
"""
import datetime as dt, os, sys
import geopandas as gpd, pandas as pd

H = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(H)
sys.path.insert(0, ROOT); sys.path.insert(0, H)
from params import get                                                # noqa: E402

SHP = "/tmp/geoglam/GEOGLAM_CM4EW_Calendars_V1.3/GEOGLAM_CM4EW_Calendars_V1.3.shp"
MON = {m: i + 1 for i, m in enumerate(
    ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"])}

# Millet has no rows in the operative calendar. Sudan from GEOGLAM Millet 1 (planting DOY 152,
# vegetative 213); Eritrea from Table 2.0, which lists pearl millet with a Jun-Jul planting.
MILLET = [
    ("Sudan",   "Kharif", "Jun-d1-Jul-d3", "Jun-d2-Aug-d3", 15, "High",
     "GEOGLAM CM4EW Millet 1; 2.278 Mha, the largest millet area in the region"),
    ("Eritrea", "Kremti", "Jun-d1-Jul-d3", "Jun-d2-Aug-d3", 14, "Medium",
     "Inception Report Table 2.0 (Eritrea: sorghum, pearl millet, barley); GEOGLAM does not "
     "monitor Eritrean millet; 0.030 Mha, uncalibratable (Eritrea absent from HarvestStat)"),
]
# GEOGLAM crop label -> the crop this pipeline calls it
CM4EW_CROP = {"wheat": "Winter Wheat", "teff": "Teff 1", "millet": "Millet 1"}


def doy_to_dekad(doy, year=2001):
    d = dt.date(year, 1, 1) + dt.timedelta(days=int(doy) - 1)
    return (d.month - 1) * 3 + (1 if d.day <= 10 else 2 if d.day <= 20 else 3)


def tok(dk):
    dk = ((int(dk) - 1) % 36) + 1
    m, k = (dk - 1) // 3 + 1, (dk - 1) % 3 + 1
    return f"{dt.date(2001, m, 1):%b}-d{k}"


def win(a, b):
    return f"{tok(a)}-{tok(b)}"


def parseable(w):
    """A combined two-season string such as 'Sep-d2-Oct / Feb-Mar' cannot be parsed."""
    return isinstance(w, str) and "/" not in w and w.count("-") == 3 and "d" in w


def cm4ew_windows():
    out = {}
    try:
        g = gpd.read_file(SHP)
    except Exception as e:
        print(f"(GEOGLAM not read: {e})"); return out
    for crop, label in CM4EW_CROP.items():
        s = g[(g.crop == label) & (g.planting > 0) & (g.vegetative > 0)]
        for country, d in s.groupby("country"):
            pl, vg = int(d.planting.mode().iat[0]), int(d.vegetative.mode().iat[0])
            out[(crop, country.replace(" ", "_"))] = win(doy_to_dekad(pl), doy_to_dekad(vg - 1))
    return out


def main():
    cal = pd.read_csv(f"{ROOT}/config/season_calendar.csv")
    cm = cm4ew_windows()
    rows, dropped = [], []

    for crop in ("wheat", "teff", "millet"):
        p = get(crop)
        masked = p.MASK_COUNTRIES
        if crop == "millet":
            src = [(c, s, pw, sw, cyc, v, n) for c, s, pw, sw, cyc, v, n in MILLET]
            for c, s, pw, sw, cyc, v, n in src:
                rows.append(dict(crop=crop, country=c, season=s, indicative_planting_window=pw,
                                 sos_detection_window=sw, cycle_dekads=cyc, crop_viability=v,
                                 crop_calendar_source=("GEOGLAM_CM4EW_v1.3" if c == "Sudan"
                                                       else "InceptionReport_Table2.0"),
                                 mapped_area_Mha=masked.get(c), notes=n,
                                 cm4ew_planting=cm.get((crop, c), "")))
            continue
        d = cal[cal.crop.str.lower() == crop]
        for _, r in d.iterrows():
            c = r["country"].replace(" ", "_")
            if c not in masked:
                dropped.append((crop, c, r["season"], "no crop-type mask band")); continue
            if not parseable(r["sos_detection_window"]):
                dropped.append((crop, c, r["season"],
                                f"calendar row is a combined two-season string "
                                f"({r['sos_detection_window']})")); continue
            if r["crop_viability"] not in ("High", "Medium"):
                dropped.append((crop, c, r["season"], f"viability {r['crop_viability']}")); continue
            rows.append(dict(crop=crop, country=c, season=r["season"],
                             indicative_planting_window=r["indicative_planting_window"],
                             sos_detection_window=r["sos_detection_window"],
                             cycle_dekads=p.KC["LGP_dekads"], crop_viability=r["crop_viability"],
                             crop_calendar_source="operative season_calendar.csv",
                             mapped_area_Mha=masked.get(c), notes=r.get("notes", ""),
                             cm4ew_planting=cm.get((crop, c), "")))

    out = pd.DataFrame(rows).sort_values(["crop", "country", "season"])
    p_ = f"{H}/config/season_calendar_wtm.csv"
    out.to_csv(p_, index=False)
    print(out[["crop", "country", "season", "indicative_planting_window", "sos_detection_window",
               "cycle_dekads", "crop_viability", "mapped_area_Mha", "cm4ew_planting"]]
          .to_string(index=False))
    print(f"\n{len(out)} products -> {p_}")
    for crop in ("wheat", "teff", "millet"):
        p = get(crop)
        got = out[out.crop == crop].mapped_area_Mha.sum()
        tot = sum(p.MASK_COUNTRIES.values())
        print(f"  {crop:<8} {len(out[out.crop==crop])} products covering "
              f"{got:.3f} of {tot:.3f} Mha mapped ({100*got/tot:.0f} %)")
    if dropped:
        print(f"\nNOT BUILT ({len(dropped)}):")
        for cr, c, s, why in dropped:
            print(f"   {cr:<8}{c} {s}: {why}")


if __name__ == "__main__":
    main()
