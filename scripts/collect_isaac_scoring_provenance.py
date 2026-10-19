"""Read frozen scan ranges and hash-bound event/video provenance for original Isaac groups."""
import base64,gzip,json,subprocess
from pathlib import Path
OUT=Path('review/scene_family_completion_20261018')
rows=json.loads(Path('review/release_boundary_binding_20261018/matched_registry.json').read_text())
rows=[{k:r[k] for k in ['sample_id','folder','production','config_sha256','event_sha256','qa_sha256']} for r in rows if r['route']=='matched_search_visual_review_pending']
code=r'''
import pathlib,json,hashlib,gzip,base64
root=pathlib.Path('/home/wangzijun_p25/liyuhan/isaac_sim_everyday_bifurcation/repro_t16_t20_13200_20260919')
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
planpath=root/'production_plan.json';plan=json.loads(planpath.read_text());cells={c['id']:c for c in plan['cells']};ranges={}
for cell in {r['production']['cell'] for r in ROWS}:
 vals=[];checks=[]
 for name in cells[cell]['global_inputs']:
  p=pathlib.Path(name);c=json.loads(p.read_text());parameter=c['parameter']
  vals.append(parameter.get('withdrawal_distance_m',parameter.get('value')));checks.append(sha(p)==plan['input_hashes'][name])
 ranges[cell]=dict(domain=[min(vals),max(vals)],normalization_span=max(vals)-min(vals),all_frozen_input_hashes_match=all(checks),source=str(planpath),source_sha256=sha(planpath))
result=[]
for row in ROWS:
 p=pathlib.Path(row['folder']);m=p/'metadata';complete=json.loads((m/'complete.json').read_text());c=json.loads((p/'config.json').read_text())
 checks={'config':sha(p/'config.json')==row['config_sha256']==complete['files']['input.json']}
 metadata={}
 for name in ['qa.json','event_graph.json','camera_visibility.json','media_qa.json']:
  q=m/name;metadata[name]=json.loads(q.read_text());checks[name]=sha(q)==complete['files'].get(name)
 video_hashes={}
 for cam in ['cam01','cam02','cam03']:
  value=sha(p/(cam+'.mp4'));video_hashes[cam]=value;checks[cam]=value==complete['files'].get(cam+'.mp4')
 result.append(dict(sample_id=row['sample_id'],range=ranges[row['production']['cell']],hash_checks=checks,all_hashes_match=all(checks.values()),metadata=metadata,complete=complete,video_hashes=video_hashes,parameter=c['parameter'],physics=c['physics'],event_spec=c.get('event_spec'),production=c['production']))
print(base64.b64encode(gzip.compress(json.dumps(result).encode())).decode())
'''
packed=base64.b64encode(gzip.compress(json.dumps(rows).encode())).decode()
code='import base64,gzip,json\nROWS=json.loads(gzip.decompress(base64.b64decode('+repr(packed)+')))\n'+code
p=subprocess.run(['ssh','-o','BatchMode=yes','-o','ConnectTimeout=10','p25','python3 -'],input=code.encode(),capture_output=True,timeout=240);p.check_returncode()
b=gzip.decompress(base64.b64decode(p.stdout));(OUT/'isaac_original_scoring_provenance.json').write_bytes(b)
a=json.loads(b);print(json.dumps(dict(samples=len(a),all_hashes_match=sum(r['all_hashes_match'] for r in a),ranges_valid=sum(r['range']['all_frozen_input_hashes_match'] for r in a))))
