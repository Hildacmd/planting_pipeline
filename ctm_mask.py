# -*- coding: utf-8 -*-
"""The crop-type mask as a pipeline input, for any crop and country.

`run.crop_mask_image` returns the ESA WorldCereal maize layer for maize and, for **every other
crop**, falls through to the WorldCereal temporary-crops extent, which is all cropland. That is a
placeholder, not a crop mask, and it fails silently: a wheat or sorghum run left on the default
computes over every field in the country and labels the result with the crop name.

This module returns the ICPAC crop-type mask instead: a dasymetric allocation of MapSPAM crop
shares onto a four-lineage, sixteen-source-year stable cropland vote, reweighted by agro-climatic
suitability and satellite crop evidence, and calibrated to sub-national statistics where they
exist. It raises rather than falling back, so a country or crop without a mask is a visible
error.

    from ctm_mask import crop_mask, crop_fraction
    mask = crop_mask(ee, "Kenya", "maize")            # binary, frac >= 10 % of the cell
    mask = crop_mask(ee, "Kenya", "maize", 25)        # your own threshold on frac
    frac = crop_fraction(ee, "Kenya", "maize")        # % of the cell, for area weights
"""
ASSET_ROOT = "projects/indigo-proxy-484220-q8/assets/crop_type_mask"

# country -> (ISO code used in the asset name, crops the product carries)
# Rwanda, Burundi and Somalia use their SPAM-2020 profiles, which are the released products.
PROFILES = {
    "Ethiopia":    ("ET",   ("maize", "wheat", "sorghum", "teff")),
    "Kenya":       ("KE",   ("maize", "wheat", "sorghum")),
    "Uganda":      ("UG",   ("maize", "sorghum")),
    "Tanzania":    ("TZ",   ("maize", "wheat", "sorghum")),
    "Rwanda":      ("RW20", ("maize", "wheat", "sorghum")),
    "Burundi":     ("BI20", ("maize", "wheat", "sorghum")),
    "Somalia":     ("SO20", ("maize", "sorghum")),
    "South_Sudan": ("SS",   ("maize", "sorghum")),
    "Sudan":       ("SD",   ("sorghum", "millet", "wheat")),
    "Eritrea":     ("ER",   ("sorghum", "millet")),
    "Djibouti":    ("DJ",   ()),          # cropland only, no crop split
}
# mapped area, Mha, from crop_type_mask/regional_report/tbl_crops.csv — for sanity checks
AREA_MHA = {
    ("Ethiopia", "maize"): 2.034, ("Ethiopia", "wheat"): 1.585, ("Ethiopia", "sorghum"): 1.836,
    ("Ethiopia", "teff"): 2.716, ("Kenya", "maize"): 1.539, ("Kenya", "wheat"): 0.151,
    ("Kenya", "sorghum"): 0.209, ("Uganda", "maize"): 0.575, ("Uganda", "sorghum"): 0.199,
    ("Tanzania", "maize"): 3.581, ("Tanzania", "wheat"): 0.078, ("Tanzania", "sorghum"): 0.573,
    ("Rwanda", "maize"): 0.198, ("Rwanda", "wheat"): 0.019, ("Rwanda", "sorghum"): 0.156,
    ("Burundi", "maize"): 0.093, ("Burundi", "wheat"): 0.003, ("Burundi", "sorghum"): 0.023,
    ("Somalia", "maize"): 0.110, ("Somalia", "sorghum"): 0.162,
    ("South_Sudan", "maize"): 0.013, ("South_Sudan", "sorghum"): 0.295,
    ("Sudan", "sorghum"): 6.320, ("Sudan", "millet"): 2.278, ("Sudan", "wheat"): 0.203,
    ("Eritrea", "sorghum"): 0.134, ("Eritrea", "millet"): 0.030,
}


def _key(country):
    c = str(country).replace(" ", "_")
    if c not in PROFILES:
        raise KeyError(f"no crop-type mask for {country!r}; have {sorted(PROFILES)}")
    return c


def asset(country):
    iso, _ = PROFILES[_key(country)]
    return f"{ASSET_ROOT}/croptype_{iso}_100m"


def has(country, crop):
    try:
        return crop in PROFILES[_key(country)][1]
    except KeyError:
        return False


def crop_mask(ee, country, crop, min_fraction=None):
    """Binary crop mask, 1 where the crop is, masked elsewhere.

    `min_fraction` (percent of the 100 m cell) overrides the shipped 10 % threshold. The binary
    mask turns a whole cell on once the crop reaches 10 % of it, so it covers about 2.4 times the
    ground the crop actually occupies region-wide. That is fine as a computation stratum and
    wrong as an area: for area use `crop_fraction` and the pixel-area raster.
    """
    c = _key(country)
    if crop not in PROFILES[c][1]:
        raise KeyError(f"{PROFILES[c][0]} has no {crop} band; it carries {PROFILES[c][1]}")
    img = ee.Image(asset(country))
    if min_fraction is None:
        return img.select(f"mask_{crop}").selfMask()
    return img.select(f"frac_{crop}").gte(float(min_fraction)).selfMask()


def crop_fraction(ee, country, crop):
    """Percentage of each 100 m cell occupied by the crop. Use this as the area weight."""
    c = _key(country)
    if crop not in PROFILES[c][1]:
        raise KeyError(f"{PROFILES[c][0]} has no {crop} band; it carries {PROFILES[c][1]}")
    return ee.Image(asset(country)).select(f"frac_{crop}")
