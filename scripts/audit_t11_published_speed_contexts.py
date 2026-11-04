"""Check published T11 contexts before reusing a published speed contrast.

Read-only: no simulator execution, no event/score migration.
"""
import base64
import gzip
import hashlib
import inspect
import json
from pathlib import Path
import zlib

from physedit.core100_critical import load
from scripts.build_critical_supplement import fixed_context
from scripts.recover_core100_released_scans import normalized
from review.cvpr_experiments_20261031.archive_hunyuan_checkpoint_sftp import rpc, P21_OPTIONS

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'benchmarks/t11_observable_events_candidate_v1_20261103'


def projection(s):
    return dict(
        fixed_context_sha256=fixed_context(s, 'T11'),
        experiment_parameter=s['experiment']['parameter'],
        original_runtime_forces=s.get('runtime_forces', []),
        condition_poses={o['name']: {k: o.get(k) for k in ['position', 'quaternion', 'velocity']}
                         for o in s['frames'][4]['objects']},
        physics_steps_per_render_frame=s['render']['physics_steps_per_render_frame'],
        pre_static_frames=s['render'].get('pre_static_frames'),
        manifest=s.get('manifest'),
    )


def main():
    data, registry = load()
    rows = []
    for sid, cid in [('T11_S01', 'T11_C01'), ('T11_S02', 'T11_C02')]:
        path = ROOT / 'benchmarks/critical_supplement_v1_20261101/evidence' / (sid + '.json.gz')
        raw = path.read_bytes()
        rows.append(dict(clip_id=cid, stored_state_sha256=hashlib.sha256(raw).hexdigest(),
                         projection=projection(json.loads(gzip.decompress(raw)))))
    targets = [dict(clip_id=c['clip_id'], native=c['reference_native_state_binding'])
               for c in data['cases'] if c['clip_id'] in ['T11_C04', 'T11_C05']]
    code = '''
import copy,gzip,hashlib,json
from pathlib import Path
FUNCTIONS
rows=[]
for t in TARGETS:
 raw=Path(t['native']['state_path']).read_bytes()
 decoded=gzip.decompress(raw)if raw[:2]==bytes([31,139])else raw
 assert hashlib.sha256(raw).hexdigest()==t['native']['stored_state_sha256']
 assert hashlib.sha256(decoded).hexdigest()==t['native']['decoded_state_sha256']
 rows.append(dict(clip_id=t['clip_id'],stored_state_sha256=hashlib.sha256(raw).hexdigest(),
                  projection=projection(json.loads(decoded))))
print(json.dumps(rows))
'''.replace('FUNCTIONS', '\n'.join(inspect.getsource(f) for f in [normalized, fixed_context, projection]))
    payload = 'TARGETS=' + repr(targets) + '\n' + code
    encoded = base64.b64encode(zlib.compress(payload.encode())).decode()
    rows += rpc(P21_OPTIONS, 'p25', 'import base64,zlib;exec(zlib.decompress(base64.b64decode(' + repr(encoded) + ')))')
    result = dict(source_registry_sha256=hashlib.sha256(registry.read_bytes()).hexdigest(), rows=rows,
                  simulations_started=0, active_protocol_modified=False)
    base = rows[0]['projection']
    result['comparisons_to_C01'] = [dict(
        clip_id=r['clip_id'],
        same_physical_context=r['projection']['fixed_context_sha256'] == base['fixed_context_sha256'],
        same_condition_poses=r['projection']['condition_poses'] == base['condition_poses'],
        same_frame_clock=r['projection']['physics_steps_per_render_frame'] == base['physics_steps_per_render_frame'],
    ) for r in rows]
    raw = json.dumps(result, ensure_ascii=False, indent=2).encode()
    digest = hashlib.sha256(raw).hexdigest()
    path = OUT / ('published_speed_contexts_' + digest[:12] + '.json')
    path.write_bytes(raw)
    (OUT / 'PUBLISHED_SPEED_CONTEXTS.json').write_text(json.dumps(dict(path=path.name, sha256=digest), indent=2))
    print(json.dumps(result['comparisons_to_C01']))


if __name__ == '__main__':
    main()
