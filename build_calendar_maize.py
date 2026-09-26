#!/usr/bin/env python3
"""Give the maize crop calendar the provenance record the sorghum one has.

`config/season_calendar.csv` is hand-maintained. It drives every maize product, yet it carries no
record of where each window came from and no cross-check against an independent source, so there
is no way to tell a window that was read off a national extension calendar from one that was
inferred. The sorghum calendar is generated from the Inception Report and ships a `cm4ew_*`
comparison column; this does the same for maize.

Three sources, side by side:

  operative   config/season_calendar.csv, what the pipeline actually runs
  report      Inception Report Table 2.0 (pp. 16-17), planting months per country and season
  cm4ew       GEOGLAM Crop Monitor for Early Warning v1.3, the MAIZE-specific calendar

**This script does not touch the operative calendar.** Changing it would silently move every maize
product, and the disagreements below are a question for national partners, not something to resolve
from a desk. It writes a comparison table and prints the disagreements.

    python build_calendar_maize.py
"""
import datetime as dt, os, sys
import geopandas as gpd, pandas as pd

H = os.path.dirname(os.path.abspath(__file__))
SHP = sys.argv[1] if len(sys.argv) > 1 else (
    "/tmp/geoglam/GEOGLAM_CM4EW_Calendars_V1.3/GEOGLAM_CM4EW_Calendars_V1.3.shp")
