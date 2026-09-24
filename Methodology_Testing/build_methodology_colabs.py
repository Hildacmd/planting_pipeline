#!/usr/bin/env python3
"""Generate the Methodology_Testing Colab notebooks — one per test family run in this round.

Each notebook is self-contained: it states the QUESTION, runs the EXPORT stage, runs the
SCORING stage, and records the RESULT that was obtained, so a reader can both reproduce and
audit. Shares the setup convention of build_module_colabs.py (Drive-mounted pipeline + EE auth).

Run:  python Methodology_Testing/build_methodology_colabs.py
"""
import nbformat as nbf, os

HERE = os.path.dirname(os.path.abspath(__file__))
def md(s): return nbf.v4.new_markdown_cell(s.strip("\n"))
def co(s): return nbf.v4.new_code_cell(s.strip("\n"))

SETUP = lambda title, blurb: [
    md(f"# {title}\n\n{blurb}\n\n**How to run:** put the `planting_pipeline` folder on your Google "
       "Drive, run top-to-bottom, approve the Drive-mount and Earth-Engine prompts. Export cells "
       "start GEE tasks and return immediately; the scoring cells read the CSVs once the tasks "
       "finish (watch https://code.earthengine.google.com/tasks)."),
    md("## Setup"),
    co("!pip -q install earthengine-api geemap pandas geopandas scipy 2>/dev/null\nprint('installed.')"),
    co('import ee\nPROJECT="ee-manzikye"\ntry:\n    ee.Initialize(project=PROJECT)\nexcept Exception:\n'
       '    ee.Authenticate(); ee.Initialize(project=PROJECT)\nprint("EE ready:", ee.String("ok").getInfo())'),
    co('from google.colab import drive; drive.mount("/content/drive")\nimport sys, os\n'
       'PIPE_DIR="/content/drive/MyDrive/planting_pipeline"   # adjust if needed\n'
       'assert os.path.isdir(PIPE_DIR), f"Upload planting_pipeline to Drive; not at {PIPE_DIR}"\n'
       'sys.path.insert(0, PIPE_DIR); os.chdir(PIPE_DIR)\nprint("pipeline on path:", PIPE_DIR)'),
    md("### Scoring convention used throughout\n"
       "`n` is small (6–81 zones) in every test here, and a single 70/30 split at n≈45 has a "
       "**±0.10 t/ha standard deviation — larger than any effect measured**. So every test below "
       "uses **leave-one-out CV** (each free parameter refit on n−1) plus a **paired bootstrap** "
       "CI, and reports **Spearman** alongside MAE because rank skill is invariant to the yield "
       "ceiling Ym. Reporting a single split would have produced two false positives in this round."),
]

NB = {}

