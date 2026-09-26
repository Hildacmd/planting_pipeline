"""Crop Performance Index (CPI) — multi-stress multiplicative stacking (AquaCrop / crop-model logic).

    Ya/Ym = (1 − S_water) · (1 − S_heat) · (1 − S_veg)      CPI = 100 · Ya/Ym
    yield (t/ha) = CPI/100 · Ym       total (t) = yield · maize_area_ha

Each hazard is an independent 0–1 yield-reduction, stage-weighted by the FAO-33 Ky (flowering hurts
most). Water stress uses the FAO-33 stage form; heat is concentrated at flowering (pollen sterility);
vegetation (VCI) is a down-weighted condition confirmation. References: Doorenbos & Kassam 1979 (Ky);
Steduto/Raes 2009 (AquaCrop multiplicative stacking); Butler & Huybers 2013 (maize heat); Kogan 1995
(VCI). Ym is a REFERENCE potential yield — calibrate against observed yields (KALRO / HarvestStat).
"""
KY = {"veg": 0.4, "flo": 1.5, "grf": 0.5}   # FAO-33 stage yield-response factors
HEAT_TCAP = 33.0                            # °C: dekad-mean Tmax above which maize flowering is hurt
HEAT_K = 0.06                               # yield loss per heat-degree-dekad at flowering (capped)
VEG_W = 0.4                                 # vegetation-condition weight (VCI is a confirmation)
YM_THA = 4.5                                # legacy uncalibrated default, short-duration maize (t/ha)

# HarvestStat-calibrated attainable ceiling Ym per (country, season) - TYPICAL-YEAR fit (Sep 2026).
# calibrate_ym_local.py: 2024 admin CPI aggregated onto HarvestStat units (maize-area overlap weights);
# target = median yield over the available years; least squares through the origin, 70/30 x 200 held-out
# test. Report: yield_calibration_2024/YIELD_CALIBRATION_2024.md. Held-out MAE t/ha (calibrated vs default), r:
#   Kenya Long rains    2.34  2015-24, n45   0.68 vs 2.26   r 0.57   level + pattern
#   Kenya Short rains   1.44  2016-24, n44   0.39 vs 1.94   r 0.36   level, weak pattern
#   Ethiopia Meher      4.14  2012-21, n76   0.71 vs 1.38   r 0.64   level + pattern
#   Rwanda Season A     2.61  2010-17, n30   0.37 vs 2.75   r -0.07  level only
#   Burundi Season A    1.88  2012-16, n16   0.71 vs 3.57   r 0.28   level only
#   Somalia Gu          1.02  2015-24, n18   0.24 vs 1.58   r 0.34   level only
#   Uganda 1st rains    2.34  2008-09, n74   1.24 vs 2.90   r -0.14  PROVISIONAL (statistics end 2009)
# Superseded 2024-season values: Kenya Long 2.59 (+ highland 3.2/2.1), Short 2.02; Ethiopia Meher 4.42.
# Tanzania and South Sudan have no HarvestStat maize yields: they fall back to the uncalibrated defaults.
YM_CAL = {
    ("Kenya", "Long rains"):   2.34,
    ("Kenya", "Short rains"):  1.44,
    ("Ethiopia", "Meher"):     4.14,
    ("Rwanda", "Season A"):    2.61,
    ("Burundi", "Season A"):   1.88,
    ("Somalia", "Gu"):         1.02,
    ("Uganda", "1st rains"):   2.34,     # provisional
}
# Ym fitted on the ICPAC CROP-TYPE-MASK footprint (calibrate_ym_ctm.py). Use ONLY
# with the cpiCTMX_/newcCTM_ products - a ceiling and a footprint are a matched
# pair, because the mask changes both CPI and the crop-area weights it is fitted
# against. Do NOT apply these to the WorldCereal products in YM_CAL above.
YM_CAL_CTM = {
    ("Kenya", "Long rains"): 2.16,   # n46 MAE 0.72 vs wc 0.65  r 0.48
    ("Kenya", "Short rains"): 1.32,   # n44 MAE 0.34 vs wc 0.4  r 0.27
    ("Ethiopia", "Meher"): 3.78,   # n77 MAE 0.7 vs wc 0.69  r 0.45
    ("Rwanda", "Season A"): 2.58,   # n30 MAE 0.36 vs wc 0.37  r -0.08
    ("Burundi", "Season A"): 1.89,   # n16 MAE 0.72 vs wc 0.71  r 0.22
    ("Somalia", "Gu"): 0.88,   # n31 MAE 0.25 vs wc 0.24  r 0.53
    ("Uganda", "1st rains"): 2.23,   # n74 MAE 1.26 vs wc 1.24  r -0.23  PROVISIONAL
}

