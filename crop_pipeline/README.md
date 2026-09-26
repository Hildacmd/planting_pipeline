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

## Irrigated products need a different onset, and a different reading of the water balance

Sudan's Shitwi wheat is scheme-irrigated winter wheat on the Nile and the Gezira, sown in November
in the dry season. **Neither onset method can find it.** The CHIRPS 25/20 mm rule needs 25 mm in a
dekad and Sudan gets essentially none in November; green-up onset is gated to a rainfall-driven
climatological onset that does not exist there. The first run produced an asset with 10,478 wheat
mask pixels and **zero valid ones** — an empty product that reduced to 0 of 0 units.

Irrigated products now take a **fixed planting dekad** at the start of the calendar's indicative
window, because planting on a scheme is scheduled rather than rain-driven. The asset records
`onset_method = "fixed (irrigated scheme)"` and `irrigated = true`.

**Read their water balance differently.** WRSI and `S_water` compare crop demand against
**rainfall**. For a rainfed crop that is water stress. For an irrigated crop the shortfall is met by
the scheme, so the deficit is the **irrigation requirement** — useful in its own right, and not the
same quantity. CPI and yield for an irrigated product must not be pooled with rainfed ones.

## Independent validation: EthCT2020

`crop_type_mask/validation_ethct/` scores the Ethiopian masks against **EthCT2020**, 2,428 real
field polygons surveyed in 2020, quality `very good`, from three independent sources.

| Crop | Fields | AUC vs other crops' fields | 95 % |
|---|---|---|---|
| maize | 96 | **0.770** | [0.717, 0.821] |
| wheat | 2,077 | **0.757** | [0.728, 0.785] |
| teff | 255 | **0.661** | [0.632, 0.689] |

All three separate. This is a **harder** test than the AUC quoted in the regional report, which used
cropland as the background: here the background is fields of *other* crops, so it asks whether the
mask tells crops apart rather than merely finding cropland.

**A caveat specific to teff.** Its AUC is comfortably above chance, but the mean teff fraction at
teff fields (7.20 %) is no higher than at other crops' fields (7.45 %). The skill is in the ranking,
not the level: the mask puts teff fields above non-teff fields more often than not, while a few
non-teff fields carry a very high teff fraction and pull the mean up. Report the teff mask as
ranking teff land, not as estimating how much teff is in a cell.

**Do not use `ethiopia_crop_ground_truth_points.csv` in the same folder.** All 6,823 of its rows,
including its 82 teff points, carry `provenance = SIMULATED_reconstructed_from_published_counts_and_extent`,
and its own methodology note says: *"Do not use them as authoritative in-situ truth for accuracy
assessment."* The locations are random draws inside a bounding box, so any accuracy figure computed
from them would be meaningless.
