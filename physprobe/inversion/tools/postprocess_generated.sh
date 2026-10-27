#!/bin/bash
# After eval_generated.py: known-truth validation gate (D28), per-model summary, motion amplitude / onset check, the
# sigma x2 sensitivity comparison (when results_gen/<NAME>_sigma3.jsonl exists), the report figures and the best-fit
# statistics (best_fit_stats.py).
# Logs to <WORK>/runs/post_<step>.log; <WORK>/runs/post.done marks the end. Run detached (setsid) on a server mirror.
# Usage (on the server): bash postprocess_generated.sh ROOT [NAME=all_cc] [WORKERS=12]
ROOT=$1; NAME=${2:-all_cc}; NW=${3:-12}
. $ROOT/physprobe/inversion/deploy/sam_env.sh
export PHYSPROBE_ROOT=$ROOT OMP_NUM_THREADS=1
W=${PHYSPROBE_WORK:-$ROOT/.local-research/evaluation/core100_inversion_workspace/evaluation}; R=$W/runs; mkdir -p $R; rm -f $R/post.done
cd $ROOT/physprobe/inversion
step() { local n=$1; shift; echo "$(date) start $n" >> $R/post_progress.log; $SAM_PY "$@" > $R/post_$n.log 2>&1; local rc=$?; echo "$(date) end $n exit=$rc" >> $R/post_progress.log; }
step gate validation_gate.py $NAME $NAME
step summary summarize_generated.py ${NAME}_gated
if [ -e $W/results_gen/${NAME}_sigma3.jsonl ]; then
  step gate_sigma3 validation_gate.py ${NAME}_sigma3 $NAME
  step compare compare_runs.py ${NAME}_gated ${NAME}_sigma3_gated
fi
step motion motion_check.py ${NAME}_gated $W/sam_gen/all/tracks/all_camcomp.jsonl --items $NAME --with-truth --workers $NW
step figures report_figures.py $W/report --generated ${NAME}_gated
step bestfit best_fit_stats.py ${NAME}_gated
date > $R/post.done
