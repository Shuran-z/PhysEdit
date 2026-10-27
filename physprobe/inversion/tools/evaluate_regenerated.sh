#!/bin/bash
# Evaluate a re-generated delivery after its SAM 3.1 tracking (e.g. the prompt-corrected videos, issue log E4) and merge
# it into the generated-video results: camera compensation, evaluation, merge (the new results replace the same keys; rows
# carry prompts = original / revised), known-truth gate, per-model summary, generated-video metrics, the comparison with the official
# gated results, and the paired before / after comparison of the replaced results. Official files are not overwritten.
# With KNOWN_CONDITIONS (the known conditions of the new prompt release), mu of the new rows is scored against the friction
# that their prompts declare for the measured contact (apply_declared_mu.py, issue log E4).
# Logs: <WORK>/runs/regen_<NAME>_<step>.log; <WORK>/runs/regen_<NAME>.done marks the end.
# Usage (on the server, detached): [GATE_ITEMS=all_cc,NAME] bash evaluate_regenerated.sh ROOT NAME [BASE=all_cc] [WORKERS=24] [KNOWN_CONDITIONS]
# (GATE_ITEMS: when BASE is itself a merge, list the job sets whose items cover all keys)
ROOT=$1; NAME=$2; BASE=${3:-all_cc}; NW=${4:-24}; KC=${5:-}
. $ROOT/physprobe/inversion/deploy/sam_env.sh
export PHYSPROBE_ROOT=$ROOT OMP_NUM_THREADS=1
W=${PHYSPROBE_WORK:-$ROOT/.local-research/evaluation/core100_inversion_workspace/evaluation}; R=$W/runs; G=$W/sam_gen/$NAME; M=${BASE}_$NAME
mkdir -p $R; rm -f $R/regen_$NAME.done
cd $ROOT/physprobe/inversion
step() { local n=$1; shift; echo "$(date) start $n" >> $R/regen_${NAME}_progress.log; $SAM_PY "$@" > $R/regen_${NAME}_$n.log 2>&1; local rc=$?; echo "$(date) end $n exit=$rc" >> $R/regen_${NAME}_progress.log; }
step camcomp cam_comp.py $G/items.json $G/tracks_lean.jsonl --out $G/tracks_camcomp.jsonl --workers $NW
step eval eval_generated.py $NAME $G/tracks_camcomp.jsonl --workers $NW --clock realtime
step merge merge_generated.py $BASE $NAME $M
[ -n "$KC" ] && step declared apply_declared_mu.py $M $KC --prompts revised
step gate validation_gate.py $M ${GATE_ITEMS:-$BASE,$NAME}   # item sets that know every key's video format
step summary summarize_generated.py ${M}_gated
step metrics response_metrics.py ${M}_gated
step compare compare_runs.py ${BASE}_gated ${M}_gated
step paired regen_compare.py ${BASE}_gated ${M}_gated --out $W/results_gen/regen_compare_${M}.md
date > $R/regen_$NAME.done
