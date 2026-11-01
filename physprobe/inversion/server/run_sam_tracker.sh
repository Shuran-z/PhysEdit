#!/bin/bash
# SAM 3.1 lean tracker on one job directory (jobs.jsonl + videos/), N shards sharing the GPU(s) through MPS, OMP threads
# limited (issue log C12, F15). Optional: wait for a file before starting. Writes tracks_s<i>.jsonl, tracks_lean.jsonl, done.
# Usage: run_sam_tracker.sh JOB_DIR N_SHARDS [GPU_LIST e.g. 0 or 0,1] [WAIT_FOR_FILE]
P=$1; N=${2:-3}; GPUS=${3:-0}; WAIT=${4:-}
D=/workspace/wz/home/wangzijun_p25/zhangshuran/core100_inversion
[ -n "$WAIT" ] && while [ ! -e "$WAIT" ]; do sleep 30; done
. $D/deploy/sam_env.sh
export OMP_NUM_THREADS=4 MKL_NUM_THREADS=4 OPENBLAS_NUM_THREADS=4 CUDA_MPS_PIPE_DIRECTORY=/workspace/wz/mps/pipe CUDA_MPS_LOG_DIRECTORY=/workspace/wz/mps/log
$D/deploy/mps_on.sh
cd $SAM_CODE
IFS=, read -ra G <<< "$GPUS"
for ((i = 0; i < N; i++)); do
  CUDA_VISIBLE_DEVICES=${G[$((i % ${#G[@]}))]} $SAM_PY $D/deploy/sam_tracker.py $P/jobs.jsonl $P/tracks_s$i.jsonl --sam3 $SAM_SRC --checkpoint $SAM_CKPT --shard $i/$N > $P/lean_s$i.log 2>&1 &
done
wait
cat $P/tracks_s*.jsonl > $P/tracks_lean.jsonl; date > $P/done
