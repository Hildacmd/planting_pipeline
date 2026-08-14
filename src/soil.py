"""Spatial soil water-holding capacity (WHC, mm) over the crop root zone, for the WRSI balance.

WHC = integral over 0..root_depth of AWC(z) dz ,  AWC = (FieldCapacity - WiltingPoint) [vol fraction]

Two builders, selected by `soil_cfg['whc_source']` via `get_whc()`:

1. 'saxton_soilgrids' (default, most rigorous) — field capacity (theta_33) AND wilting point
   (theta_1500) are BOTH derived physically from SoilGrids 2.0 texture (sand, clay) and organic
   matter (from SOC) using the Saxton & Rawls (2006) pedotransfer functions. No proxy WP.
     SoilGrids assets (ISRIC on GEE, 6 depth layers, 250 m):
       projects/soilgrids-isric/clay_mean  (g/kg)   projects/soilgrids-isric/sand_mean (g/kg)
       projects/soilgrids-isric/soc_mean   (dg/kg)
2. 'openlandmap' (legacy) — field capacity from OpenLandMap 33 kPa water content; wilting point
   estimated as wp_frac * FC (texture-agnostic), unless a real WP raster is passed via wp_asset.

The soil layers are STATIC, so `get_whc()` returns a server-side ee.Image that Earth Engine caches;
for repeated runs, materialize it ONCE with `export_whc_to_asset()` (stays in EE, referenced by id,
nothing re-downloads per run) or `export_whc_to_drive()` (a single GeoTIFF on disk), then set
`soil_cfg['whc_asset']` to that id/path so runs just load it.
"""
from __future__ import annotations

# ---- OpenLandMap (legacy builder) ---------------------------------------------------------------
FC_ASSET = "OpenLandMap/SOL/SOL_WATERCONTENT-33KPA_USDA-4B1C_M/v01"
NODES_CM = [0, 10, 30, 60, 100, 200]
BANDS    = ["b0", "b10", "b30", "b60", "b100", "b200"]

# ---- SoilGrids 2.0 (Saxton-Rawls builder) -------------------------------------------------------
SG_CLAY = "projects/soilgrids-isric/clay_mean"   # g/kg   -> fraction = /1000
SG_SAND = "projects/soilgrids-isric/sand_mean"   # g/kg   -> fraction = /1000
SG_SOC  = "projects/soilgrids-isric/soc_mean"    # dg/kg  -> SOC% = /100 ; OM% = 1.724 * SOC%
SG_LAYERS_CM = [(0, 5), (5, 15), (15, 30), (30, 60), (60, 100), (100, 200)]
SG_SUFFIX    = ["0-5cm_mean", "5-15cm_mean", "15-30cm_mean", "30-60cm_mean", "60-100cm_mean", "100-200cm_mean"]


def build_whc_mm(ee, root_depth_cm=100, wp_frac=0.45, fc_scale=0.01,
                 fc_asset=FC_ASSET, wp_asset=None, wp_scale=0.01, min_whc_mm=25):
    """Legacy OpenLandMap WHC (mm). Field capacity real; wilting point = wp_frac*FC unless wp_asset."""
    fc = ee.Image(fc_asset).multiply(fc_scale)          # vol% -> fraction
    if wp_asset:
        wp = ee.Image(wp_asset).multiply(wp_scale)
    else:
        wp = fc.multiply(wp_frac)                       # WP ~ wp_frac * FC (fallback)
    awc = fc.subtract(wp).max(0)                        # available water fraction per node

    whc = ee.Image.constant(0.0)
    for i in range(len(NODES_CM) - 1):
        top, bot = NODES_CM[i], NODES_CM[i + 1]
        if top >= root_depth_cm:
            break
        eff_bot = min(bot, root_depth_cm)
        th_mm = (eff_bot - top) * 10.0                  # cm -> mm
        a_top = awc.select(BANDS[i])
        a_bot = awc.select(BANDS[i + 1])
        frac = (eff_bot - top) / (bot - top)            # linear clip of partial layer
        a_eff = a_top.add(a_bot.subtract(a_top).multiply(frac))
        whc = whc.add(a_top.add(a_eff).multiply(0.5 * th_mm))
    return whc.max(min_whc_mm).rename("WHC_mm")


