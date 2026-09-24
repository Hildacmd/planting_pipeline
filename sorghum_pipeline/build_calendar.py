#!/usr/bin/env python3
"""Build the sorghum season calendar for the ICPAC region.

**Primary source: the Inception Report, Table 2.0** ("Operative crop for phenology clock",
pages 16 to 17), which gives the rainfall regime, main seasons, planting months and harvest
months per country, with the season names FEWS NET and the GEOGLAM Crop Monitor use
operationally. Sorghum is a monitored crop in every one of the ten countries listed there.

    planting window = the report's planting months, as whole dekads
    SOS window      = planting start + 1 dekad .. planting end + 3 dekads
    cycle           = mid-harvest minus mid-planting, in dekads, clamped to 9 .. 18

The SOS rule is the one the maize calendar already uses: green-up follows planting by about a
dekad, and the tail allows for the late end of a staggered planting front.

**GEOGLAM CM4EW v1.3 is carried alongside, not used.** Its shapefile holds a *sorghum-specific*
calendar, where Table 2.0 gives one generalised calendar per country covering all the crops it
monitors. The two disagree for several countries, and those disagreements are written into the
output as `cm4ew_*` columns so they can be put to national partners rather than silently
resolved here. The largest are Kenya (CM4EW starts sorghum planting in February, five dekads
before the report's March) and Ethiopia (CM4EW May against the report's June).

Writes `config/season_calendar_sorghum.csv`.
"""
import datetime as dt, os, sys
import geopandas as gpd, pandas as pd

H = os.path.dirname(os.path.abspath(__file__))
SHP = sys.argv[1] if len(sys.argv) > 1 else (
    "/tmp/geoglam/GEOGLAM_CM4EW_Calendars_V1.3/GEOGLAM_CM4EW_Calendars_V1.3.shp")

