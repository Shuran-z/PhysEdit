# environment for SAM 3.1 tracking on the A800 host. No path redirection is needed (the SAM trees were path-rewritten).
# libGL: the container has no system libGL, which opencv-python links against (never called for tracking); /workspace/wz/lib/gl
# holds only libGL/libGLX/libGLdispatch copied from the Genesis env. PYTHONNOUSERSITE keeps ~/.local opencv 4.11 from
# shadowing the env's opencv 4.10 (hupanwen uses 4.10).
S=/workspace/wz/sam/data2/zhangshuran/physedit
export LD_LIBRARY_PATH=/workspace/wz/lib/gl PYTHONNOUSERSITE=1
SAM_PY=$S/sam_env/bin/python
SAM_CODE=$S/sam_code
SAM_SRC=$S/sam_source
SAM_CKPT=$S/sam_weights/sam3.1_multiplex.pt   # the official SAM 3.1 checkpoint
