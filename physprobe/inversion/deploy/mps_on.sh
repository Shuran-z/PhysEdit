#!/bin/bash
# Start the NVIDIA MPS control daemon of this container if it is not running (issue log F15: without MPS, simulations on the
# same GPU time-slice their kernels; with it, 4 T03 replays on an A800 ran 3.2x the total step rate). Uses the pipe/log
# directories of genesis_env.sh. Stop with: echo quit | nvidia-cuda-mps-control
export CUDA_MPS_PIPE_DIRECTORY=/workspace/wz/mps/pipe CUDA_MPS_LOG_DIRECTORY=/workspace/wz/mps/log
mkdir -p $CUDA_MPS_PIPE_DIRECTORY $CUDA_MPS_LOG_DIRECTORY
if echo get_server_list | nvidia-cuda-mps-control > /dev/null 2>&1; then echo "MPS daemon already running"
else nvidia-cuda-mps-control -d && echo "MPS daemon started"; fi
