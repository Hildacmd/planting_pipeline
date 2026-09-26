#!/bin/bash
# Wait for a crop's cheap tier-2 run to exit, then run its FCCI pass.
# They MERGE COLUMNS INTO THE SAME CSVs (read-modify-write), so running them concurrently would
# make the second writer clobber the first's columns. Chaining is the fix, not an optimisation.
crop="$1"; pid="$2"
while kill -0 "$pid" 2>/dev/null; do sleep 20; done
echo "[chain] $crop cheap run (pid $pid) exited; starting FCCI at $(date +%H:%M:%S)"
cd /Users/hildamanzi/Downloads/planting_pipeline
EE_PROJECT=ee-manzikye /opt/anaconda3/bin/python -u reduce_newcountries_tier2.py \
    --crop "$crop" --metrics fcci
echo "[chain] $crop FCCI finished at $(date +%H:%M:%S) rc=$?"
