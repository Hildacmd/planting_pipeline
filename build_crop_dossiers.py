#!/usr/bin/env python3
"""Build one folder per crop: its products, and a methodology dossier for them.

    crop_products/<crop>/METHODOLOGY.md   the dossier - method, status, gaps, recommendations
    crop_products/<crop>/PRODUCTS.csv     machine-readable status of every product
    crop_products/<crop>/outputs/         that crop's admin-level reduce CSVs

Everything in the status tables is COMPUTED at build time - from the parameter modules, the
calendars, the reduce CSVs on disk, the Ym registries and irrigation_exposure.py. The prose that
cannot be computed (why a parameter was chosen, what a gap means) lives in NARRATIVE below, so the
numbers can never drift away from the shipped product while the reasoning stays put.

    python build_crop_dossiers.py
"""
import csv, glob, os, shutil, sys
import pandas as pd

H = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, H); sys.path.insert(0, f"{H}/crop_pipeline"); sys.path.insert(0, f"{H}/sorghum_pipeline")
sys.path.insert(0, f"{H}/crop_pipeline/irrigation")
OUT = f"{H}/crop_products"
CROPS = ["maize", "sorghum", "wheat", "teff", "millet"]
TIER2 = ["spi3_mean", "mean_deficit_mm", "lvpd_dekad", "fcci"]
TIER2_LABEL = {"spi3_mean": "SPI-3", "mean_deficit_mm": "deficit mm", "lvpd_dekad": "LVPD",
               "fcci": "FCCI"}

import irrigation_exposure as IRR
from products import inventory


# --------------------------------------------------------------------------- computed facts
def params_for(crop):
    """(Kc dict, Ky dict, Tcap, Ym defaults, Ym calibration map) for a crop."""
    if crop == "maize":
        from src import utils, cpi as CPI
        kc, _ = utils.load_crop_coeffs()
        return (kc["maize"], CPI.KY, CPI.HEAT_TCAP, (CPI.YM_MAIN_DEFAULT, CPI.YM_SHORT_DEFAULT),
                CPI.YM_CAL)
    from params import get
    p = get(crop)
    return p.KC, p.KY, p.HEAT_TCAP, (p.YM_DEFAULT, p.YM_SHORT_DEFAULT), p.YM_CAL


def calendar_rows(crop):
    """Calendar rows actually used for this crop, keyed (country, season)."""
    files = {"maize": "config/season_calendar.csv",
             "sorghum": "sorghum_pipeline/config/season_calendar_sorghum.csv"}
    f = files.get(crop, "crop_pipeline/config/season_calendar_wtm.csv")
    out = {}
    for r in csv.DictReader(open(f"{H}/{f}")):
        if str(r.get("crop", "")).lower() != crop:
            continue
        out[(r["country"].replace(" ", "_"), r["season"])] = r
    return out


def tier2_state(csv_path):
    """Which tier-2 metrics are populated in a product's L1 CSV."""
    try:
        d = pd.read_csv(csv_path)
    except Exception:
        return {}
    return {c: (c in d.columns and int(d[c].notna().sum()) or 0) for c in TIER2}, len(
        pd.read_csv(csv_path))


def status_table(crop):
    rows = []
    _, _, _, (ym_def, ym_short), ym_cal = params_for(crop)
    cal = calendar_rows(crop)
    for p in inventory():
        if p["crop"] != crop:
            continue
        country, season = p["country"], p["season"]
        # the calendar spells seasons with spaces; the file stem does not
        crow = cal.get((country, season)) or next(
            (v for (c, s), v in cal.items()
             if c == country and s.replace(" ", "") == season), {})
        key = (country, season if (country, season) in ym_cal else
               (crow.get("season") or season))
        ymk = next((k for k in ym_cal if k[0] == country
                    and k[1].replace(" ", "") == season.replace(" ", "")), None)
        t2, n1 = tier2_state(p["csv"])
        rows.append(dict(
            country=country.replace("_", " "), season=crow.get("season") or season,
            stem=p["stem"], admin1_units=n1,
            calendar_source=crow.get("crop_calendar_source", "—"),
            planting_window=crow.get("indicative_planting_window", "—"),
            ym_tha=(ym_cal[ymk] if ymk else None),
            ym_status=("fitted" if ymk else "fallback"),
            irrigation=IRR.grade(country, crop),
            **{f"t2_{k}": (t2.get(k) or 0) for k in TIER2}))
    return pd.DataFrame(rows).sort_values(["country", "season"])


