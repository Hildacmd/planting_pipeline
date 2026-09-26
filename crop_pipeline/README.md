# Wheat, teff and millet — ICPAC / FSRP-AF

The same engine as maize and sorghum, driven by one crop-agnostic runner so the crops cannot drift
apart in anything but their parameters.

## Coverage is set by the crop-type masks, not by the statistics

| Crop | Mask countries | Products built | Mapped area covered |
|---|---|---|---|
| wheat | Ethiopia, Sudan, Kenya, Tanzania, Rwanda, Burundi | **4** | 2.017 of 2.039 Mha (99 %) |
| teff | Ethiopia only | **1** | 2.716 of 2.716 Mha (100 %) |
| millet | Sudan, Eritrea only | **2** | 2.308 of 2.308 Mha (100 %) |

**The millet constraint is the one to know.** HarvestStat holds millet yields for Ethiopia (51
units), Kenya (35), Uganda (61 and 70) and Burundi as well as Sudan — but **no millet crop-type mask
exists for any of those countries**, so no millet product can be built there. That is a limit of the
mask series, not of the statistics, and closing it means adding millet to those masks.

Seventeen calendar rows were not built, and each says why: no mask band (13 rows, mostly teff, which
only Ethiopia grows at scale), a combined two-season calendar string that cannot be parsed (Rwanda
and Burundi wheat, both `Low` viability and 0.019 and 0.003 Mha), or `Low`/`Negligible` viability.

## Parameters, and which are sourced

| | maize | sorghum | wheat | teff | millet |
|---|---|---|---|---|---|
| Kc mid | 1.20 | 1.05 | 1.15 | 1.10 | **1.00** |
| Root zone, m | 1.0 | 1.5 | 1.0 | **0.6** | 1.5 |
| FAO-33 Ky at flowering | **1.50** | 0.55 | 0.65 | 0.55* | **0.45*** |
| Heat cap at flowering, °C | 33 | 36 | **31** | 30* | **38** |
| Emergence offset, dekads | 2 | 2 | 1 | 1 | 2* |

`*` **FIRST PASS — not from a published source for that crop.** FAO-33 covers wheat and sorghum but
**not millet or teff**, so their stage yield factors are analogues: teff from wheat scaled down,
millet from sorghum scaled down. The heat loss rate of 0.06 per heat-degree-dekad is the maize value
for every crop. Any result that turns on those numbers must say so.

The gradient across crops is at least coherent: a flowering water deficit costs maize more than
three times what it costs millet, and the heat cap rises from cool-season wheat and teff through
maize to the drought-adapted C4 cereals.

## Run

```bash
python crop_pipeline/build_calendar.py                       # rebuild the calendar
python crop_pipeline/run_all_crop.py --crop all              # dry run
EE_PROJECT=ee-manzikye python crop_pipeline/run_all_crop.py --crop all --rich --submit
EE_PROJECT=ee-manzikye python reduce_newcountries.py --asset-prefix wheatX --out-prefix newcW --crop wheat --project ee-manzikye
```

**Use `--rich`.** The reducer that feeds the apps needs `planting_dekad` and the six WRSI/WSI stage
bands.

## Status

**Yield is not reportable for any of the seven.** No ceiling has been fitted for wheat, teff or
millet; every product carries the uncalibrated default from its parameter module and the asset
property `ym_calibrated` records it. Report CPI until the calibration has run.

Two calendar disagreements worth putting to partners, both Ethiopian and both of the same shape as
the maize one that was tested and resolved in the operative window's favour: **teff** operative
Jun-d3 against GEOGLAM May-d2, and **wheat** operative Jun-d2 against GEOGLAM May-d1.
