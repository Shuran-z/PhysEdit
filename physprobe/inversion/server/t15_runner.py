"""T15 replay/inversion runner: calls the author's batched Genesis simulation (`simulate` of the author's T15 physics script, imported
from its own path, unchanged) with the solver options recorded in the task's own physics annotation, for one or more
parameter values (one batched environment per value). Output matches run_batch.py: <root>/<TAG>/<param>_poses.json =
{value: {rc, poses: {mover: [[x,y,z,qx,qy,qz,qw] per frame]}}}.
Friction changes a shared material, which the batched simulation forbids across environments -> one value per call.
Usage: python t15_runner.py TAG CONFIG PHYSICS_JSON PARAM(none|g|v|mu) VALUE [VALUE ...]"""
import copy, importlib.util, json, math, os, sys, time
from pathlib import Path

ROOT = Path('/home/wangzijun_p25/zhangshuran/core100_inversion')
SRC = Path(os.environ.get('T15_PHYSICS_SCRIPT', '/home/wangzijun_p25/liyuhan/phydataset/ase_asset_importer/everyday_bifurcation_T15_v4_edge_transfer/scripts/t15_v11_physics.py'))   # the author's file
tag, config, physics_json, param = sys.argv[1:5]
values = [float(v) for v in sys.argv[5:]]
assert not (param == 'mu' and len(values) > 1), 'friction: one value per call'
out_root = ROOT / tag; out_root.mkdir(parents=True, exist_ok=True)
spec = importlib.util.spec_from_file_location('author_t15_physics', SRC); mod = importlib.util.module_from_spec(spec); spec.loader.exec_module(mod)
prov = json.loads(Path(physics_json).read_text())['physical_provenance']
opts = dict(box_detection=bool(prov['box_box_detection']), steps=int(round(1 / (30 * prov['solver_dt_s']))), settle=prov['settle_seconds'] > 0,
            timeconst=float(prov['constraint_timeconst']), stiff=prov.get('contact_sol_params') is not None,
            precision=str(prov['precision_bits']), exact=prov['integrator'] == 'implicitfast')
base = json.loads(Path(config).read_text())
DRIVER, MOVERS, PLANE = mod.NAMES[2], mod.NAMES[2:], mod.NAMES[0]
rows = []
for v in values:
    c = copy.deepcopy(base)
    if param == 'g':
        c['scene_overrides']['gravity'] = [0.0, 0.0, -v]
    elif param == 'v':
        mo = next(o for o in c['dynamic_objects'] if o['name'] == DRIVER)['motion']; iv = mo['initial_velocity']; n = math.sqrt(sum(x * x for x in iv))
        mo['initial_velocity'] = [x / n * v for x in iv]
    elif param == 'mu':   # main contact plane = tabletop under the driver book
        next(o for o in c['dynamic_objects'] if o['name'] == PLANE)['friction'] = v
    d = out_root / f'{param}_{v:.6g}'; d.mkdir(exist_ok=True)
    (d / 'config.json').write_text(json.dumps(c, indent=1))
    rows.append(dict(sample_id=f'{tag}_{v:.6g}', config=str(d / 'config.json'), output=str(d / 'run')))
t0 = time.time(); res = {}
try:
    mod.simulate(rows, **opts)
    for v, r in zip(values, rows):
        ann = json.loads((Path(r['output']) / 'metadata/physics.json').read_text())
        poses = {m: [[*next(o for o in f['objects'] if o['name'] == m)['position'], *next(o for o in f['objects'] if o['name'] == m)['quaternion_xyzw']]
                     for f in ann['frames']] for m in MOVERS}
        res[f'{v:.6g}'] = dict(rc=0, poses=poses)
        (Path(r['output']) / 'metadata/physics.json').unlink()
except Exception as e:
    for v in values: res.setdefault(f'{v:.6g}', dict(rc=1, poses=None, error=repr(e)[:300]))
(out_root / f'{param}_poses.json').write_text(json.dumps(res))
print(json.dumps(dict(tag=tag, param=param, n=len(values), ok=sum(r['rc'] == 0 for r in res.values()), wall_s=round(time.time() - t0, 1), opts=opts)))