# --------------------------------------------------------------------------- narrative
NARRATIVE = {
"maize": dict(
 headline="The reference crop. Every method in the pipeline was built and validated on maize first, then carried to the others.",
 why="""Maize is the only crop with independent ground truth at scale (4.8 M Kenyan farmer planting
records) and the only one whose yield calibration has both level *and* pattern skill in more than one
country. It is therefore the benchmark: a method that cannot be shown to work on maize is not carried
to a crop where it could not be checked.""",
 params="""FAO-33 Ky is **0.40 / 1.50 / 0.50** (vegetative / flowering / grain-fill). The flowering
value of 1.5 is the highest of any crop here and is the single most consequential parameter in the
pipeline: a flowering deficit costs maize roughly three times what it costs sorghum. Kc runs
0.30 → 1.20 → 0.35 over 12 dekads with a 1.0 m rooting depth. Heat is capped at 33 °C, accumulated
only during flowering, because maize sterilises at silking.""",
 achieved="""- **16 products** across 8 countries and 3 season types, all on the 250 m grid.
- **Planting dekad validated against 4.8 M farmer records**: Kenya MAM 2024 is **92.9 % within
  ±2 dekads** and **100 % within the GIEWS calendar window**; Ethiopia Meher 100 % in window.
- **Ym calibrated for 7 products** against HarvestStat with a 70/30 × 200 held-out test. Kenya Long
  rains national bias fell from +2.03 to **+0.04 t/ha**, held-out MAE from 2.3 to **0.61**.
- **Ethiopia Meher calendar A/B settled** — the operative window beats both GEOGLAM CM4EW
  (Δρ +0.355 [+0.163, +0.564]) and the Inception Report window (Δρ +0.463 [+0.229, +0.710]). The
  first A/B in the project whose confidence intervals exclude zero.
- **Season-A green-up failure diagnosed and fixed**: Rwanda and Burundi Season A returned ~64
  planting pixels against 3,365 maize pixels because cue-fusion cannot find green-up under persistent
  highland cloud. Routed to rainfall-anchored onset; full coverage restored.
- **South Sudan maize dropped, on evidence.** The crop-type mask maps 0.013 Mha of maize there
  against 0.295 Mha of sorghum; the product retained 135 maize pixels country-wide against
  WorldCereal's 9,398, and Eastern Equatoria - 90 % of the country's maize by WorldCereal - had none
  at all. Only 2 of 9 states kept enough pixels for a CPI. South Sudan is a sorghum country and its
  two sorghum products are sound. Recorded in `crop_coverage.DROPPED` with the evidence, which the
  runners, the apps and this inventory all honour, so it cannot return by a side door.
- **Ym re-fitted on the crop-type-mask footprint, and the result argues against switching.**
  `calibrate_ym_ctm.py` fits both footprints at admin-2 with the same units, targets, 70/30 x 200
  held-out test and seed, so the difference is the footprint alone. **Ceilings move: median -6.7 %,
  range -13.7 % (Somalia Gu) to +0.5 % (Burundi Season A)** - so a WorldCereal ceiling must never be
  carried onto a crop-type-mask product. But the new footprint does **not** fit the yield statistics
  better: held-out MAE improves in only **2 of 7** products (median change +0.01 t/ha, a wash), and
  the CPI-yield correlation r **falls in 5 of 7** - Kenya Long rains 0.60 to 0.48, Ethiopia Meher
  0.58 to 0.45. Only Somalia Gu improves materially (0.34 to 0.53). Ceilings are stored separately
  as `YM_CAL_CTM` in `src/cpi.py`, never mixed with the WorldCereal `YM_CAL`.
- **Cached-WHC footprint bug found and fixed** — the materialised asset stopped at 32.3 °E, which had
  emptied Rwanda and Burundi entirely and silently clipped western Uganda, Tanzania and South Sudan.""",
 gaps="""- **Yield is level-only in the ASAL.** Kenya Short rains calibrates to the right national average but
  **r ≈ 0** against county crop-cutting — it sets the level and does not rank the counties. Reported
  as such; do not use it for county targeting.
- **Only 7 of the 15 products can be Ym-calibrated at all**, on either footprint: the rest have no
  HarvestStat maize yields to fit against. Tanzania (3 products) and the second seasons of Uganda,
  Rwanda and Burundi, plus Somalia Deyr and Ethiopia Belg, run on fallback ceilings under both masks.
- **8 of 15 products still use a fallback Ym.** Their CPI is fully valid; the absolute t/ha is
  provisional. Tanzania and South Sudan have no HarvestStat maize yields at all.
- **Total production is an upper bound.** The mask does not distinguish season, so short-rains totals
  assume the whole mask plants twice. Yield (t/ha) is the reliable figure.
- **Short-rains season attribution.** ~39 % of mapped western Kenyan short-rains area may be the
  standing long-rains crop (KENYA_SEASON_REGIMES.md §7). The regime-aware onset is **provisional**.
- **Ethiopia maize is locally irrigation-biased** via Afar (96.8 % irrigated, 1,707 ha).
- **The shipped maize products still run on WorldCereal, not the ICPAC crop-type mask.** All 16 have
  now been re-run on the crop-type mask as `cpiCTMX_`/`newcCTM_` and compared, but the apps and Atlas
  still serve the WorldCereal versions pending a decision (see Recommendations).
- **Two products re-rank under the crop-type mask**: Uganda 1st rains (Spearman rho 0.758 between the
  two admin rankings) and Burundi Season A (0.734). A level shift can be absorbed by re-fitting Ym;
  a re-ranking cannot, and which units look worst is what an early-warning product is for.
- *(Resolved)* South Sudan maize has been **dropped**, see Achievements.""",
 recs="""1. ~~**Re-run maize on the ICPAC crop-type mask and A/B it.**~~ **Done, 26 September 2026** - all 16
   products re-run and compared (`maize_ctm/compare_masks.py`, `mask_comparison.csv`). Over the 14
   comparable products the level barely moves (mean CPI +1.22, median per-unit change 2.0) and the
   ranking mostly holds (median rho 0.905), so the change is largely absorbable by re-fitting Ym.
   **The switch is not automatic, for three reasons:** Uganda 1st rains and Burundi Season A re-rank
   (rho 0.758 and 0.734); South Sudan collapses to 2 usable states; and the footprint moves in both
   directions - WorldCereal claims 1.9x more maize area in Uganda and 1.6x in Burundi, while the
   crop-type mask claims 1.3x more in Rwanda, 1.4x more in Kenya and 5x more in Somalia. **Decide per
   product, not wholesale**, and re-fit Ym on the new footprint before promoting any of them.
2. ~~**Drop or re-scope South Sudan maize.**~~ **Dropped, 26 September 2026** - see Achievements.
3. **Resolve short-rains season attribution** before the regime-aware onset is promoted out of
   provisional — the 39 % figure is large enough to change county rankings.
4. **Fit Ym for Tanzania and South Sudan** from any sub-national source other than HarvestStat.
5. **Report ASAL yield as a level, not a ranking**, in the apps as well as the docs."""),

"sorghum": dict(
 headline="The largest product set, and the first crop built end-to-end on the ICPAC crop-type mask.",
 why="""Sorghum is not maize with different numbers. FAO-33 gives it a flowering Ky of **0.55** against
maize's 1.50, so maize parameters would declare sorghum failed in seasons it comfortably survives.
It also heads with a green canopy, so Kc_end is 0.55 rather than 0.35, and it roots to 1.5 m rather
than 1.0 m — which is why sorghum needed its own WHC asset at 150 cm.""",
 params="""Ky **0.20 / 0.55 / 0.45**. Kc 0.30 → 1.05 → **0.55** over 13 dekads, rooting depth **1.5 m**,
heat cap **36 °C**. Cycles run 9–18 dekads per product rather than a fixed 12. Calendars are the
**Inception Report Table 2.0** (pp. 16–17) as instructed, with GEOGLAM CM4EW retained in parallel
`cm4ew_*` columns for partner validation.""",
 achieved="""- **18 products** across 10 countries — the widest coverage of any crop here.
- **First crop built entirely on the ICPAC crop-type mask.** `sorghum_params.sorghum_mask()` raises
  rather than falling back, because `run.crop_mask_image` silently falls through to the WorldCereal
  *temporary crops* extent for any non-maize crop — a default run would have computed over all
  cropland and labelled it sorghum.
- **Ym fitted for 12 of 18 products** against HarvestStat, each with its held-out MAE and r recorded
  inline in `sorghum_params.py`.
- **150 cm WHC asset built** so the 1.5 m rooting depth is served from cache rather than rebuilt live
  from SoilGrids on every run.
- **Calendar disagreement documented rather than silently resolved**: CM4EW ships a sorghum-specific
  calendar that differs from the report for 6 of the 9 products it covers, by up to 3 dekads.
- **Tier-1/2/3 alignment established** — the crop-type mask *is* the Inception Report's Tier 1, built
  stronger than the report assumed; Tier 2 (label acquisition) has produced nothing, so Tier 3 is
  correctly not attempted.""",
 gaps="""- **Ky for sorghum is FAO-33 generic, not cultivar-specific.** Sorghum's drought strategy varies more
  between landraces than maize's does between hybrids.
- **6 of 18 products have no fitted Ym.** Tanzania and Eritrea can never be calibrated from
  HarvestStat — it holds no sorghum yields for either.
- **Sudan Kharif's fitted ceiling carries r = −0.33** — a negative correlation shipped as a
  calibration. §Irrigation below is the likely cause.
- **Irrigation: Somalia (both seasons) and Sudan Kharif are materially biased.** Sudan sorghum has
  288,569 ha under irrigation — more than any other product in the pipeline.
- **No independent validation of the calendar itself** beyond the CM4EW comparison; there is no
  sorghum equivalent of the 4.8 M maize planting records.""",
 recs="""1. **Re-fit Sudan Kharif Ym on rainfed area only**, once the mask is split by technology. The
   r = −0.33 is the test: if the split works, it should turn positive.
2. **Run the calendar A/B (report vs CM4EW) to a decision** for the 6 products where they disagree,
   the way the Ethiopia maize Meher A/B was run.
3. **Seek sub-national sorghum yields for Tanzania and Eritrea** outside HarvestStat.
4. **Report CPI rather than yield** for the 6 uncalibrated products — already flagged on the asset
   via `ym_calibrated`, and in the app note."""),

"wheat": dict(
 headline="Four products, one of which is the pipeline's clearest demonstration that a rainfed water balance cannot describe an irrigated crop.",
 why="""Wheat is the coolest-season crop in the set and the only one grown at scale under full
irrigation in the region. Its flowering Ky of 0.65 sits between sorghum's 0.55 and maize's 1.50, and
its heat cap of 31 °C is the second lowest here — wheat aborts grain at temperatures maize tolerates.""",
 params="""Ky **0.20 / 0.65 / 0.55**. Kc 0.40 → **1.15** → 0.35 over 12 dekads, rooting depth 1.0 m,
heat cap **31 °C**, emergence offset 1 dekad. Kc_ini of 0.40 is higher than the other crops' 0.30
because wheat is drilled dense and covers ground fast.""",
 achieved="""- **4 products** — Ethiopia Meher, Kenya Long rains, Tanzania Msimu, Sudan Shitwi.
- **Ym fitted for Ethiopia Meher (2.69 t/ha) and Kenya Long rains (3.11 t/ha)** against HarvestStat.
- **Sudan Shitwi diagnosed end-to-end and handled honestly.** It is scheme-irrigated winter wheat on
  the Nile and the Gezira, sown in November in the dry season. The first run produced an asset with
  10,478 wheat-mask pixels and **zero valid ones**, because the CHIRPS 25/20 mm onset rule cannot fire
  when Sudan gets essentially no November rain. Fixed with a scheme planting date; the run then
  completed and returned WRSI 0, S_water 100 % and CPI 0 across all 18 localities including the
  Gezira — arithmetically correct and agronomically meaningless. **The product is excluded from the
  apps and the Atlas, and the asset kept, because the deficit is the irrigation requirement.**
- **The exclusion is now grade-driven**, so a future majority-irrigated product is caught
  automatically rather than by someone remembering.""",
 gaps="""- **Sudan Shitwi cannot be made valid under a rainfed balance.** 98.4 % of Sudan's wheat is irrigated;
  no parameter change fixes this. It needs either an irrigation supply term or an irrigated/rainfed
  mask split.
- **Sudan wheat Ym can never be fitted** while CPI is 0 everywhere — there is nothing to regress.
- **Tanzania Msimu wheat has no fitted Ym** and runs on the 4.0 t/ha fallback.
- **Ethiopia's irrigated wheat expansion post-dates SPAM 2020.** Ethiopia wheat is graded *negligible*
  at 0.4 % irrigated; that is an as-of-2020 prior and is likely an understatement.
- **Only 2 of 4 products have any yield calibration**, and both are level-only (r = 0.15 and 0.07).""",
 recs="""1. **Split the Sudan wheat mask by technology and run the two separately** — the rainfed product
   becomes valid, the irrigated one reports `deficit_mm` as an irrigation requirement with no
   condition claim. This is the highest-value single fix in the pipeline.
2. **Re-grade Ethiopia wheat against a post-2020 irrigated-extent source** before reporting it as
   rainfed without caveat.
3. **Fit Tanzania Msimu Ym**, or report CPI only.
4. **Do not pool the four wheat products in one table** — one of them is not measuring crop condition."""),

"teff": dict(
 headline="A single product, the shallowest rooting depth in the set, and the only crop with no FAO-33 entry of its own.",
 why="""Teff is Ethiopia's staple and has no FAO-33 yield-response factor, no SPAM crop class and no
FAO-56 Kc curve. Every parameter below is a **first-pass analogue**, chosen from the closest
documented small-grain cereal and marked as such. That is not a defect to be hidden — it is the
honest state of the science for this crop, and it sets how the output may be used.""",
 params="""Ky **0.20 / 0.55\\* / 0.45\\***, Kc 0.30 → 1.10 → 0.40 over **9 dekads** — the shortest cycle
here — rooting depth **0.6 m**, the shallowest, heat cap **30 °C\\***, emergence offset 1 dekad.
Asterisked values are first-pass analogues, not measured teff parameters. The 0.6 m rooting depth is
why the 60 cm WHC asset was built.""",
 achieved="""- **1 product**: Ethiopia Meher, 6 regions and 37 zones.
- **Ym fitted at 1.77 t/ha** against HarvestStat (n = 60, 2012–2021, held-out MAE 0.31 vs 0.35,
  r = 0.33 — level with weak pattern). Modest, but it is a real fit on real statistics.
- **60 cm WHC asset built and registered**, so teff's shallow rooting depth is served from a cached
  raster integrated to the depth actually asked for, rather than silently inheriting the 100 cm asset.
  WHC is not linear in depth, so this is a correction and not an optimisation: at a highland site the
  60 cm asset gives 79 mm against the 100 cm asset's 128 mm.
- **Tier-2 water deficit computed** (6/6 regions, 37/37 zones).
- **Ground-truthing data assessed and one source rejected.** `ethiopia_crop_ground_truth_points.csv`
  is **100 % simulated** and must never be used for accuracy assessment; EthCT2020 (2,793 real field
  polygons) is the usable source.""",
 gaps="""- **No FAO-33 Ky for teff.** The flowering Ky of 0.55 is borrowed. A wrong Ky biases CPI in a way no
  amount of calibration detects, because Ym absorbs the level and leaves the pattern wrong.
- **No SPAM teff class.** Area, and therefore irrigation exposure, is carried on *other cereals*.
- **Heat cap 30 °C is an analogue.** Teff is grown at altitude where 30 °C is rare, so this is
  probably harmless — but it is untested.
- **One product, one country, one season.** There is no second case to check the parameters against.
- **Tier-2 is only 1 of 4 metrics** — SPI-3, LVPD and FCCI are not yet run.""",
 recs="""1. **Commission or locate a teff Ky.** Ethiopian Institute of Agricultural Research trial data would
   settle the flowering value, which is the parameter that matters. Until then, report CPI as a
   relative index and say the parameters are analogues.
2. **Validate against EthCT2020** (2,793 real polygons) — the data is in hand and unused for teff.
3. **Run the remaining three tier-2 metrics** (all inputs verified available).
4. **Sensitivity-test Ky_flo across 0.4–0.8** and report how far the zone ranking moves. If it is
   stable, the borrowed parameter is defensible; if not, that is the number to go and measure."""),

"millet": dict(
 headline="Two products in the driest cropping systems in the region, and the crop where the irrigation bias was actually caught.",
 why="""Pearl millet is the most drought-tolerant cereal here and is grown where nothing else will
ripen. Its parameters reflect that: the lowest Ky values in the set (a deficit costs it least), the
highest heat cap at 38 °C, and a 1.5 m rooting depth to reach water the others cannot.""",
 params="""Ky **0.15 / 0.45\\* / 0.35\\*** — the lowest here. Kc 0.30 → 1.00 → 0.30 over 11 dekads,
rooting depth **1.5 m**, heat cap **38 °C**, emergence offset **2 dekads\\*** (millet emerges slowly
in hot dry seedbeds). Asterisked values are first-pass; FAO-33 does not tabulate pearl millet
separately.""",
 achieved="""- **2 products**: Sudan Kharif (15 states, 43 localities) and Eritrea Kremti (4 regions, 37 sub-regions).
- **Ym fitted for Sudan Kharif at 0.63 t/ha** (n = 14, 2015–2023, held-out MAE 0.14 vs 0.81, r = 0.24).
- **This is the crop that exposed the irrigation gap quantitatively.** Sudan millet Kharif is the one
  product where the rainfed balance is *measurably* inverted: across 15 states, CPI ranks negatively
  against the SPAM irrigated share, **Spearman ρ = −0.678, p = 0.005**. Al Jazirah (71.9 % irrigated)
  and Khartoum (95.4 %) score below fully-rainfed Darfur and Kurdufan.
- **The honest reading was recorded with it**: only two units carry that signal, and Sudan's irrigated
  millet is 12,081 ha of 2.75 M ha. The national figure is sound; two states are wrong. Graded
  *materially biased*, not *invalid*.""",
 gaps="""- **Ky and emergence offset are first-pass.** FAO-33 has no pearl millet row; the values are analogues
  from sorghum adjusted for millet's greater drought tolerance.
- **Eritrea Kremti has no fitted Ym** and runs on the 2.0 t/ha fallback — no HarvestStat millet series.
- **Sudan millet is materially irrigation-biased** in Al Jazirah and Kassala (see above).
- **Sudan's Ym was fitted over states that include the two irrigated ones**, so the ceiling is
  contaminated in the same way Sudan sorghum's is, though it still came out positive (r = +0.24).
- **Tier-2 has not been run at all** for either product.
- **Two products, both in data-poor countries**, with no independent planting-date validation.""",
 recs="""1. **Re-fit Sudan Kharif Ym excluding Al Jazirah and Kassala**, or on the rainfed mask split. This is
   cheap — the states are identified and the fit is a one-liner — and directly removes a known
   contamination.
2. **Run all four tier-2 metrics** for both products (inputs verified available).
3. **Report Sudan millet at admin-1 with the two irrigated states named**, never as a single national
   condition figure ranked against other countries.
4. **Sensitivity-test Ky_flo** as for teff — with only 2 products and no validation, parameter
   robustness is the only assurance available."""),
}

