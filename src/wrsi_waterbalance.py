"""Full FAO-56/33 dekadal Water Requirement Satisfaction Index (WRSI) in pure GEE.
No GeoWRSI hand-off. Components:
  - Hargreaves ET0 from ERA5-Land 2 m Tmin/Tmax (global; GRIDMET does NOT cover Africa).
  - Extraterrestrial radiation Ra computed per dekad from latitude + mid-dekad DOY.
  - Per-crop Kc curve (config/crop_coefficients.yaml).
  - Per-pixel soil-water balance that STARTS at each pixel's detected planting dekad.
WRSI = 100 * sum(AET) / sum(WR) over the crop cycle.
"""
from __future__ import annotations
import math
from .utils import dekad_to_start_date

GSC = 0.0820  # MJ m-2 min-1

# ---------------- extraterrestrial radiation & ET0 ----------------
def _ra_mm_image(ee, lat_rad_img, doy):
    """Ra (mm/day equiv) image for a given day-of-year (client int)."""
    b = 2 * math.pi * doy / 365.0
    dr = 1 + 0.033 * math.cos(b)
    delta = 0.409 * math.sin(b - 1.39)
    sin_d, cos_d = math.sin(delta), math.cos(delta)
    ws = lat_rad_img.tan().multiply(-math.tan(delta)).acos()          # sunset hour angle (img)
    ra = (ws.multiply(lat_rad_img.sin()).multiply(sin_d)
            .add(lat_rad_img.cos().multiply(cos_d).multiply(ws.sin())))
    ra = ra.multiply((24 * 60 / math.pi) * GSC * dr)                  # MJ m-2 day-1
    return ra.multiply(0.408)                                         # -> mm/day

def _ndays(year, dekad):
    import calendar
    month = (dekad - 1) // 3 + 1
    k = (dekad - 1) % 3
    if k < 2: return 10
    return calendar.monthrange(year, month)[1] - 20

def hargreaves_et0_dekadal(ee, aoi, year, gd_offset=0):
    """Dekadal ET0 (mm) ImageCollection for one year; each image tagged 'gd'=dekad+gd_offset."""
    era = (ee.ImageCollection("ECMWF/ERA5_LAND/DAILY_AGGR")
             .filterBounds(aoi).filterDate(f"{year}-01-01", f"{year+1}-01-05"))
    lat = ee.Image.pixelLonLat().select("latitude").multiply(math.pi / 180.0)
    out = []
    for dk in range(1, 37):
        s = ee.Date(dekad_to_start_date(year, dk).isoformat()); e = s.advance(10, "day")
        blk = era.filterDate(s, e)
        tmax = blk.select("temperature_2m_max").mean().subtract(273.15)
        tmin = blk.select("temperature_2m_min").mean().subtract(273.15)
        tmean = tmax.add(tmin).divide(2)
        doy = dekad_to_start_date(year, dk).timetuple().tm_yday + 5
        ra = _ra_mm_image(ee, lat, doy)
        et0d = (ra.multiply(0.0023)
                  .multiply(tmean.add(17.8))
                  .multiply(tmax.subtract(tmin).max(0).sqrt()))       # mm/day
        et0 = et0d.multiply(_ndays(year, dk)).rename("ET0")          # mm/dekad
        out.append(et0.set({"gd": dk + gd_offset, "system:time_start": s.millis()}))
    return ee.ImageCollection(out)

# ---------------- Kc curve ----------------
def kc_from_dsp(ee, dsp, p):
    """Kc image from dekads-since-planting `dsp` (float image) and param dict p."""
    Lini, Ldev, Lmid, Llate = p["L_ini"], p["L_dev"], p["L_mid"], p["L_late"]
    d1, d2, d3, d4 = Lini, Lini+Ldev, Lini+Ldev+Lmid, p["LGP_dekads"]
    ki, km, ke = p["Kc_ini"], p["Kc_mid"], p["Kc_end"]
    kc = ee.Image.constant(0.0)
    kc = kc.where(dsp.gte(0).And(dsp.lt(d1)), ki)
    devf = dsp.subtract(d1).divide(max(Ldev, 1e-6))
    kc = kc.where(dsp.gte(d1).And(dsp.lt(d2)), ee.Image.constant(ki).add(devf.multiply(km-ki)))
    kc = kc.where(dsp.gte(d2).And(dsp.lt(d3)), km)
    latef = dsp.subtract(d3).divide(max(Llate, 1e-6))
    kc = kc.where(dsp.gte(d3).And(dsp.lt(d4)), ee.Image.constant(km).add(latef.multiply(ke-km)))
    return kc.rename("Kc")

