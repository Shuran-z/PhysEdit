#!/bin/bash
# Run one inversion script on a server mirror of the project, detached from the SSH session (the NSCC proxy drops
# connections), with the SAM 3.1 python environment (numpy / scipy / opencv) and PHYSPROBE_ROOT set.
# Writes <WORK>/runs/<NAME>.log and <WORK>/runs/<NAME>.done (exit code + time).
# Usage (on the server): run_on_mirror.sh ROOT NAME SCRIPT.py [ARGS ...]
ROOT=$1; NAME=$2; shift 2
. $ROOT/physprobe/inversion/deploy/sam_env.sh
export PHYSPROBE_ROOT=$ROOT OMP_NUM_THREADS=${OMP_NUM_THREADS:-1}
W=$ROOT/.local-research/evaluation/core100_inversion_workspace/trial/batch2; mkdir -p $W/runs; rm -f $W/runs/$NAME.done
cd $ROOT/physprobe/inversion
( $SAM_PY "$@" > $W/runs/$NAME.log 2>&1; echo "exit=$? $(date)" > $W/runs/$NAME.done ) < /dev/null > /dev/null 2>&1 &
disown
echo "started $NAME"
