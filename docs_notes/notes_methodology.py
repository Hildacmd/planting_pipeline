# -*- coding: utf-8 -*-
"""Stage notes for the methodology A/B test notebooks.

These notebooks already carry a Question and a Result section. What is added here is the
operational layer: what each script actually does, what it writes, how long it takes, and
the numbers to expect from it.
"""

TEST_SETUP = [
("!pip -q install earthengine-api geemap pandas geopandas scipy", r"""
### Stage 0 · Runtime

Installs the Earth Engine client, geemap, pandas, geopandas and scipy. `scipy` is the one that matters
here: every score in this notebook is a leave-one-out cross-validation with a paired bootstrap interval,
and both come from scipy.

**Expected output.** `installed.`
"""),
("ee.Initialize(project=PROJECT)", r"""
### Stage 0b · Earth Engine

`EE ready: ok`. The export cells below submit **batch tasks** and return immediately; the scoring cells
read the resulting CSVs. Between the two you have to wait, and you can close the browser while you do.
Watch the queue at code.earthengine.google.com/tasks.

**The export queue is per cloud project.** `ee-manzikye` has left batches in READY for hours. If the
tasks are not entering RUNNING within about 20 minutes, switch `PROJECT` to
`indigo-proxy-484220-q8` and resubmit rather than waiting.
"""),
("PIPE_DIR=\"/content/drive/MyDrive/planting_pipeline\"", r"""
### Stage 0c · Drive

`pipeline on path: ...`. The scoring scripts read and write `Cropyield-Data/` inside this folder, so the
notebook must `chdir` here for the relative paths to resolve.
"""),
]

NOTES = {}

# ------------------------------------------------------------------ 01 WHC A/B
NOTES["Methodology_Testing/01_whc_ab_soilgrids.ipynb"] = TEST_SETUP + [

("!python whc_ab_test.py", r"""
### Stage 1 · Export the two arms

**What runs.** Four export jobs. Both arms use the identical pipeline and **only `whc_img` differs**:
arm A is the uniform 100 mm bucket, arm B is the per-pixel SoilGrids and Saxton-Rawls root-zone
capacity.

| Script | Variant | Units |
|---|---|---|
| `whc_ab_test.py` | Kenya long rains, county | 44 |
| `whc_ab_variants.py --variant short_county` | Kenya short rains, county | 46 |
| `whc_ab_variants.py --variant short_ward` | Kenya short rains, 2021 and 2022 crop-cut wards | 66 and 15 |
| `whc_ab_variants.py --variant et_meher` | Ethiopia Meher, region | 6 |

**CPI is exported with `ym = 1`**, deliberately. That keeps the ceiling out of the export so each arm
can be given its own, or a shared one, at scoring time. Stage 3 is where that choice decides the answer.

**Expected output.** Task submission lines, returning in seconds. The exports themselves run for
minutes to hours.

**The gotcha that invalidated the first run, and why the exports are at level 2.** GAUL 2015 level 1
for Kenya is the **eight old provinces**, not the 47 counties HarvestStat reports. The first export
returned 8 rows and would have matched a single county. Everything now exports at level 2, the old
districts, and rolls up through `src/kenya_gaul_counties.py`, 71 districts to 47 counties,
**weighted by pixel count** so a one-pixel district cannot outvote a 9,917-pixel one.
"""),

("!python whc_ab_score.py", r"""
### Stage 2 · Score with a per-arm ceiling

**What runs.** Each arm is given **its own** fitted $Y_m$, then scored by leave-one-out MAE and
Spearman against HarvestStat.

**Why leave-one-out rather than a 70/30 split.** With 6 to 81 zones, a single 70/30 split at $n\approx45$
has a standard deviation of about **±0.10 t/ha**, which is larger than any effect measured in this whole
round of tests. A single split would have produced **two false positives** here. Every free parameter is
refit on $n-1$, and the interval is a paired bootstrap.

**Expected output.** A per-variant table of $\Delta$ MAE with a confidence interval. Read the interval,
not the point estimate: only one variant produces an interval clear of zero, and stage 3 removes it.
"""),

("!python whc_ab_score_ymfixed.py", r"""
### Stage 3 · Score with the ceiling held fixed, which is the step that changes the answer

**What runs.** The same comparison with **one shared $Y_m$ across both arms**, under three regimes:
`prod`, the ceiling the pipeline ships; `fit_A`; and `fit_B`. The last two bracket the answer, so a
result cannot be an artefact of which arm set the level.

**Why it matters.** SoilGrids WHC is uniformly a **bigger bucket** than 100 mm, so its dominant effect
on CPI is a **level shift**. Refitting a separate $Y_m$ per arm absorbs exactly that shift by
construction, which is how a level difference disguises itself as a skill difference.

**Expected values.**

| Variant | n | Per-arm Ym Δ(A−B) | Fixed Ym Δ(A−B) | Verdict |
|---|---|---|---|---|
| Kenya long, county | 44 | +0.010 [−0.060, +0.071] | −0.024 [−0.076, +0.023] | null |
| Kenya short, county | 46 | +0.046 [+0.006, +0.085] | +0.010 [−0.049, +0.066] | **the win does not survive** |
| Kenya short, ward 2021 | 66 | −0.000 | −0.082 [−0.101, −0.064] | uniform better |
| Kenya short, ward 2022 Kitui | 15 | +0.006 | **−0.318 [−0.384, −0.240]** | uniform much better |
| Ethiopia Meher, region | 6 | +0.002 | −0.006 | arms identical |

**How to read this.** The single positive result was an artefact of the per-arm ceiling. Under a shared
ceiling SoilGrids is never better and is clearly worse in Kitui 2022, where the bigger bucket **hides
the drought**: it carries enough stored water through the dry spell for the model not to register it.
Ethiopia's arms are identical because Meher WRSI saturates near 100 in both.

**What this does and does not license.** SoilGrids WHC remains defensible on physical grounds and stays
the default. What cannot be claimed is that it improves yield skill; the evidence says it does not.
A null result recorded properly is the point of the exercise.
"""),
]

