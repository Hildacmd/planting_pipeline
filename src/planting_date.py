"""SOS -> planting dekad (crop-specific emergence offset) + anomaly vs LTN."""
from __future__ import annotations

# emergence/green-up lag in dekads: planting precedes detectable SOS
EMERGENCE_OFFSET = {"maize": 2, "wheat": 1, "teff": 1}

def sos_to_planting(ee, sos_img, crop):
    off = EMERGENCE_OFFSET.get(crop, 1)
    return sos_img.subtract(off).rename("planting_dekad")

def planting_anomaly(ee, planting_img, ltn_planting_img):
    """Positive = later than normal (delayed onset); negative = earlier."""
    return planting_img.subtract(ltn_planting_img).rename("planting_anom_dekads")

def export_planting(ee, planting_img, aoi, desc, scale=10, folder="planting_outputs"):
    task = ee.batch.Export.image.toDrive(
        image=planting_img.toFloat(), description=desc, folder=folder,
        region=aoi, scale=scale, maxPixels=1e13,
        fileFormat="GeoTIFF")
    task.start()
    return task
