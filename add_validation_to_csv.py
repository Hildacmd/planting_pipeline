#!/usr/bin/env python3
"""Merge observed MAM-2024 farmer planting dekad (+ error vs our estimate) into the Kenya Long-rains
skill CSVs, so the app can show observed vs estimated. County obs (L1/L2) + ward obs (L3)."""
import pandas as pd, warnings; warnings.filterwarnings("ignore")
VAL="/Users/hildamanzi/Downloads/Planting_dates/Planting_Dates_by_County_2023-2025 (1).xlsx"
def to_dk(d):
    d=pd.to_datetime(d); return (d.month-1)*3+min(3,(d.day-1)//10+1)
def key(s): return s.astype(str).str.upper().str.replace("'","",regex=False).str.replace("-"," ",regex=False).str.replace(".","",regex=False).str.strip()

cty=pd.read_excel(VAL,sheet_name="Median by county-year")[["County","Median planting 2024"]].dropna()
cty["dk"]=cty["Median planting 2024"].map(to_dk); cty["CK"]=key(cty["County"])
cty_map=dict(zip(cty["CK"],cty["dk"]))
wl=pd.read_excel(VAL,sheet_name="Ward level"); wl=wl[wl["Year"]==2024]
wl["dk"]=wl["Median date"].map(to_dk); wl["WK"]=key(wl["County"])+"|"+key(wl["Ward"])
ward_map=dict(zip(wl["WK"],wl["dk"]))

for lvl in (1,2,3):
    p=f"planting_Kenya_maize_Longrains_2024_L{lvl}_skill_WKT.csv"
    df=pd.read_csv(p)
    if lvl==1:
        obs=key(df["name"]).map(cty_map)
    elif lvl==2:
        obs=key(df["county"]).map(cty_map)                       # constituencies inherit county reference
    else:
        wk=key(df["county"])+"|"+key(df["name"])
        obs=wk.map(ward_map); obs=obs.fillna(key(df["county"]).map(cty_map))   # ward, fallback county
    df["obs_plant_dk"]=obs
    df["plant_err"]=df["modal_dekad"]-obs
    df.to_csv(p,index=False)
    print(f"  L{lvl}: obs planting merged -> {df['obs_plant_dk'].notna().sum()}/{len(df)} units "
          f"(median |err| {df['plant_err'].abs().median():.1f} dekad)")
