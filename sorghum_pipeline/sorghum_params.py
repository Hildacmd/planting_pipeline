# -*- coding: utf-8 -*-
"""Sorghum crop parameters for the ICPAC pipeline.

Everything sorghum-specific lives here, so the maize pipeline in `src/` and `config/` is
untouched. The only change made outside this folder is an optional `ky=` argument on
`src.cpi.s_water`, which defaults to the maize values.

Sources are named against each block. Where a parameter has no published sorghum equivalent,
it is marked FIRST PASS and carries the maize value, so it is visible rather than hidden.
"""

# --------------------------------------------------------------- FAO-56 crop coefficients
# Allen et al. (1998) FAO-56: stage lengths Table 11 (grain sorghum 20/35/40/30 = 125 d),
# crop coefficients Table 12 (Kc_ini 0.30, Kc_mid 1.00-1.10, Kc_end 0.55), rooting depth
# Table 22 (1.0 to 2.0 m, depletion fraction p = 0.55).
# Lengths are rounded to whole dekads: 2 + 4 + 4 + 3 = 13 dekads = 130 d.
# Kc_end is 0.55 for grain harvested at maturity; it is NOT the maize 0.35, because sorghum
# heads are cut with the canopy still partly green.
SORGHUM_KC = {
    "LGP_dekads": 13, "L_ini": 2, "L_dev": 4, "L_mid": 4, "L_late": 3,
    "Kc_ini": 0.30, "Kc_mid": 1.05, "Kc_end": 0.55, "root_depth_m": 1.5,
}

# Short-duration sorghum, for the second and short seasons (Somalia Deyr, Kenya short rains).
# Same shape, 9 dekads. Mirrors the maize EARLY override in run_all_maize_2024.py.
SORGHUM_KC_EARLY = {"LGP_dekads": 9, "L_ini": 2, "L_dev": 3, "L_mid": 2, "L_late": 2}

# --------------------------------------------------------------- FAO-33 yield response
# Doorenbos & Kassam (1979) FAO-33 Table 24: sorghum total Ky = 0.9, against maize 1.25.
# Stage values: vegetative 0.2, flowering 0.55, yield formation 0.45, ripening 0.2. The
# pipeline's three stages map to vegetative / flowering / grain filling.
# Sorghum is far less sensitive to a water deficit than maize at every stage, and the
# flowering peak is much flatter (0.55 against 1.50). That difference is the main reason a
# sorghum CPI cannot be produced by running the maize CPI over a sorghum mask.
SORGHUM_KY = {"veg": 0.2, "flo": 0.55, "grf": 0.45}

# --------------------------------------------------------------- heat
# Sorghum pollen viability and seed set fall away above about 36 C at flowering, against
# about 33 C for maize (Prasad et al. 2008, 2015; Singh et al. 2015). HEAT_TCAP is applied to
# a DEKAD-MEAN Tmax, so it fires only where a whole dekad averages above the cap.
SORGHUM_HEAT_TCAP = 36.0
# FIRST PASS: the loss per heat-degree-dekad is the maize value. No sorghum-specific slope was
# found in the literature reviewed. Calibrate before any heat result is reported on its own.
SORGHUM_HEAT_K = 0.06

# --------------------------------------------------------------- phenology
# Dekads between planting and a detectable green-up crossing. Sorghum emerges in 4 to 6 days
# but builds canopy more slowly than maize, so the same 2-dekad offset is used.
# FIRST PASS: no sorghum-specific emergence-to-green-up study was used. It is the single
# parameter most worth checking against the farmer records collected at the workshop.
SORGHUM_EMERGENCE_OFFSET = 2

