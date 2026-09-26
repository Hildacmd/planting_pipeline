# -*- coding: utf-8 -*-
"""Teff parameters. Ethiopia only: no other Member State has a teff crop-type mask.

**Teff is not in FAO-56 or FAO-33.** Every coefficient below is a small-grain-cereal analogue, and
the whole crop is therefore weaker-founded than maize, wheat or sorghum. That is a property of the
literature, not of this implementation, and it must travel with any teff result.
"""

CROP = "teff"

# FAO-56 has no teff. The pipeline's existing entry treats it as a short small-grain cereal and is
# already flagged APPROX in config/crop_coefficients.yaml; it is reproduced unchanged here.
# 9 dekads, 2/3/3/1, Kc 0.30 -> 1.10 -> 0.40, root 0.6 m. Teff is genuinely shallow-rooted, which
# is why it is grown on vertisols that hold water near the surface.
KC = {"LGP_dekads": 9, "L_ini": 2, "L_dev": 3, "L_mid": 3, "L_late": 1,
      "Kc_ini": 0.30, "Kc_mid": 1.10, "Kc_end": 0.40, "root_depth_m": 0.6}
KC_EARLY = {"LGP_dekads": 8, "L_ini": 2, "L_dev": 2, "L_mid": 2, "L_late": 2}

# FIRST PASS: FAO-33 has no teff. Wheat's stage factors are used as the closest small-grain
# analogue, scaled down slightly because teff is grown as a low-input catch crop and is more
# tolerant of a poor season than bread wheat. These are ASSUMPTIONS.
KY = {"veg": 0.2, "flo": 0.55, "grf": 0.45}

# FIRST PASS: teff is a warm-season C4 pseudocereal but grown in the Ethiopian highlands. Table 7.0
# of the Inception Report gives a base temperature of 10-12 C and an upper cap near 30 C.
HEAT_TCAP = 30.0
HEAT_K = 0.06                                 # FIRST PASS, carried over from maize

EMERGENCE_OFFSET = 1                          # src/planting_date.EMERGENCE_OFFSET

MASK_COUNTRIES = {"Ethiopia": 2.716}

YM_DEFAULT, YM_SHORT_DEFAULT = 2.0, 1.5       # uncalibrated; teff yields far below wheat
YM_CAL = {}