COMMON_METHOD = """## 4. Method — the chain that produces a product

Identical in structure for every crop; only the parameters and the mask band change.

1. **Crop mask.** The ICPAC crop-type mask at 100 m gives a per-pixel percentage of this crop
   (`ctm_mask.crop_mask`). It is built from a 4-lineage, 16-source-year cropland vote, SPAM area
   shares, fuzzy suitability and dasymetric allocation. It **raises rather than falling back**: a
   missing band is an error, not a silent substitution of all cropland.
2. **Season calendar.** Fixes the sowing-detection window and the indicative planting window per
   (country, season).
3. **Onset.** Green-up cue fusion (Sentinel-2 NDRE + MODIS FPAR + Sentinel-1 RVI) where cloud allows;
   the FEWS CHIRPS 25/20 mm rainfall rule with a 5+7 dekad false-start gate for short and second
   seasons and cloudy highlands; a fixed scheme date for irrigated products.
4. **Water balance.** FAO-56 dekadal single-layer bucket (`src/wrsi_waterbalance.py`):
   `WR = Kc·ET0`, `Wb = SW + P`, `AET = min(Wb, WR)`, `SW = clamp(Wb − AET, 0, WHC)`, and
   `WRSI = 100·ΣAET/ΣWR`. ET0 is Hargreaves from ERA5-Land; P is CHIRPS; WHC is Saxton–Rawls over
   SoilGrids texture, integrated to **this crop's rooting depth**.
5. **Stresses.** `S_water` from the FAO-33 stage-weighted Ky; `S_heat` from ERA5-Land Tmax above the
   crop's cap, accumulated only during flowering; `S_veg` from VCI/zFPAR as a down-weighted
   confirmation.
6. **CPI and yield.** `CPI = 100(1−Sw)(1−Sh)(1−Sv)`, then `Ya = CPI/100 × Ym`.

**The balance is rainfed.** `Wb = SW + P` credits soil water and rainfall and nothing else, with a
dry start. On an irrigated crop the deficit is the *irrigation requirement*, not crop stress — see
the irrigation section below and `crop_pipeline/docs/IRRIGATED_WATER_BALANCE.md`.
"""


