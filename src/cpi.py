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
YM_THA = 4.5                                # reference water-unlimited yield, short-duration maize (t/ha)


def s_water(ee, staged):
    """FAO-33 stage-weighted water-stress fraction 0–1, from per-stage AET/WR (run_wrsi_staged)."""
    S = ee.Image.constant(0.0)
    for s, ky in KY.items():
        rel_def = ee.Image(1).subtract(staged[f"aet_{s}"].divide(staged[f"wr_{s}"].max(1e-6))).clamp(0, 1)
        S = S.add(rel_def.multiply(ky))
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


def s_heat(ee, aoi, year, planting_dk, d_veg, d_flo, sos_start, sos_end):
    """Heat-stress fraction 0–1 — heat-degree-dekads above HEAT_TCAP during the FLOWERING stage."""
    tmax = _tmax_dekadal(ee, aoi, year)
    heat = ee.Image.constant(0.0)
    for gd in range(max(1, sos_start), sos_end + d_flo + 2):
        dsp = ee.Image.constant(gd).subtract(planting_dk)
        flo = dsp.gte(d_veg).And(dsp.lt(d_flo))                      # flowering window
        tg = ee.Image(tmax.filter(ee.Filter.eq("gd", gd)).first())
        heat = heat.add(tg.subtract(HEAT_TCAP).max(0).multiply(flo))
    return heat.multiply(HEAT_K).clamp(0, 1).rename("S_heat")


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
