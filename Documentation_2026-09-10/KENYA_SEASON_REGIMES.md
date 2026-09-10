# Kenya maize season regimes — and where the short-rains product is not valid

**Finding in one line.** The pipeline runs one bimodal template for Kenya. Farmer-reported planting
and harvest dates show at least **three** regimes, and in the largest of them the long-rains crop is
still in the field when the short-rains SOS window opens — so **39.4% of the mapped short-rains
maize area is not a short-rains crop.**

**Evidence.** Kenya Agricultural Insurance Atlas, `Plnt_Time` / `Harv_Time` per Unit Area of
Insurance, parsed to dekads (`parse_atlas_season.py`); 937 long-rains UAI across 27 counties.
Independent of every model in the pipeline. Classification and area: `season_regimes.py` ->
`Cropyield-Data/kenya_season_regimes.csv`.

---

## 1. What the pipeline assumes

`config/season_calendar.csv`:

| season | planting window | SOS detection | configured cycle |
|---|---|---|---|
| Long rains | Mar-d2 – Apr-d3 | dekads **9–15** (Mar-d3 – May-d3) | 120 d |
| Short rains | Oct-d1 – Nov-d2 | dekads **28–34** (Oct-d2 – Dec-d1) | 90 d |

The calendar already labels the long rains **"Bimodal / W-unimodal"** — the regime split is
acknowledged in the config but not acted on: one window and one cycle are applied nationally.

## 2. What farmers report

> **CORRECTION (2026-09-04) — the planting-truncation claim below is WITHDRAWN.**
> It was benchmarked against the Insurance Atlas `Plnt_Time`, of which **71% of records name a
> RANGE** ("March/April", "3rd week of March to 1st week of April") and the parser takes its
> **start**. The Atlas therefore reports the earliest edge of a nominal insurance window, not
> observed planting. Against the TomorrowNow farmer survey (**4.8M farmers, 2024**), only
> **14.9% of ward-median planting falls before the detection window and 85.0% falls inside it** —
> the reverse of the Atlas figure. Paired on 368 shared wards the two sources differ by a
> systematic **1.46 dekads**.
> **The pipeline's planting date is fine**: +0.43 dekads (~4 days early) against the survey, not
> 1–3 dekads late. Sources compiled in `Cropyield-Data/planting_dates_all_sources_{county,ward}.csv`.
> Findings that rest on Atlas *cycle length* (planting→harvest) are unaffected, because a
> consistent offset at both ends largely cancels.


~~**83.4% of long-rains planting occurs BEFORE the SOS window opens at dekad 9.**~~ *(withdrawn — see the correction above; the farmer survey puts this at 14.9%.)*
The farmer-reported median is dekad 8 (Mar-d2). Nothing is reported after the window closes.

Splitting those early planters by their *harvest* date separates two different things:

| | plant | harvest | cycle |
|---|---|---|---|
| early planters (n=781) | Mar-d2 | **Aug-d2** | **170 d** (IQR 150–210) |
| in-window planters (n=156) | Mar-d3 | Sep-d2 | 150 d |

**41% of early planters harvest at or after dekad 25 (Sep+); 26% at or after dekad 28 (Oct+).**

## 3. The three regimes

Classified on county medians (n >= 3 UAI): cycle >= 200 d -> highland unimodal; else planting
dekad <= 6 -> western early; else standard bimodal. Area is the 250 m crop-mask pixel count
(6.25 ha/pixel).

### A. Highland unimodal long-cycle — **65.2% of long-rains maize area**

| county | UAI | plant | harvest | cycle | LR ha | SR ha |
|---|---|---|---|---|---|---|
| Trans Nzoia | 43 | Mar-d2 | Oct-d2 | 210 d | 61,831 | 78,750 |
| Uasin Gishu | 61 | Mar-d2 | Oct-d2 | 210 d | 48,038 | 103,288 |
| Nakuru | 75 | Mar-d2 | Nov-d2 | 240 d | 19,162 | 93,981 |
| Nandi | 8 | Mar-d2 | Oct-d2 | 215 d | 18,675 | 45,906 |
| Nyandarua | 45 | Mar-d2 | Nov-d1 | 270 d | 4,575 | 30,344 |