# --------------------------------------------------------------- attainable yield ceiling
# Ym (t/ha). EMPTY until the 2024 sorghum CPI exists and calibrate_ym_sorghum.py has been run:
# a ceiling must be fitted to reported yields, not guessed. Until then the pipeline falls back
# to SORGHUM_YM_DEFAULT, which is a rainfed agronomic potential and, on every maize country
# where the equivalent default could be tested, is several times what smallholders harvest.
# HarvestStat v1.2 sorghum yield records available for the fit, by country and season:
#   Ethiopia Meher   76 units 1993-2021   Somalia Gu     40 units 1995-2025
#   Kenya Annual     47 units 1981-2020   Somalia Deyr   39 units 1996-2025
#   Kenya Long       44 units 2015-2016   Sudan Main     18 units 1975-2023
#   Kenya Short      35 units 2016-2017   Rwanda A/B     23/30 units 2009-2017
#   Uganda First     70 units 2009        Burundi A/B/C   9/13/11 units 2012-2016
#   Uganda Second    70 units 2008        South Sudan     2 units 1975-2010
# Tanzania and Eritrea have NO HarvestStat sorghum yields and cannot be calibrated.
YM_CAL_SORGHUM = {}
SORGHUM_YM_DEFAULT = 3.0        # rainfed grain sorghum potential, uncalibrated
SORGHUM_YM_SHORT_DEFAULT = 2.0  # short-duration second-season sorghum, uncalibrated


def ym_for(country, season):
    """Attainable ceiling (t/ha) for a (country, season). Falls back to the uncalibrated
    default and is honest about it: check `is_calibrated` before quoting a yield."""
    key = (country.replace(" ", "_"), season)
    if key in YM_CAL_SORGHUM:
        return YM_CAL_SORGHUM[key]
    s = str(season).lower()
    return SORGHUM_YM_SHORT_DEFAULT if ("short" in s or "2nd" in s or "deyr" in s) else SORGHUM_YM_DEFAULT


def is_calibrated(country, season):
    return (country.replace(" ", "_"), season) in YM_CAL_SORGHUM


# --------------------------------------------------------------- crop mask
# The sorghum mask comes from the crop-type mask series, not from WorldCereal: WorldCereal has
# no sorghum class, and its cereals layer does not separate sorghum from wheat or millet, so
# `run.crop_mask_image` would silently return the temporary-crops extent instead.
# Rwanda, Burundi and Somalia use the SPAM-2020 profiles, which are the released products.
MASK_ISO = {
    "Ethiopia": "ET", "Kenya": "KE", "Uganda": "UG", "Tanzania": "TZ",
    "Rwanda": "RW20", "Burundi": "BI20", "Somalia": "SO20",
    "South_Sudan": "SS", "Sudan": "SD", "Eritrea": "ER",
}
import os as _os
# Where the masks LIVE, which need not be the project running the compute; readable
# cross-project under the same account. Override with CTM_ASSET_ROOT.
MASK_ASSET_ROOT = _os.environ.get(
    "CTM_ASSET_ROOT", "projects/indigo-proxy-484220-q8/assets/crop_type_mask")
# mapped sorghum area, Mha, from crop_type_mask/regional_report/tbl_crops.csv
MASK_AREA_MHA = {"Sudan": 6.320, "Ethiopia": 1.836, "Tanzania": 0.573, "South_Sudan": 0.295,
                 "Kenya": 0.209, "Uganda": 0.199, "Somalia": 0.162, "Rwanda": 0.156,
                 "Eritrea": 0.133, "Burundi": 0.023}


def mask_asset(country):
    iso = MASK_ISO.get(country.replace(" ", "_"))
    if iso is None:
        raise KeyError(f"no sorghum crop-type mask for {country}; "
                       f"available: {sorted(MASK_ISO)}")
    return f"{MASK_ASSET_ROOT}/croptype_{iso}_100m"


def sorghum_mask(ee, country, min_fraction=None):
    """Sorghum mask as a 1/masked image.

    `min_fraction` (percent of the 100 m cell) applies your own threshold to `frac_sorghum`
    instead of the shipped 10 % binary mask. Use it to tighten the stratum: the binary mask
    turns a whole cell on once sorghum reaches 10 % of it, so it covers far more ground than
    the crop does (Sudan: a 13.1 Mha mask over a 6.3 Mha crop).
    """
    img = ee.Image(mask_asset(country))
    if min_fraction is None:
        return img.select("mask_sorghum").selfMask()
    return img.select("frac_sorghum").gte(float(min_fraction)).selfMask()


def crop_fraction(ee, country):
    """frac_sorghum, percent of each 100 m cell. Use this as the area weight for any
    aggregation, never the binary mask."""
    return ee.Image(mask_asset(country)).select("frac_sorghum")