def write_crop(crop):
    d = f"{OUT}/{crop}"
    os.makedirs(f"{d}/outputs", exist_ok=True)
    kc, ky, tcap, (ym_def, ym_short), ym_cal = params_for(crop)
    st = status_table(crop)
    st.to_csv(f"{d}/PRODUCTS.csv", index=False)

    # copy this crop's reduce CSVs
    n_copied = 0
    for p in inventory():
        if p["crop"] != crop:
            continue
        for f in glob.glob(f"{H}/{p['stem']}_L?_*.csv"):
            shutil.copy2(f, f"{d}/outputs/{os.path.basename(f)}")
            n_copied += 1

    N = NARRATIVE[crop]
    n_fit = int((st.ym_status == "fitted").sum())
    n_irr = int((st.irrigation != "negligible").sum())
    t2done = {k: int((st[f"t2_{k}"] > 0).sum()) for k in TIER2}

    # ---- products table
    hdr = ("| country | season | planting window | calendar | Ym t/ha | irrigation | "
           + " | ".join(TIER2_LABEL[k] for k in TIER2) + " |")
    sep = "|" + "---|" * (6 + len(TIER2))
    lines = [hdr, sep]
    for r in st.itertuples():
        ym = f"**{r.ym_tha:.2f}**" if r.ym_status == "fitted" else f"{ym_def:.1f} *(fallback)*"
        ir = "—" if r.irrigation == "negligible" else f"**{r.irrigation}**"
        t2 = " | ".join("✓" if getattr(r, f"t2_{k}") > 0 else "·" for k in TIER2)
        cal = str(r.calendar_source).replace("InceptionReport_Table2.0", "Report T2.0")[:22]
        lines.append(f"| {r.country} | {r.season} | {r.planting_window} | {cal} | {ym} | {ir} | {t2} |")
    ptable = "\n".join(lines)

    stages = (f"{kc['L_ini']}/{kc['L_dev']}/{kc['L_mid']}/{kc['L_late']}")
    doc = f"""# {crop.capitalize()} — product dossier

**{N['headline']}**

{len(st)} product{'s' if len(st) != 1 else ''} · {n_fit} with a fitted Ym · {n_irr} carrying irrigation
exposure · tier-2 complete for {t2done['mean_deficit_mm']}/{len(st)} (deficit), {t2done['spi3_mean']}/{len(st)} (SPI-3),
{t2done['lvpd_dekad']}/{len(st)} (LVPD), {t2done['fcci']}/{len(st)} (FCCI).

Generated by `build_crop_dossiers.py` — every table is computed from the shipped products, the
parameter modules and `irrigation_exposure.py`. Do not hand-edit; edit the generator.

---

## 1. Why this crop is not another crop with different numbers

{N['why']}

## 2. Products

{ptable}

Tier-2 columns: ✓ = computed, · = not yet run. `PRODUCTS.csv` in this folder carries the same table
machine-readably, with unit counts. `outputs/` holds this crop's {n_copied} admin-level reduce CSVs.

## 3. Parameters

{N['params']}

| | value |
|---|---|
| FAO-33 Ky (veg / flo / grf) | {ky['veg']} / **{ky['flo']}** / {ky['grf']} |
| FAO-56 Kc (ini → mid → end) | {kc['Kc_ini']} → **{kc['Kc_mid']}** → {kc['Kc_end']} |
| cycle length (dekads) | {kc['LGP_dekads']} (stages {stages}) |
| rooting depth | **{kc['root_depth_m']} m** → WHC asset at {int(kc['root_depth_m']*100)} cm |
| flowering heat cap | **{tcap:.0f} °C** |
| Ym fallback (main / short season) | {ym_def} / {ym_short} t/ha |

{COMMON_METHOD}

## 5. Irrigation exposure

The water balance cannot see irrigation. Grades for this crop, from SPAM 2020's `_I`/`_A`
technology split:

{irrigation_block(crop, st)}

Full treatment, including the eight gaps and the remediation order:
`crop_pipeline/docs/IRRIGATED_WATER_BALANCE.md`.

## 6. What has been achieved in the current dispensation

{N['achieved']}

## 7. Gaps

{N['gaps']}

## 8. Recommendations

{N['recs']}

---

*Regenerate: `python build_crop_dossiers.py`. Related: `CPI_METHODOLOGY.md` ·
`ALL_COUNTRIES_2024.md` · `crop_pipeline/docs/IRRIGATED_WATER_BALANCE.md` ·
`crop_products/README.md`.*
"""
    open(f"{d}/METHODOLOGY.md", "w").write(doc)
    return len(st), n_copied, n_fit, n_irr, t2done


