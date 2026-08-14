"""Aggregate per-pixel planting dekad to admin units -> planting-window distribution."""
from __future__ import annotations

def zonal_planting_stats(ee, planting_img, admin_fc, scale=100):
    """Modal + spread of planting dekad per admin unit (GAUL level-1/2 FeatureCollection)."""
    reducer = (ee.Reducer.mode()
               .combine(ee.Reducer.percentile([10,50,90]), sharedInputs=True)
               .combine(ee.Reducer.count(), sharedInputs=True))
    return planting_img.rename("pd").reduceRegions(
        collection=admin_fc, reducer=reducer, scale=scale)

def gaul_admin(ee, country_names, level=1):
    tbl = "FAO/GAUL_SIMPLIFIED_500m/2015/level%d" % level
    return ee.FeatureCollection(tbl).filter(
        ee.Filter.inList("ADM0_NAME", country_names))
