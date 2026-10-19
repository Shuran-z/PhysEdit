"""Audit published T16--T19 directories against original search and repair provenance."""
import json,subprocess
from pathlib import Path

REMOTE=r'''
import pathlib,json,hashlib
root=pathlib.Path('/data_cached/wangzijun_p25/isaac_out/Isaac_T16-T19_Dataset')
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def read(p):return json.loads(p.read_text())
out=[]
for scene in ['T16','T17','T18','T19']:
 for folder in sorted((root/scene).iterdir()):
  if not folder.is_dir():continue
  try:
   c=read(folder/'config.json');m=folder/'metadata';d=read(m/'delivery.json');q=read(m/'qa.json');e=read(m/'event_graph.json')
   prod=c.get('production',{});param=c.get('parameter',{})
   row=dict(sample_id=folder.name,scene_id=scene,folder=str(folder),parameter=param,production=prod,
     config_sha256=sha(folder/'config.json'),event_sha256=sha(m/'event_graph.json'),qa_sha256=sha(m/'qa.json'),
     qa_status=q.get('status'),depth=e.get('depth'),source_output=d.get('source_output'),
     delivery_hashes_match=sha(folder/'config.json')==d.get('config_sha256') and all((m/n).exists() and sha(m/n)==h for n,h in d.get('metadata_sha256',{}).items()),
     videos_exist=all((folder/('cam%02d.mp4'%i)).exists() for i in [1,2,3]),
     classification=c.get('classification'),scientific_revalidation_performed=d.get('scientific_revalidation_performed'),
     media_qa=read(m/'media_qa.json').get('status'),physics=c.get('physics'),schema=c.get('schema'))
   source=pathlib.Path(d.get('source_output','/nonexistent'))
   row['source_input_exists']=(source/'input.json').exists()
   row['source_config_matches']=row['source_input_exists'] and sha(source/'input.json')==row['config_sha256']
   out.append(row)
  except Exception as exc:out.append(dict(sample_id=folder.name,scene_id=scene,error=str(exc)))
print(json.dumps(out))
'''

def main():
 out=Path('review/release_boundary_binding_20261018');out.mkdir(exist_ok=False)
 r=subprocess.run(['ssh','p25','python3 -'],input=REMOTE.encode(),capture_output=True,timeout=240)
 (out/'delivery_records.json').write_bytes(r.stdout);(out/'stderr.txt').write_bytes(r.stderr)
 r.check_returncode();rows=json.loads(r.stdout)
 old=json.loads(Path('review/all_scene_boundary_audit_20261018/isaac_boundary_status.json').read_text())
 status={item['output']:(g['status'],item) for c in old['cells'].values() for g in c.get('groups',{}).values() for item in g.get('outputs',[])}
 for row in rows:
  found=status.get(row.get('source_output'));row['search_source_exact_match']=bool(found)
  if found:
   group,item=found;row['search_group_status']=group
   row['search_hashes_match']=item.get('input_sha256')==row.get('config_sha256') and item.get('qa_sha256')==row.get('qa_sha256')
  else:row['search_group_status']='not_in_original_boundary_outputs'
  row['route']='needs_review'
  if (row.get('delivery_hashes_match') and row.get('source_config_matches') and row.get('videos_exist')
      and row.get('search_hashes_match') and row.get('qa_status')=='PASS'
      and row.get('production',{}).get('measured_bracket')
      and row['search_group_status']=='BOUNDARY_PASS_VISUAL_REVIEW_PENDING'):
   row['route']='matched_search_visual_review_pending'
 (out/'matched_registry.json').write_text(json.dumps(rows,ensure_ascii=False,indent=2),encoding='utf-8')
 import collections
 summary={s:dict(total=sum(r['scene_id']==s for r in rows),routes=dict(collections.Counter(r['route'] for r in rows if r['scene_id']==s)),sources=dict(collections.Counter('repair' if 'repair_' in (r.get('source_output') or '') else 'original_or_other' for r in rows if r['scene_id']==s))) for s in ['T16','T17','T18','T19']}
 (out/'summary.json').write_text(json.dumps(summary,indent=2));print(json.dumps(summary))

if __name__=='__main__':main()
