#!/usr/bin/env python3
"""Rebuild Kenya Short-rains admin tables from the RAINFALL-ANCHORED raster (full coverage),
so the apps show the 96%-coverage product instead of the sparse green-up one.

Writes planting_Kenya_maize_Shortrains_2024_rainfed_L{1,2,3}_skill_WKT.csv with the full app schema:
planting skill + CAF + SPI-3 + GDD stage dekads. WRSI admin WKT (…_250m) is unchanged and still
merged by the app via its wbase.
"""
import os, numpy as np, pandas as pd, geopandas as gpd, rasterio, datetime as dt
from rasterio.features import rasterize
from rasterio.warp import reproject, Resampling
import caf_add  # DRIVE, GADM, KEYS

DRIVE, GADM, KEYS = caf_add.DRIVE, caf_add.GADM, caf_add.KEYS
BASE = "planting_Kenya_maize_Shortrains_2024_rainfed"
RAINFED = "planting_Kenya_maize_Shortrains_2024_rainfed_gated.tif"   # band 1 = viable-gated planting_dekad
SPI = "spi3_Kenya_Shortrains_2024.tif"
GDD = "gddclock_Kenya_Shortrains_2024_rainfed.tif"   # rainfall-anchored + year-wrapping
WIN = (28, 32); CENTRE = 30.0; MINPX = 5
GDD_STAGES = {"peak_vegetative_dekad": "pkv_dekad", "flowering_dekad": "flo_dekad",
              "grain_filling_dekad": "grf_dekad", "maturity_dekad": "mat_dekad"}
COLS = ["county", "name", "level", "constituency", "n_px", "modal_dekad", "modal_label",
        "mean_dekad", "p10", "p50", "p90", "hit_rate", "bias_dek", "mae_dek",
        "crop_area_frac", "crop_viable_pct", "lvpd_dekad", "spi3_dry_pct", "spi3_mean",
        "pkv_dekad", "flo_dekad", "grf_dekad", "mat_dekad",
        "wrsi_veg", "wrsi_flo", "wrsi_grf", "wsi_veg", "wsi_flo", "wsi_grf", "failflo_pct",
        "cpi", "yield_tha", "total_yield_t", "s_water", "s_heat", "s_veg",
        "geometry_wkt"]


def dl(d):
    d = int(round(d)); m = (d - 1) // 3 + 1
    return f"{d}·{dt.date(2000, m, 1):%b}"


def reproj_to(src_path, tr, crs, shp, band=1):
    dst = np.full(shp, np.nan, "float32")
    with rasterio.open(os.path.join(DRIVE, src_path)) as s:
        reproject(rasterio.band(s, band), dst, src_transform=s.transform, src_crs=s.crs,
                  dst_transform=tr, dst_crs=crs, resampling=Resampling.nearest)
    return dst


with rasterio.open(os.path.join(DRIVE, RAINFED)) as d:
    plant = d.read(1).astype("float32"); tr = d.transform; crs = d.crs; shp = plant.shape
maize_all = reproj_to("planting_Kenya_maize_Shortrains_2024_rainfed.tif", tr, crs, shp)  # ungated (all maize w/ onset)
lvpd = reproj_to("lvpd_Kenya_maize_Shortrains_2024.tif", tr, crs, shp)                    # LVPD dekad (climatological)
STAGE_BANDS = ["wrsi_veg", "wrsi_flo", "wrsi_grf", "wsi_veg", "wsi_flo", "wsi_grf"]        # stage monitor
stage = {}
try:
    with rasterio.open(os.path.join(DRIVE, "stagemonitor_Kenya_maize_Shortrains_2024.tif")) as sd:
        snames = [sd.descriptions[i] for i in range(sd.count)]
    for b in STAGE_BANDS:
        stage[b] = reproj_to("stagemonitor_Kenya_maize_Shortrains_2024.tif", tr, crs, shp, band=snames.index(b) + 1)
except Exception:
    stage = None
CPI_BANDS = ["CPI", "yield_tha_x100", "S_water", "S_heat", "S_veg"]
cpi_r = {}
try:
    with rasterio.open(os.path.join(DRIVE, "cpi_Kenya_maize_Shortrains_2024.tif")) as cd:
        cnames = [cd.descriptions[i] for i in range(cd.count)]
    for b in CPI_BANDS:
        cpi_r[b] = reproj_to("cpi_Kenya_maize_Shortrains_2024.tif", tr, crs, shp, band=cnames.index(b) + 1)
except Exception:
    cpi_r = None
PIXEL_HA = 6.25   # 250 m pixel = 6.25 ha
spi = reproj_to(SPI, tr, crs, shp)
gdd = {}
with rasterio.open(os.path.join(DRIVE, GDD)) as g:
    names = {g.descriptions[i]: i + 1 for i in range(g.count)}
for src in GDD_STAGES:
    gdd[src] = reproj_to(GDD, tr, crs, shp, band=names[src])

