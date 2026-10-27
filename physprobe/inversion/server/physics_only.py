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
p.add_argument("--patch-config-path", action="append", default=[], metavar="FUNC",
               help="replace module function FUNC (e.g. render_sample.config_path) by one returning our config path")
p.add_argument("--precision", choices=["32", "64"], help="force Genesis floating-point precision (gs.init precision)")
p.add_argument("--record-quat", action="store_true",
               help="renderers whose per-frame annotation stores positions only (T12, T13): record each entity's orientation "
                    "whenever the module's _read_entity_pos is called and attach it to the matching frame object afterwards")
p.add_argument("--seed", type=int, help="Genesis seed to use when the renderer passes none (e.g. T13 initializes with seed=None)")
p.add_argument("--noop", action="append", default=[], metavar="FUNC",
               help="replace module function FUNC (e.g. validate_rendered_video) by a no-op")
p.add_argument("--frames", type=int,
               help="simulate only the first N render frames (the evaluation never looks past the last predictability window "
                    "+ time shift); every frame-count field of the config is set to N. Validated per task family against "
                    "full-length replays before use")
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
cfg["annotations"]["enabled"] = True   # some camera configs (e.g. T03 cam03) disable the per-frame state export
so = cfg.setdefault("scene_overrides", {})
so["raytracing"] = False
if a.frames:
    for blk in (r, cfg.get("experiment", {}).get("render")):
        if isinstance(blk, dict) and "frames" in blk: blk["frames"] = min(int(blk["frames"]), a.frames)
    tr = cfg.get("trajectory_replay")
    if isinstance(tr, dict) and "frame_count" in tr: tr["frame_count"] = min(int(tr["frame_count"]), a.frames)
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

if a.precision or a.seed is not None:   # every renderer calls genesis.init itself; override there without touching its files
    import genesis as _gs
    _gs_init = _gs.init
    def _init_with_precision(*x, **k):
        if a.precision: k["precision"] = a.precision
        if a.seed is not None and k.get("seed") is None: k["seed"] = a.seed
        return _gs_init(*x, **k)
    _gs.init = _init_with_precision

import importlib._bootstrap_external as _bx


class NoCamera:
    def __getattr__(self, name):
        return lambda *x, **k: None


def no_camera(*args, **kwargs):
    return NoCamera(), {"camera": "disabled_physics_only"}


QUATS = {}   # (x, y, z) as returned by _read_entity_pos -> orientation x, y, z, w at that moment
_orig_exec = _bx.SourceFileLoader.exec_module


def _exec_and_patch(self, module):
    # renderer modules loaded at any depth (direct, load_base, render_sample) get the camera stub
    _orig_exec(self, module)
    if hasattr(module, "_add_camera_with_render_overrides"):
        module._add_camera_with_render_overrides = no_camera
    if a.record_quat and callable(getattr(module, "_read_entity_pos", None)):
        _orig_read = module._read_entity_pos
        def _read_and_record(entity, *x, **k):
            pos = _orig_read(entity, *x, **k)
            try:
                q = entity.get_quat()
                q = q.detach().cpu().numpy() if hasattr(q, "detach") else q
                q = [float(v) for v in list(q)[-4:]]                       # Genesis: w, x, y, z
                QUATS[tuple(float(v) for v in list(pos)[:3])] = [q[1], q[2], q[3], q[0]]   # -> x, y, z, w
            except Exception:
                pass
            return pos
        module._read_entity_pos = _read_and_record
    for name in a.patch_config_path:
        if callable(getattr(module, name, None)):
            setattr(module, name, lambda *x, **k: cfg_path.resolve())
    for name in a.noop:
        if callable(getattr(module, name, None)):
            setattr(module, name, lambda *x, **k: None)


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
if a.record_quat and (out / "meta.json").exists():   # attach orientations to the per-frame states (exact position match)
    meta = json.loads((out / "meta.json").read_text()); hit = miss = 0
    for fr in meta.get("frames", []):
        for o in fr.get("objects", []):
            if o.get("quaternion_xyzw") is None:
                q = QUATS.get(tuple(float(v) for v in o["position"][:3]))
                if q is None: miss += 1
                else: o["quaternion_xyzw"] = q; hit += 1
    (out / "meta.json").write_text(json.dumps(meta))
    (out / "quat_attach.json").write_text(json.dumps({"attached": hit, "missing": miss}))
(out / "timing.json").write_text(json.dumps({"wall_s": time.time() - t0, "status": status, "precision": a.precision or "renderer default", "seed_override": a.seed}))