YM_MAIN_DEFAULT = 6.0                        # uncalibrated fallback, medium/long maize (t/ha)
YM_SHORT_DEFAULT = 4.5                       # uncalibrated fallback, short-duration maize (t/ha)

def ym_for(country, season):
    """Calibrated attainable yield ceiling (t/ha) for a (country, season); falls back to the
    uncalibrated season default where no HarvestStat calibration exists yet."""
    if (country, season) in YM_CAL:
        return YM_CAL[(country, season)]
    return YM_SHORT_DEFAULT if "short" in str(season).lower() else YM_MAIN_DEFAULT


# AEZ-aware ceiling: cool highland maize has a HIGHER attainable Ym than lowland/midland (its yield
# edge is potential, not water). Kenya Long rains, HarvestStat 70/30 A/B: a per-zone Ym (highland
# 3.7 / rest 2.3 t/ha) beats a single Ym — held-out MAE 0.57 -> 0.47 — whereas a zone-aware growing
# period (180 d highland) made it WORSE (0.57 -> 0.66). So the highland lever is Ym, not the season.
# The highland split was fitted to 2024 county yields alone (3.2 / 2.1 t/ha, MAE 0.40 against 2024). It is OFF
# under the typical-year calibration, which uses one ceiling per (country, season); re-enable to reproduce 2024.
YM_HIGHLAND = {}   # e.g. {("Kenya", "Long rains"): (3.2, 2.1)}  (highland >= 1800 m, rest)
HIGHLAND_ELEV_M = 1800

def ym_img_for(ee, aoi, country, season, dem="USGS/SRTMGL1_003"):
    """Per-pixel attainable ceiling Ym (t/ha), AEZ-aware where calibrated: highland pixels
    (elevation >= 1800 m) carry a higher ceiling. Returns a constant image = ym_for() elsewhere.
    Usable directly as the `ym` argument to cpi() (which multiplies element-wise)."""
    hl = YM_HIGHLAND.get((country, season))
    if hl is None:
        return ee.Image.constant(ym_for(country, season)).rename("Ym")
    ym_hi, ym_lo = hl
    highland = ee.Image(dem).select(0).gte(HIGHLAND_ELEV_M)
    return ee.Image.constant(ym_lo).where(highland, ym_hi).rename("Ym")


def s_water(ee, staged, ky=None):
    """FAO-33 stage-weighted water-stress fraction 0–1, from per-stage AET/WR (run_wrsi_staged).

    `ky` overrides the module's maize stage factors with another crop's, e.g. FAO-33 sorghum
    {"veg": 0.2, "flo": 0.55, "grf": 0.45} (total 0.9 against maize 1.25). Default = maize."""
    S = ee.Image.constant(0.0)
    for stage, k in (ky or KY).items():
        rel_def = ee.Image(1).subtract(staged[f"aet_{stage}"].divide(staged[f"wr_{stage}"].max(1e-6))).clamp(0, 1)
        S = S.add(rel_def.multiply(k))
    return S.clamp(0, 1).rename("S_water")


def _tmax_dekadal(ee, aoi, year):
    """Dekad-mean Tmax (°C) keyed by global dekad gd (1..72 = year then year+1)."""
    from .utils import dekad_to_start_date
    col = ee.ImageCollection("ECMWF/ERA5_LAND/DAILY_AGGR").filterBounds(aoi)
    out = []
    for off, yr in ((0, year), (36, year + 1)):
        for dk in range(1, 37):
            s = ee.Date(dekad_to_start_date(yr, dk).isoformat())
            tmax = col.filterDate(s, s.advance(10, "day")).select("temperature_2m_max").mean().subtract(273.15)
            out.append(tmax.set("gd", dk + off))
    return ee.ImageCollection(out)


