import ee, sys
ee.Initialize(project="ee-manzikye")

KE = ee.FeatureCollection("FAO/GAUL/2015/level2").filter(ee.Filter.eq("ADM0_NAME","Kenya"))
aoi = KE.geometry()

# maize mask so greenup is read over cropland, not rangeland bush
try:
    crop = ee.ImageCollection("ESA/WorldCover/v200").first().select("Map").eq(40)
except Exception:
    crop = ee.Image(1)

def greenup_dekad(img, cyc):
    yr = ee.Date(img.get("system:time_start")).get("year")
    y0 = ee.Date.fromYMD(yr,1,1).difference(ee.Date("1970-01-01"),"day")
    g = img.select("Greenup_%d"%cyc)
    g = g.updateMask(g.neq(32767))
    return g.subtract(y0).divide(10.139).ceil().clamp(1,36).rename("dk")

ic = (ee.ImageCollection("MODIS/061/MCD12Q2").filterBounds(aoi)
        .filter(ee.Filter.calendarRange(2001,2023,"year")))

# cycle 1 = first (long rains) green-up, cycle 2 = second (short rains / OND) green-up
g1 = ic.map(lambda im: greenup_dekad(im,1)).median().rename("g1")
g2 = ic.map(lambda im: greenup_dekad(im,2)).median().rename("g2")
# how often a 2nd cycle is detected at all -> tells us if a county is truly bimodal
n2 = ic.map(lambda im: im.select("Greenup_2").neq(32767).rename("has2")).sum().rename("n_cycle2")
nY = ic.size()

stack = g1.addBands(g2).addBands(n2).updateMask(crop)

out = stack.reduceRegions(
    collection = KE.select(["ADM1_NAME","ADM2_NAME"]),
    reducer = ee.Reducer.median(),
    scale = 500, tileScale = 4)
out = out.map(lambda f: f.set("n_years", nY))

t = ee.batch.Export.table.toDrive(collection=out, description="modis_pheno_ond_ke",
        folder="planting_outputs", fileFormat="CSV",
        selectors=["ADM1_NAME","ADM2_NAME","g1","g2","n_cycle2","n_years"])
t.start(); print("started", t.id)
