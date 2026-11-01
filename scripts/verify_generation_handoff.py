"""Stdlib-only input verifier. Does not change old videos or annotations."""
import collections,hashlib,json,math
from pathlib import Path
R=Path(__file__).resolve().parent
def verify(root):
 hashes=json.loads((root/'SHA256SUMS.json').read_text(encoding='utf8'))
 for name,h in hashes.items():
  p=(root/name).resolve();assert p.is_relative_to(root.resolve())and p.is_file(),name
  assert hashlib.sha256(p.read_bytes()).hexdigest()==h,name
 rows=[json.loads(l)for l in (root/'tasks_all207.jsonl').read_text(encoding='utf8').splitlines()]
 assert len(rows)==207 and len({r['task_id']for r in rows})==207
 assert collections.Counter(r['group']for r in rows)=={'T17_W5_SUPPLEMENT':27,'T19_ISAAC_V1':180}
 for r in rows:
  assert type(r['seed'])is int and r['prompt_variant']in (1,2,3)
  assert hashlib.sha256(r['prompt'].encode()).hexdigest()==r['prompt_sha256']
  assert (root/r['prompt_file']).read_bytes()==r['prompt'].encode()
  assert hashlib.sha256((root/r['condition_image']).read_bytes()).hexdigest()==r['condition_sha256']
  assert r['minimum_frames_at_recorded_native_fps']==math.ceil(r['evaluation_window_s']*r['recorded_model_native_fps']-1e-9)+1
  assert r['legacy_annotations_reusable']is False and r['output_video'].startswith('outputs/')
  assert 'reference_label'not in r and 'expected_event'not in r
  if r['group']=='T19_ISAAC_V1':
   assert r['reference_release_version']=='core100-t19-isaac-v1-20261031'and r['condition_frame_index']==0
   assert r['evaluation_window_s']==209/30
  else:assert r['condition_frame_index']==4 and r['evaluation_window_s']==5
 counts=collections.Counter((r['model'],r['case_id'])for r in rows if r['group']=='T19_ISAAC_V1');assert len(counts)==60 and set(counts.values())=={3}
 for model in {r['model']for r in rows}:
  own=[json.loads(l)for l in (root/'model_tasks'/f'{model}.jsonl').read_text(encoding='utf8').splitlines()]
  assert own==[r for r in rows if r['model']==model]
 return {'tasks':207,'T17':27,'T19':180,'models':12,'verified_files':len(hashes)}
if __name__=='__main__':print(json.dumps(verify(R),ensure_ascii=False,indent=2))
