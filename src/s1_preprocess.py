"""Sentinel-1: dekadal VV/VH/ratio/RVI backscatter (GEE). Cloud-proof onset signal."""
from __future__ import annotations

def build_s1_dekadal(ee, aoi, year, orbit="DESCENDING", dekads=range(1,37)):
    from .utils import dekad_to_start_date

    s1 = (ee.ImageCollection("COPERNICUS/S1_GRD")
            .filterBounds(aoi)
            .filterDate(f"{year}-01-01", f"{year+1}-01-05")
            .filter(ee.Filter.eq("instrumentMode", "IW"))
            .filter(ee.Filter.listContains("transmitterReceiverPolarisation", "VV"))
            .filter(ee.Filter.listContains("transmitterReceiverPolarisation", "VH"))
            .filter(ee.Filter.eq("orbitProperties_pass", orbit))
            .select(["VV","VH"]))

    def refine(img):
        # GEE S1_GRD is already thermal-noise-removed, calibrated (dB), terrain-corrected.
        # Light speckle reduction via focal mean in linear space, then derive features.
        lin = ee.Image(10).pow(img.divide(10))                 # dB -> linear
        lin = lin.focal_mean(30, "circle", "meters")           # ~speckle filter
        vv, vh = lin.select("VV"), lin.select("VH")
        ratio = vh.divide(vv).rename("VH_VV")
        rvi   = vh.multiply(4).divide(vv.add(vh)).rename("RVI")
        vv_db = vv.log10().multiply(10).rename("VV")
        vh_db = vh.log10().multiply(10).rename("VH")
        return (ee.Image.cat([vv_db, vh_db, ratio, rvi])
                  .copyProperties(img, ["system:time_start"]))

    s1 = s1.map(refine)
    BANDS = ["VV", "VH", "VH_VV", "RVI"]
    # fully-masked 4-band fallback so a dekad with NO S1 scene still yields the RVI band (masked),
    # instead of a band-less image that breaks downstream select("RVI").
    empty = ee.Image.constant([0, 0, 0, 0]).rename(BANDS).updateMask(ee.Image.constant(0))
    out = []
    for dk in dekads:
        start = ee.Date(dekad_to_start_date(year, dk).isoformat())
        end   = start.advance(10, "day")
        col   = s1.filterDate(start, end)
        comp  = (ee.Image(ee.Algorithms.If(col.size().gt(0), col.mean(), empty))
                   .select(BANDS)
                   .set({"dekad": dk, "year": year, "system:time_start": start.millis()}))
        out.append(comp)
    return ee.ImageCollection(out)