# ------------------------------------------------------------------ 02 LGP / AEZ Ym
NOTES["Methodology_Testing/02_lgp_and_aez_ym_recheck.ipynb"] = TEST_SETUP + [

("!python lgp_ym_ab_recheck.py", r"""
### Stage 1 · Rebuild and re-score both earlier A/Bs

**What runs.** The original script was not kept, so this reconstructs both tests from source: the
county-mean water-limited relative yield from the CHIRPS MAM water balance at each season duration, a
highland flag from SRTM at 1800 m, and the HarvestStat multi-year county mean.

**Why they needed re-checking, for two different reasons.** The **LGP** test refits $Y_m$ per arm, so it
can mistake a level shift for skill. The **AEZ-Ym** test fits **two** free parameters against one, so it
can win simply by having more freedom. Leave-one-out with the parameters refit on $n-1$ pays for both.

**Fidelity check first.** The reconstruction reproduces the published Pearson r of 0.66 and 0.51 almost
exactly. That is what makes the re-scoring trustworthy; if it did not, nothing below would mean anything.

**Expected values.**

| Arm | Free parameters | LOO MAE | Pearson | Spearman |
|---|---|---|---|---|
| A, fixed 120 d, single $Y_m$ | 1 | 0.601 | +0.642 | +0.725 |
| B1, zone-aware LGP | 1 | 0.684 | +0.497 | +0.525 |
| B2, per-zone $Y_m$ 3.7 / 2.3 | 2 | **0.537** | **+0.780** | **+0.830** |

**Two different verdicts.**

* **LGP: confirmed, keep the fixed 120 days.** B1 loses on MAE and collapses the ranking. The rank half
  of the verdict is invariant to $Y_m$, so the refit trap never applied. Across 500 seeds B1 beats A in
  only 10 % of them, so the published result was typical rather than lucky.
* **AEZ-Ym: right decision, wrong evidence.** The MAE gain of +0.063 has an interval of
  [−0.046, +0.167], which is **not significant** once the second parameter is paid for. The out-of-sample
  **ranking** gain is real. So the highland lever is the ceiling, not the season length, but the claim
  should be made about rank skill and not about MAE.

The highland split is currently **off** in `src/cpi.py` (`YM_HIGHLAND = {}`) because the typical-year
calibration uses one ceiling per country and season. The commented values reproduce the 2024 fit.
"""),
]

