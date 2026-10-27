"""Where code and data live. Code: this directory (in git). Data (simulation libraries, caches, tracks, results — never in
git): PHYSPROBE_WORK, default = the local research workspace. PHYSPROBE_ROOT: root of a server mirror of the project tree;
gt() maps the absolute local paths recorded in data files (metadata bindings, generated-video records) into it, so the
same scripts run on a server (the Mac is only an SSH connector).
Layout under the research workspace (EVALUATION):
  core100_inversion_workspace/evaluation/   WORK: libraries, box cache, horizons, tracks, results
  core100_inversion_workspace/projection/   the first projection test: cameras, task configs, its replays
  core100_inversion_workspace/ready/        bindings of the reference videos and their recorded metadata
  known_conditions/                         known-condition readiness table of the 100 tasks
  preparation/                              condition images (frame 5 of the reference videos)
Generated deliveries: ROOT/data/generated/original_prompts/ and revised_prompts/ (the prompt-corrected re-generation)."""
import os, re
from pathlib import Path

CODE = Path(__file__).resolve().parent
LOCAL_ROOTS = ('/Users/zhangshuran/data/projects/PhysProbe', '/Users/zhangshuran/data/projects/gravtrace')   # project renamed 2026-10-24
ROOT = os.environ.get('PHYSPROBE_ROOT', LOCAL_ROOTS[0])
EVALUATION = Path(ROOT) / '.local-research/evaluation'
WORKSPACE = EVALUATION / 'core100_inversion_workspace'
WORK = Path(os.environ.get('PHYSPROBE_WORK', WORKSPACE / 'evaluation'))
PROJECTION = WORKSPACE / 'projection'
READY = WORKSPACE / 'ready'
KNOWN = EVALUATION / 'known_conditions'
PREPARATION = EVALUATION / 'preparation'
GENERATED = Path(ROOT) / 'data/generated'
READINESS = KNOWN / 'readiness100.jsonl'   # one row per task (100 tasks)


def chunk_name(tag):
    """local file name of a library chunk: the job tag <task>_<param>_<chunk> (tags of older plans carry one prefix word);
    other tags (host checks, horizon runs) are kept as they are"""
    m = re.match(r'[A-Za-z0-9]+_(T\d\d_C\d\d_(?:g|mu|v)_[A-Za-z0-9]+)$', tag)
    return m.group(1) if m else tag


def gt(p):
    """map a recorded absolute local path into ROOT (identity when running locally)"""
    s = str(p)
    for lr in LOCAL_ROOTS:
        if s.startswith(lr): return ROOT + s[len(lr):]
    return s
