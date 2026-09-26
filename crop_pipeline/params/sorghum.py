# -*- coding: utf-8 -*-
"""Sorghum parameters — a thin view over sorghum_pipeline/sorghum_params.py.

The sorghum pipeline shipped first and its parameters are the ones already used to build eighteen
products and twelve fitted ceilings. They are re-exported here rather than copied, so there is one
definition and the two cannot drift apart.
"""
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__)))), "sorghum_pipeline"))
import sorghum_params as _S                                           # noqa: E402

CROP = "sorghum"
KC, KC_EARLY = _S.SORGHUM_KC, _S.SORGHUM_KC_EARLY
KY = _S.SORGHUM_KY
HEAT_TCAP, HEAT_K = _S.SORGHUM_HEAT_TCAP, _S.SORGHUM_HEAT_K
EMERGENCE_OFFSET = _S.SORGHUM_EMERGENCE_OFFSET
MASK_COUNTRIES = {c: a for (c, cr), a in
                  __import__("ctm_mask").AREA_MHA.items() if cr == "sorghum"}
YM_DEFAULT, YM_SHORT_DEFAULT = _S.SORGHUM_YM_DEFAULT, _S.SORGHUM_YM_SHORT_DEFAULT
YM_CAL = _S.YM_CAL_SORGHUM
