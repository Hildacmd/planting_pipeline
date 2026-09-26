"""Per-crop parameters for the ICPAC pipeline: wheat, teff, millet and sorghum.

One module per crop, all the same shape, so the runner is crop-agnostic and every value is
attributable. Each module states its source next to the number, and marks `FIRST PASS` wherever a
value had to be carried over from another crop because no published equivalent exists.

That distinction is not cosmetic. FAO-56 covers wheat and (approximately) small grains; FAO-33
covers wheat and sorghum but **not millet or teff**, so their stage yield-response factors are
analogues, not measurements, and any result that turns on them must say so.
"""
import importlib

CROPS = ("sorghum", "wheat", "teff", "millet")


def get(crop):
    c = str(crop).lower()
    if c not in CROPS:
        raise KeyError(f"no parameter module for {crop!r}; have {CROPS}")
    return importlib.import_module(f"{__name__}.{c}")