This is **not an early long rains**. It is a single long season occupying most of the year: plant
March, harvest October–November. It is the Kenyan maize belt — the counties that grow the crop.

### B. Western early bimodal — 2.0% of long-rains maize area

| county | UAI | plant | harvest | cycle |
|---|---|---|---|---|
| Narok | 4 | Feb-d1 | Jul-d2 | 160 d |
| Kisumu | 40 | Feb-d2 | Jul-d2 | 150 d |
| Migori | 64 | Feb-d2 | Jul-d2 | 150 d |
| Kisii | 27 | Feb-d2 | Aug-d2 | 170 d |
| Homa Bay | 44 | Feb-d2 | Aug-d2 | 180 d |

Here the window genuinely opens late: planting is **February**, a full 3–4 dekads before dekad 9,
on an otherwise normal 150–180 d cycle.

### C. Standard bimodal — 32.8%

17 counties (Baringo, Kakamega, Bungoma, Laikipia, Kitui, Kilifi, Kwale, Busia, Siaya, coastal and
eastern). Plant Mar-d1–d3, harvest Jun–Sep, cycle 90–180 d. The configured template fits these.

## 4. The consequence

**39.4% of the mapped short-rains maize area lies in regime-A counties**, where the long-rains crop
is still standing when the short-rains SOS window opens at dekad 28. Any green-up detected there in
Oct–Dec is the **standing long-rains crop**, not a new planting.

That makes the short-rains product over those counties an artefact, not a weak signal. It also
explains an anomaly found earlier and wrongly set aside: pipeline short-rains planting in
Bomet/Narok read dekad 28–29 against a farmer-reported 35–36, and the ward records were dismissed as
questionable. They were not — the pipeline was detecting the wrong crop.

**Converging evidence.** Independent lines agree that regime A is a long season:
- GDD clock: highland thermal cycle 188–232 d (`METHODOLOGY_TESTING` §5.6)
- Atlas farmer reports: 210–270 d (this document)
- Climatic LGP: 320–334 d max-run in western Kenya, i.e. near-continuous moisture (§5.4)

## 5. Caveats

1. **Planting date and SOS are different quantities.** Dry planting — sowing before the rains — is
   common in western Kenya, and green-up necessarily lags sowing. Part of the 83% is definitional,
   not error. It does not excuse the truncation: a window starting at dekad 9 cannot represent the
   early tail at all.
2. **Narok rests on 4 UAI** yet carries the largest short-rains area (155,169 ha). Its regime
   assignment is weak and should be re-checked before it drives anything.
3. **Farmer "harvest" includes field drying**, so cycle lengths are an upper bound on physiological
   maturity.
4. Regime boundaries are county-level medians. Several counties span more than one regime
   internally; a pixel-level classification would be sharper.

## 6. What follows

1. **Do not ship a short-rains product for regime-A counties** without a mask, or state on it that
   the detected signal may be the long-rains crop.
2. **Give regime A its own season definition** — a Mar–Nov unimodal window with a ~210–260 d cycle —
   rather than a long-rains + short-rains pair. This is the "highland needs its own unimodal season"
   hypothesis from `lgp_ab_test_MAM.md`, now with independent observational support.
3. ~~Open the long-rains SOS window earlier.~~ **No longer indicated** — the farmer survey shows
   85% of planting already inside the window and the pipeline only ~4 days early. The apparent
   truncation was an Atlas artefact (see §2).
4. **Taita Taveta records its short rains as Aug–Sep**, not Oct–Nov, and 7 UAI nationally plant in
   dekads 19–27 — a window neither configured season can detect.

## References

- FAO (1978). *Report on the Agro-ecological Zones Project, Vol. 1.* World Soil Resources Report 48.
  — the growing-period convention underlying the season definitions.
- Jaetzold, R., Schmidt, H., Hornetz, B. & Shisanya, C. (2006–2012). *Farm Management Handbook of
  Kenya, Vol. II* (2nd edn), Ministry of Agriculture / GTZ. — the standard Kenyan agro-ecological
  zone reference; documents the highland long-cycle and western regimes.
