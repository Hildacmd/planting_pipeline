#!/usr/bin/env python3
"""Prepare compact multi-product geo+attribute data for the interactive planting app (one JSON).

Emits {"products":[...]} — one entry per (country, season) layer. Each product carries its own
admin level-names (Kenya: County/Constituency/Ward · Ethiopia: Region/Zone/Woreda), calendar
window, and per-level GeoJSON+attributes. The app switches between products client-side.
"""
import json, pandas as pd, geopandas as gpd
from shapely import wkt
import irrigation_exposure as IRR
import crop_coverage as COV

# --- product registry: id -> config ---
PRODUCTS = [
    {"id": "ke_long", "country": "Kenya", "season": "Long rains 2024", "crop": "maize",
     "base": "planting_Kenya_maize_Longrains_2024", "wbase": "wrsi_Kenya_maize_Longrains_2024",
     "win": [8, 12], "levelnames": {1: "County", 2: "Constituency", 3: "Ward"}, "scale": "10 m"},
    {"id": "ke_short", "country": "Kenya", "season": "Short rains 2024", "crop": "maize",
     "base": "planting_Kenya_maize_Shortrains_2024_rainfed", "wbase": "wrsi_Kenya_maize_Shortrains_2024_250m",
     "win": [24, 33], "levelnames": {1: "County", 2: "Constituency", 3: "Ward"},
     "scale": "250 m grid · rainfall-anchored (~5.5 km content)",
     "note": "PROVISIONAL regime-aware onset: western/Rift bimodal counties use the early Aug-d3–Oct-d2 "
             "window (they plant Aug–Sep), eastern/coastal keep Oct–Nov; unimodal Rift grain-basket "
             "counties (Trans Nzoia, Uasin Gishu, Kericho, West Pokot, Bomet) stay late. Held-out "
             "validation significant only at the boundary; ~39% of mapped western short-rains area may "
             "be the standing long-rains crop — see KENYA_SEASON_REGIMES.md sec 7"},
    {"id": "et_meher", "country": "Ethiopia", "season": "Meher 2024", "crop": "maize",
     "base": "planting_Ethiopia_maize_Meher_2024_250m", "wbase": "wrsi_Ethiopia_maize_Meher_2024_250m",
     "win": [10, 15], "levelnames": {1: "Region", 2: "Zone", 3: "Woreda"}, "scale": "250 m"},
]

# ---- new-country 2024 products (reduce_newcountries.py -> newc_*_skill_WKT.csv) --------------------
# CPI/yield/stress + planting distribution + WRSI stages from the cpiX_ rich assets. Validation
# (hit/bias/mae) columns are absent (no ground reference outside Kenya) -> app leaves that panel blank.
# id, country, season-label, base token (matches cpiX_ id), win dekads, admin level names, note.
_NEW = [
    ("ug_1st",  "Uganda", "1st rains 2024",  "Uganda_1strains",  [7, 14],  ("Sub-region", "District")),
    ("ug_2nd",  "Uganda", "2nd rains 2024",  "Uganda_2ndrains",  [23, 29], ("Sub-region", "District")),
    ("rw_a",    "Rwanda", "Season A 2024",   "Rwanda_SeasonA",   [27, 32], ("Province", "District")),
    ("rw_b",    "Rwanda", "Season B 2024",   "Rwanda_SeasonB",   [5, 10],  ("Province", "District")),
    ("bi_a",    "Burundi", "Season A 2024",  "Burundi_SeasonA",  [27, 32], ("Province", "Commune")),
    ("bi_b",    "Burundi", "Season B 2024",  "Burundi_SeasonB",  [5, 10],  ("Province", "Commune")),
    ("tz_mas",  "Tanzania", "Masika 2024",   "Tanzania_Masika",  [8, 14],  ("Region", "District")),
    ("tz_msi",  "Tanzania", "Msimu 2024",    "Tanzania_Msimu",   [34, 40], ("Region", "District")),
    ("tz_vul",  "Tanzania", "Vuli 2024",     "Tanzania_Vuli",    [29, 34], ("Region", "District")),
    ("so_gu",   "Somalia", "Gu 2024",        "Somalia_Gu",       [11, 16], ("Region", "District")),
    ("so_deyr", "Somalia", "Deyr 2024",      "Somalia_Deyr",     [29, 34], ("Region", "District")),
    ("et_belg", "Ethiopia", "Belg 2024",     "Ethiopia_Belg",    [7, 12],  ("Region", "Zone")),
]
_RAIN = {"Uganda_2ndrains", "Rwanda_SeasonA", "Rwanda_SeasonB", "Burundi_SeasonA", "Burundi_SeasonB",
         "Tanzania_Vuli", "Somalia_Deyr", "Ethiopia_Belg"}   # Season A moved to rainfall (cloudy highlands)
