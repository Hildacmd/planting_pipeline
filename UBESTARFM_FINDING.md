# ubESTARFM for onset detection — a documented negative result

**Verdict: no net benefit. `cue` fusion (NDRE + FPAR + SAR) alone is the best onset estimator.
ubESTARFM gap-fill is a small net negative (−3 to −4 pts) even after NDVI→NDRE calibration.**
This file records the experiment so the dead-end is *proven*, not re-litigated later.

## What was tested

Reference: Kenya maize, Long rains 2024. Skill = calendar hit-rate against the
calculation-based planting window **dekads 8–12** (Mar-d2 centre = dekad 10). Metrics
computed locally from the exported planting rasters (pixels with dekad ∈ [1,36]).

| Variant | Fusion greenness | Scale | Hit-rate | Bias | MAE | vs cue@250 |
|---|---|---|---|---|---|---|
| **cue @ 10 m** | NDRE + FPAR + SAR | 10 m | **92.7%** | — | — | (reference ceiling) |
| **cue @ 250 m** | NDRE + FPAR + SAR | 250 m | **81.5%** | −1.88 | 1.90 | — |
| raw-merge @ 250 m | NDRE+FPAR primary, **raw-NDVI** ubESTARFM gap-fill, SAR last | 250 m | 77.3% | −1.93 | 1.94 | **−4.3 pts** |
| calibrated-merge @ 250 m | NDRE+FPAR primary, **NDVI→NDRE-calibrated** ubESTARFM gap-fill, SAR last | 250 m | 78.4% | −1.95 | 1.97 | **−3.1 pts** |

## What the numbers say

1. **Resolution is the dominant lever, not fusion.** Coarsening 10 m → 250 m costs
   **−11.2 pts** (92.7 → 81.5). Every fusion choice below that is a second-order effect.
2. **ubESTARFM gap-fill hurts onset.** At *matched* 250 m resolution, adding the ubESTARFM
   NDVI fill costs **−4.3 pts** vs cue alone. The extra gap-free density in cloudy dekads
   injects early greenness that red-edge would not see, nudging SOS ~1 dekad early.
3. **Calibration works, but not enough.** Moment-matching the ubESTARFM NDVI into NDRE space
   recovers **+1.2 pts** (77.3 → 78.4) — the mechanism was right — but the merge is still
   **−3.1 pts** below cue. It never breaks even.

## Why (the honest reason)

The pipeline's whole premise is **red-edge (NDRE) for clean early-canopy onset**. MODIS has
no red-edge, so ubESTARFM can only gap-fill with **NDVI**, which rises earlier and flatter for
sparse early canopy. Denser coverage helps *area completeness* but hurts *onset precision*, and
for onset, precision wins. Calibration shifts the NDVI baseline/amplitude toward NDRE but cannot
reconstruct the red-edge's sharp green-up timing from a broadband index.

## Decision

- **Keep `cue` fusion as the production greenness** (`--fusion cue`, the default).
- **Shelve `--fusion estarfm` for onset.** The code (`src/estarfm.py`,
  `build_fused_greenness_enhanced`) is retained and functional for reproducibility / future use
  (e.g. a canopy-density or biomass product where NDVI density *is* the goal), but is **not** on
  the planting-window path.
- Resolution — not fusion — is where future skill gains live: run at the finest scale the
  compute budget allows (10 m ≫ 250 m).

_Experiment closed 2026-07. Fan-out to Short rains / Ethiopia Meher and a ubESTARFM WRSI were
considered and dropped: they would only reproduce this same small-negative pattern._
