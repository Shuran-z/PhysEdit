"""Audit the exact 120 conflict videos and export an isolated admitted prompt view."""
from pathlib import Path
import base64
import collections
import gzip
import hashlib
import json
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts.boundary_ssh import remote_text

SOURCE = ROOT / 'review/prompt_revision_20261102'
OUT = ROOT / 'review/t10_groundtruth_resolution_20261102'


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    OUT.mkdir(exist_ok=True)
    audit = json.loads((SOURCE / 'T10_conflict_audit.json').read_text())
    ids = {r['video_id'] for r in audit['rows']}
    probes = json.loads((SOURCE / 'probe_all.json').read_text())
    wanted = [r for r in probes if r['canonical_video_id'] in ids]
    assert len(wanted) == 120
    inputs = [{k: r[k] for k in ['canonical_video_id', 'native_sample_id', 'camera', 'sha256']} for r in wanted]
    published = {r['video_id']: r['published_configs'] for r in audit['rows']}
    for r in inputs:
        r['registered_config_path'] = published[r['canonical_video_id']][0]['path']
    remote = '''from pathlib import Path
import json,hashlib,base64
root=Path('/home/wangzijun_p25/liyuhan/phydataset/ase_asset_importer/everyday_bifurcation_72k_T06_T10_v1')
inputs=INPUTS
rows=[]
for r in inputs:
 n=r['native_sample_id'];cam=r['camera'];name=n+'__'+cam
 directory=root/'outputs/production'/name
 video=directory/'videos'/(name+'.mp4')
 cp=Path(r['registered_config_path'])
 c=json.loads(cp.read_text()) if cp.exists() else {}
 ap=Path(c.get('annotations',{}).get('save_path','/nonexistent'))
 files=[{'path':str(p),'size':p.stat().st_size} for p in directory.rglob('*') if p.is_file()]
 state=[x for x in files if not x['path'].endswith('.mp4')]
 row={**r,'original_video_path':str(video),'video_exists':video.exists(),'output_files':files,
      'same_directory_state_candidates':state,'annotation_path':str(ap),'annotation_exists':ap.is_file(),
      'config_path':str(cp),'config':c}
 if video.exists():
  b=video.read_bytes();row['observed_video_sha256']=hashlib.sha256(b).hexdigest()
  row['video_base64']=base64.b64encode(b).decode()
 if ap.is_file():
  b=ap.read_bytes();row['annotation_sha256']=hashlib.sha256(b).hexdigest()
  row['annotation_base64']=base64.b64encode(b).decode()
 rows.append(row)
logs=[]
for directory in [root/'logs',root/'reports',root.parent/'logs',root.parent/'reports']:
 if not directory.is_dir():continue
 for p in directory.rglob('*'):
  if not p.is_file() or p.stat().st_size>10_000_000 or p.suffix not in ['.log','.txt','.json','.jsonl']:continue
  text=p.read_text(errors='replace')
  hits=[r['native_sample_id'] for r in inputs if r['native_sample_id'] in text]
  if hits:logs.append({'path':str(p),'sha256':hashlib.sha256(p.read_bytes()).hexdigest(),'matched_samples':sorted(set(hits))})
print(json.dumps({'rows':rows,'matching_logs':logs}))
'''.replace('INPUTS', repr(inputs))
    result = json.loads(remote_text('p25', remote, timeout=120))
    media = OUT / 'groundtruth'
    media.mkdir(exist_ok=True)
    for r in result['rows']:
        vid = r['canonical_video_id']
        b = base64.b64decode(r.pop('video_base64'))
        assert hashlib.sha256(b).hexdigest() == r['sha256'] == r['observed_video_sha256']
        (media / (vid + '.mp4')).write_bytes(b)
        if 'annotation_base64' in r:
            (media / (vid + '.annotation')).write_bytes(base64.b64decode(r.pop('annotation_base64')))
    (OUT / 'SOURCE_AUDIT.json').write_text(json.dumps(result, indent=2), encoding='utf8')
    print(json.dumps({'videos_verified':len(result['rows']), 'annotations_found':sum(r['annotation_exists'] for r in result['rows']),
                      'state_candidate_files':sum(len(r['same_directory_state_candidates']) for r in result['rows']),
                      'matching_logs':len(result['matching_logs'])}))


if __name__ == '__main__':
    main()
