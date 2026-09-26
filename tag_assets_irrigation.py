#!/usr/bin/env python3
"""Attach irrigation-exposure properties to the Earth Engine assets already exported.

The runners now set these at export time, but the 2024 products were exported before the exposure
was known. Re-exporting 40-odd assets to add metadata would be absurd, so this patches them in
place with ee.data.updateAsset. Existing properties are READ FIRST AND MERGED — updateAsset with an
updateMask of "properties" replaces the whole map, so a blind write would delete ym_tha,
crop_calendar_source and everything else.

    python tag_assets_irrigation.py                # dry run, prints what would change
    python tag_assets_irrigation.py --apply
"""
import argparse, re, sys
import ee
import irrigation_exposure as IRR

PROJECTS = ["ee-manzikye", "indigo-proxy-484220-q8"]
COUNTRIES = ["South_Sudan", "SouthSudan", "Ethiopia", "Tanzania", "Somalia", "Burundi", "Eritrea",
             "Rwanda", "Uganda", "Sudan", "Kenya", "Djibouti"]
# asset-name prefix -> crop. Longest prefix wins, so the bare maize prefixes come last.
PREFIX_CROP = [("sorghumBX_", "sorghum"), ("sorghumX_", "sorghum"), ("sorghum_", "sorghum"),
               ("wheatX_", "wheat"), ("wheat_", "wheat"), ("teffX_", "teff"), ("teff_", "teff"),
               ("milletX_", "millet"), ("millet_", "millet"),
               ("cpiX_", "maize"), ("cpi_", "maize"), ("planting_", "maize"),
               ("wrsi_", "maize"), ("fcci_", "maize"), ("stagemonitor_", "maize"),
               ("onsetexcess_", "maize"), ("crop_cycle_", "maize")]
SKIP = ("whc_", "crop_type_mask", "ke_subcounty")


def parse(name):
    """(crop, country) from an asset's short name, or None."""
    if name.startswith(SKIP):
        return None
    for pfx, crop in PREFIX_CROP:
        if not name.startswith(pfx):
            continue
        rest = name[len(pfx):]
        for c in COUNTRIES:                          # longest first: South_Sudan before Sudan
            if rest.startswith(c):
                return crop, c.replace("SouthSudan", "South_Sudan")
        return None                                  # e.g. crop_cycle_ke_meher_2024 (lowercase ids)
    return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true")
    a = ap.parse_args()

    n_tag = n_skip = n_same = 0
    for proj in PROJECTS:
        try:
            ee.Initialize(project=proj)
            assets = ee.data.listAssets({"parent": f"projects/{proj}/assets"}).get("assets", [])
        except Exception as e:
            print(f"!! {proj}: {type(e).__name__}: {str(e)[:120]}"); continue
        print(f"\n=== {proj} ({len(assets)} assets) ===")
        for a_ in sorted(assets, key=lambda x: x["name"]):
            full = a_["name"]; short = full.rsplit("/", 1)[-1]
            p = parse(short)
            if p is None:
                n_skip += 1; continue
            crop, country = p
            props = IRR.asset_properties(country, crop)
            if props.get("irrigation_exposure") == "unknown":
                print(f"  ? {short:42s} {crop}/{country}: no SPAM entry"); n_skip += 1; continue
            grade = props["irrigation_exposure"]
            try:
                cur = ee.data.getAsset(full).get("properties", {}) or {}
            except Exception as e:
                print(f"  ! {short:42s} getAsset failed: {str(e)[:60]}"); continue
            if cur.get("irrigation_exposure") == grade:
                n_same += 1; continue
            merged = dict(cur); merged.update(props)
            flag = "  " if grade == "negligible" else "**"
            print(f"{flag}{short:42s} {crop:8s}{country:12s} -> {grade}")
            if a_["type"] not in ("IMAGE", "IMAGE_COLLECTION", "TABLE"):
                print(f"    (skipping type {a_['type']})"); n_skip += 1; continue
            if a.apply:
                try:
                    ee.data.updateAsset(full, {"properties": merged}, ["properties"])
                    n_tag += 1
                except Exception as e:
                    print(f"    !! update failed: {type(e).__name__}: {str(e)[:110]}")
            else:
                n_tag += 1
    verb = "tagged" if a.apply else "would tag"
    print(f"\n{verb}: {n_tag}   already current: {n_same}   not a product: {n_skip}")
    if not a.apply:
        print("dry run — re-run with --apply")


if __name__ == "__main__":
    main()