for lvl in (1, 2, 3):
    gdf = gpd.read_file(GADM["KEN"] % lvl).to_crs("EPSG:4326")
    z = rasterize(((geom, i + 1) for i, geom in enumerate(gdf.geometry)),
                  out_shape=shp, transform=tr, fill=0, dtype="int32")
    rows = []
    for i in range(len(gdf)):
        m = z == (i + 1)
        ntot = int(m.sum())
        pv = plant[m]; pv = pv[(pv >= 1) & (pv <= 36)]
        if pv.size < MINPX:
            continue
        modal = int(np.bincount(pv.astype(int)).argmax())
        p10, p50, p90 = np.percentile(pv, [10, 50, 90])
        hit = float(((pv >= WIN[0]) & (pv <= WIN[1])).mean())
        row = {"county": gdf["NAME_1"].iloc[i], "name": gdf[f"NAME_{lvl}"].iloc[i], "level": lvl,
               "constituency": gdf["NAME_2"].iloc[i] if lvl >= 2 else "",
               "n_px": int(pv.size), "modal_dekad": modal, "modal_label": dl(modal),
               "mean_dekad": round(float(pv.mean()), 2),
               "p10": round(float(p10), 1), "p50": round(float(p50), 1), "p90": round(float(p90), 1),
               "hit_rate": round(hit, 3), "bias_dek": round(float(pv.mean() - CENTRE), 2),
               "mae_dek": round(float(np.abs(pv - CENTRE).mean()), 2),
               "crop_area_frac": round(pv.size / ntot, 4) if ntot else None,
               "geometry_wkt": gdf.geometry.iloc[i].wkt}
        ma = maize_all[m]; nmaize = int(((ma >= 1) & (ma <= 36)).sum())   # all maize w/ onset in unit
        row["crop_viable_pct"] = round(pv.size / nmaize * 100, 1) if nmaize else None  # LVPD keep-rate
        lv = lvpd[m]; lv = lv[(lv >= 1) & (lv <= 54)]                      # climatological LVPD dekad
        row["lvpd_dekad"] = round(float(np.median(lv)), 1) if lv.size >= MINPX else None
        if stage is not None:                                              # stage-resolved WRSI/WSI
            mm = m & (maize_all >= 1) & (maize_all <= 36)                  # actual maize pixels only
            for b in STAGE_BANDS:
                sv = stage[b][mm]; sv = sv[(sv >= 0) & (sv <= 100)]
                row[b] = round(float(np.median(sv)), 1) if sv.size >= MINPX else None
            fv = stage["wrsi_flo"][mm]; fv = fv[(fv >= 0) & (fv <= 100)]
            row["failflo_pct"] = round(float((fv < 50).mean() * 100), 1) if fv.size >= MINPX else None
        else:
            for b in STAGE_BANDS + ["failflo_pct"]:
                row[b] = None
        if cpi_r is not None:                                              # CPI + yield
            mm = m & (maize_all >= 1) & (maize_all <= 36)
            cv = cpi_r["CPI"][mm]; cv = cv[(cv >= 0) & (cv <= 100)]
            row["cpi"] = round(float(np.median(cv)), 1) if cv.size >= MINPX else None
            yv = cpi_r["yield_tha_x100"][mm] / 100.0; yv = yv[(yv >= 0) & (yv <= 15)]
            row["yield_tha"] = round(float(np.median(yv)), 2) if yv.size >= MINPX else None
            row["total_yield_t"] = round(float(np.sum(yv) * PIXEL_HA), 0) if yv.size >= MINPX else None
            for b, c in (("S_water", "s_water"), ("S_heat", "s_heat"), ("S_veg", "s_veg")):
                sv = cpi_r[b][mm]; sv = sv[(sv >= 0) & (sv <= 100)]
                row[c] = round(float(np.median(sv)), 1) if sv.size >= MINPX else None
        else:
            for c in ["cpi", "yield_tha", "total_yield_t", "s_water", "s_heat", "s_veg"]:
                row[c] = None
        sv = spi[m]; sv = sv[np.isfinite(sv)]
        row["spi3_dry_pct"] = round(float((sv <= -1).mean() * 100), 1) if sv.size >= MINPX else None
        row["spi3_mean"] = round(float(sv.mean()), 2) if sv.size >= MINPX else None
        for src, col in GDD_STAGES.items():
            gv = gdd[src][m]; gv = gv[(gv >= 1) & (gv <= 54)]   # stages may wrap past 36 (next-year)
            row[col] = round(float(np.median(gv)), 1) if gv.size >= MINPX else None
        rows.append(row)
    df = pd.DataFrame(rows)[COLS]
    out = f"{BASE}_L{lvl}_skill_WKT.csv"
    df.to_csv(out, index=False)
    print(f"  L{lvl}: {len(df)} units  (was sparse green-up) -> {out}")
