#!/usr/bin/env python3
"""The crop-type mask decides which crops run in which country. One authority, used by every runner.

A product can only be computed where the ICPAC crop-type mask carries a band for that crop in that
country (`ctm_mask.PROFILES`). The season calendars are a separate, hand-maintained list, and the
two had drifted: `config/season_calendar.csv` carries rows for Sudan maize, Eritrea maize, Eritrea
wheat, Eritrea teff and Uganda wheat, none of which has a mask band, so none can ever be built. A
row like that is not a pending product — it is a product that cannot exist, and anything that reads
the calendar as an inventory (an exposure grader, a coverage report, a work plan) will be wrong.

This module intersects the two and names the difference:

    RUNNABLE      mask band AND calendar row      -> the runners iterate exactly these
    NO MASK BAND  calendar row, no mask band      -> cannot be built; drop or extend the mask
    NO CALENDAR   mask band, no calendar row      -> buildable, needs a calendar entry

    from crop_coverage import runnable, gate
    rows = gate(rows, "sorghum")        # filters a calendar row list, printing what it drops

    python crop_coverage.py             # the full matrix and the two difference lists
"""
import csv, os, sys

H = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, H); sys.path.insert(0, f"{H}/crop_pipeline/irrigation")
import ctm_mask as CTM

# Products DROPPED by decision, with the evidence. This is separate from ACCEPTED because the mask
# DOES carry a band here - it is just too thin to support a product. PROFILES keeps describing the
# asset truthfully; the decision lives here, where it can be read and reversed.
DROPPED = {
    ("maize", "South_Sudan"):
        "Dropped 26 Sep 2026 by decision. The crop-type mask maps 0.013 Mha of maize in South Sudan "
        "against 0.295 Mha of sorghum. On that mask the product retains 135 maize pixels country-wide "
        "against WorldCereal's 9,398, and Eastern Equatoria - 90 % of the country's maize by "
        "WorldCereal - has none at all. Only 2 of 9 states keep enough pixels to produce a CPI, so it "
        "cannot support admin-level reporting. South Sudan is a sorghum country and its sorghum "
        "products (Main and 2nd) are sound. Evidence: maize_ctm/mask_comparison.csv.",
}

# Differences that are DELIBERATE, with the reason. Without this the report reads every difference
# as a defect, and someone eventually "fixes" one that was a decision.
ACCEPTED = {
    ("maize", "Sudan"):
        "Maize is not a Sudanese crop at scale and is deliberately not mapped or run. Confirmed by "
        "the pipeline owner, 26 Sep 2026. The calendar row is a legacy placeholder; the mask carries "
        "sorghum, millet and wheat for Sudan and that is the intended coverage.",
    ("maize", "Eritrea"):
        "Same: the Eritrean mask carries sorghum and millet, which are the cereals of consequence "
        "there. The calendar row is a legacy placeholder.",
    ("wheat", "Rwanda"):
        "Buildable but deferred: 0.019 Mha mapped, the smallest wheat area in the region. Needs a "
        "calendar entry before it can run; low priority against that area.",
    ("wheat", "Burundi"):
        "Buildable but deferred: 0.003 Mha mapped. Needs a calendar entry; lowest priority in the set.",
}

CALENDARS = {"maize": "config/season_calendar.csv",
             "sorghum": "sorghum_pipeline/config/season_calendar_sorghum.csv",
             "wheat": "crop_pipeline/config/season_calendar_wtm.csv",
             "teff": "crop_pipeline/config/season_calendar_wtm.csv",
             "millet": "crop_pipeline/config/season_calendar_wtm.csv"}
CROPS = list(CALENDARS)


def _rows(crop):
    """Calendar rows for a crop that describe a real season (a '-' window means 'not grown')."""
    out = []
    for r in csv.DictReader(open(f"{H}/{CALENDARS[crop]}")):
        if str(r.get("crop", "")).lower() != crop:
            continue
        if str(r.get("indicative_planting_window", "")).strip() in ("", "-"):
            continue
        r["_country"] = r["country"].replace(" ", "_")
        out.append(r)
    return out


def is_dropped(crop, country):
    return (str(crop).lower(), str(country).replace(" ", "_")) in DROPPED


def runnable(crop=None):
    """Calendar rows the crop-type mask can actually support and that have not been dropped."""
    return {c: [r for r in _rows(c)
                if CTM.has(r["_country"], c) and not is_dropped(c, r["_country"])]
            for c in ([crop] if crop else CROPS)}