# ------------------------------------------------------------------ 03 GDD
NOTES["Methodology_Testing/03_lgp_vs_gdd_phenology.ipynb"] = TEST_SETUP + [

("!python lgp_vs_gdd.py --variant ke_long", r"""
### Stage 1 · Export season length and flowering timing

**What runs.** Three variants. Each exports two things, and the second is the one people forget:
**season length** and **flowering timing**. A shifted flowering dekad moves the critical-window water
balance even when total length agrees, and CPI puts the FAO-33 weight of $K_y = 1.5$ on flowering.

**Two compute traps hit here, both now fixed in the scripts.**

1. The short-rains variant timed out. The production short-rains planting gap-fills with a **44-year
   CHIRPS climatology**, which on top of 27 dekads of ERA5-Land exceeds the Earth Engine budget. Fixed
   with a light onset and `dk_hi = se + 14`.
2. `gdd_maturity_from_aez` builds a very large client-side graph and stalled submission. Short rains now
   use the constant early-class target of **1300 °C·d**, which is the right target for short-duration
   maize anyway.

**Expected output.** Task submission lines. Allow time before scoring.
"""),

("!python lgp_vs_gdd_score.py", r"""
### Stage 2 · Score, and the largest discrepancy in the whole pipeline

**What runs.** Compares the fixed 120-day season against the per-pixel thermal season from ERA5-Land
growing degree days, anchored on the detected start of season.

**Expected values, Kenya long rains 2024.** The GDD county mean is 137 days, but **pixel-weighted over
actual maize it is 173 days**. Only **8 of 44** counties fall within ±15 days of the fixed assumption.

| | GDD season | vs fixed 120 d | Flowering shift |
|---|---|---|---|
| Highland, 1800 m and above, n = 14 | **187.7 d** | **+67.7 d** | **+25.9 d later** |
| Lowland, below 1800 m, n = 30 | 113.7 d | −6.3 d | −12.7 d earlier |

The overruns are the grain basket: Nyandarua +112, Bomet +100, Kericho +84, Uasin Gishu +79. The
shortfalls are the hot arid and semi-arid lands: Turkana −55, Marsabit −50, Tana River −46.
Ethiopia Meher: GDD 142 days, 154 pixel-weighted, +22 days, with 3 of 6 regions within ±15 days.

**Why this matters more than the other tests.** The fixed cycle is wrong by more than two months in the
highlands, and the flowering window moves by nearly a month with it. Because the stage weights put
three times the weight on flowering, the water balance is being read at the wrong point of the season
exactly where most of Kenya's maize is grown.

**And why the fix is not simply to adopt the GDD clock.** Notebook 02 shows a zone-aware **season
length** made the yield worse, and the CHIRTS work shows the spreadsheet GDD targets are worse than the
ERA5 ones. The evidence supports replacing the **fixed 120-day cycle**, not adopting the current
maturity targets uncritically. Treat this as the strongest open item in the methodology, not as a
settled change.
"""),
]

