"""Where code and data live. Code: this directory (in git). Data (simulation libraries, caches, tracks, results — never in
git): PHYSPROBE_WORK, default = the local research workspace. PHYSPROBE_ROOT: root of a server mirror of the project tree;
gt() maps the absolute local paths recorded in data files (metadata bindings, generated-video records) into it, so the
same scripts run on a server (the Mac is only an SSH connector)."""
import os
from pathlib import Path

CODE = Path(__file__).resolve().parent
LOCAL_ROOTS = ('/Users/zhangshuran/data/projects/PhysProbe', '/Users/zhangshuran/data/projects/gravtrace')   # project renamed 2026-10-24
ROOT = os.environ.get('PHYSPROBE_ROOT', LOCAL_ROOTS[0])
WORK = Path(os.environ.get('PHYSPROBE_WORK', ROOT + '/.local-research/evaluation/core100_inversion_workspace/trial/batch2'))


def gt(p):
    """map a recorded absolute local path into ROOT (identity when running locally)"""
    s = str(p)
    for lr in LOCAL_ROOTS:
        if s.startswith(lr): return ROOT + s[len(lr):]
    return s
