#!/usr/bin/env python3
"""Merge the local stat/skill/AEZ CSVs with polygon geometry -> CSV with a WKT column.

Produces QGIS/CARTO-ready tables (load 'geometry' as WKT) carrying every attribute already
computed locally: planting distribution, calendar skill (hit/bias/MAE), AEZ maturity class.
The GEE input-layer values (NDRE, S1, S2, rainfall/temperature/phenology LTN) are appended by
attributes_table.py once that export lands — this covers the outputs/statistics side.

Run: python build_wkt_table.py --product planting_Kenya_maize_Longrains_2024
"""
import argparse, os
import pandas as pd
import geopandas as gpd

GADM = "/Users/hildamanzi/Downloads/gadm41_KEN_shp/gadm41_KEN_%d.shp"
AEZ_SHP = "/Users/hildamanzi/AEZ-COUNTRIES/KENYA_AEZ/kenya_aezones.shp"


def admin_wkt(product, level):
    csv = f"{product}_L{level}_skill.csv"
    if not os.path.exists(csv):
        return None
    df = pd.read_csv(csv)
    g = gpd.read_file(GADM % level).to_crs("EPSG:4326")
    if level == 1:
        g = g[["NAME_1", "geometry"]].rename(columns={"NAME_1": "name"})
        keys = ["name"]
    elif level == 2:
        g = g[["NAME_1", "NAME_2", "geometry"]].rename(columns={"NAME_1": "county", "NAME_2": "name"})
        keys = ["county", "name"]
    else:
        g = g[["NAME_1", "NAME_2", "NAME_3", "geometry"]].rename(
            columns={"NAME_1": "county", "NAME_2": "constituency", "NAME_3": "name"})
        keys = ["county", "constituency", "name"]
    m = g.merge(df, on=keys, how="inner")
    m["geometry_wkt"] = m.geometry.to_wkt()
    return pd.DataFrame(m.drop(columns="geometry"))


def aez_wkt(product):
    csv = f"{product}_AEZ_maturity.csv"
    if not os.path.exists(csv):
        return None
    df = pd.read_csv(csv)
    g = gpd.read_file(AEZ_SHP).to_crs("EPSG:4326").dissolve("AEZONE").reset_index()
    g = g[["AEZONE", "geometry"]].rename(columns={"AEZONE": "aez"})
    m = g.merge(df, on="aez", how="inner")
    m["geometry_wkt"] = m.geometry.to_wkt()
    return pd.DataFrame(m.drop(columns="geometry"))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--product", default="planting_Kenya_maize_Longrains_2024")
    args = ap.parse_args()

    made = []
    for level in (1, 2, 3):
        t = admin_wkt(args.product, level)
        if t is not None:
            out = f"{args.product}_L{level}_skill_WKT.csv"
            t.to_csv(out, index=False)
            made.append((out, len(t), len(t.columns)))
    a = aez_wkt(args.product)
    if a is not None:
        out = f"{args.product}_AEZ_maturity_WKT.csv"
        a.to_csv(out, index=False)
        made.append((out, len(a), len(a.columns)))

    print("WKT tables written:")
    for f, r, c in made:
        print(f"  {f}   ({r} rows, {c} cols incl. geometry_wkt)")


if __name__ == "__main__":
    main()
