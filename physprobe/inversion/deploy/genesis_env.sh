# environment for every Genesis evaluation process on the xdliang3 container hosts (A800, H100): path redirection, GL bypass,
# Genesis env libs, cache. PYTHONNOUSERSITE: this account's ~/.local/lib/python3.10 holds PyOpenGL/typing_extensions/opencv
# builds that would shadow the copied environments; the 4090 reference host loads nothing from user site (issue log F11).
# Thread pools: one CPU thread drives each simulation, the pools only oversubscribe the container's cores (F15);
# QD_NUM_THREADS sets quadrants' kernel-compile threads (default = all host cores). MPS pipe: clients use the MPS daemon when
# batch2/mps_on.sh has started it (concurrent simulations then share the GPU instead of time-slicing) and run normally otherwise.
E=/workspace/wz/home/wangzijun_p25/miniconda3/envs/genesis
export LD_PRELOAD=/workspace/wz/lib/libpathredirect.so LD_LIBRARY_PATH=$E/lib XDG_CACHE_HOME=/workspace/wz/cache PYTHONPATH=/workspace/wz/lib/pyshim PYTHONNOUSERSITE=1
export OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 QD_NUM_THREADS=2
export CUDA_MPS_PIPE_DIRECTORY=/workspace/wz/mps/pipe CUDA_MPS_LOG_DIRECTORY=/workspace/wz/mps/log