MON = {m: i + 1 for i, m in enumerate(
    ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"])}

# Inception Report Table 2.0, the planting months of each maize season it lists.
#
# INFERRED entries are marked. Table 2.0 gives ONE planting column per country, so where a country
# has two seasons the published months cover the dominant one and the other has to be inferred.
# The rule used is: planting occupies the first two months of the season span given in the "Main
# season(s)" column. That is an assumption, not a source, and a window derived this way must not
# be reported as a disagreement with the operative calendar - it is a disagreement with a guess.
INFERRED = {("South Sudan", "2nd")}
REPORT = {
    ("Sudan", "Kharif"):        ("Jun", "Jul"),
    ("South Sudan", "Main"):    ("Apr", "Jun"),
    ("South Sudan", "2nd"):     ("Jul", "Aug"),   # INFERRED: Table 2.0 gives only "Apr-Jun" for
                                                  # the country and "2nd Jul-Nov (SW)" as the span
    ("Eritrea", "Kremti"):      ("Jun", "Jul"),
    ("Ethiopia", "Meher"):      ("Jun", "Jul"),
    ("Ethiopia", "Belg"):       ("Feb", "Mar"),
    ("Somalia", "Gu"):          ("Apr", "Apr"),
    ("Somalia", "Deyr"):        ("Oct", "Oct"),
    ("Uganda", "1st rains"):    ("Mar", "Apr"),
    ("Uganda", "2nd rains"):    ("Sep", "Sep"),
    ("Kenya", "Long rains"):    ("Mar", "Apr"),
    ("Kenya", "Short rains"):   ("Oct", "Oct"),
    ("Tanzania", "Msimu"):      ("Nov", "Dec"),
    ("Tanzania", "Masika"):     ("Mar", "Mar"),
    ("Tanzania", "Vuli"):       ("Oct", "Oct"),
    ("Rwanda", "Season A"):     ("Sep", "Sep"),
    ("Rwanda", "Season B"):     ("Feb", "Mar"),
    ("Burundi", "Season A"):    ("Sep", "Sep"),
    ("Burundi", "Season B"):    ("Feb", "Feb"),
}
# GEOGLAM (country, crop) -> the season this pipeline calls it. CM4EW numbers the seasons by
# calendar order, so "Maize 1" is the FIRST of the year, which for the bimodal highlands is the
# season this pipeline calls B, not A.
CM4EW_SEASON = {
    ("Burundi", "Maize 1"): "Season B",   ("Burundi", "Maize 2"): "Season A",
    ("Rwanda", "Maize 1"): "Season B",    ("Rwanda", "Maize 2"): "Season A",
    ("Ethiopia", "Maize 1"): "Meher",     ("Ethiopia", "Maize 2"): "Belg",
    ("Kenya", "Maize 1"): "Long rains",   ("Kenya", "Maize 2"): "Short rains",
    ("Somalia", "Maize 1"): "Gu",         ("Somalia", "Maize 2"): "Deyr",
    ("South Sudan", "Maize 1"): "Main",   ("South Sudan", "Maize 2"): "2nd",
    ("Uganda", "Maize 1"): "1st rains",   ("Uganda", "Maize 2"): "2nd rains",
}


def doy_to_dekad(doy, year=2001):
    d = dt.date(year, 1, 1) + dt.timedelta(days=int(doy) - 1)
    return (d.month - 1) * 3 + (1 if d.day <= 10 else 2 if d.day <= 20 else 3)


def tok(dk):
    dk = ((int(dk) - 1) % 36) + 1
    m, k = (dk - 1) // 3 + 1, (dk - 1) % 3 + 1
    return f"{dt.date(2001, m, 1):%b}-d{k}"


def win(a, b):
    return f"{tok(a)}-{tok(b)}"


def month_dekads(a, b):
    s = (MON[a] - 1) * 3 + 1
    e = (MON[b] - 1) * 3 + 3
    return s, (e + 36 if e < s else e)


def dekad_of(t):
    m, k = t.split("-d")
    return (MON[m] - 1) * 3 + int(k)


def gap(w1, w2):
    """Dekads between the START of two windows; None if either is missing."""
    if not w1 or not w2:
        return None
    return dekad_of(w2.split("-")[0] + "-" + w2.split("-")[1]) - \
           dekad_of(w1.split("-")[0] + "-" + w1.split("-")[1])


def main():
    op = pd.read_csv(f"{H}/config/season_calendar.csv")
    op = op[op.crop.str.lower() == "maize"]

    cm = {}
    try:
        g = gpd.read_file(SHP)
        s = g[g.crop.str.startswith("Maize", na=False)]
        s = s[(s.planting > 0) & (s.vegetative > 0)]
        for (country, crop), d in s.groupby(["country", "crop"]):
            season = CM4EW_SEASON.get((country, crop))
            if season is None:
                continue
            pl, vg = int(d.planting.mode().iat[0]), int(d.vegetative.mode().iat[0])
            cm[(country, season)] = dict(
                window=win(doy_to_dekad(pl), doy_to_dekad(vg - 1)), regions=d.region.nunique())
    except Exception as e:
        print(f"(GEOGLAM not read: {e})")

    rows = []
    for _, r in op.iterrows():
        c, s = r["country"], r["season"]
        rep = REPORT.get((c, s))
        repw = win(*month_dekads(*rep)) if rep else ""
        cmw = cm.get((c, s), {}).get("window", "")
        rows.append(dict(
            country=c, season=s, crop_viability=r["crop_viability"],
            report_source=("inferred from the season span" if (c, s) in INFERRED
                           else "Table 2.0" if rep else "not in Table 2.0"),
            operative_planting=r["indicative_planting_window"],
            operative_sos=r["sos_detection_window"],
            report_planting=repw, cm4ew_planting=cmw,
            cm4ew_regions=cm.get((c, s), {}).get("regions", ""),
            gap_report_dekads=gap(r["indicative_planting_window"], repw),
            gap_cm4ew_dekads=gap(r["indicative_planting_window"], cmw),
            notes=r.get("notes", "")))
    out = pd.DataFrame(rows)
    p = f"{H}/config/season_calendar_maize_provenance.csv"
    out.to_csv(p, index=False)

    show = ["country", "season", "crop_viability", "operative_planting",
            "report_planting", "report_source", "cm4ew_planting",
            "gap_report_dekads", "gap_cm4ew_dekads"]
    print(out[show].to_string(index=False))
    print(f"\n{len(out)} maize products -> {p}")

    # A gap against an INFERRED window is a gap against an assumption, so it is reported
    # separately and never counted as a source disagreement.
    pub = out.report_source != "inferred from the season span"
    big = out[(out.gap_cm4ew_dekads.abs() >= 2) | (pub & (out.gap_report_dekads.abs() >= 2))]
    inf = out[~pub]
    nocm = out[out.cm4ew_planting == ""]
    print(f"\nDISAGREEMENTS of 2 dekads or more: {len(big)} of {len(out)}")
    for _, r in big.iterrows():
        src = []
        if pd.notna(r.gap_report_dekads) and abs(r.gap_report_dekads) >= 2:
            src.append(f"report {r.gap_report_dekads:+.0f}")
        if pd.notna(r.gap_cm4ew_dekads) and abs(r.gap_cm4ew_dekads) >= 2:
            src.append(f"CM4EW {r.gap_cm4ew_dekads:+.0f}")
        print(f"   {r.country} {r.season}: operative {r.operative_planting}  ({', '.join(src)})")
    for _, r in inf.iterrows():
        print(f"\nINFERRED, not a source disagreement: {r.country} {r.season}. Table 2.0 gives no "
              f"planting months for this season; {r.report_planting} is this script's assumption "
              f"that planting fills the first two months of the season span. GEOGLAM, which does "
              f"publish it, gives {r.cm4ew_planting or 'nothing'} "
              f"({'agrees with' if r.gap_cm4ew_dekads == 0 else 'differs from'} the operative "
              f"window).")
    if len(nocm):
        print(f"\nNo GEOGLAM maize calendar to check against ({len(nocm)}): "
              f"{', '.join(sorted(set(nocm.country + ' ' + nocm.season)))}")
    print("\nThe operative calendar is NOT modified. A window that is wrong by three dekads puts "
          "flowering, which carries the yield weight, in the wrong part of the season, so these "
          "are questions for national partners rather than desk fixes.")


if __name__ == "__main__":
    main()