# ---------------------------------------------------------------- 01 WHC A/B
NB["01_whc_ab_soilgrids.ipynb"] = SETUP(
    "01 · WHC A/B — uniform bucket vs SoilGrids/Saxton",
    "**Question.** Does the per-pixel root-zone water-holding capacity derived from ISRIC "
    "SoilGrids 2.0 texture (Saxton–Rawls FC/WP, 250 m, `src/soil.py`) beat the uniform 100 mm "
    "fallback (`default_whc_mm`)? SoilGrids WHC was already the `run_cpi.py` default on physical "
    "grounds; this supplies — or withholds — the evidence."
) + [
    md("## 1. Export the arms\nIdentical pipeline in both arms; **only `whc_img` differs**. CPI is "
       "exported with `ym=1` so each arm can be given its own ceiling at scoring time.\n\n"
       "> **Gotcha that invalidated the first run:** GAUL-2015 level 1 for Kenya is the **8 old "
       "provinces**, not the 47 counties HarvestStat uses. The first export returned 8 rows and "
       "would have matched 1 county. Everything now exports at **level 2** (old districts) and "
       "rolls up with `src/kenya_gaul_counties.py` (71 districts → 47 counties), **pixel-count "
       "weighted** so a 1-pixel district cannot outvote a 9,917-pixel one."),
    co("!python whc_ab_test.py            # Kenya Long rains, county\n"
       "!python whc_ab_variants.py --variant short_county\n"
       "!python whc_ab_variants.py --variant short_ward     # 2021 + 2022 crop-cut wards\n"
       "!python whc_ab_variants.py --variant et_meher"),
    md("## 2. Score — per-arm Ym (the original protocol)"),
    co("!python whc_ab_score.py\n!python whc_ab_score_variants.py --variant short_ward\n"
       "!python whc_ab_score_variants.py --variant short_county\n"
       "!python whc_ab_score_variants.py --variant et_meher"),
    md("## 3. Score — Ym HELD FIXED across arms\n"
       "**This is the step that changes the answer.** SoilGrids WHC is uniformly a *bigger* bucket, "
       "so its dominant effect is a **level shift** in CPI — and refitting a separate Ym per arm "
       "absorbs exactly that by construction. Three shared-ceiling regimes: `prod` (the ceiling "
       "`src/cpi.py` actually ships), `fit_A` and `fit_B` (fitted on one arm, applied to both) — "
       "the latter two bracket the answer so a result cannot be an artifact of normalisation."),
    co("!python whc_ab_score_ymfixed.py"),
    md("## Result\n\n"
       "| variant | n | per-arm Ym Δ(A−B) | **fixed Ym Δ(A−B)** | verdict |\n|---|---|---|---|---|\n"
       "| KE Long, county | 44 | +0.010 [−0.060,+0.071] | −0.024 [−0.076,+0.023] | null |\n"
       "| KE Short, county | 46 | **+0.046 [+0.006,+0.085]** | +0.010 [−0.049,+0.066] | **win does NOT survive** |\n"
       "| KE Short, ward 2021 | 66 | −0.000 | −0.082 [−0.101,−0.064] | **uniform better** |\n"
       "| KE Short, ward 2022 Kitui | 15 | +0.006 | **−0.318 [−0.384,−0.240]** | **uniform much better** |\n"
       "| ET Meher, region | 6 | +0.002 | −0.006 | arms identical |\n\n"
       "**1. The one positive result was an artifact.** The short-rains county win vanished once "
       "both arms shared a ceiling — it was arm B being allowed its own better-fitting Ym.\n\n"
       "**2. SoilGrids improves spatial ranking nowhere**, in any variant, under any regime.\n\n"
       "**3. In the one true failure season it HIDES the drought.** Kitui SR-2022, all 15 wards "
       "under 0.15 t/ha: the uniform bucket flags **14/15** wards as severe (CPI<25); SoilGrids "
       "flags **5/15**. For early warning the uniform bucket's pessimism is a feature.\n\n"
       "**4. Ethiopia proves when the bucket cannot matter at all.** Flowering WRSI is 99.5–100 in "
       "every region under both arms — the Meher balance is fully satisfied, the store never draws "
       "down, so bucket size is arithmetically irrelevant. Don't re-run this test for Meher.\n\n"
       "**Recommendation.** Keep SoilGrids/Saxton as default on physical-realism grounds (per-pixel "
       "TAW is the defensible physics and costs nothing), but state in the report that it is **not "
       "skill-validated**, and do not cite the short-rains MAE as supporting evidence."),
]