def s_heat(ee, aoi, year, planting_dk, d_veg, d_flo, sos_start, sos_end, d_flo_max=None,
           tcap=None, k=None):
    """Heat-stress fraction 0–1 — heat-degree-dekads above HEAT_TCAP during the FLOWERING stage.

    `d_veg`/`d_flo` may be SCALARS (fixed config stages, previous behaviour) or ee.Images (per-pixel
    stage boundaries stretched to a data-derived cycle — see wrsi_waterbalance.stage_bounds). When
    they are images the Python loop still needs a scalar upper bound: pass `d_flo_max`, the maximum
    flowering-end dekad over the AOI, otherwise the window would be truncated for late pixels."""
    # tcap/k override the module constants so the threshold can be A/B tested. HEAT_TCAP is a
    # DEKAD-MEAN Tmax; measured dekad-mean flowering Tmax peaks at 22.9 / 25.9 / 29.3 C across
    # Kenya's three season regimes, so the shipped 33 C cannot fire in two of them.
    TC = HEAT_TCAP if tcap is None else float(tcap)
    KK = HEAT_K if k is None else float(k)
    tmax = _tmax_dekadal(ee, aoi, year)
    heat = ee.Image.constant(0.0)
    is_img = hasattr(d_flo, "bandNames")
    if is_img and d_flo_max is None:
        raise ValueError("s_heat: d_flo is an image — pass d_flo_max (scalar AOI max) for the loop bound")
    hi = int(d_flo_max) if is_img else d_flo
    dv = d_veg if hasattr(d_veg, "bandNames") else ee.Image.constant(d_veg)
    df = d_flo if is_img else ee.Image.constant(d_flo)
    for gd in range(max(1, sos_start), sos_end + hi + 2):
        dsp = ee.Image.constant(gd).subtract(planting_dk)
        flo = dsp.gte(dv).And(dsp.lt(df))                            # flowering window
        tg = ee.Image(tmax.filter(ee.Filter.eq("gd", gd)).first())
        heat = heat.add(tg.subtract(TC).max(0).multiply(flo))
    return heat.multiply(KK).clamp(0, 1).rename("S_heat")


# vegetation index for S_veg. 'ndvi' -> VCI (min-max, Kogan 1995); 'fpar' -> standardized FPAR
# anomaly zFPAR (JRC-ASAP convention, Rembold 2019). Selectable at runtime via env VEG_INDEX.
VEG_CFG = {"ndvi": ("MODIS/061/MOD13Q1", "NDVI", 0.0001),   # 250 m
           "fpar": ("MODIS/061/MCD15A3H", "Fpar", 0.01)}    # 500 m
ZFPAR_FULL = 2.0                                            # z = −2 (shortfall) -> full stress weight


def _seasonal_peak(ee, aoi, yr, sos_start, sos_end, collection, band, scale):
    """Max compositing of `band` over the season (sos_start..sos_end, year-wrap aware) -> peak value."""
    from .utils import dekad_to_start_date
    s = ee.Date(dekad_to_start_date(yr, sos_start).isoformat())
    e = ee.Date(dekad_to_start_date(yr if sos_end <= 36 else yr + 1,
                                    ((sos_end - 1) % 36) + 1).isoformat()).advance(40, "day")
    return ee.ImageCollection(collection).filterBounds(aoi).filterDate(s, e).select(band).max().multiply(scale)


def s_veg(ee, aoi, year, sos_start, sos_end, clim_years=range(2003, 2024), source="ndvi"):
    """Vegetation-condition stress (0–1), down-weighted by VEG_W (a confirmation on water/heat).
      source='ndvi' -> S_veg = VEG_W·(1 − VCI),  VCI = (NDVI−min)/(max−min)         [Kogan 1995]
      source='fpar' -> S_veg = VEG_W·clamp(−zFPAR/2, 0, 1),  zFPAR = (FPAR−μ)/σ      [ASAP; Rembold 2019]
    Both use the seasonal-peak value, current vs the historical distribution over clim_years."""
    collection, band, scale = VEG_CFG[source]
    peak = lambda yr: _seasonal_peak(ee, aoi, yr, sos_start, sos_end, collection, band, scale)
    cur = peak(year)
    hist = ee.ImageCollection([peak(y) for y in clim_years])
    if source == "fpar":
        mu, sd = hist.mean(), hist.reduce(ee.Reducer.stdDev())
        z = cur.subtract(mu).divide(sd.max(1e-6))                       # standardized anomaly (zFPAR)
        stress = z.multiply(-1.0).divide(ZFPAR_FULL).clamp(0, 1)        # only shortfalls; z=−2 -> 1
    else:
        vmin, vmax = hist.min(), hist.max()
        vci = cur.subtract(vmin).divide(vmax.subtract(vmin).max(1e-3)).clamp(0, 1)
        stress = ee.Image(1).subtract(vci)
    return stress.multiply(VEG_W).clamp(0, 1).rename("S_veg")


def s_veg_fpar(ee, aoi, year, sos_start, sos_end, clim_years=range(2003, 2024)):
    """ASAP-aligned vegetation stress from the standardized FPAR anomaly (zFPAR). Thin wrapper."""
    return s_veg(ee, aoi, year, sos_start, sos_end, clim_years, source="fpar")


def cpi(ee, Sw, Sh, Sv, ym=YM_THA):
    """Combine the three stresses -> CPI (0–100) and yield (t/ha)."""
    rel = ee.Image(1).subtract(Sw).multiply(ee.Image(1).subtract(Sh)).multiply(ee.Image(1).subtract(Sv))
    cpi_img = rel.clamp(0, 1).multiply(100).rename("CPI")
    yld = cpi_img.divide(100).multiply(ym).rename("yield_tha")
    return cpi_img, yld