for _id, _c, _s, _tok, _win, _ln in _NEW:
    PRODUCTS.append({
        "id": _id, "country": _c, "season": _s, "crop": "maize",
        "base": f"newc_{_tok}_2024", "wbase": f"newc_{_tok}_2024_wrsi",  # wbase absent -> null WRSI merge
        "win": _win, "levelnames": {1: _ln[0], 2: _ln[1]}, "scale": "250 m",
        "note": ("rainfall-anchored onset" if _tok in _RAIN else "green-up cue-fusion onset")
                + " · yield on fallback Ym (no HarvestStat match yet)",
    })
# ---- 2024 sorghum products (sorghum_pipeline) ---------------------------------------------------
# Same shape as the maize entries. The calendar is the Inception Report Table 2.0; the mask is the
# ICPAC crop-type mask sorghum band, not WorldCereal, which has no sorghum class. Products appear
# in the app only once their reduce CSV exists, so this list can be registered before the Earth
# Engine exports finish.
# id, country, season label, base token, SOS window dekads, admin level names
_SORGHUM = [
    ("sd_kharif_s",  "Sudan",       "Kharif 2024",      "Sudan_Kharif",       [17, 26], ("State", "Locality")),
    ("et_meher_s",   "Ethiopia",    "Meher 2024",       "Ethiopia_Meher",     [17, 26], ("Region", "Zone")),
    ("tz_msimu_s",   "Tanzania",    "Msimu 2024",       "Tanzania_Msimu",     [32, 39], ("Region", "District")),
    ("ss_main_s",    "South Sudan", "Main 2024",        "South_Sudan_Main",   [11, 22], ("State", "County")),
    ("ss_2nd_s",     "South Sudan", "2nd 2024",         "South_Sudan_2nd",    [20, 27], ("State", "County")),
    ("ke_long_s",    "Kenya",       "Long rains 2024",  "Kenya_Longrains",    [8, 15],  ("County", "Constituency")),
    ("ke_short_s",   "Kenya",       "Short rains 2024", "Kenya_Shortrains",   [29, 33], ("County", "Constituency")),
    ("ug_1st_s",     "Uganda",      "1st rains 2024",   "Uganda_1strains",    [8, 15],  ("Sub-region", "District")),
    ("ug_2nd_s",     "Uganda",      "2nd rains 2024",   "Uganda_2ndrains",    [26, 30], ("Sub-region", "District")),
    ("so_gu_s",      "Somalia",     "Gu 2024",          "Somalia_Gu",         [11, 15], ("Region", "District")),
    ("so_deyr_s",    "Somalia",     "Deyr 2024",        "Somalia_Deyr",       [29, 33], ("Region", "District")),
    ("rw_a_s",       "Rwanda",      "Season A 2024",    "Rwanda_SeasonA",     [26, 30], ("Province", "District")),
    ("rw_b_s",       "Rwanda",      "Season B 2024",    "Rwanda_SeasonB",     [5, 12],  ("Province", "District")),
    ("bi_a_s",       "Burundi",     "Season A 2024",    "Burundi_SeasonA",    [26, 30], ("Province", "Commune")),
    ("bi_b_s",       "Burundi",     "Season B 2024",    "Burundi_SeasonB",    [5, 9],   ("Province", "Commune")),
    ("er_kremti_s",  "Eritrea",     "Kremti 2024",      "Eritrea_Kremti",     [17, 27], ("Region", "Sub-region")),
    ("tz_masika_s",  "Tanzania",    "Masika 2024",      "Tanzania_Masika",    [8, 12],  ("Region", "District")),
    ("et_belg_s",    "Ethiopia",    "Belg 2024",        "Ethiopia_Belg",      [5, 12],  ("Region", "Zone")),
]
_SORGHUM_RAIN = {"Kenya_Shortrains", "Uganda_2ndrains", "Rwanda_SeasonA", "Rwanda_SeasonB",
                 "Burundi_SeasonA", "Burundi_SeasonB", "Somalia_Deyr", "Ethiopia_Belg",
                 "South_Sudan_2nd"}