# ---------------------------------------------------------------- 02 LGP / Ym recheck
NB["02_lgp_and_aez_ym_recheck.ipynb"] = SETUP(
    "02 · Re-check of the LGP and AEZ-Ym A/Bs",
    "**Question.** Both earlier A/Bs were decided on **one 70/30 split (test n=14)**. Do they "
    "survive proper cross-validation? Two *different* concerns: the LGP test refits Ym per arm "
    "(level blindness), while the AEZ-Ym test fits **two** free parameters against one "
    "(degrees of freedom). The original script was not kept, so this reconstructs it from source."
) + [
    md("## Reconstruction\nCounty-mean water-limited relyield from the CHIRPS MAM water balance at "
       "each duration, highland flag from SRTM ≥1800 m, HarvestStat multi-year county mean.\n\n"
       "**Fidelity check:** the reconstruction reproduces the published Pearson r (0.66 / 0.51) "
       "almost exactly — which is what makes the re-scoring trustworthy."),
    co("!python lgp_ym_ab_recheck.py"),
    md("## Result\n\n"
       "| arm | params | LOO MAE | Pearson | Spearman |\n|---|---|---|---|---|\n"
       "| A fixed 120 d, single Ym | 1 | 0.601 | +0.642 | +0.725 |\n"
       "| B1 zone-aware LGP | 1 | 0.684 | +0.497 | +0.525 |\n"
       "| B2 per-zone Ym (3.7/2.3) | 2 | **0.537** | **+0.780** | **+0.830** |\n\n"
       "**LGP verdict CONFIRMED — keep fixed 120 d.** B1 loses on MAE and collapses the ranking; "
       "the rank half of the verdict is Ym-invariant so the refit trap never applied. Across 500 "
       "seeds B1 beats A in only 10% — the published result was typical, not lucky.\n\n"
       "**AEZ-Ym: right decision, wrong evidence.** Δ MAE +0.063, CI [−0.046,+0.167] — **not "
       "significant** once the second parameter is paid for. But the out-of-sample *ranking* gain "
       "is real and substantial (Spearman 0.725 → 0.830), and that is not a DoF artifact. Keep "
       "`YM_HIGHLAND`, justify it by ranking rather than MAE.\n\n"
       "**`lgp_ab_test_MAM.md` overstates precision.** It reports 0.568 → 0.472; across 500 seeds "
       "the means are 0.604 → 0.544 and B2 wins 77% of splits, not all. Worth softening if that "
       "table feeds the report."),
]

# ---------------------------------------------------------------- 03 LGP vs GDD
NB["03_lgp_vs_gdd_phenology.ipynb"] = SETUP(
    "03 · Fixed LGP vs the GDD thermal clock",
    "**Question.** The pipeline gives maize a fixed calendar season from "
    "`config/crop_coefficients.yaml` (120 d main, 90 d short), identical everywhere. "
    "`src/gdd_clock.py` already derives a per-pixel thermal season from ERA5-Land GDD anchored on "
    "SOS, with maturity targets seeded per pixel from the AEZ class. How far apart are they, and "
    "does it matter?"
) + [
    md("## Export\nExports season length **and flowering timing** — a shifted flowering dekad moves "
       "the critical-window water balance even when total length agrees, and CPI puts the FAO-33 "
       "Ky=1.5 weight on flowering.\n\n"
       "> **Two compute traps hit here.** (a) The short-rains variant timed out: the production "
       "short-rains planting gap-fills with a **44-year CHIRPS climatology**, which on top of 27 "
       "dekads of ERA5-Land exceeds the EE budget — fixed with a light onset and `dk_hi = se+14`. "
       "(b) `gdd_maturity_from_aez` builds a very large client-side graph and stalled submission; "
       "short rains now use the constant **early-class 1300 °C·d**, which is the right target for "
       "short-duration maize anyway."),
    co("!python lgp_vs_gdd.py --variant ke_long\n!python lgp_vs_gdd.py --variant ke_short\n"
       "!python lgp_vs_gdd.py --variant et_meher"),
    co("!python lgp_vs_gdd_score.py"),
    md("## Result — Kenya Long rains 2024\n\n"
       "Fixed 120 d. GDD county mean 137 d, but **pixel-weighted over actual maize 173 d**. Only "
       "**8 of 44** counties within ±15 d.\n\n"
       "| | GDD LGP | vs fixed | flowering shift |\n|---|---|---|---|\n"
       "| highland ≥1800 m (n=14) | **187.7 d** | **+67.7 d** | **+25.9 d later** |\n"
       "| lowland <1800 m (n=30) | 113.7 d | −6.3 d | −12.7 d earlier |\n\n"
       "Overruns are the grain basket (Nyandarua +112, Bomet +100, Kericho +84, Uasin Gishu +79); "
       "shortfalls are hot ASAL (Turkana −55, Marsabit −50, Tana River −46).\n\n"
       "**Ethiopia Meher:** GDD 142 d (pixel-wtd 154), +22 d; 3/6 regions within ±15 d. "
       "SNNP +47, Oromia +41, Amhara +39; Gambela +0, Benshangul −2.\n\n"
       "### Why this is the most consequential finding of the round\n"
       "1. The fixed LGP errs in **opposite directions** highland vs lowland — no single national "
       "value can fix it.\n"
       "2. Highland **flowering lands 26 d later** than the Kc curve assumes, so the Ky=1.5 "
       "critical-window weight is currently applied to roughly the wrong three dekads there. That "
       "is plausibly a larger error than season length itself.\n"
       "3. **It explains the failed zone-aware LGP A/B** (notebook 02). That test gave the highland "
       "180 d — close to the GDD answer of 188 d — and still lost, because it kept the Mar–May MAM "
       "rainfall window: 180 d on MAM just accumulates deficit past the rains. The correct "
       "experiment is a highland **unimodal Mar–Aug window at ~188 d**, exactly what "
       "`lgp_ab_test_MAM.md` hypothesised but could not test."),
]

