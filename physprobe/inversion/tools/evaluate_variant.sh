#!/bin/bash
# Evaluate a rule variant (environment overrides such as PHYSPROBE_MIN_COVER=0.5 or PHYSPROBE_SIGMA_PX=3) on the reference
# known-answer set, the synthetic generated-like sets and the generated videos, next to the official results:
#   results_reference_<TAG>/, results_gen/<set>_<TAG>.jsonl, results_gen/all_cc_<TAG>.jsonl and its gated file (gate built from the
#   variant's own known-truth results), then the reference statistics against results_reference and compare_runs against the
#   official gated results. Logs: <WORK>/runs/variant_<TAG>_<step>.log; <WORK>/runs/variant_<TAG>.done marks the end.
# Usage (on the server, detached): VAR=VALUE ... bash evaluate_variant.sh ROOT TAG [WORKERS]
ROOT=$1; TAG=$2; NW=${3:-24}
. $ROOT/physprobe/inversion/deploy/sam_env.sh
export PHYSPROBE_ROOT=$ROOT OMP_NUM_THREADS=1 PHYSPROBE_REF_OUT=results_reference_$TAG PHYSPROBE_WORKERS=$NW
W=${PHYSPROBE_WORK:-$ROOT/.local-research/evaluation/core100_inversion_workspace/evaluation}; R=$W/runs; mkdir -p $R; rm -f $R/variant_$TAG.done
cd $ROOT/physprobe/inversion
step() { local n=$1; shift; echo "$(date) start $n" >> $R/variant_${TAG}_progress.log; $SAM_PY "$@" > $R/variant_${TAG}_$n.log 2>&1; local rc=$?; echo "$(date) end $n exit=$rc" >> $R/variant_${TAG}_progress.log; }
step ref evaluator.py ref
step ref_stats ref_stats.py $W/results_reference_$TAG --compare $W/results_reference
for s in s15v s10f16 s30f121; do
  step synth_$s eval_generated.py $s $W/sam_gen/$s/tracks_lean.jsonl --workers $NW --clock reference --out ${s}_$TAG
done
step generated eval_generated.py all_cc $W/sam_gen/all/tracks/all_camcomp.jsonl --workers $NW --clock realtime --out all_cc_$TAG
step gate validation_gate.py all_cc_$TAG all_cc $TAG
step compare compare_runs.py all_cc_gated all_cc_${TAG}_gated
date > $R/variant_$TAG.done