for _id, _c, _s, _tok, _win, _ln in _SORGHUM:
    PRODUCTS.append({
        "id": _id, "country": _c, "season": _s, "crop": "sorghum",
        "base": f"newcS_{_tok}_2024", "wbase": f"newcS_{_tok}_2024_wrsi",
        "win": _win, "levelnames": {1: _ln[0], 2: _ln[1]}, "scale": "250 m",
        "note": ("rainfall-anchored onset" if _tok in _SORGHUM_RAIN else "green-up cue-fusion onset")
                + " · crop-type mask sorghum band · Inception Report Table 2.0 calendar"
                + " · YIELD UNCALIBRATED, report CPI not yield",
    })

# ---- 2024 wheat, teff and millet products (crop_pipeline) ---------------------------------------
# Coverage is set by the crop-type masks, not by the statistics: millet exists only for Sudan and
# Eritrea because no other country has a millet mask band, and teff only for Ethiopia.
# id, crop, country, season label, base token, SOS window dekads, admin level names
_WTM = [
    ("wheat_et",   "wheat",  "Ethiopia", "Meher 2024",      "newcW", "Ethiopia_Meher",   [17, 24], ("Region", "Zone")),
    ("wheat_ke",   "wheat",  "Kenya",    "Long rains 2024", "newcW", "Kenya_Longrains",  [10, 19], ("County", "Constituency")),
    ("wheat_sd",   "wheat",  "Sudan",    "Shitwi 2024",     "newcW", "Sudan_Shitwi",     [32, 36], ("State", "Locality")),
    ("wheat_tz",   "wheat",  "Tanzania", "Msimu 2024",      "newcW", "Tanzania_Msimu",   [34, 39], ("Region", "District")),
    ("teff_et",    "teff",   "Ethiopia", "Meher 2024",      "newcT", "Ethiopia_Meher",   [19, 24], ("Region", "Zone")),
    ("millet_sd",  "millet", "Sudan",    "Kharif 2024",     "newcM", "Sudan_Kharif",     [17, 26], ("State", "Locality")),
    ("millet_er",  "millet", "Eritrea",  "Kremti 2024",     "newcM", "Eritrea_Kremti",   [17, 26], ("Region", "Sub-region")),
]
for _id, _cr, _c, _s, _pfx, _tok, _win, _ln in _WTM:
    PRODUCTS.append({
        "id": _id, "country": _c, "season": _s, "crop": _cr,
        "base": f"{_pfx}_{_tok}_2024", "wbase": f"{_pfx}_{_tok}_2024_wrsi",
        "win": _win, "levelnames": {1: _ln[0], 2: _ln[1]}, "scale": "250 m",
        "note": "crop-type mask " + _cr + " band",
        # Irrigated products are EXCLUDED from the apps. The FAO-56 water balance compares crop
        # demand against RAINFALL, so for a crop the scheme irrigates it returns WRSI 0, S_water
        # 100 % and CPI 0 everywhere. Sudan's Shitwi wheat came out as total failure across all 18
        # localities including the Gezira, the most productive irrigated wheat in the region. That
        # is not a caveat, it is a false statement, and in an early-warning app it is the dangerous
        # kind. The asset and the reduce CSV are kept: their DEFICIT is the irrigation requirement
        # and is meaningful. CPI, yield and stress are not, until the balance can credit irrigation.
        # Driven by the SPAM 2020 exposure grade, not by a hardcoded country-season, so any future
        # product on a majority-irrigated crop is caught without anyone remembering to add it.
        "exclude_from_apps": IRR.grade(_c, _cr) == "INVALID as rainfed",
        "exclude_reason": "irrigated: the rainfed water balance returns CPI 0 everywhere",
    })

KEYS = {1: ["name"], 2: ["county", "name"], 3: ["county", "constituency", "name"]}
SIMPLIFY = {1: 0.008, 2: 0.006, 3: 0.004}
PLANT = {"modal_dekad": "md", "mean_dekad": "mean", "p10": "p10", "p50": "p50", "p90": "p90",
         "hit_rate": "hit", "bias_dek": "bias", "mae_dek": "mae", "n_px": "n",
         "crop_area_frac": "caf", "spi3_dry_pct": "spidry", "spi3_mean": "spi",
         "pkv_dekad": "pkv", "flo_dekad": "flo", "grf_dekad": "grf", "mat_dekad": "mat",
         "crop_viable_pct": "viab", "lvpd_dekad": "lvpd",
         "wrsi_veg": "wrv", "wrsi_flo": "wrf", "wrsi_grf": "wrg",
         "wsi_veg": "wsv", "wsi_flo": "wsf", "wsi_grf": "wsg", "failflo_pct": "failflo",
         "cpi": "cpi", "yield_tha": "yld", "total_yield_t": "tyld",
         "s_water": "sw", "s_heat": "sh", "s_veg": "sv",
         "false_start_pct": "fstart", "waterlog_idx": "wlog", "waterlog_pct": "wlogp", "spi_wet_pct": "spiwet",
         "obs_plant_dk": "obs", "plant_err": "perr", "fcci": "fcci",
         # DMP: an INDEPENDENT ranking covariate, present only on the 8 products where CPI ranks
         # admin units backwards against reported yield. See dmp_covariate.py.
         "dmp": "dmp"}
