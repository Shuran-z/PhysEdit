#!/bin/bash
# SAM 3.1 lean tracker on nscc-hupanwen (native SAM 3.1 environment, shared multi-user machine: no MPS, only the GPUs listed,
# 2 processes per GPU, OMP threads limited). Usage: run_sam_tracker_hupanwen.sh JOB_DIR GPU_LIST(e.g. 3,4,5,6,7) [PROCS_PER_GPU]
P=$1; GPUS=$2; K=${3:-2}
S=/data2/zhangshuran/physedit
export OMP_NUM_THREADS=4 MKL_NUM_THREADS=4 OPENBLAS_NUM_THREADS=4 PYTHONNOUSERSITE=1
cd $S/sam_code
IFS=, read -ra G <<< "$GPUS"; N=$(( ${#G[@]} * K ))
for ((i = 0; i < N; i++)); do
  CUDA_VISIBLE_DEVICES=${G[$((i % ${#G[@]}))]} $S/sam_env/bin/python $S/lean_tools/sam_tracker.py $P/jobs.jsonl $P/tracks_s$i.jsonl \
    --sam3 $S/sam_source --checkpoint $S/sam_weights/sam3.1_multiplex.pt --shard $i/$N > $P/lean_s$i.log 2>&1 &
done
wait
cat $P/tracks_s*.jsonl > $P/tracks_lean.jsonl; date > $P/done
