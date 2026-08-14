# Short-Rains Planting Workflow — Rainfall-Anchored (Kenya maize)

**Scope: SHORT RAINS ONLY.** The main pipeline (green-up-led SOS) stays primary for the **long rains**
and **Ethiopia Meher**, where the vegetation signal is strong and gives finer, higher-skill dates. This
variant applies **only** to the short rains (OND), where the green-up signal is too sparse to lead.

---

## Workflow at a glance

![Short-rains planting pipeline — rainfall-anchored, LVPD-gated, year-wrapping GDD](WORKFLOW_SHORTRAINS_diagram.png)

*Inputs (green) → ① FEWS onset rule → ② rainfall-anchored planting window (full coverage) →
③ LVPD variety-adaptive WRSI viability gate → ④ year-wrapping GDD phenology clock →
⑤ admin aggregation → interactive apps and QGIS/WKT. The orange and purple arrows show the temperature/
DEM and AEZ inputs feeding the WRSI gate and the GDD clock.*

## 1. Why the short rains need a different primary signal

The standard pipeline detects planting from a **green-up start-of-season (SOS)**. In the short rains
that signal is *confirmation-limited*: MODIS `Greenup_2` is sparse and the canopy response is weak and
noisy. Measured on Kenya maize 2024, the green-up-led product was both **sparse and biased**:

| Green-up-led product (current) | Value |
|---|---|
| Valid maize pixels | **612** of 253,003 (0.2%) |
| Modal planting dekad | **27 · Sep-d3** — *outside* the Oct-d1–Nov-d2 window |
| Calendar hit-rate (28–32) | 56% |

The sparse green-up was catching early/residual greenness, not the short-rains onset — so it planted
*early* and *almost nowhere*.

## 2. The rainfall-anchored algorithm — `run_shortrains_rainfed.py`

Rainfall establishes the window; the satellite is not required to fire. On **every** maize pixel:

```
1. LTN normal onset   = FEWS 25/20 mm rule  AND  P/PET ≥ 0.5,
                        on the 44-yr CHIRPS climatology (1981–2024), searched Oct-d1..Nov-d3
2. 2024 onset         = the same rule on actual-2024 CHIRPS
3. planting_dekad     = 2024 onset  where it fires,  else the 44-yr LTN normal   (unmask fill)
4. mask to WorldCereal maize
```
Rainfall onset is the planting trigger, so **no emergence offset** is subtracted. CHIRPS exists on
every pixel every season, so step 1 guarantees a value wherever the season is climatologically viable —
that is the coverage fix. References: 25/20 mm + WRSI onset [Senay & Verdin 2003; Verdin & Klaver 2002];
P/PET ≥ 0.5 growing-period criterion [Frère & Popov 1979]; CHIRPS [Funk 2015]. (Full citations in
`ALGORITHMS_AND_REFERENCES.md`.)

## 3. Result — measured improvement

| | Green-up-led | **Rainfall-anchored** |
|---|---|---|
| Valid maize pixels | 612 | **243,247** |
| Coverage of maize extent | 0.2% | **96%** (of 253,003) |
| Modal planting dekad | 27·Sep-d3 (out of window) | **29·Oct-d2 (in window)** |
| Hit-rate (28–32) | 56% | 100% |
| Coverage gain | — | **397×** |

Planting dekads carry real spatial spread across the short-rains belt (peaks Oct-d1/d2, tail into
Nov-d2), i.e. pixel-specific onset, not a flat fill.

## 4. Green-up as "confirmation" — tested, and it does *not* help here

On the 326 pixels where both exist, the green-up runs **~1.9 dekads earlier** than the rainfall onset
(median −2; only 37% agree within ±1 dekad). The sparse green-up is systematically **early-biased** —
it is the unreliable signal being replaced, not a trustworthy confirmer. **Decision: do not blend
green-up into the short-rains planting date.** The rainfall-anchored product stands alone; green-up may
be shown as a coarse cross-reference only.

## 5. Dry / marginal-season detection (a bonus of the method)

Where the 25/20 mm + P/PET rule **never fires even in the 44-yr climatology**, the pixel is genuinely
too marginal for a reliable short rains and is dropped: **9,756 maize pixels (4%)**. Unlike the
green-up product — which cannot tell "too dry" from "signal missing" — this run **flags the
dry/failed-season zones explicitly** (no-onset = too dry). Useful for the semi-arid short-rains belt.

## 5b. Viability gate — Last Viable Planting Date (variety-adaptive WRSI)

The rainfall onset gives full coverage, but a *late* onset can be non-viable — the crop can't complete
its cycle before the moisture runs out. The **Last Viable Planting Date (LVPD)** caps the late edge of
the window so the pipeline stops recording doomed late plantings. Rather than a rainfall-timing proxy,
the gate uses the **WRSI water balance** directly (it already accounts for stored soil moisture):

```
keep a pixel IF  WRSI( EARLY-variety maize, planted at onset ) ≥ 50   (FEWS "not crop-failure")
else             flag non-viable
```

**Why the EARLY variety, and why this never wrongly removes a viable pixel.** Farmers match the
maturity variety to the season: a marginal short-rains zone uses a short-duration (~85–90 day) variety.
Judging viability against the **shortest-that-fits (early)** variety is the most permissive test — a
pixel is dropped **only if even early maize fails**. Since early maize gives the crop the best chance,
the gate cannot remove a pixel that some variety could grow.

**Accommodating early / medium / late maturity per region.** The per-pixel **AEZ maturity class**
(early / medium / late, from `agroecology.py`, LGP + elevation) sets the crop **cycle and Kc**:
- the **viability gate** uses the **early** variety (permissive, no false removal);
- the **phenology** (flowering / maturity dates, §5c) uses the **AEZ-matched** variety;
- the **short rains** cap at short-duration everywhere (the short season forces it), while the long
  rains / Meher keep the full early→late range.

