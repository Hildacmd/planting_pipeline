# Notebook stage notes

Every Colab notebook in this repository carries a markdown note above each code cell: what the
stage does, the formula behind it, the output to expect, and what a wrong result looks like.

The notes are **generated, not hand-pasted**, so they can be corrected in one place and re-applied
after the notebooks are edited.

```bash
python docs_notes/annotate.py            # annotate every notebook
python docs_notes/annotate.py --check    # report coverage, write nothing
python docs_notes/annotate.py 01_planting_window.ipynb
```

## How it works

Each note is a `(anchor, markdown)` pair. The anchor is a substring of the code cell the note belongs
to, so the note follows its cell if cells are reordered. Inserted cells are tagged `"autonote": true`
in their metadata; `annotate.py` strips those before re-inserting, so it is idempotent.

If a code cell is edited so that its anchor no longer matches, `--check` reports
`MISSING ANCHORS` and names it. Fix the anchor in the notes file, not the notebook.

## Where the notes live

| File | Notebooks |
|---|---|
| `notes_core.py` | `01_planting_window`, `02_risk_monitoring`, `03_cpi_yield`, `04_flooding_waterlogging` |
| `notes_masks.py` | `crop_type_mask/crop_type_mask_colab`, `crop_type_mask/crop_type_mask_VIEWER_colab` |
| `notes_runners.py` | `run_in_colab`, `planting_pipeline_colab`, `planting_pipeline_ALL_colab`, `planting_pipeline_kenya` |
| `notes_methodology.py` | `Methodology_Testing/01` to `05`, `methodology testing/methodology_testing_colab` |

`Documentation_ALL_2026-08-09/` is a dated snapshot and is deliberately left unannotated.

## Where the expected numbers come from

Nothing in the notes is invented. The figures are read from the shipped results:

| Statistic | Source |
|---|---|
| Planting validation, 42 counties and 855 wards | `planting_validation_MAM_2024.csv`, `planting_validation_MAM_ward_2024.csv` |
| Planting distribution, 253 constituencies | `estarfm_planting_Kenya_maize_Longrains_2024_L2_skill.csv` |
| Yield ceilings and held-out error | `src/cpi.py` `YM_CAL`, `yield_calibration_2024/YIELD_CALIBRATION_2024.md` |
| Crop-mask areas, calibration and held-out years | `crop_type_mask/regional_report/tbl_*.csv` |
| A/B verdicts | the Result sections of the `Methodology_Testing` notebooks |
| Thresholds and constants | `src/*.py` and `config/*.yaml`, `crop_type_mask/config.py` |

When any of those change, update the note in `docs_notes/` and re-run `annotate.py`.
