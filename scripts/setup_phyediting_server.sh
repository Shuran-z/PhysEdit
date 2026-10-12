#!/usr/bin/env bash
# Create an isolated PhyEditing/SAM3.1 overlay on an existing CUDA Python.
set -euo pipefail

usage() {
  cat <<'EOF'
Usage: scripts/setup_phyediting_server.sh --python BASE_PYTHON --sam-source OFFICIAL_SAM3_GIT \
  --checkpoint SAM3_1_MULTIPLEX_PT --env-dir NEW_ENV_DIR

The base Python must already provide a working PyTorch/CUDA and Diffusers stack.
This script creates a new virtual environment that can see those packages, adds
the pinned lightweight SAM dependencies, installs this repository, and verifies
the frozen SAM source commit and checkpoint SHA. It never changes the base env.
EOF
}

base_python= sam_source= checkpoint= env_dir=
while (($#)); do
  case "$1" in
    --python|--sam-source|--checkpoint|--env-dir)
      (($# >= 2)) || { usage >&2; exit 2; }
      case "$1" in
        --python) base_python=$2 ;;
        --sam-source) sam_source=$2 ;;
        --checkpoint) checkpoint=$2 ;;
        --env-dir) env_dir=$2 ;;
      esac
      shift 2 ;;
    -h|--help) usage; exit 0 ;;
    *) usage >&2; exit 2 ;;
  esac
done

[[ -n "$base_python" && -n "$sam_source" && -n "$checkpoint" && -n "$env_dir" ]] || { usage >&2; exit 2; }
[[ -x "$base_python" && -d "$sam_source/.git" && -f "$checkpoint" ]] || {
  echo 'Missing base Python, official SAM3 Git checkout, or checkpoint' >&2
  exit 2
}
[[ ! -e "$env_dir" ]] || { echo "Environment already exists: $env_dir" >&2; exit 2; }

repo=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
mkdir -p "$(dirname "$env_dir")"
"$base_python" -m venv --system-site-packages "$env_dir"
venv_python="$env_dir/bin/python"
"$venv_python" -m pip install --disable-pip-version-check --no-deps 'setuptools==70.3.0' 'timm==1.0.28'
"$venv_python" -m pip install --disable-pip-version-check --no-deps --no-build-isolation -e "$repo"

PYTHONPATH="$sam_source:$repo${PYTHONPATH:+:$PYTHONPATH}" \
  "$venv_python" - "$sam_source" "$checkpoint" <<'PY'
import importlib
import json
import sys
from pathlib import Path

for name in ('torch', 'torchvision', 'diffusers', 'transformers', 'accelerate',
             'cv2', 'numpy', 'scipy', 'timm', 'pkg_resources', 'sam3'):
    importlib.import_module(name)
from sam3.model_builder import build_sam3_multiplex_video_predictor
from scripts.sam31_frontend import validate_runtime

receipt = validate_runtime(Path(sys.argv[1]), Path(sys.argv[2]))
receipt['environment_python'] = sys.executable
receipt['inference_started'] = False
print(json.dumps(receipt, sort_keys=True))
PY

cat > "$env_dir/activate_phyediting.sh" <<EOF
export PYTHONPATH='$sam_source:$repo'
export PHYEDIT_SAM3_SOURCE='$sam_source'
export PHYEDIT_SAM31_CHECKPOINT='$checkpoint'
export PHYEDIT_PYTHON='$venv_python'
EOF
echo "Configured isolated environment: $env_dir"