def _saxton_fc_wp(sand_frac, clay_frac, om_pct):
    """Saxton & Rawls (2006) SSSAJ pedotransfer -> (theta_33 FC, theta_1500 WP), vol fractions.
    Inputs: sand & clay as mass fractions (0-1), organic matter as percent. All ee.Image."""
    Sa, Cl, OM = sand_frac, clay_frac, om_pct
    # wilting point, 1500 kPa
    wp_t = (Sa.multiply(-0.024).add(Cl.multiply(0.487)).add(OM.multiply(0.006))
            .add(Sa.multiply(OM).multiply(0.005)).subtract(Cl.multiply(OM).multiply(0.013))
            .add(Sa.multiply(Cl).multiply(0.068)).add(0.031))
    wp = wp_t.add(wp_t.multiply(0.14).subtract(0.02))
    # field capacity, 33 kPa
    fc_t = (Sa.multiply(-0.251).add(Cl.multiply(0.195)).add(OM.multiply(0.011))
            .add(Sa.multiply(OM).multiply(0.006)).subtract(Cl.multiply(OM).multiply(0.027))
            .add(Sa.multiply(Cl).multiply(0.452)).add(0.299))
    fc = fc_t.add(fc_t.pow(2).multiply(1.283).subtract(fc_t.multiply(0.374)).subtract(0.015))
    return fc, wp


def _saxton_sat_ksat(ee, fc, wp, sand_frac, clay_frac, om_pct):
    """Saxton & Rawls (2006): saturation theta_sat (vol frac) and Ksat (mm/hr) from texture + FC/WP.
    Used for the aeration-stress (waterlogging) water balance."""
    import math
    Sa, Cl, OM = sand_frac, clay_frac, om_pct
    # theta(S-33): drainable (macro) porosity between saturation and field capacity
    s33t = (Sa.multiply(0.278).add(Cl.multiply(0.034)).add(OM.multiply(0.022))
            .subtract(Sa.multiply(OM).multiply(0.018)).subtract(Cl.multiply(OM).multiply(0.027))
            .subtract(Sa.multiply(Cl).multiply(0.584)).add(0.078))
    s33 = s33t.add(s33t.multiply(0.636).subtract(0.107))
    sat = fc.add(s33).subtract(Sa.multiply(0.097)).add(0.043)              # theta_sat
    # Ksat = 1930 * (theta_sat - theta_33)^(3 - lambda) ;  lambda = 1/B, B from the FC/WP tension curve
    B = ee.Image.constant(math.log(1500.0) - math.log(33.0)).divide(fc.log().subtract(wp.log()).max(1e-4))
    lam = B.pow(-1)
    ksat = sat.subtract(fc).max(1e-4).pow(ee.Image(3).subtract(lam)).multiply(1930.0)   # mm/hr
    return sat.clamp(0.30, 0.75), ksat.max(1e-3)


def build_hydro_mm(ee, root_depth_cm=100, clay_asset=SG_CLAY, sand_asset=SG_SAND, soc_asset=SG_SOC):
    """Root-zone hydraulics for the aeration-stress balance, from SoilGrids texture + Saxton-Rawls:
      FC_mm  = field capacity over the root zone (mm)      SAT_mm = saturation (mm)
      tau    = AquaCrop daily drainage coefficient (fraction/day) from the bottleneck-layer Ksat.
    Well-drained soils get tau -> 1 (excess drains in a day); heavy clay tau small (water perches)."""
    clay, sand, soc = ee.Image(clay_asset), ee.Image(sand_asset), ee.Image(soc_asset)
    fc_mm = ee.Image(0.0); sat_mm = ee.Image(0.0); ksat_layers = []
    for (top, bot), suf in zip(SG_LAYERS_CM, SG_SUFFIX):
        if top >= root_depth_cm:
            break
        th_mm = (min(bot, root_depth_cm) - top) * 10.0
        Cl = clay.select("clay_" + suf).divide(1000.0); Sa = sand.select("sand_" + suf).divide(1000.0)
        OM = soc.select("soc_" + suf).divide(100.0).multiply(1.724)
        fc, wp = _saxton_fc_wp(Sa, Cl, OM)
        sat, ksat = _saxton_sat_ksat(ee, fc, wp, Sa, Cl, OM)
        fc_mm = fc_mm.add(fc.multiply(th_mm)); sat_mm = sat_mm.add(sat.multiply(th_mm))
        ksat_layers.append(ksat.rename("ksat"))
    ksat_day = ee.ImageCollection(ksat_layers).min().multiply(24.0)         # bottleneck layer, mm/day
    tau = ksat_day.pow(0.35).multiply(0.0866).clamp(0.0, 1.0)               # AquaCrop drainage coef
    return {"FC_mm": fc_mm.rename("FC_mm"), "SAT_mm": sat_mm.max(fc_mm.add(10)).rename("SAT_mm"),
            "tau": tau.rename("tau")}