- Hassan, R.M. (ed.) (1998). *Maize Technology Development and Transfer: A GIS Application for
  Research Planning in Kenya.* CAB International. — maize production systems and maturity classes
  by zone.

## 8. Independent climatological check of the OND window (added 2026-09-04)

§7's OND early/late split was derived entirely from reported planting (farmer survey, Insurance Atlas,
Growing Season Planner). It has now been tested against three climatologies that never saw the survey:
the CHIRPS rainfall normal (1996–2025), the CHIRTS temperature normal (1996–2025), and MODIS MCD12Q2
land-surface phenology (2001–2023, cropland-masked). Per-county results:
`Cropyield-Data/ond_window_ltn_validation.csv`. Figures: `Methodology_Testing/figs/ond_ltn_fig1..5*.png`.

**The split survives.** CHIRPS separates the two survey-defined groups on rainfall structure —
Aug–Sep rainfall 211 mm (early) vs 34 mm (late), Wilcoxon p = 0.009, AUC 0.79; pre-season fraction
0.40 vs 0.11 (p = 0.011); CHIRPS onset dekad 21 vs 29 (p = 0.030). MODIS agrees independently:
second-cycle green-up dekad 26.5 vs 29.0 (p = 0.019) and second-cycle detection rate 20% vs 35%
(p = 0.029). Survey labels and CHIRPS rainfall structure agree in 22 of 28 counties.

**CHIRTS returns a negative.** No temperature variable separates the regimes — Tmax over OND
(p = 0.226), Tmax over Aug–Sep (p = 0.611), accumulated GDD over OND (p = 0.396). The OND split is a
rainfall-structure phenomenon, not a thermal one, so it must not be proxied by temperature or altitude.

**The "early" regime is misnamed.** In 13 of the 17 "early" counties (Kakamega, Vihiga, Bungoma, Nandi,
Nyamira, Busia, Kisumu, Siaya, Homa Bay, Migori, Nyandarua, Narok, Nyeri) CHIRPS shows
no dry break: rain runs continuously from July and the 25/20 mm rule fires at the start of the scan
because it is already raining. These counties do not have an early short-rains onset; they have **no
distinct short rains** — what the calendar calls OND is the tail of one long wet season. MODIS concurs:
a second green-up cycle is detected in only 20% of years there. No detection window is meaningful in a
continuous-rainfall county, so onsets reported there should carry a low-confidence flag.

**The shipped window is correctly placed for the counties it is for.** Across all 28 counties the CHIRPS
onset falls inside dk 28–33 in 54% of cases, but every miss is a continuous-rainfall county. Restricted to
the 13 counties with a genuine dry break, **CHIRPS places the onset inside the window in 13/13 and MODIS
places green-up inside it in 13/13**, with a CHIRPS onset range of Oct-d1 to Nov-d1 — interior, not at
either edge. The dekad 34 → 33 trim removes only space no anchor occupies. MODIS green-up correlates with
CHIRPS onset at ρ = +0.73 (p < 0.001) and with survey onset at ρ = +0.50 (p = 0.007), lagging CHIRPS by
a median 1.1 dekads (≈11 days) — the physically expected rain → germination → canopy order.

**The three doubtful assignments are overturned.** Both climatologies resolve Garissa, Bomet and Kisii
against their survey labels: Garissa (30 mm Aug–Sep, CHIRPS onset Nov-d1) is late/distinct, not early;
Bomet (243 mm, onset Jul-d1, second cycle in only 4% of years) and Kisii (290 mm, onset Jul-d1) are
continuous, not late. Kisii is the weakest — MODIS still detects a second cycle in 48% of its years.

**Limits.** Normals compared against one season of survey data test *placement*, not year-to-year skill;
n = 28 counties, so p-values near 0.03 are not robust to a few reclassifications; MCD12Q2 green-up over a
mixed cropland pixel responds to whatever is growing, not specifically to maize; and the 25/20 mm rule is
one onset definition among several. The 13/13 coverage result is the robust finding; the per-variable
p-values are supporting evidence.
