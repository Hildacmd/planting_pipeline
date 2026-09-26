# -*- coding: utf-8 -*-
"""Wheat parameters. Rainfed and irrigated bread wheat as grown in the IGAD region."""

CROP = "wheat"

# FAO-56 Allen et al. (1998). Stage lengths Table 11 (winter wheat 30/140/40/30; spring wheat
# 20/25/60/30 = 135 d); crop coefficients Table 12 (Kc_ini 0.3-0.7, Kc_mid 1.15, Kc_end 0.25-0.4);
# rooting depth Table 22 (1.0 to 1.8 m).
# The pipeline's existing config/crop_coefficients.yaml wheat entry is kept unchanged so the
# numbers here and there cannot diverge: 12 dekads, 3/4/3/2, Kc 0.40 -> 1.15 -> 0.35, root 1.0 m.
KC = {"LGP_dekads": 12, "L_ini": 3, "L_dev": 4, "L_mid": 3, "L_late": 2,
      "Kc_ini": 0.40, "Kc_mid": 1.15, "Kc_end": 0.35, "root_depth_m": 1.0}
KC_EARLY = {"LGP_dekads": 9, "L_ini": 2, "L_dev": 3, "L_mid": 2, "L_late": 2}

# FAO-33 Doorenbos & Kassam (1979) Table 24: wheat total Ky 1.15 (winter), 1.05 (spring).
# Stage values: vegetative 0.2, flowering 0.65, yield formation 0.55, ripening ~0.
# Mapped to the pipeline's three stages. Wheat sits between maize (flo 1.5) and sorghum (0.55):
# sensitive at anthesis, but less catastrophically so than maize.
KY = {"veg": 0.2, "flo": 0.65, "grf": 0.55}

# Wheat is a COOL-season cereal. Anthesis is damaged above roughly 31 C, far below maize's 33 and
# sorghum's 36 (Porter & Gawith 1999; Asseng et al. 2015). Applied to a DEKAD-MEAN Tmax, so it
# fires only where a whole dekad averages above it.
HEAT_TCAP = 31.0
# FIRST PASS: loss per heat-degree-dekad carried over from maize. No wheat-specific slope was used.
HEAT_K = 0.06

# Dekads from planting to a detectable green-up crossing. The pipeline uses 1 for wheat
# (src/planting_date.EMERGENCE_OFFSET), against 2 for maize: wheat establishes a canopy faster.
EMERGENCE_OFFSET = 1

# Countries whose crop-type mask carries a wheat band, and the mapped area in Mha.
MASK_COUNTRIES = {"Ethiopia": 1.585, "Sudan": 0.203, "Kenya": 0.151,
                  "Tanzania": 0.078, "Rwanda": 0.019, "Burundi": 0.003}

YM_DEFAULT, YM_SHORT_DEFAULT = 4.0, 3.0      # uncalibrated rainfed potentials, t/ha
YM_CAL = {
    ("Ethiopia", "Meher"): 2.69,   # n52 2012-2021  MAE 0.48 vs 1.08  r 0.15  level only
    ("Kenya", "Long rains"): 3.11,   # n16 2010-2020  MAE 0.54 vs 0.89  r 0.07  level only
}                                   # filled by the calibration, keyed (country, season)
