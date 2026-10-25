"""Run an original phyediting renderer in physics-only mode with a parameter override.

The original module is imported from its own path so all stage/asset loading is unchanged; only camera creation
is replaced by a no-op camera, the render backend is set to overlay_2d, video writing is disabled, and every output
path is redirected into the given output directory.
"""
import argparse, copy, importlib.util, json, sys, time
from pathlib import Path

p = argparse.ArgumentParser()
p.add_argument("--renderer", required=True)
p.add_argument("--config", required=True)
p.add_argument("--out", required=True)
p.add_argument("--gravity", type=float)
p.add_argument("--friction", nargs=2, action="append", metavar=("OBJECT", "MU"), default=[])
p.add_argument("--speed", nargs=2, action="append", metavar=("OBJECT", "V"), default=[])
p.add_argument("--renderer-arg", action="append", default=[], help="extra renderer argument")
a = p.parse_args()

out = Path(a.out); out.mkdir(parents=True, exist_ok=True)
cfg = json.loads(Path(a.config).read_text())
cfg = copy.deepcopy(cfg)
r = cfg.setdefault("render", {})
r["render_backend"] = "overlay_2d"; r["write_video"] = False; r["use_native_recording"] = False
r["save_rgb_frames"] = False; r["save_depth_frames"] = False; r["save_seg_frames"] = False
r["save_video"] = str(out / "unused.mp4"); r["save_first_rgb"] = str(out / "first.png"); r["save_last_rgb"] = str(out / "last.png")
for k in list(r):
    if isinstance(r[k], str) and r[k].startswith("/") and k not in ("render_backend",) and not r[k].startswith(str(out)):
        if any(s in k for s in ("save", "dir", "path")):
            r[k] = str(out / Path(r[k]).name)
cfg.setdefault("annotations", {})["save_path"] = str(out / "meta.json")
so = cfg.setdefault("scene_overrides", {})
so["raytracing"] = False
if a.gravity is not None:
    so["gravity"] = [0.0, 0.0, -float(a.gravity)]
    par = cfg.setdefault("experiment", {}).setdefault("parameter", {})
    if "gravity_vector_mps2" in par: par["gravity_vector_mps2"] = [0.0, 0.0, -float(a.gravity)]
    if "gravity_magnitude_mps2" in par: par["gravity_magnitude_mps2"] = float(a.gravity)
    if "gravity_vector_mps2" in cfg["experiment"]: cfg["experiment"]["gravity_vector_mps2"] = [0.0, 0.0, -float(a.gravity)]
for name, mu in a.friction:
    hit = [o for o in cfg.get("dynamic_objects", []) if o.get("name") == name]
    assert hit, f"no object {name}"
    for o in hit:
        (o.get("spec") or o)["friction"] = float(mu)
import math
for name, v in a.speed:
    hit = [o for o in cfg.get("dynamic_objects", []) if o.get("name") == name]
    assert hit, f"no object {name}"
    for o in hit:
        mo = (o.get("spec") or o).setdefault("motion", {})
        iv = mo["initial_velocity"]; n = math.sqrt(sum(x * x for x in iv)); assert n > 0
        old = n; mo["initial_velocity"] = [x / n * float(v) for x in iv]
        if mo.get("initial_angular_velocity"):  # keep rolling consistent (omega scales with v)
            mo["initial_angular_velocity"] = [w * float(v) / old for w in mo["initial_angular_velocity"]]
        for k, val in list(cfg.get("experiment", {}).items()):
            if "speed" in k and isinstance(val, (int, float)) and abs(val - old) < 1e-6:
                cfg["experiment"][k] = float(v)
cfg_path = out / "config.json"; cfg_path.write_text(json.dumps(cfg, indent=1))

import importlib._bootstrap_external as _bx


class NoCamera:
    def __getattr__(self, name):
        return lambda *x, **k: None


def no_camera(*args, **kwargs):
    return NoCamera(), {"camera": "disabled_physics_only"}


_orig_exec = _bx.SourceFileLoader.exec_module


def _exec_and_patch(self, module):
    # renderer modules loaded at any depth (direct, load_base, render_sample) get the camera stub
    _orig_exec(self, module)
    if hasattr(module, "_add_camera_with_render_overrides"):
        module._add_camera_with_render_overrides = no_camera


_bx.SourceFileLoader.exec_module = _exec_and_patch
spec = importlib.util.spec_from_file_location("orig_renderer", a.renderer)
mod = importlib.util.module_from_spec(spec); sys.modules["orig_renderer"] = mod; spec.loader.exec_module(mod)
sys.argv = [a.renderer, *a.renderer_arg, "--config", str(cfg_path)]
t0 = time.time(); status = "ok"
try:
    mod.main()
except SystemExit as e:
    status = f"system_exit_{e.code}"
except Exception as e:  # e.g. post-render video validation; keep meta.json if physics finished
    status = "exception: " + repr(e)[:300]
(out / "timing.json").write_text(json.dumps({"wall_s": time.time() - t0, "status": status}))