# ---------------- WRSI water balance ----------------
def run_wrsi_fao33(ee, aoi, year, planting_dekad_img, crop, kc_cfg, soil_cfg,
                   sos_start, sos_end, chirps_ic=None, whc_img=None):
    """Return dict of images: WRSI, deficit, AET, WR, end soil water.
    Iterates dekads from just before earliest planting to latest planting + LGP,
    spanning into year+1 when the cycle wraps the year end."""
    p = kc_cfg[crop]
    LGP = p["LGP_dekads"]

    # 2-year dekadal ET0 and rainfall keyed by global dekad gd (1..72)
    et0 = (hargreaves_et0_dekadal(ee, aoi, year, 0)
           .merge(hargreaves_et0_dekadal(ee, aoi, year+1, 36)))
    if chirps_ic is None:
        from .wrsi_feedback import chirps_dekadal
        chirps_ic = (_tag_gd(ee, chirps_dekadal(ee, aoi, year), 0)
                     .merge(_tag_gd(ee, chirps_dekadal(ee, aoi, year+1), 36)))
    et0_by = {}; p_by = {}
    gd_start = max(1, sos_start - 1)
    gd_end = sos_end + LGP + 1
    for gd in range(gd_start, gd_end + 1):
        et0_by[gd] = ee.Image(et0.filter(ee.Filter.eq("gd", gd)).first())
        p_by[gd]   = ee.Image(chirps_ic.filter(ee.Filter.eq("gd", gd)).first())

    whc = whc_img if whc_img is not None else ee.Image.constant(soil_cfg["default_whc_mm"])
    SW = whc.multiply(soil_cfg["init_soil_water_frac"])
    cumAET = ee.Image.constant(0.0); cumWR = ee.Image.constant(0.0); cumDef = ee.Image.constant(0.0)

    for gd in range(gd_start, gd_end + 1):
        et0_g = et0_by[gd]
        P = p_by[gd]
        dsp = ee.Image.constant(gd).subtract(planting_dekad_img)     # dekads since planting
        active = dsp.gte(0).And(dsp.lt(LGP))
        Kc = kc_from_dsp(ee, dsp, p).multiply(active)
        WR = Kc.multiply(et0_g)                                      # water requirement (mm)
        Wb = SW.add(P)                                              # water available
        AET = Wb.min(WR)
        leftover = Wb.subtract(AET)
        SW = leftover.min(whc).max(0)                              # updated soil water
        cumAET = cumAET.add(AET); cumWR = cumWR.add(WR); cumDef = cumDef.add(WR.subtract(AET))

    wrsi = cumAET.divide(cumWR.max(1e-6)).multiply(100).rename("WRSI")
    return {"WRSI": wrsi, "deficit_mm": cumDef.rename("deficit_mm"),
            "AET_mm": cumAET.rename("AET_mm"), "WR_mm": cumWR.rename("WR_mm"),
            "soil_water_end_mm": SW.rename("SW_end")}

