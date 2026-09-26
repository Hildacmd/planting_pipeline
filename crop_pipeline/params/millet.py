# -*- coding: utf-8 -*-
"""Pearl millet parameters.

**Only Sudan and Eritrea have a millet crop-type mask**, so the pipeline can only produce millet
there, even though HarvestStat holds millet yields for Ethiopia, Kenya, Uganda and Burundi as well.
That is a limit of the mask series, not of the statistics, and it is the single biggest constraint
on millet: 2.31 Mha of the region's millet can be monitored and the rest cannot.
"""

CROP = "millet"

# FAO-56 Allen et al. (1998) Table 11 (millet 15/25/40/25 = 105 d) and Table 12 (Kc_ini 0.30,
# Kc_mid 1.00, Kc_end 0.30); rooting depth Table 22 (1.0 to 2.0 m).
# 11 dekads: 2/3/4/2. Kc_mid 1.00 is below sorghum's 1.05 and well below maize's 1.20 - pearl
# millet transpires less per unit ground area, which is part of why it survives where they fail.
KC = {"LGP_dekads": 11, "L_ini": 2, "L_dev": 3, "L_mid": 4, "L_late": 2,
      "Kc_ini": 0.30, "Kc_mid": 1.00, "Kc_end": 0.30, "root_depth_m": 1.5}
KC_EARLY = {"LGP_dekads": 9, "L_ini": 2, "L_dev": 3, "L_mid": 2, "L_late": 2}

# FIRST PASS: FAO-33 has no millet. Sorghum's factors are used as the closest analogue - both are
# drought-adapted C4 cereals - scaled DOWN, because pearl millet is the more drought-tolerant of
# the two and is grown where sorghum fails (FAO 1976; Wortmann et al. 2009). These are ASSUMPTIONS
# and any millet result that turns on the stage weighting must say so.
KY = {"veg": 0.15, "flo": 0.45, "grf": 0.35}

# Pearl millet is the most heat-tolerant cereal in the region; flowering damage sets in around
# 40 C (Gupta et al. 2015; Djanaguiraman et al. 2018), against sorghum 36 and maize 33. Applied to
# a dekad-MEAN Tmax, this will essentially never fire in the IGAD region - which is the correct
# behaviour and should be reported as such, not as an absence of heat stress.
HEAT_TCAP = 38.0
HEAT_K = 0.06                                 # FIRST PASS, carried over from maize

# FIRST PASS: no millet entry exists in src/planting_date.EMERGENCE_OFFSET. Millet emerges fast but
# builds canopy slowly on sand; 2 dekads, as for sorghum.
EMERGENCE_OFFSET = 2

MASK_COUNTRIES = {"Sudan": 2.278, "Eritrea": 0.030}

YM_DEFAULT, YM_SHORT_DEFAULT = 2.0, 1.5       # uncalibrated rainfed potentials, t/ha
YM_CAL = {}
