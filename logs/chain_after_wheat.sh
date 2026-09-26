#!/bin/bash
# Runs once the wheat FCCI chain exits. Sequential on purpose: "User memory limit exceeded" is a
# PER-USER quota, so concurrent jobs make each other fail. Sudan millet L1 FCCI failed while 16
# maize exports and two tier-2 runs were in flight; L2 (smaller polygons) succeeded in the same run.
pid="$1"
while kill -0 "$pid" 2>/dev/null; do sleep 20; done
cd /Users/hildamanzi/Downloads/planting_pipeline
echo "[chain2] wheat chain exited; retrying Sudan millet L1 FCCI alone at $(date +%H:%M:%S)"
EE_PROJECT=ee-manzikye /opt/anaconda3/bin/python -u reduce_newcountries_tier2.py \
    Sudan_Kharif --crop millet --metrics fcci
echo "[chain2] Sudan millet FCCI retry rc=$? at $(date +%H:%M:%S)"
echo "[chain2] reducing the 16 cpiCTMX_ maize products at $(date +%H:%M:%S)"
EE_PROJECT=ee-manzikye /opt/anaconda3/bin/python -u reduce_newcountries.py \
    --asset-prefix cpiCTMX --out-prefix newcCTM --project ee-manzikye
echo "[chain2] maize CTM reduce rc=$? at $(date +%H:%M:%S)"
