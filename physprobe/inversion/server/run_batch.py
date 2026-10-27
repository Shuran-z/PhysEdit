"""Launch physics-only runs for a list of parameter values concurrently on one GPU; keep only per-frame mover poses."""
import json, os, subprocess, sys, time
from pathlib import Path
import os as _os
R = _os.environ["RENDERER"]   # the task's renderer script, set by refine_queue.py from the task manifest
PY = "/home/wangzijun_p25/miniconda3/envs/genesis/bin/python"
tag, cfg, param, gpu, movers = sys.argv[1], sys.argv[2], sys.argv[3], sys.argv[4], sys.argv[5].split(",")
values = [float(v) for v in sys.argv[6:]]
root = Path("/home/wangzijun_p25/zhangshuran/core100_inversion") / tag; root.mkdir(parents=True, exist_ok=True)
procs = []; t0 = time.time()
for v in values:
    out = root / f"{param}_{v:.6g}"
    args = [PY, "/home/wangzijun_p25/zhangshuran/core100_inversion/physics_only.py", "--renderer", R, "--config", cfg, "--out", str(out)] + [f"--renderer-arg={x}" for x in os.environ.get("RENDERER_ARGS", "").split() if x]
    args += [x for x in os.environ.get("WRAPPER_ARGS", "").split() if x]   # extra physics_only.py options
    args += [] if param == "none" else ["--gravity", str(v)] if param == "g" else (["--speed", movers[0], str(v)] if param == "v" else [x for o in (os.environ.get("FRICTION_OBJECTS") or movers[0]).split(",") for x in ("--friction", o, str(v))])
    log = open(str(out) + ".log", "w")
    procs.append((v, out, subprocess.Popen(args, stdout=log, stderr=subprocess.STDOUT, env=dict(os.environ, CUDA_VISIBLE_DEVICES=gpu))))
res = {}
for v, out, p in procs:
    rc = p.wait()
    poses = None
    if (out / "meta.json").exists():
        meta = json.loads((out / "meta.json").read_text())
        mv = [o["name"] for o in meta["frames"][0]["objects"]] if "ALL" in movers else movers   # ALL: every object (occluders)
        poses = {m: [[*next(o for o in f["objects"] if o["name"] == m)["position"], *next(o for o in f["objects"] if o["name"] == m).get("quaternion_xyzw", [0, 0, 0, 1])] for f in meta["frames"]] for m in mv}
        (out / "meta.json").unlink()
    res[f"{v:.6g}"] = dict(rc=rc, poses=poses)
(root / f"{param}_poses.json").write_text(json.dumps(res))
print(json.dumps({"tag": tag, "param": param, "n": len(values), "ok": sum(r["rc"] == 0 for r in res.values()), "wall_s": round(time.time() - t0, 1)}))