# ------------------------------------------------------------------ 04 DMP
NOTES["Methodology_Testing/04_dmp_vs_cpi_yield.ipynb"] = TEST_SETUP + [

("!python dmp_run.py --variant ke_long", r"""
### Stage 1 · Export the biomass route

**What runs.** Five zonal exports of seasonal dry matter, for Kenya long rains, Kenya short rains, the
2021 and 2022 crop-cut wards, and Ethiopia Meher.

**Raw dry matter in kg/ha is what is exported.** Harvest index, above-ground fraction and grain moisture
are applied at **scoring** time, so they can be retuned without re-exporting anything.

$$\text{seasonal DM}=\sum_t \mathrm{DMP}_t \times \text{days in dekad } t,\qquad
\text{grain}=\mathrm{DM}\,\frac{F_{\text{above}}\times HI}{1-\text{moisture}},$$

with maize defaults 0.80, 0.45 and 0.135. Dekads are 8 to 11 days, not a flat 10, and `dekad_to_t()`
uses the real calendar; a flat ×10 introduces a systematic error of a few percent, and time is indexed
continuously so a short-rains season maturing the following year integrates without a day-of-year wrap.

**The source is a stand-in and you must say so.** Copernicus DMP is 300 m or 1 km, is not in the Earth
Engine catalog, and needs a NetCDF download and ingest before `CGLS_DMP_ASSET` can be set. Until then
**MODIS MOD17A2H GPP stands in**, converted to net primary production with a carbon-use efficiency of
0.45 and to dry matter by dividing by 0.475. `--source modis|cgls` is a one-flag swap. Treat MODIS
**magnitudes as provisional and the rankings as more robust**, which is exactly what the results below
show.
"""),

("!python dmp_score.py", r"""
### Stage 2 · Score the biomass route against the water-balance route

**Expected values.** Both routes against the same ground truth.

| Variant | n | DMP: MAE / bias / ρ | CPI: MAE / bias / ρ | Implied HI | DMP over-prediction |
|---|---|---|---|---|---|
| Kenya long 2024 | 43 | 1.09 / +1.04 / **+0.77** | 0.68 / +0.09 / +0.73 | 0.275 | 1.7× |
| Kenya short 2024 | 46 | 0.76 / +0.68 / **+0.64** | 0.52 / +0.06 / +0.59 | 0.285 | 1.6× |
| Kenya ward 2021 | 66 | 1.45 / +1.45 / **+0.49** | 1.25 / +1.22 / +0.15 | 0.066 | 7.3× |
| Kenya ward 2022, Kitui | 15 | 1.46 / +1.46 / **+0.41** | 0.54 / +0.54 / **−0.32** | 0.019 | 23.5× |
| Ethiopia Meher 2024 | 7 | **0.53 / −0.36 / +0.64** | 1.58 / +1.58 / **−0.40** | 0.468 | 0.8× |

**How to read it.** **DMP out-ranks the CPI water balance in all five variants.** Spearman is higher
every time, and the gap is widest exactly where CPI ranks **backwards**: Kitui 2022 at −0.32 and
Ethiopia Meher at −0.40. A negative rank correlation is worse than no information, and it is the single
most serious finding in this set.

**The level is a different matter.** DMP over-predicts by 1.6 to 23.5 times, and the implied harvest
index collapses to 0.019 in the Kitui wards, which is agronomically impossible. The cause is mixed
pixels: at 500 m the signal carries non-crop biomass. That is why notebook 05 uses a DMP **anomaly**
rather than raw biomass, since the contamination is largely static per pixel and differencing against
the pixel's own climatology cancels most of it.

**Ethiopia is the immediately actionable case.** DMP wins on every metric, and its implied harvest index
of 0.468 sits squarely in the agronomic range of 0.30 to 0.55. Ethiopia Meher is where the water balance
is least informative and the biomass route most defensible.
"""),
]

