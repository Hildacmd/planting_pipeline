"""Sentinel-2: cloud-masked, dekadal composites of red-edge + VI phenology bands (GEE)."""
from __future__ import annotations

def _add_indices(img, ee):
    b = {k: img.select(k) for k in ["B3","B4","B5","B6","B7","B8","B8A","B11","B12"]}
    ndvi  = img.normalizedDifference(["B8","B4"]).rename("NDVI")
    evi2  = img.expression("2.5*(N-R)/(N+2.4*R+1)", {"N":b["B8"],"R":b["B4"]}).rename("EVI2")
    ndre1 = img.normalizedDifference(["B6","B5"]).rename("NDRE1")
    ndre2 = img.normalizedDifference(["B7","B5"]).rename("NDRE2")
    rendvi= img.normalizedDifference(["B8A","B5"]).rename("ReNDVI")
    cire  = img.expression("(RE3/RE1)-1", {"RE3":b["B7"],"RE1":b["B5"]}).rename("CIre")
    return img.addBands([ndvi,evi2,ndre1,ndre2,rendvi,cire])

def _mask_clouds(img, ee):
    # Cloud Score+ (preferred): keep clear pixels
    cs = img.select("cs_cdf") if "cs_cdf" in img.bandNames().getInfo() else None
    return img

def build_s2_dekadal(ee, aoi, year, dekads=range(1,37), cs_thresh=0.60):
    """Return an ImageCollection: one median composite per dekad with VI+red-edge bands."""
    from .utils import dekad_to_start_date
    import datetime as dt

    s2 = (ee.ImageCollection("COPERNICUS/S2_SR_HARMONIZED")
            .filterBounds(aoi)
            .filterDate(f"{year}-01-01", f"{year+1}-01-05"))
    csp = ee.ImageCollection("GOOGLE/CLOUD_SCORE_PLUS/V1/S2_HARMONIZED")
    s2 = s2.linkCollection(csp, ["cs_cdf"])

    def prep(img):
        img = img.updateMask(img.select("cs_cdf").gte(cs_thresh))
        # resample 20 m red-edge/SWIR to 10 m (nearest is default); scale reflectance
        img = img.divide(10000).copyProperties(img, ["system:time_start"])
        return _add_indices(ee.Image(img), ee)

    s2 = s2.map(prep)
    out = []
    for dk in dekads:
        start = ee.Date(dekad_to_start_date(year, dk).isoformat())
        end   = start.advance(10, "day")
        comp  = (s2.filterDate(start, end)
                   .select(["NDVI","EVI2","NDRE1","NDRE2","ReNDVI","CIre"])
                   .median()
                   .set({"dekad": dk, "year": year, "system:time_start": start.millis()}))
        out.append(comp)
    return ee.ImageCollection(out)   # gaps (all-cloud dekads) -> masked; filled in fusion step