**Evidence (eastern Kenya short-rains maize, WRSI at onset):**

| Variety | Mean WRSI | Viable (≥ 50) |
|---|---|---|
| **Early ~90 d (gate)** | **75** | **100%** |
| Medium ~120 d | 56 | 79% |
| Late ~150 d | 61 | 96% |

So the gate keeps the whole core belt and flags only genuinely-too-dry margins. Reducers: **median** for
the dekad quantities (LGP-end, LVPD, onset, planting — ordinal, robust across the year-wrap), **mean**
for the *fraction* viable. Runner: `run_shortrains_gated.py` (bands: planting_dekad, wrsi_early, viable).

## 5c. GDD phenology clock for the short rains (year-wrapping)

The short rains need two changes to the GDD clock (`src/gdd_clock.py`, `run_gdd_shortrains_rainfed.py`):
1. **Anchor on the rainfall onset** (+1 dekad = emergence), not the sparse green-up SOS → full coverage.
2. **Wrap accumulation into the next calendar year.** Short rains plant in Oct (dekad ≈ 28–32) and
   **mature in Feb–Mar of the following year** (dekad > 36). The clock now maps dekads > 36 to the next
   year, so flowering/maturity are not truncated; a stage dekad of 42 means dekad 6 of the next year.

**Measured (Kenya short rains 2024, full coverage ~243 k px):** peak-vegetative → **flowering ≈ Jan-d3
(dekad 39, +1 yr)** → grain-filling → **maturity ≈ Mar (dekad 44, +1 yr)**, correctly ordered. Labels
in the app carry a `+1y` flag for wrapped dekads. `GDD_maturity` is AEZ-seeded per pixel (early 1300 /
medium 1500 / late 1700 °C·d), so the phenology uses the region-matched variety (§5b).

## 5d. Dekadal, stage-resolved WRSI / WSI / crop-failure monitor

A whole-season WRSI hides *when* stress bites. Because the FAO-56/33 water balance is accumulated
**dekad by dekad**, a **running WRSI** and the **dekadal water stress (WSI)** are snapshotted at the end
of the three growth stages — **vegetative** (initial+development) · **flowering** (mid-season) ·
**grain-fill** (late):

| Band | Meaning |
|---|---|
| `wrsi_veg` / `wrsi_flo` / `wrsi_grf` | running WRSI at each stage end (0–100; **< 50 = crop failure at that stage**) |
| `wsi_veg` / `wsi_flo` / `wsi_grf` | worst dekadal water stress within the stage (0–100) |

Flowering is the **critical** stage (FAO-33 Ky = 1.5), so **crop-failure @ flowering** (% of maize area
with running WRSI < 50 at flowering) is the headline risk. **Kenya short rains 2024:** WRSI **100 → 92 →
87** (veg → flowering → grain-fill), crop-failure at flowering ~0% — the season held through the
critical stage, with a mild grain-fill decline as the rains quit in Jan–Feb (WSI peaks at grain-fill).
Short-duration (early) maize; the balance wraps into 2025 for grain-fill.

Code: `run_wrsi_staged` (`src/wrsi_waterbalance.py`), `run_shortrains_staged_monitor.py`. Surfaced in the
Risk Monitor as the *Crop-failure @ flowering (ASAP)* layer and a per-unit stage read-out (WRSI
veg→flo→grf, stress veg/flo/grf). References: Verdin & Klaver 2002; Senay & Verdin 2003 (WRSI);
Doorenbos & Kassam 1979 (stage Ky).

## 6. Resolution — honest note

The rainfall onset is CHIRPS-derived, so its true information content is **~5.5 km**, written on the
250 m grid for overlay with the maize mask (see `ALGORITHMS_AND_REFERENCES.md` §C). It is a robust,
complete, *climatologically-anchored* planting window — not a 250 m-resolved observation. That is the
correct trade for the short rains: full, reliable coverage at rainfall resolution beats a sparse,
early-biased 250 m green-up that exists on 0.2% of pixels.

## 7. Scope boundary (why not everywhere)

| Season | Green-up signal | Primary estimator |
|---|---|---|
| **Long rains** (MAM) | strong, dense (92.7% @ 10 m) | **green-up SOS** (finer, higher skill) |
| **Ethiopia Meher** (JJAS) | strong (370k px) | **green-up SOS** |
| **Short rains** (OND) | sparse, early-biased | **rainfall-anchored** (this doc) |

Using rainfall as primary for the long rains/Meher would *coarsen* products that are already excellent
and finer — so it is not done. Match the primary signal to where the signal is strong.

**Decision — viability %, LVPD and the stage monitor are short-rains-only.** The long rains and Meher are
main, reliable seasons where maize fits with room to spare: the viability layer would read ~100% almost
everywhere, the LVPD window would be wide, and the stage-WRSI would show little stress — i.e. a nearly
uniform, low-information layer (and running the gate could wrongly imply a constraint that isn't biting).
The marginal semi-arid *long-rains* zones that would be flagged are already visible in the whole-season
WRSI / crop-failure layers. These marginal-season tools therefore earn their keep in the short rains and
are deliberately not extended to the main seasons.

## 8. Files
- `run_shortrains_rainfed.py` — the runner
- `src/wrsi_feedback.py::chirps_clim_dekadal` — the 44-yr CHIRPS climatology
- `src/wrsi_feedback.py::wrsi_onset` — 25/20 mm + P/PET ≥ 0.5 onset (reused)
- Output: `planting_Kenya_maize_Shortrains_2024_rainfed.tif` (Drive `planting_outputs/`)