# ------------------------------------------------------------------ 05 S_veg swap
NOTES["Methodology_Testing/05_sveg_swap_dmp.ipynb"] = TEST_SETUP + [

("!python sveg_swap_run.py --variant ke_long", r"""
### Stage 1 · Export the two arms

**The design keeps one thing different and everything else identical.** $S_{\text{water}}$ and
$S_{\text{heat}}$ are computed **once and shared**, so the arms differ in exactly one term:

| Arm | $S_{\text{veg}}$ source |
|---|---|
| V | `cpi.s_veg(source='ndvi')`, the production MOD13Q1 VCI |
| D | `dmp_yield.s_veg_dmp(mode='vci')`, the same Kogan VCI form computed from DMP |

Three choices keep it honest. The DMP term is an **anomaly, not raw biomass**, which cancels the static
mixed-pixel contamination that over-predicted the Kitui wards 23.5-fold in notebook 04. Both arms keep
the same `VEG_W = 0.4`, so only the source changes, which also **caps the achievable effect**, since
$S_{\text{veg}}$ is deliberately down-weighted to a confirmation. Both use a matched 2015 to 2023
climatology, which means arm V is not byte-identical to the shipped product but is comparable to arm D.

**Two silent bugs this test surfaced, both of which produced plausible wrong numbers.**

1. Mapped images dropped `system:time_start`, so the inner `filterDate` matched nothing and the seasonal
   sum returned a **zero-band image**. It did not error; it returned zeros.
2. **MOD17A2H v061 in Earth Engine covers only 2021 to 2026**, so every year of the intended climatology
   was empty. Switched to **MOD17A2HGF**, gap-filled, 2000 to 2025. Gap-filling is an advantage for a
   climatology, because missing composites would bias the minimum and maximum that VCI is built from.

Both are worth remembering generally: in Earth Engine a wrong filter returns an empty collection, and an
empty collection reduces to zeros rather than to an error.
"""),

("!python sveg_swap_score.py", r"""
### Stage 2 · Score

**Expected values.**

| Variant | n | V Spearman | D Spearman | Δ LOO-MAE | Interval | D better in | Fixed-Ym winner |
|---|---|---|---|---|---|---|---|
| Kenya long 2024 | 43 | +0.737 | +0.754 | +0.014 | [−0.024, +0.054] | 77 % | V |
| Kenya short 2024 | 46 | +0.594 | +0.617 | +0.010 | [−0.008, +0.031] | 84 % | V |
| Ethiopia Meher 2024 | 5 | **+0.100** | **+0.700** | +0.075 | [−0.032, +0.185] | 92 % | D |

**The verdict is suggestive, not conclusive.** No variant is statistically significant; every interval
spans zero. But the direction is consistent: DMP ranks better in three of three, and wins 77, 84 and
92 % of resamples across three independent datasets.

**Do not read the fixed-Ym column as a skill statement.** DMP reads **less** stress than NDVI in Kenya,
0.084 against 0.120 in the long rains, so CPI rises and the bias worsens; it reads **more** in Ethiopia,
0.192 against 0.135, so CPI falls and the known over-prediction improves. That column only records
whether the level shift happened to point in a helpful direction, which is not evidence about the
vegetation term.

**Why the swap was not adopted.** The Ethiopia result rests on **n = 5**. Re-run at admin level 2 with
n = 39 it does not hold, so the headline number here has no support at a usable sample size. The
production $S_{\text{veg}}$ stays on MOD13Q1 VCI.
"""),
]