# ---------------------------------------------------------------- 04 DMP
NB["04_dmp_vs_cpi_yield.ipynb"] = SETUP(
    "04 · DMP biomass yield vs the CPI water-balance yield",
    "**Question.** How does a yield estimate built from **dry matter productivity** compare with "
    "the pipeline's CPI water-balance yield, against the same ground truth?"
) + [
    md("## Data note — read before running\n"
       "Copernicus DMP is **300 m or 1 km, not 250 m**, so it does not grid-align 1:1 with the "
       "250 m products (everything here is reduced zonally, which sidesteps that). It is **not in "
       "the GEE catalog** — it needs a NetCDF download from land.copernicus.eu / Terrascope, "
       "ingest as an EE asset, then set `CGLS_DMP_ASSET` in `src/dmp_yield.py`.\n\n"
       "Until then **MODIS MOD17A2H GPP stands in** (500 m / 8-day): GPP→NPP via CUE 0.45, "
       "C→dry matter ÷0.475. `--source modis|cgls` is a one-flag swap; everything downstream is "
       "identical. Treat MODIS magnitudes as provisional and rankings as more robust.\n\n"
       "**Raw DM (kg/ha) is exported**, so harvest index, above-ground fraction and grain moisture "
       "are applied at scoring time and can be retuned with no re-export."),
    md("### Conversion\n"
       "```\nseasonal DM (kg/ha) = Σ (DMP_dekad × days_in_dekad)      # DMP is kg DM/ha/DAY\n"
       "grain (kg/ha)       = DM × F_ABOVEGROUND × HARVEST_INDEX / (1 − moisture)\n```\n"
       "Maize defaults 0.80 / 0.45 / 0.135. Dekads are 8–11 days, not a flat 10, so a flat ×10 "
       "introduces a systematic few-percent bias — `dekad_to_t()` handles the real calendar, and "
       "time is indexed continuously so short-rains seasons maturing in the following year "
       "integrate without a day-of-year wrap."),
    co("!python dmp_run.py --variant ke_long\n!python dmp_run.py --variant ke_short\n"
       "!python dmp_run.py --variant ke_ward_2021\n!python dmp_run.py --variant ke_ward_2022\n"
       "!python dmp_run.py --variant et_meher"),
    co("!python dmp_score.py"),
    md("## Result\n\n"
       "| variant | n | DMP MAE / bias / ρ | CPI MAE / bias / ρ | implied HI | over-pred |\n"
       "|---|---|---|---|---|---|\n"
       "| KE Long 2024 | 43 | 1.09 / +1.04 / **+0.77** | 0.68 / +0.09 / +0.73 | 0.275 | 1.7× |\n"
       "| KE Short 2024 | 46 | 0.76 / +0.68 / **+0.64** | 0.52 / +0.06 / +0.59 | 0.285 | 1.6× |\n"
       "| KE ward 2021 | 66 | 1.45 / +1.45 / **+0.49** | 1.25 / +1.22 / +0.15 | 0.066 | 7.3× |\n"
       "| KE ward 2022 Kitui | 15 | 1.46 / +1.46 / **+0.41** | 0.54 / +0.54 / **−0.32** | 0.019 | 23.5× |\n"
       "| ET Meher 2024 | 7 | **0.53 / −0.36 / +0.64** | 1.58 / +1.58 / **−0.40** | 0.468 | 0.8× |\n\n"
       "**DMP out-ranks the CPI water balance in all five** — Spearman higher every time, and the "
       "gap is widest exactly where CPI ranks *backwards* (Kitui 2022 −0.32, ET Meher −0.40).\n\n"
       "**Ethiopia is immediately actionable:** DMP wins on every metric AND its implied harvest "
       "index (0.468) sits squarely in the agronomic 0.30–0.55 range — everything is internally "
       "consistent.\n\n"
       "**Kenya's implied HI is the diagnostic, not a knob.** 0.275 / 0.285 are below the "
       "agronomic range; at ward level 0.066 and 0.019 are physically impossible. No harvest index "
       "reconciles those — the error is **mixed pixels**: smallholder 500 m pixels carry bush, "
       "weeds and intercrop biomass that grows whether or not the maize does. Hence DMP "
       "over-predicts the Kitui 2022 total failure by **23.5×**.\n\n"
       "### How to register this — DMP measures the OUTCOME, not the CAUSE\n"
       "DMP ranks yield better, but it **cannot attribute** *why* biomass is short (water? heat? "
       "pest? nutrient? late planting?), it is a **lagging** indicator (the shortfall appears "
       "*after* the stress, too late for anticipatory action), and it **cannot see failure** in "
       "smallholder mixed pixels. So it does **not** replace `S_water` / `S_heat`:\n\n"
       "| role | use |\n|---|---|\n"
       "| causal attribution + lead time | WRSI / water balance (`S_water`), heat (`S_heat`) — keep |\n"
       "| outcome ranking, late-season estimate | DMP |\n"
       "| where DMP actually belongs in CPI | it is a better-calibrated **`S_veg`** — the existing "
       "greenness term — *not* a replacement for the stress terms |\n"
       "| divergence as a diagnostic | DMP high + water balance stressed → suspect mask/irrigation; "
       "DMP low + balance fine → suspect heat, pest or nutrient |\n\n"
       "The natural next test is therefore **swap or augment `S_veg` with DMP and re-score CPI** — "
       "not 'replace the water balance with DMP'."),
]