def irrigation_block(crop, st):
    rows = []
    for country in sorted(st.country.unique()):
        r = IRR.record(country, crop)
        if r is None:
            rows.append(f"| {country} | — | no SPAM class for this crop |"); continue
        if r["grade"] == "negligible":
            rows.append(f"| {country} | negligible | {r['national_irr_pct']:g} % irrigated — "
                        f"report as rainfed, no caveat |")
        else:
            rows.append(f"| {country} | **{r['grade']}** | {r['national_irr_pct']:g} % nationally, "
                        f"{r['irr_area_ha']:,} ha. Affected: {r['compromised_units']} |")
    return "| country | grade | detail |\n|---|---|---|\n" + "\n".join(rows)


def to_word(md_path, title):
    """Render a dossier to .docx and .html beside it. Partners read Word, not Markdown."""
    import subprocess
    base = md_path[:-3]
    ok = []
    for ext, args in ((".docx", []), (".html", ["-s", "--toc"])):
        try:
            subprocess.run(["pandoc", md_path, "--metadata", f"title={title}", *args,
                            "-o", base + ext], check=True, capture_output=True)
            ok.append(ext)
        except Exception as e:
            print(f"    [warn] {ext} not written: {str(e)[:80]}")
    return ok


def main():
    os.makedirs(OUT, exist_ok=True)
    summary = []
    for c in CROPS:
        n, files, fit, irr, t2 = write_crop(c)
        ext = to_word(f"{OUT}/{c}/METHODOLOGY.md", f"{c.capitalize()} — product dossier")
        summary.append((c, n, fit, irr, t2, files))
        print(f"  {c:8s} {n:2d} products · {fit} fitted Ym · {irr} irrigation-flagged · "
              f"{files} output CSVs · {'+'.join(e.lstrip('.') for e in ext) or 'md only'}")

    idx = ["# Crop product dossiers", "",
           "One folder per crop. Each holds the products, a machine-readable status table, and a",
           "methodology dossier covering the method, what has been achieved, the gaps and the",
           "recommendations. All tables are generated by `build_crop_dossiers.py` from the shipped",
           "products — they cannot drift from what is actually in Earth Engine and on disk.", "",
           "| crop | products | fitted Ym | irrigation-flagged | tier-2 (def/SPI/LVPD/FCCI) | dossier |",
           "|---|---|---|---|---|---|"]
    for c, n, fit, irr, t2, _ in summary:
        idx.append(f"| **{c}** | {n} | {fit} | {irr} | "
                   f"{t2['mean_deficit_mm']}/{t2['spi3_mean']}/{t2['lvpd_dekad']}/{t2['fcci']} | "
                   f"[{c}/METHODOLOGY.md]({c}/METHODOLOGY.md) |")
    tot = sum(s[1] for s in summary)
    idx += ["", f"**{tot} products in total.** Cross-cutting methodology lives in `CPI_METHODOLOGY.md`",
            "(the CPI chain), `ALL_COUNTRIES_2024.md` (the run and its gaps) and",
            "`crop_pipeline/docs/IRRIGATED_WATER_BALANCE.md` (why a rainfed balance misreads an",
            "irrigated crop, and which products it affects).", "",
            "Regenerate: `python build_crop_dossiers.py`"]
    open(f"{OUT}/README.md", "w").write("\n".join(idx) + "\n")
    to_word(f"{OUT}/README.md", "Crop product dossiers")
    print(f"\n{tot} products across {len(CROPS)} crops → {OUT}/")


if __name__ == "__main__":
    main()
