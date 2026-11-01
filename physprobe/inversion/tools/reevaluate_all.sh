#!/bin/bash
# Full re-evaluation on a server mirror after a library or rule change (run detached via run_on_mirror-style setsid):
#  1 reference known-answer run  2 threshold calibration  3 reference run with the calibrated threshold + statistics
#  4 generated videos (camera-compensated tracks)  5 synthetic generated-like known-answer sets
#  6 known-truth validation gate (D28) + per-model summary + report figures.
# Each step logs to <WORK>/runs/reeval_<step>.log; <WORK>/runs/reeval.done marks the end.
# Usage (on the server): bash reevaluate_all.sh ROOT [WORKERS] [FROM_STEP: 1 = all, 2 = keep step 1 results]
ROOT=$1; NW=${2:-12}
. $ROOT/physprobe/inversion/deploy/sam_env.sh
export PHYSPROBE_ROOT=$ROOT OMP_NUM_THREADS=1 PHYSPROBE_WORKERS=$NW
W=${PHYSPROBE_WORK:-$ROOT/.local-research/evaluation/core100_inversion_workspace/evaluation}; R=$W/runs; mkdir -p $R; rm -f $R/reeval.done
cd $ROOT/physprobe/inversion
step() { local n=$1; shift; echo "$(date) start $n" >> $R/reeval_progress.log; $SAM_PY "$@" > $R/reeval_$n.log 2>&1; local rc=$?; echo "$(date) end $n exit=$rc" >> $R/reeval_progress.log; }
FROM=${3:-1}
[ $FROM -le 1 ] && { rm -f $W/results_reference/band_calibration.json; step 1_ref evaluator.py ref; }
step 2_calibrate calibrate_band.py --coverage 0.9
step 3_ref evaluator.py ref
step 3_stats ref_stats.py
T=$W/sam_gen/all/tracks
step 4_generated eval_generated.py all_cc $T/all_camcomp.jsonl --workers $NW --clock realtime
for s in s15v s10f16 s30f121; do
  [ -e $W/sam_gen/$s/tracks_lean.jsonl ] && step 5_synth_$s eval_generated.py $s $W/sam_gen/$s/tracks_lean.jsonl --workers $NW --clock reference
done
# camera-pan known-answer test (make_pan_test.py): compensated and uncompensated tracks of the same moved videos
[ -e $W/sam_gen/s15v_pan/tracks_comp.jsonl ] && step 5_pan eval_generated.py s15v_pan $W/sam_gen/s15v_pan/tracks_comp.jsonl --workers $NW --clock reference
[ -e $W/sam_gen/s15v_pan/tracks_moved.jsonl ] && step 5_pan_raw eval_generated.py s15v_pan_raw $W/sam_gen/s15v_pan/tracks_moved.jsonl --workers $NW --clock reference
step 6_gate validation_gate.py all_cc
step 6_summary summarize_generated.py all_cc_gated
step 6_figures report_figures.py $W/report
step 6_bestfit best_fit_stats.py all_cc_gated
date > $R/reeval.done