MON = {m: i + 1 for i, m in enumerate(
    ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"])}

# ---------------------------------------------------------------------------------------------
# Inception Report Table 2.0, restricted to the seasons in which sorghum is grown.
# (country, season, planting months, harvest months, regime, note)
# Months are inclusive ranges; a harvest range that wraps the year end is handled below.
REPORT_T20 = [
    ("Sudan",       "Kharif",      ("Jun", "Jul"), ("Oct", "Jan"), "Unimodal",
     "Main rains Jun-Sep. Sorghum (dominant), millet, irrigated wheat"),
    ("South_Sudan", "Main",        ("Apr", "Jun"), ("Sep", "Dec"), "Unimodal N / bimodal SW",
     "Main season Apr or Jun to Sep"),
    ("South_Sudan", "2nd",         ("Jul", "Aug"), ("Nov", "Dec"), "Bimodal SW",
     "Second season Jul-Nov in the south west; planting months inferred from the season span"),
    ("Eritrea",     "Kremti",      ("Jun", "Jul"), ("Oct", "Dec"), "Unimodal",
     "Kiremt Jun-Sep. Sorghum, pearl millet, barley"),
    ("Ethiopia",    "Meher",       ("Jun", "Jul"), ("Oct", "Dec"), "Bimodal Belg + Meher",
     "Meher / Kiremt Jun-Sep, the dominant season"),
    ("Ethiopia",    "Belg",        ("Feb", "Mar"), ("Jun", "Jul"), "Bimodal Belg + Meher",
     "Short Belg season Feb-May; marginal for sorghum"),
    ("Somalia",     "Gu",          ("Apr", "Apr"), ("Jul", "Aug"), "Bimodal",
     "Gu Apr-Jun. Sorghum, maize"),
    ("Somalia",     "Deyr",        ("Oct", "Oct"), ("Jan", "Jan"), "Bimodal",
     "Deyr Oct-Dec"),
    ("Uganda",      "1st rains",   ("Mar", "Apr"), ("Jun", "Jul"), "Bimodal S / unimodal Karamoja",
     "1st rains Mar-Jun. Karamoja, the main sorghum zone, runs Apr-Aug and is later"),
    ("Uganda",      "2nd rains",   ("Sep", "Sep"), ("Dec", "Jan"), "Bimodal S",
     "2nd rains Sep-Dec"),
    ("Kenya",       "Long rains",  ("Mar", "Apr"), ("Jul", "Aug"), "Bimodal + unimodal Rift",
     "Long rains Mar-May. Maize dominant, sorghum second"),
    ("Kenya",       "Short rains", ("Oct", "Oct"), ("Jan", "Feb"), "Bimodal",
     "Short rains Oct-Dec"),
    ("Tanzania",    "Msimu",       ("Nov", "Dec"), ("May", "Jul"), "Unimodal S and central",
     "Msimu Nov-Apr, the southern and central unimodal season"),
    ("Tanzania",    "Masika",      ("Mar", "Mar"), ("Jun", "Jun"), "Bimodal N",
     "Masika Mar-May in the bimodal north"),
    ("Rwanda",      "Season A",    ("Sep", "Sep"), ("Jan", "Jan"), "Bimodal",
     "Season A Sep-Jan. Maize, sorghum, beans"),
    ("Rwanda",      "Season B",    ("Feb", "Mar"), ("Jun", "Jul"), "Bimodal",
     "Season B Feb-Jun"),
    ("Burundi",     "Season A",    ("Sep", "Sep"), ("Jan", "Jan"), "Bimodal",
     "Season A Sep-Jan. Maize, sorghum, rice, beans"),
    ("Burundi",     "Season B",    ("Feb", "Feb"), ("Jun", "Jun"), "Bimodal",
     "Season B Feb-Jun"),
]
# Djibouti is excluded: the report records minimal cropping, pastoral and import dependent.

# Report Table 1.0: the admin level at which harmonised sub-national statistics exist.
STATS_LEVEL = {"Sudan": "Admin-1", "South_Sudan": "Admin-1", "Eritrea": "Sparse",
               "Ethiopia": "Admin-2", "Somalia": "Admin-2", "Uganda": "Admin-2",
               "Kenya": "Admin-1", "Tanzania": "Admin-1", "Rwanda": "Admin-2",
               "Burundi": "Admin-2"}
# mapped sorghum area (Mha) from crop_type_mask/regional_report/tbl_crops.csv
AREA_MHA = {"Sudan": 6.320, "Ethiopia": 1.836, "Tanzania": 0.573, "South_Sudan": 0.295,
            "Kenya": 0.209, "Uganda": 0.199, "Somalia": 0.162, "Rwanda": 0.156,
            "Eritrea": 0.133, "Burundi": 0.023}
VIABILITY = {
    ("Sudan", "Kharif"): "High", ("Ethiopia", "Meher"): "High", ("Uganda", "1st rains"): "High",
    ("Somalia", "Gu"): "High", ("Somalia", "Deyr"): "High", ("South_Sudan", "Main"): "High",
    ("Kenya", "Long rains"): "High", ("Eritrea", "Kremti"): "High", ("Tanzania", "Msimu"): "High",
    ("Kenya", "Short rains"): "Medium", ("Uganda", "2nd rains"): "Medium",
    ("Rwanda", "Season A"): "Medium", ("Rwanda", "Season B"): "Medium",
    ("South_Sudan", "2nd"): "Medium", ("Tanzania", "Masika"): "Medium",
    ("Burundi", "Season A"): "Low", ("Burundi", "Season B"): "Low", ("Ethiopia", "Belg"): "Low",
}
# GEOGLAM (country, crop) -> this pipeline's season name, for the comparison columns only
CM4EW_SEASON = {
    ("Eritrea", "Sorghum 1"): "Kremti", ("Ethiopia", "Sorghum 1"): "Meher",
    ("Kenya", "Sorghum 1"): "Long rains", ("Somalia", "Sorghum 1"): "Gu",
    ("Somalia", "Sorghum 2"): "Deyr", ("South Sudan", "Sorghum 1"): "Main",
    ("South Sudan", "Sorghum 2"): "2nd", ("Sudan", "Sorghum 1"): "Kharif",
    ("Uganda", "Sorghum 1"): "1st rains",
}


def month_dekads(a, b):
    """('Jun','Jul') -> (first dekad of Jun, last dekad of Jul), wrap-aware."""
    s = (MON[a] - 1) * 3 + 1
    e = (MON[b] - 1) * 3 + 3
    if e < s:
        e += 36
    return s, e


def dekad_of(token):
    """'Jun-d1' -> dekad 1..36."""
    m, k = token.split("-d")
    return (MON[m] - 1) * 3 + int(k)


def tok(dk):
    dk = ((int(dk) - 1) % 36) + 1
    m, k = (dk - 1) // 3 + 1, (dk - 1) % 3 + 1
    return f"{dt.date(2001, m, 1):%b}-d{k}"


def win(a, b):
    return f"{tok(a)}-{tok(b)}"


def doy_to_dekad(doy, year=2001):
    d = dt.date(year, 1, 1) + dt.timedelta(days=int(doy) - 1)
    return (d.month - 1) * 3 + (1 if d.day <= 10 else 2 if d.day <= 20 else 3)


def cm4ew_table():
    """Sorghum windows from the GEOGLAM shapefile, for comparison only."""
    try:
        g = gpd.read_file(SHP)
    except Exception as e:
        print(f"(GEOGLAM shapefile not read: {e}; comparison columns left blank)")
        return {}
    s = g[g.crop.str.startswith("Sorghum", na=False)]
    s = s[(s.planting > 0) & (s.vegetative > 0)]
    out = {}
    for (country, crop), d in s.groupby(["country", "crop"]):
        season = CM4EW_SEASON.get((country, crop))
        if season is None:
            continue
        pl, vg, hv = (int(d[c].mode().iat[0]) for c in ("planting", "vegetative", "harvest"))
        p0, p1 = doy_to_dekad(pl), doy_to_dekad(vg - 1)
        out[(country.replace(" ", "_"), season)] = {
            "cm4ew_planting_window": win(p0, p1),
            "cm4ew_sos_window": win(p0 + 1, doy_to_dekad(vg) + 3),
            "cm4ew_cycle_dekads": max(9, min(18, round(((hv - pl) if hv > pl else hv + 365 - pl) / 10))),
            "cm4ew_regions": d.region.nunique(),
        }
    return out


def write_cm4ew_arm(rows, cm):
    """Arm B: the same products with the GEOGLAM CM4EW sorghum-specific **planting window** and
    cycle substituted wherever CM4EW monitors sorghum.

    The SOS window is re-derived with **arm A's rule** (planting start + 1 .. planting end + 3)
    rather than CM4EW's own, so the only thing that changes between the arms is the calendar
    itself. Deriving each arm's SOS by its own rule would have made Sudan and Somalia differ too,
    even though their planting windows agree exactly, and any result would then have been partly
    an artefact of the rule."""
    out = []
    for r in rows:
        r = dict(r)
        c = cm.get((r["country"], r["season"]))
        if c:
            a, b = c["cm4ew_planting_window"].rsplit("-", 2)[0], c["cm4ew_planting_window"]
            p0 = dekad_of(b.split("-d")[0] + "-d" + b.split("-d")[1][0])
            p1 = dekad_of(b.rsplit("-", 2)[1] + "-d" + b.rsplit("-", 1)[1][1])
            r["indicative_planting_window"] = c["cm4ew_planting_window"]
            r["sos_detection_window"] = win(p0 + 1, p1 + 3)
            r["cycle_dekads"] = c["cm4ew_cycle_dekads"]
            r["crop_calendar_source"] = "GEOGLAM_CM4EW_v1.3"
        out.append(r)
    d = pd.DataFrame(out).sort_values(["country", "season"])
    p = f"{H}/config/season_calendar_sorghum_cm4ew.csv"
    d.to_csv(p, index=False)
    n = (d.crop_calendar_source == "GEOGLAM_CM4EW_v1.3").sum()
    print(f"\narm B -> {p}  ({n} products on CM4EW windows, "
          f"{len(d) - n} unchanged because CM4EW does not monitor sorghum there)")


def main():
    cm = cm4ew_table()
    rows = []
    for country, season, plant, harv, regime, note in REPORT_T20:
        p0, p1 = month_dekads(*plant)
        h0, h1 = month_dekads(*harv)
        if h0 < p1:                                   # harvest runs into the next year
            h0 += 36; h1 += 36
        cycle = max(9, min(18, round(((h0 + h1) / 2) - ((p0 + p1) / 2))))
        c = cm.get((country, season), {})
        agree = ""
        if c:
            agree = "same" if c["cm4ew_planting_window"] == win(p0, p1) else "differs"
        rows.append(dict(
            country=country, season_regime=regime, crop="Sorghum", season=season,
            indicative_planting_window=win(p0, p1),
            sos_detection_window=win(p0 + 1, p1 + 3),
            crop_viability=VIABILITY.get((country, season), "Medium"),
            crop_calendar_source="InceptionReport_Table2.0",
            cycle_dekads=cycle,
            report_planting_months=f"{plant[0]}-{plant[1]}",
            report_harvest_months=f"{harv[0]}-{harv[1]}",
            stats_admin_level=STATS_LEVEL.get(country, ""),
            mapped_area_Mha=AREA_MHA.get(country),
            cm4ew_planting_window=c.get("cm4ew_planting_window", ""),
            cm4ew_cycle_dekads=c.get("cm4ew_cycle_dekads", ""),
            cm4ew_agreement=agree,
            notes=note))
    out = pd.DataFrame(rows).sort_values(["country", "season"])
    p = f"{H}/config/season_calendar_sorghum.csv"
    out.to_csv(p, index=False)
    print(out[["country", "season", "indicative_planting_window", "sos_detection_window",
               "cycle_dekads", "crop_viability", "cm4ew_planting_window",
               "cm4ew_agreement"]].to_string(index=False))
    n = (out.cm4ew_agreement == "differs").sum()
    print(f"\n{len(out)} products -> {p}")
    print(f"GEOGLAM CM4EW has a sorghum-specific calendar for {(out.cm4ew_agreement != '').sum()} "
          f"of them and disagrees with the report for {n}. The report's calendar is arm A; the "
          f"CM4EW windows are written as arm B so the two can be scored against each other.")
    write_cm4ew_arm(rows, cm)


if __name__ == "__main__":
    main()
