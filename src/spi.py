"""SPI-3 — 3-month Standardized Precipitation Index from CHIRPS, in pure GEE.

Standard SPI fits a gamma distribution to the historical N-month precipitation totals (per pixel,
per calendar period) and maps the current total to a z-score via the gamma CDF. GEE has no
incomplete-gamma function, so we use the **Wilson–Hilferty** cube-root normal approximation of the
gamma — a recognised, well-behaved SPI estimator that is pure ee.Image arithmetic:

    a   = (mu/sigma)^2                      # gamma shape, method-of-moments, per pixel
    SPI = ( (P3/mu)^(1/3) - 1 + 1/(9a) ) * sqrt(9a)

where mu, sigma are the climatological mean/SD of the 3-month total for the same ending month.

SPI classes (McKee 1993): ≤ -1 moderate drought · ≤ -1.5 severe · ≤ -2 extreme  (and the wet mirror).
"""


def chirps_3month(ee, aoi, year, end_month):
    """3-month CHIRPS precipitation total ending in `end_month` of `year` (band 'P3')."""
    ch = ee.ImageCollection("UCSB-CHG/CHIRPS/DAILY").filterBounds(aoi)
    end = ee.Date.fromYMD(ee.Number(year), ee.Number(end_month), 1).advance(1, "month")  # exclusive
    start = end.advance(-3, "month")
    return ch.filterDate(start, end).sum().rename("P3").clip(aoi)


def spi3(ee, aoi, year, end_month, clim_start=1981, clim_end=2020):
    """SPI-3 image for the 3 months ending `end_month` of `year`, vs the clim_start..clim_end normal."""
    cur = chirps_3month(ee, aoi, year, end_month)
    yrs = ee.List.sequence(clim_start, clim_end)
    coll = ee.ImageCollection(yrs.map(
        lambda y: chirps_3month(ee, aoi, ee.Number(y), end_month)))
    mu = coll.mean().rename("mu").max(1e-3)
    sd = coll.reduce(ee.Reducer.stdDev()).rename("sd").max(1e-3)
    a = mu.divide(sd).pow(2).rename("a").max(1e-3)                 # gamma shape (MoM)
    inv9a = a.multiply(9).pow(-1)                                  # 1/(9a)
    z = (cur.divide(mu).pow(1.0 / 3.0)                             # (P3/mu)^(1/3)
         .subtract(1).add(inv9a)                                   # - 1 + 1/(9a)
         .multiply(a.multiply(9).sqrt()))                          # * sqrt(9a)
    return z.rename("SPI3").clamp(-3.5, 3.5)
