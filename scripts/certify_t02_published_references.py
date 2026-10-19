"""Run original family-aware T02 event extractor on exact published states."""
import collections,gzip,json,sys,tempfile
from pathlib import Path
from physedit.boundary import digest,distance
from scripts.audit_t02_runtime_contexts import physics,diff
OUT=Path('review/scene_family_completion_20261018')
def main():
 sys.path.insert(0,str((OUT/'t02_original_auditor').resolve()))
 import audit_t02_full_chain_calibration as audit
 source=OUT/'t02_runtime_distance_registry.json';distances={r['sample_id']:r for r in json.loads(source.read_text())}
 configs={r['config'].get('experiment',{}).get('trajectory_id',r['config'].get('sample_id')):r['config'] for r in json.loads((OUT/'p26_configs.json').read_text(encoding='utf-8')) if 'config' in r}
 original=Path('review/original_search_tasks_20261018/t02_original_family_bindings.json');bindings=json.loads(original.read_text());groups=collections.defaultdict(list)
 for r in bindings:groups[(r['gravity_id'],r['family'])].append(r['theta'])
 receipts={r['sample_id']:r for f in OUT.glob('t02_state_receipt_*.json') for r in json.loads(f.read_text()) if 'path' in r}
 results=[]
 for sid,r in sorted(receipts.items()):
  raw=Path(r['path']);assert digest(raw)==r['sha256'];data=json.loads(gzip.decompress(raw.read_bytes()));base=distances[sid];c=configs[sid]
  differences=diff(physics(c,None),physics(data,None));forces_match=c.get('runtime_forces',[])==data.get('runtime_forces',[])
  with tempfile.TemporaryDirectory() as folder:
   p=Path(folder)/(sid+'__cam01.json');p.write_text(json.dumps(data),encoding='utf-8');a=audit.audit_one(p,write=False)
  event=base['target_event'];frame=a.get('event_frames',{}).get(event);event_registered=event in a.get('event_frames',{});label=int(frame is not None and frame>=0) if event_registered else None
  values=groups[(base['gravity_id'],base['family_id'])];low,high=min(values),max(values)
  intervals=base['boundary']['intervals'];checks=dict(published_state_hash_matches=True,published_physics_matches_original_config=not differences,runtime_forces_match=forces_match,original_family_audit_pass=a['status']=='PASS',event_defined=event_registered,unique_local_interval=len(intervals)==1,normalization_positive=high>low)
  x={**base,'reference_label':label,'reference_event_frame':frame,'reference_state_sha256':r['sha256'],'published_state_receipt':r,'original_event_audit':a,'published_physics_differences':differences,'numerical_checks':checks,'numerical_reference_verified':all(checks.values()),'normalization_basis':dict(rule='span of frozen original formal matrix within gravity and original parameter family',domain=[low,high],source=str(original.resolve()),source_sha256=digest(original)),'boundary':dict(status='verified' if all(checks.values()) else 'unavailable',bracket=intervals[0]['bracket'],normalization_span=high-low,source=str(source.resolve()),source_sha256=digest(source)),'blocking_reasons':['reference_rgb_observability_pending'],'rgb_observability_status':'pending'}
  x['distance']=distance(x);x['near_numerical_eligible']=x['numerical_reference_verified'] and x['distance']['bin']=='near';results.append(x)
  x['mapping_status']='matched' if not differences and forces_match else 'mismatch'
  x['mapping_evidence']={'published_revision':r['revision'],'state_sha256':r['sha256'],'physics_differences':differences,'original_runtime_context_sha256':base['context_source_sha256']}
  x['original_event_audit']['metadata_path']=str(raw.resolve())
 (OUT/'t02_published_scoring_registry.json').write_text(json.dumps(results,indent=2),encoding='utf-8')
 print(json.dumps(dict(downloaded=len(results),numerically_verified=sum(r['numerical_reference_verified'] for r in results),near_numerical=sum(r['near_numerical_eligible'] for r in results),bins=dict(collections.Counter(str(r['distance']['bin']) for r in results)),failed_checks=dict(collections.Counter(k for r in results for k,v in r['numerical_checks'].items() if not v)))))
if __name__=='__main__':main()