# ------------------------------------------------------------------ combined notebook
NOTES["methodology testing/methodology_testing_colab.ipynb"] = [

("!pip -q install earthengine-api geemap pandas scipy", r"""
### Stage 0 · What this notebook is

**Every A/B and validation test in one place**, for the 2024 maize pipeline in Kenya and Ethiopia. Each
section is one test: the question, the code that reproduces it, and the verdict on record.

**Most re-run switches are off by default.** The heavy stages are guarded by flags such as
`RERUN_UBESTARFM` and `RUN_WHC_EXPORTS`, set to `False`, so the notebook runs end to end in seconds and
prints the recorded findings. Set a flag to `True` only when you intend to reproduce that test, and
expect Earth Engine exports that run for hours.

The same tests, one notebook each and with more detail, are in `Methodology_Testing/01` to `05`.
"""),

("ee.Initialize(project=PROJECT)", r"""
### Stage 0b · Earth Engine

`EE ready: ok`. Only needed for the re-run flags; the scoring cells read CSVs. Use
`indigo-proxy-484220-q8` if you are going to export, since the queue is per project.
"""),

("DRIVE_OUT=", r"""
### Stage 0c · Drive, and where the results live

Two folders matter. `Cropyield-Data/` inside the pipeline holds the scoring inputs and outputs, and
`DRIVE_OUT` is where Earth Engine exports land. The helper below searches both.
"""),

("def find_csv(pat)", r"""
### Stage 0d · Shared scoring helpers

**What these do.** `find_csv` resolves a glob across both folders and returns the **newest** match.
That newest-first rule is not cosmetic: Earth Engine never overwrites, so a re-export lands as
`name (1).csv` while the stale file keeps the clean name. Taking the newest is what stops a re-run
silently scoring the previous run's numbers.

The rest are the scoring conventions used throughout: leave-one-out cross-validation with every free
parameter refit on $n-1$, a paired bootstrap interval, and Spearman reported beside MAE because rank
skill is invariant to the yield ceiling. With 6 to 81 zones, a single 70/30 split has a spread larger
than any effect measured here.
"""),

("def ee_tasks(", r"""
### Stage 0e · Poll the export queue

Prints the state of the most recent tasks. Re-run to refresh. More than about 20 minutes with nothing
entering RUNNING is a stalled queue, not a slow one; cancel, switch project, resubmit.
"""),

("RERUN_UBESTARFM", r"""
### T1 · Cue fusion against ubESTARFM — retired

**On record.** Cue fusion **81.5 %** against ubESTARFM **77.3 to 78.4 %** at 250 m. The blended
reflectance product did not beat the simpler multi-cue fusion for onset detection, at a much higher
compute cost.

**Expected output.** The skipped message and that finding. The module is kept in `src/estarfm.py` if
the result ever needs reproducing; set the flag to `True` only then, because the run is heavy.

**Why a negative result is kept.** It is the reason the production onset is cue fusion. Without it, the
same idea would be proposed again.
"""),

("RERUN_RESOLUTION", r"""
### T2 · 10 m against 250 m

**The question.** How much onset skill does the operational 250 m scale cost against a native 10 m run
of the same method?

**To reproduce.** Run `01_planting_window.ipynb` twice over the same box with the scale changed, then
score both with `admin_skill_local.py`. The comparison is only meaningful over a small box; a 10 m run
of a whole country is not feasible interactively.
"""),

("RERUN_LTN_ABLATION", r"""
### T3 · Does the climatological prior help?

**The question.** Does gating the start-of-season search to within two dekads of the long-term normal
improve planting skill, or does it just suppress variability?

**Why the gate exists.** Without it, a weed flush or a second green-up can be picked up as the season.
With it, a genuinely anomalous season is clipped toward the normal. The pipeline applies the gate **only
where a prior exists**, passing the calendar window through where it is masked, so a sparse
second-season normal cannot reject every pixel.

**Expected runtime.** Minutes over a test box, when the flag is set to `True`.
"""),

("maize_wkt_kenya_wb_MAM_120d_masked", r"""
### T4 · Fixed 120 days against a zone-aware season length

**On record: keep the fixed 120 days.** The zone-aware arm loses on MAE, 0.684 against 0.601, and
collapses the ranking, Spearman 0.525 against 0.725. Across 500 seeds it wins in only 10 % of them.

**Expected output.** The scores if the per-duration CSVs are present, otherwise a message saying the
recorded verdict stands, with the write-up in `Cropyield-Data/lgp_ab_test_MAM.md`.

**Read this with T8.** T4 says a zone-aware **length** does not improve yield. T8 says the fixed length
is wrong by 68 days in the highlands. Both are true: the fixed cycle is wrong, and the particular
zone-aware replacement tested was not an improvement.
"""),

("REBUILD_OBS", r"""
### T5 · Fitting the yield ceiling to HarvestStat

**What this does.** Fits $Y_m$ so that $Y_a = (\mathrm{CPI}/100)\,Y_m$ matches reported sub-national
yields, as a least-squares slope through the origin, tested out of sample.

**The current fit is the typical-year one**, with the median over the available years as the target:
Kenya 2.34 long rains and 1.44 short rains, Ethiopia 4.14, Rwanda 2.61, Burundi 1.88, Somalia 1.02,
Uganda 2.34 provisional. Held-out error falls by 49 to 87 % against the uncalibrated defaults.

**The distinction that matters for use.** Where $r$ is near zero, as in Rwanda, Burundi and Somalia, the
ceiling fixes the **level** only. Those maps are usable for national and seasonal totals and not for
ranking districts. Full write-up in `yield_calibration_2024/YIELD_CALIBRATION_2024.md`.
"""),

("from src.cpi import ym_for, ym_img_for", r"""
### T6 · One national ceiling against a highland split

**The question.** Is the highland yield advantage potential, meaning a higher ceiling, rather than a
longer season?

**On record: the highland lever is the ceiling, but the evidence supports the ranking claim only.** The
per-zone ceiling improved leave-one-out MAE by 0.063 with an interval of [−0.046, +0.167], which is not
significant once the second free parameter is paid for; the out-of-sample **ranking** gain is real.

**Expected output.** The current scalar ceilings, then the per-zone image. `YM_HIGHLAND` is **empty** in
`src/cpi.py`, so `ym_img_for` returns a constant image: the split is off under the typical-year
calibration, which uses one ceiling per country and season. The 2024 values are kept in a comment.
"""),

("RUN_WHC_EXPORTS", r"""
### T7 · Uniform 100 mm against SoilGrids water-holding capacity

**On record: null, and worse in the case that matters.** Under a **shared** ceiling, SoilGrids never
wins: Kenya long −0.024, Kenya short +0.010, wards 2021 −0.082, and Kitui 2022 **−0.318**. The one
positive result vanished once both arms shared a ceiling, because SoilGrids is a uniformly bigger
bucket and its dominant effect is a level shift that a per-arm ceiling absorbs by construction.

**The Kitui case is the substantive one.** The bigger bucket carries enough stored water through the dry
spell that the model does not register the 2022 drought. SoilGrids stays the default on physical
grounds, but it cannot be claimed to improve skill.

**Expected output.** The four score tables. Exports are off by default; scoring reads the CSVs.
"""),

("RUN_LGP_EXPORTS", r"""
### T8 · Fixed 120 days against the GDD thermal clock

**On record, and the largest open discrepancy in the pipeline.** Pixel-weighted over actual maize the
thermal season is **173 days** against the fixed 120, and only **8 of 44** Kenyan counties fall within
±15 days. Highlands run **+67.7 days** long with flowering **25.9 days later**; hot arid lands run
short. Ethiopia Meher is +22 days.

Because the stage weights put three times the weight on flowering, the water balance is being read at
the wrong point of the season over most of Kenya's maize. The recommendation on record is to replace the
fixed cycle, and **not** to adopt the current maturity targets uncritically: the CHIRTS work found the
spreadsheet targets worse than the ERA5 ones.
"""),

("RUN_DMP_EXPORTS", r"""
### T9 · The biomass route against the water-balance route

**On record: DMP out-ranks CPI in all five variants**, and the gap is widest where CPI ranks
**backwards**, Kitui 2022 at ρ −0.32 and Ethiopia Meher at −0.40.

**But the level is unusable as it stands.** DMP over-predicts by 1.6 to 23.5 times and implies a harvest
index of 0.019 in the Kitui wards, because 500 m pixels carry non-crop biomass. Notebook 05 therefore
tests DMP as an **anomaly** rather than as raw biomass.

**Ethiopia Meher is the actionable case**: DMP wins on every metric and implies a harvest index of 0.468,
inside the agronomic range.

**The source is a stand-in.** Copernicus DMP is not in the Earth Engine catalog, so MODIS MOD17A2H GPP
is used, converted through a carbon-use efficiency of 0.45 and a carbon fraction of 0.475. Report the
rankings, not the magnitudes.
"""),

("planting_validation_MAM_2024.csv", r"""
### T10 · Planting dekad against farmer records

**The strongest validation in the whole set**, because it compares against what farmers reported rather
than against another model or a calendar.

**Expected values.** **42 counties**, modal bias **−0.31 dekads**, MAE **1.02 dekads**, **93 %** within
two dekads. At ward level, **855 wards** across the same counties, bias −0.38, MAE 1.09, **96 %** within
two dekads.

**What it licenses.** Ward-level error is essentially the same as county-level error, which means the
residual is the genuine spread of planting within a season, not an aggregation artefact. Treat one dekad
as the noise floor: a one-dekad difference between two units is not a finding, a three-dekad difference
is.

**And what it does not.** This is Kenya long rains 2024 only. No other country or season has farmer
records behind it, and the planting estimate elsewhere carries only the calendar comparison, which is a
much weaker test.
"""),
]