WRSI = {"mean_WRSI": "wrsi", "mean_deficit_mm": "def", "fail_pct": "fail"}


def gload(path):
    df = pd.read_csv(path)
    g = gpd.GeoDataFrame(df, geometry=df["geometry_wkt"].map(wkt.loads), crs="EPSG:4326")
    return g.drop(columns=["geometry_wkt"])


def coords(geom, tol):
    geom = geom.simplify(tol, preserve_topology=True)
    polys = geom.geoms if geom.geom_type == "MultiPolygon" else [geom]
    out = []
    for p in polys:
        ring = [[round(x, 3), round(y, 3)] for x, y in p.exterior.coords]
        if len(ring) >= 4:
            out.append(ring)
    return out


def crop_ym_scale(cfg):
    """Factor converting the asset's yield to the FITTED ceiling, or None if there is none.

    The sorghum assets were exported before the ceilings were fitted, so their yield band carries
    the uncalibrated default. Yield is CPI/100 x Ym, linear in Ym, so multiplying by
    fitted / as-built is exact. The atlas already does this; without the same step here the apps
    and the atlas would show different yields for the same unit - the apps 2 to 4 times high.
    """
    crop = cfg.get("crop")
    if crop in (None, "maize"):
        return None
    import sys as _sys, os as _os
    _here = _os.path.dirname(_os.path.abspath(__file__))
    country, season = cfg["country"].replace(" ", "_"), cfg["season"].rsplit(" ", 1)[0]
    s_ = season.lower()
    short = "short" in s_ or "2nd" in s_ or "deyr" in s_
    if crop == "sorghum":
        _sys.path.insert(0, _os.path.join(_here, "sorghum_pipeline"))
        import sorghum_params as _P
        if not _P.is_calibrated(country, season):
            return None
        as_built = _P.SORGHUM_YM_SHORT_DEFAULT if short else _P.SORGHUM_YM_DEFAULT
        return _P.ym_for(country, season) / as_built
    _sys.path.insert(0, _os.path.join(_here, "crop_pipeline"))
    from params import get as _get
    _P = _get(crop)
    key = (country, season)
    if key not in _P.YM_CAL:
        return None                                   # leave it as exported, and say so in the note
    as_built = _P.YM_SHORT_DEFAULT if short else _P.YM_DEFAULT
    return _P.YM_CAL[key] / as_built