def run_wrsi_staged(ee, aoi, year, planting_dekad_img, crop, kc_cfg, soil_cfg,
                    sos_start, sos_end, chirps_ic=None, whc_img=None):
    """Dekadal RUNNING WRSI + dekadal water-stress (WSI) snapshotted at the end of the three FAO-56
    growth stages — vegetative (initial+development) · flowering (mid-season) · grain-fill (late).
    Bands: wrsi_veg/flo/grf (running WRSI at each stage end, 0-100), wsi_veg/flo/grf (max dekadal
    water stress in each stage, 0-100). Crop-failure per stage = wrsi_* < 50. Wraps into year+1."""
    p = kc_cfg[crop]
    Lini, Ldev, Lmid = p["L_ini"], p["L_dev"], p["L_mid"]
    LGP = p["LGP_dekads"]
    d_veg, d_flo, d_grf = Lini + Ldev, Lini + Ldev + Lmid, LGP     # stage-end (dekads-since-planting)

    et0 = (hargreaves_et0_dekadal(ee, aoi, year, 0)
           .merge(hargreaves_et0_dekadal(ee, aoi, year + 1, 36)))
    if chirps_ic is None:
        from .wrsi_feedback import chirps_dekadal
        chirps_ic = (_tag_gd(ee, chirps_dekadal(ee, aoi, year), 0)
                     .merge(_tag_gd(ee, chirps_dekadal(ee, aoi, year + 1), 36)))
    gd_start, gd_end = max(1, sos_start - 1), sos_end + LGP + 2
    et0_by = {gd: ee.Image(et0.filter(ee.Filter.eq("gd", gd)).first()) for gd in range(gd_start, gd_end + 1)}
    p_by = {gd: ee.Image(chirps_ic.filter(ee.Filter.eq("gd", gd)).first()) for gd in range(gd_start, gd_end + 1)}

    whc = whc_img if whc_img is not None else ee.Image.constant(soil_cfg["default_whc_mm"])
    SW = whc.multiply(soil_cfg["init_soil_water_frac"])
    cumAET = ee.Image.constant(0.0); cumWR = ee.Image.constant(0.0)
    Z = ee.Image.constant(0.0)
    wrsi = {"veg": Z, "flo": Z, "grf": Z}; wsi = {"veg": Z, "flo": Z, "grf": Z}
    sAET = {"veg": Z, "flo": Z, "grf": Z}; sWR = {"veg": Z, "flo": Z, "grf": Z}   # per-stage AET/WR

    for gd in range(gd_start, gd_end + 1):
        dsp = ee.Image.constant(gd).subtract(planting_dekad_img)   # dekads since planting
        active = dsp.gte(0).And(dsp.lt(LGP))
        Kc = kc_from_dsp(ee, dsp, p).multiply(active)
        WR = Kc.multiply(et0_by[gd])
        Wb = SW.add(p_by[gd]); AET = Wb.min(WR); SW = Wb.subtract(AET).min(whc).max(0)
        cumAET = cumAET.add(AET); cumWR = cumWR.add(WR)
        runWRSI = cumAET.divide(cumWR.max(1e-6)).multiply(100)
        wsi_g = ee.Image(1).subtract(AET.divide(WR.max(1e-6))).clamp(0, 1).multiply(active).multiply(100)
        veg = active.And(dsp.lt(d_veg))
        flo = active.And(dsp.gte(d_veg)).And(dsp.lt(d_flo))
        grf = active.And(dsp.gte(d_flo)).And(dsp.lt(d_grf))
        for s, msk in (("veg", veg), ("flo", flo), ("grf", grf)):
            wsi[s] = wsi[s].max(wsi_g.multiply(msk))
            sAET[s] = sAET[s].add(AET.multiply(msk)); sWR[s] = sWR[s].add(WR.multiply(msk))
        wrsi["veg"] = wrsi["veg"].where(dsp.eq(d_veg), runWRSI)
        wrsi["flo"] = wrsi["flo"].where(dsp.eq(d_flo), runWRSI)
        wrsi["grf"] = wrsi["grf"].where(dsp.eq(d_grf), runWRSI)   # = final (whole-cycle) WRSI

    m = planting_dekad_img.mask()
    out = {}
    for s in ("veg", "flo", "grf"):
        out[f"wrsi_{s}"] = wrsi[s].updateMask(m).rename(f"wrsi_{s}")
        out[f"wsi_{s}"] = wsi[s].updateMask(m).rename(f"wsi_{s}")
        out[f"aet_{s}"] = sAET[s].updateMask(m).rename(f"aet_{s}")     # per-stage actual ET
        out[f"wr_{s}"] = sWR[s].updateMask(m).rename(f"wr_{s}")        # per-stage water requirement
    return out


def _tag_gd(ee, ic, offset):
    return ic.map(lambda i: i.set("gd", ee.Number(i.get("dekad")).add(offset)))

def classify_wrsi(ee, wrsi):
    """FEWS/GeoWRSI crop-performance classes from WRSI value."""
    return (ee.Image(0)
            .where(wrsi.gte(95), 5)              # no/very-mild deficit
            .where(wrsi.lt(95).And(wrsi.gte(80)), 4)
            .where(wrsi.lt(80).And(wrsi.gte(60)), 3)  # mediocre
            .where(wrsi.lt(60).And(wrsi.gte(50)), 2)  # poor
            .where(wrsi.lt(50), 1)              # crop failure
            .rename("wrsi_class").updateMask(wrsi.mask()))
