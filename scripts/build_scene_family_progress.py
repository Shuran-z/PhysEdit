"""Build all-20 scene coverage from observed records; missing is never 'not searched'."""
import collections,hashlib,json
from pathlib import Path
OUT=Path('review/scene_family_completion_20261018')
def main():
 inventory=[json.loads(l) for l in Path('../dataset_splits_v2/all_selected_trajectories.jsonl').read_text(encoding='utf-8').splitlines()]
 gen={r['sample_id']:r for r in inventory if r['engine']=='genesis'}
 task_links={r['sample_id']:r['original_task_candidates'] for r in [json.loads(l) for l in Path('review/original_search_tasks_20261018/inventory_task_links.jsonl').read_text(encoding='utf-8').splitlines()] if r['engine']=='genesis'}
 candidates=collections.defaultdict(list)
 sources=[(host,OUT/f'{host}_configs.json') for host in ['p25','p26']]
 sources += [('huggingface_exact_revision',p) for p in sorted(OUT.glob('published_batch_*.json'))]
 sources += [('huggingface_exact_revision',p) for pattern in ['recovered_sidecar_batch_*.json','recovered_sidecar_local_*.json'] for p in sorted(OUT.glob(pattern))]
 for host,source in sources:
  for r in json.loads(source.read_text(encoding='utf-8')):
   if 'config' not in r:continue
   c=r['config'];e=c.get('experiment',{});p=Path(r['path'])
   aliases=[r.get('sample_id'),e.get('trajectory_id'),p.parent.name,p.stem.split('__cam01')[0]]
   ids={s for s in aliases if s in gen}
   if not ids:continue
   param=e.get('parameter',{});param=param if isinstance(param,dict) else {}
   family=e.get('counterfactual_group') or e.get('causal_parameter_group') or param.get('parameter_name') or c.get('sample_metadata',{}).get('counterfactual_boundary') or e.get('sweep_id')
   value=e.get('controlled_value',param.get('parameter_value'))
   if value is None and isinstance(family,str) and '_' in family:value=e.get(family.split('_',1)[-1])
   contract=dict(dynamic_objects=c.get('dynamic_objects'),physics=c.get('scene_overrides'))
   physical_hash=hashlib.sha256(json.dumps(contract,sort_keys=True).encode()).hexdigest()
   for sid in ids:
    candidates[sid].append(dict(host=host,path=r['path'],config_sha256=r['sha256'],
     embedded_sample_id=r.get('sample_id'),original_family=family,original_parameter_value=value,
     evidence_kind=r.get('evidence_kind','original_config'),
     original_parameter=param,formal_design=e.get('formal_design'),declared_controlled_variable=e.get('controlled_variable'),
     configuration_candidate_hash=physical_hash,scene_family_id=e.get('scene_family_id'),
     original_event_graph=e.get('event_graph',e.get('event_sequence')),source_video_path=c.get('render',{}).get('save_video'),
     status='config_candidate_not_yet_release_identity_certified'))
 registry=[]
 for sid,r in gen.items():
  rows=candidates.get(sid,[])
  registry.append(dict(scene_id=r['event_id'],sample_id=sid,release=r.get('release'),revision=r.get('revision'),
   candidates=rows,candidate_configuration_variants=len({x['configuration_candidate_hash'] for x in rows}),
   original_task_candidates=task_links.get(sid,[]),
   status='original_config_candidates_found' if rows else 'original_config_not_located_in_current_search'))
 with (OUT/'all_scene_family_registry.jsonl').open('w',encoding='utf-8') as f:
  for r in registry:f.write(json.dumps(r,ensure_ascii=False)+'\n')
 summary=[]
 for i in range(1,21):
  scene=f'T{i:02}';rows=[r for r in registry if r['scene_id']==scene]
  summary.append(dict(scene_id=scene,genesis_inventory=len(rows),genesis_config_candidates=sum(bool(r['candidates']) for r in rows),
   genesis_original_task_candidates=sum(bool(r['original_task_candidates']) for r in rows),
   genesis_multiple_configuration_candidates=sum(r['candidate_configuration_variants']>1 for r in rows),
   observed_family_names=sorted({str(c['original_family']) for r in rows for c in r['candidates'] if c['original_family']}),
   isaac_inventory=sum(r['engine']=='isaac' and r['event_id']==scene for r in inventory),
   scope='frozen historical inventory, not final current release or training split',all_boundaries_completed=False))
 (OUT/'all20_progress.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding='utf-8')
 print(json.dumps([{k:v for k,v in r.items() if k not in ['observed_family_names','scope']} for r in summary]))
if __name__=='__main__':main()