def build_product(cfg):
    scale_y = crop_ym_scale(cfg)
    note = cfg.get("note", "")
    # IRRIGATION EXPOSURE. The water balance credits rainfall only, so on an irrigated crop CPI and
    # yield read low and that is not crop condition. The grade rides on the product so the app can
    # show a banner rather than burying it in a footnote.
    _irr = IRR.record(cfg["country"], cfg.get("crop") or "maize")
    _iclause = IRR.app_note(cfg["country"], cfg.get("crop") or "maize")
    if cfg.get("crop") not in (None, "maize"):
        note = note.replace(" · YIELD UNCALIBRATED, report CPI not yield", "")
        if scale_y is not None:
            crop = cfg["crop"]
            country, season = cfg["country"].replace(" ", "_"), cfg["season"].rsplit(" ", 1)[0]
            if crop == "sorghum":
                import sorghum_params as _P; ym = _P.ym_for(country, season)
            else:
                from params import get as _get; ym = _get(crop).YM_CAL[(country, season)]
            note += f" · yield on the fitted ceiling Ym = {ym:.2f} t/ha"
        else:
            note += " · YIELD UNCALIBRATED — report CPI, not yield"
    # NOTE: deliberately NOT appended to `note`. The app renders it as a banner (prod["irr"]),
    # and duplicating it into the italic subtitle made the same sentence appear twice.
    # `_iclause` stays available for any consumer that has no banner.
    prod = {"id": cfg["id"], "country": cfg["country"], "season": cfg["season"],
            "crop": cfg["crop"], "scale": cfg["scale"], "win": cfg["win"],
            "note": note, "levels": {}}
    if _irr and _irr["grade"] not in ("negligible", "unknown"):
        prod["irr"] = {"grade": _irr["grade"], "pct": _irr["national_irr_pct"],
                       "ha": _irr["irr_area_ha"], "units": _irr["compromised_units"],
                       "msg": IRR.GUIDANCE[_irr["grade"]]}
    for lvl in (1, 2, 3):
        try:
            pl = gload(f"{cfg['base']}_L{lvl}_skill_WKT.csv")
        except FileNotFoundError:
            print(f"  [skip] {cfg['id']} L{lvl}: no skill WKT"); continue
        try:
            wr = gload(f"{cfg['wbase']}_L{lvl}_admin_WKT.csv")[KEYS[lvl] + list(WRSI)]
            m = pl.merge(wr, on=KEYS[lvl], how="left")
        except (FileNotFoundError, KeyError):
            m = pl.copy()
            for k in WRSI:
                if k not in m.columns:          # keep WRSI cols the skill CSV already carries (new countries)
                    m[k] = None
        units = []
        for _, r in m.iterrows():
            a = {v: (round(float(r[k]), 3) if k in r and pd.notna(r[k]) else None)
                 for k, v in {**PLANT, **WRSI}.items()}
            if scale_y is not None:                    # rescale to the fitted ceiling
                for _k in ("yld", "tyld"):
                    if a.get(_k) is not None:
                        a[_k] = round(a[_k] * scale_y, 3)
            sv = lambda k: (str(r[k]) if k in r and pd.notna(r[k]) else "")   # NaN/empty -> "" (valid JSON)
            units.append({"n": sv("name"), "p": sv("county"),
                          "c": sv("constituency") if lvl == 3 else "",
                          "a": a, "g": coords(r.geometry, SIMPLIFY[lvl])})
        prod["levels"][str(lvl)] = {"label": cfg["levelnames"][lvl], "units": units}
        print(f"  {cfg['id']} L{lvl} {cfg['levelnames'][lvl]}: {len(units)} units")
    return prod


data = {"products": [], "default": PRODUCTS[0]["id"]}
skipped = []
excluded = []
for cfg in PRODUCTS:
    # A product dropped by decision (crop_coverage.DROPPED) never reaches the apps, whichever
    # registry it was listed in. South Sudan maize is the case: the crop-type mask leaves it
    # 135 pixels country-wide, too thin for admin-level reporting.
    if COV.is_dropped(cfg.get("crop") or "maize", cfg["country"]):
        excluded.append(f"{cfg['crop']}: {cfg['country']} {cfg['season']} — dropped by decision "
                        f"(crop_coverage.DROPPED)")
        continue
    if cfg.get("exclude_from_apps"):
        excluded.append(f"{cfg['crop']}: {cfg['country']} {cfg['season']} "
                        f"— {cfg['exclude_reason']}")
        continue
    print(f"== {cfg['country']} · {cfg['season']} · {cfg['crop']} ({cfg['scale']}) ==")
    prod = build_product(cfg)
    if not prod["levels"]:
        # a product with no levels would reach the app as an empty entry and break the selector
        skipped.append(f"{cfg['crop']}: {cfg['country']} {cfg['season']}")
        continue
    data["products"].append(prod)
data["crops"] = sorted({p["crop"] for p in data["products"]})

js = json.dumps(data, separators=(",", ":"), allow_nan=False)   # NaN is invalid JSON -> fail loudly
open("app_data.json", "w").write(js)
from collections import Counter
byc = Counter(p["crop"] for p in data["products"])
print(f"\napp_data.json — {len(js)/1e6:.2f} MB · {len(data['products'])} products "
      f"({', '.join(f'{v} {k}' for k, v in sorted(byc.items()))})")
_flag = [p for p in data["products"] if p.get("irr")]
if _flag:
    print(f"IRRIGATION-FLAGGED IN APP ({len(_flag)}):")
    for p in _flag:
        print(f"    {p['crop']:8s} {p['country']:12s} {p['season']:18s} {p['irr']['grade']}")
if excluded:
    print(f"DELIBERATELY EXCLUDED ({len(excluded)}):")
    for x in excluded:
        print("   ", x)
if skipped:
    print(f"not built, no reduce CSV yet ({len(skipped)}):")
    for x in skipped:
        print("   ", x)