# ---------------------------------------------------------------- 05 S_veg swap
NB["05_sveg_swap_dmp.ipynb"] = SETUP(
    "05 \u00b7 S_veg swap \u2014 production NDVI/VCI vs a DMP anomaly",
    "**Question.** Notebook 04 showed DMP out-ranks the CPI yield everywhere \u2014 but DMP measures the "
    "OUTCOME, not the cause, so it cannot replace `S_water`/`S_heat`. The term CPI already devotes to "
    "observed greenness is `S_veg`. Does sourcing that term from DMP beat the production NDVI/VCI?"
) + [
    md("## Design\n"
       "`S_water` and `S_heat` are computed **once and shared**, so the arms differ in exactly one term:\n\n"
       "| arm | S_veg source |\n|---|---|\n"
       "| V | `cpi.s_veg(source='ndvi')` \u2014 production MOD13Q1 VCI |\n"
       "| D | `dmp_yield.s_veg_dmp(mode='vci')` \u2014 same Kogan VCI form, DMP source |\n\n"
       "Three choices that keep it honest:\n"
       "1. **The DMP term is an anomaly, not raw biomass.** Raw DMP over-predicted the Kitui wards 23.5x "
       "because mixed pixels carry non-crop biomass \u2014 but that contamination is largely *static* per "
       "pixel, so differencing against the pixel's own DMP climatology cancels it.\n"
       "2. **Same `VEG_W` = 0.4.** Only the source changes. This also caps the achievable effect: "
       "`S_veg` is deliberately down-weighted as a confirmation on water/heat.\n"
       "3. **Matched climatology (2015\u20132023) for both arms.** Production `s_veg` defaults to "
       "2003\u20132024, so arm V here is *not* byte-identical to the shipped product \u2014 but an unmatched "
       "VCI min/max range would confound source with sample length."),
    md("> **Two silent bugs this test surfaced \u2014 both produced plausible wrong numbers.**\n"
       "> 1. Mapped images dropped `system:time_start`, so the inner `filterDate` matched nothing and the "
       "seasonal sum returned a **zero-band image**.\n"
       "> 2. **MOD17A2H v061 in GEE covers only 2021\u20132026** \u2014 every year of the intended climatology "
       "was empty. Switched to **MOD17A2HGF** (gap-filled, 2000\u20132025); gap-filling is an advantage for a "
       "climatology, since missing composites would bias min/max."),
    co("!python sveg_swap_run.py --variant ke_long\n!python sveg_swap_run.py --variant ke_short\n"
       "!python sveg_swap_run.py --variant et_meher"),
    co("!python sveg_swap_score.py"),
    md("## Result\n\n"
       "| variant | n | V Spearman | D Spearman | \u0394 LOO-MAE | CI | D better | fixed-Ym winner |\n"
       "|---|---|---|---|---|---|---|---|\n"
       "| KE Long 2024 | 43 | +0.737 | +0.754 | +0.014 | [\u22120.024,+0.054] | 77% | **V** |\n"
       "| KE Short 2024 | 46 | +0.594 | +0.617 | +0.010 | [\u22120.008,+0.031] | 84% | **V** |\n"
       "| ET Meher 2024 | 5 | **+0.100** | **+0.700** | +0.075 | [\u22120.032,+0.185] | 92% | **D** |\n\n"
       "**No variant is statistically significant** \u2014 every CI spans zero. But the direction is "
       "consistent: DMP ranks better in 3/3 and wins 77/84/92% of resamples across three independent "
       "datasets. Suggestive, not conclusive.\n\n"
       "**The fixed-Ym column is not a skill statement.** DMP reads *less* stress than NDVI in Kenya "
       "(0.084 vs 0.120 long) so CPI rises and bias worsens; it reads *more* in Ethiopia (0.192 vs 0.135) "
       "so CPI falls and the known over-prediction improves. That is just whether the shift happens to "
       "point at the existing bias \u2014 Ym-dependent. **Spearman is the skill statement.**\n\n"
       "### Verdict\n"
       "**Do not swap for Kenya.** Both seasons show negligible rank gain and a worse-centred CPI under "
       "the shipped Ym.\n\n"
       "**Ethiopia is a strong lead that n=5 cannot settle.** Spearman 0.10 \u2192 0.70 is the largest skill "
       "jump seen in this whole round, and under the production Ym MAE falls 1.586 \u2192 1.268. But at n=5 "
       "one region changing position moves the rank correlation that far. **Next step: re-run Ethiopia at "
       "admin-2 (zones) to get n into the dozens** \u2014 that is the only way to settle it."),
]

os.makedirs(HERE, exist_ok=True)
for name, cells in NB.items():
    nb = nbf.v4.new_notebook(cells=cells)
    nb.metadata = {"kernelspec": {"display_name": "Python 3", "name": "python3"},
                   "colab": {"provenance": [], "toc_visible": True}}
    with open(os.path.join(HERE, name), "w") as f:
        nbf.write(nb, f)
    print("wrote", name)
