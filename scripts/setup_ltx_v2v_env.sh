#!/usr/bin/env bash
# Isolated generation overlay; never upgrade the frozen SAM/inversion environment.
set -euo pipefail
base_python= env_dir=
while (($#)); do
  case "$1" in
    --python) base_python=$2; shift 2 ;;
    --env-dir) env_dir=$2; shift 2 ;;
    *) echo 'Usage: setup_ltx_v2v_env.sh --python CUDA_BASE_PYTHON --env-dir NEW_ENV_DIR' >&2; exit 2 ;;
  esac
done
[[ -x "$base_python" && -n "$env_dir" && ! -e "$env_dir" ]] || {
  echo 'Provide an existing CUDA Python and a new environment directory' >&2; exit 2;
}
"$base_python" -m venv --system-site-packages "$env_dir"
"$env_dir/bin/python" -m pip install --disable-pip-version-check --no-deps 'diffusers==0.39.0'
"$env_dir/bin/python" - <<'PY'
import inspect, json
import diffusers
from diffusers import LTXConditionPipeline
required = {'video', 'denoise_strength', 'strength', 'frame_index', 'frame_rate'}
actual = set(inspect.signature(LTXConditionPipeline.__call__).parameters)
if not required <= actual:
    raise RuntimeError('LTX video-editing API unavailable')
print(json.dumps(dict(diffusers=diffusers.__version__, editing_arguments=sorted(required),
                     model_loaded=False, gpu_started=False)))
PY