def build_whc_saxton_mm(ee, root_depth_cm=100, min_whc_mm=25,
                        clay_asset=SG_CLAY, sand_asset=SG_SAND, soc_asset=SG_SOC):
    """SoilGrids texture + Saxton-Rawls (2006) -> WHC (mm) = plant-available water over the root zone.
    Both FC and WP are physically derived (no proxy). Block-integrates AWC over depth layers,
    clipping the deepest partial layer at root_depth_cm."""
    clay, sand, soc = ee.Image(clay_asset), ee.Image(sand_asset), ee.Image(soc_asset)
    whc = ee.Image.constant(0.0)
    for (top, bot), suf in zip(SG_LAYERS_CM, SG_SUFFIX):
        if top >= root_depth_cm:
            break
        eff_bot = min(bot, root_depth_cm)
        th_mm = (eff_bot - top) * 10.0                                # cm -> mm
        Cl = clay.select("clay_" + suf).divide(1000.0)               # g/kg  -> fraction
        Sa = sand.select("sand_" + suf).divide(1000.0)               # g/kg  -> fraction
        OM = soc.select("soc_" + suf).divide(100.0).multiply(1.724)  # dg/kg -> SOC% -> OM%
        fc, wp = _saxton_fc_wp(Sa, Cl, OM)
        awc = fc.subtract(wp).max(0)                                  # available fraction (layer mean)
        whc = whc.add(awc.multiply(th_mm))                           # block integration
    return whc.max(min_whc_mm).rename("WHC_mm")


def get_whc(ee, aoi, soil_cfg, root_depth_cm=100):
    """Single entry point. Precedence: a materialized `whc_asset` > `whc_source` builder.
    root_depth_cm should come from the crop's FAO-56 rooting depth."""
    aid = (soil_cfg.get("whc_asset") or "").strip()
    if aid:
        return ee.Image(aid).rename("WHC_mm")
    mn = soil_cfg.get("min_whc_mm", 25)
    if soil_cfg.get("whc_source", "saxton_soilgrids") == "saxton_soilgrids":
        return build_whc_saxton_mm(ee, root_depth_cm=root_depth_cm, min_whc_mm=mn)
    return build_whc_mm(ee, root_depth_cm=root_depth_cm,
                        wp_frac=soil_cfg.get("wp_over_fc_frac", 0.45),
                        fc_asset=soil_cfg.get("openlandmap_fc_asset", FC_ASSET),
                        wp_asset=(soil_cfg.get("wp_asset") or None), min_whc_mm=mn)


def export_whc_to_asset(ee, whc_img, region, asset_id, scale=250, description="whc_saxton_soilgrids"):
    """One-time materialization: WHC stays in Earth Engine; runs later load it via whc_asset (no re-download)."""
    t = ee.batch.Export.image.toAsset(image=whc_img.clip(region), description=description,
                                      assetId=asset_id, region=region, scale=scale, maxPixels=int(1e13))
    t.start(); return t


def export_whc_to_drive(ee, whc_img, region, folder="planting_outputs",
                        name="WHC_saxton_soilgrids_mm", scale=250):
    """One-time GeoTIFF export to Drive (single static file)."""
    t = ee.batch.Export.image.toDrive(image=whc_img.clip(region), description=name, folder=folder,
                                      fileNamePrefix=name, region=region, scale=scale,
                                      crs="EPSG:4326", maxPixels=int(1e13))
    t.start(); return t