def no_mask_band(crop=None):
    """(crop, country, season) in a calendar with no mask band — cannot ever be built."""
    return [(c, r["_country"], r["season"])
            for c in ([crop] if crop else CROPS)
            for r in _rows(c) if not CTM.has(r["_country"], c)]


def no_calendar(crop=None):
    """(crop, country) the mask supports but no calendar row exists — buildable, needs a calendar."""
    want = [crop] if crop else CROPS
    have = {(c, r["_country"]) for c in want for r in _rows(c)}
    return sorted((c, co) for co, (_iso, crops) in CTM.PROFILES.items()
                  for c in crops if c in want and (c, co) not in have)


def gate(rows, crop, country_key="country", verbose=True):
    """Filter a runner's calendar rows to those the mask supports, saying what it dropped and why.

    Runners should call this instead of iterating the calendar directly, so the plan they print is
    the plan that can run."""
    keep, noband, dropped = [], [], []
    for r in rows:
        co = str(r[country_key]).replace(" ", "_")
        if is_dropped(crop, co):
            dropped.append(r)
        elif CTM.has(co, crop):
            keep.append(r)
        else:
            noband.append(r)
    if noband and verbose:
        print(f"  [crop-type mask] {len(noband)} row(s) skipped — no {crop} band for that country:")
        for r in noband:
            co = str(r[country_key]).replace(" ", "_")
            have = CTM.PROFILES.get(co, ("?", ()))[1]
            print(f"      {co} {r.get('season', '')} — mask carries {', '.join(have) or 'nothing'}")
    if dropped and verbose:
        print(f"  [dropped by decision] {len(dropped)} {crop} row(s):")
        for r in dropped:
            co = str(r[country_key]).replace(" ", "_")
            print(f"      {co} {r.get('season', '')} — {DROPPED[(crop, co)][:96]}...")
    return keep


def main():
    print("=== what the crop-type mask supports, against what the calendars ask for ===\n")
    print(f"{'country':14s}" + "".join(f"{c:>11}" for c in CROPS))
    print("-" * 69)
    cal = {c: {r["_country"] for r in _rows(c)} for c in CROPS}
    for co in sorted(CTM.PROFILES):
        line = f"{co:14s}"
        for c in CROPS:
            band, has_cal = CTM.has(co, c), co in cal[c]
            cell = ("DROPPED" if is_dropped(c, co) else
                    "RUN" if band and has_cal else "no-cal" if band else
                    "NO BAND" if has_cal else "·")
            line += f"{cell:>11}"
        print(line)

    if DROPPED:
        print(f"\n=== DROPPED by decision — mask has a band, product retired ({len(DROPPED)}) ===")
        for (c, co), why in sorted(DROPPED.items()):
            print(f"  {co:14s} {c:8s}")
            print(f"      {why}")

    nb = no_mask_band()
    print(f"\n=== NO MASK BAND — in a calendar, cannot ever be built ({len(nb)}) ===")
    for c, co, sea in nb:
        have = CTM.PROFILES.get(co, ("?", ()))[1]
        tag = "DELIBERATE" if (c, co) in ACCEPTED else "** UNEXPLAINED **"
        print(f"  {co:14s} {c:8s} {sea:14s}  mask carries: {', '.join(have) or 'nothing'}   {tag}")
        if (c, co) in ACCEPTED:
            print(f"      {ACCEPTED[(c, co)]}")

    nc = no_calendar()
    print(f"\n=== NO CALENDAR — buildable, but no calendar row ({len(nc)}) ===")
    for c, co in nc:
        a = CTM.AREA_MHA.get((co, c))
        tag = "DEFERRED" if (c, co) in ACCEPTED else "** UNEXPLAINED **"
        print(f"  {co:14s} {c:8s} mapped area {a if a is not None else '?'} Mha   {tag}")
        if (c, co) in ACCEPTED:
            print(f"      {ACCEPTED[(c, co)]}")

    tot = sum(len(v) for v in runnable().values())
    unexplained = ([x for x in nb if (x[0], x[1]) not in ACCEPTED]
                   + [x for x in nc if x not in ACCEPTED])
    print(f"\n{tot} runnable products · {len(nb)} unbuildable calendar rows · "
          f"{len(nc)} uncalendared bands · {len(unexplained)} unexplained")
    if unexplained:
        print("  every difference should be either runnable or in ACCEPTED with a reason:")
        for x in unexplained:
            print("   ", x)


if __name__ == "__main__":
    main()
