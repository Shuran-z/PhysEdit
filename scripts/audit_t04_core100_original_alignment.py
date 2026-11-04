"""Read original T04 states; retain event identities, conflicting repeats and existing thresholds."""
import collections,concurrent.futures,copy,gzip,hashlib,json,math,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT));from scripts.recover_core100_released_scans import context,observe,intervals
O=ROOT/'review/t04_critical_followup';S=ROOT/'review/scene_family_completion_20261018/completion_states/T04'
def sha(b):return hashlib.sha256(b).hexdigest()
def worker(path):
 p=Path(path);packed=p.read_bytes();raw=gzip.decompress(packed);d=json.loads(raw);theta,labels=observe(d,'T04');frames=d['frames'];first=frames[4];ss='t04v3_removable_support_bar';bar0=next(o for o in first['objects'] if o['name']==ss);dy=max(abs(next(o['position'][1] for o in f['objects'] if o['name']==ss)-bar0['position'][1])for f in frames[4:155]);clearance=d['experiment']['parameter']['estimated_support_release_threshold_m'];seed=d['experiment'].get('seed');r=dict(sample_id=p.name.removesuffix('.json.gz'),theta=theta,labels=labels,fixed_context_sha256=context(d,'T04'),state_path=str(p),stored_state_sha256=sha(packed),state_sha256=sha(raw),source_seed=seed,render_timing={k:d['render'].get(k) for k in ['fps','frames','pre_static_frames','physics_steps_per_render_frame']},auxiliary_support_clearance_observation=dict(original_clearance_m=clearance,max_absolute_y_displacement_m=dy,reaches_declared_clearance=int(dy>=clearance),formal_target=False,reason='A recorded geometric clearance is not a replacement for the original full_chain event.'),original_formal_design=d['experiment'].get('formal_design'))
 return r
if __name__=='__main__':
 cases=json.loads((O/'source_site/core100_active_distance_bindings.json').read_text(encoding='utf8'))['cases'];targets=[x for x in cases if x['clip_id'].startswith('T04')];wanted={x['sample_id']:x for x in targets};prefixes={n.split('__global_')[0].split('__cf_')[0] for n in wanted};paths=[str(p) for p in S.glob('*.gz') if any(p.name.startswith(pref+'__') for pref in prefixes)];print('state_files',len(paths),flush=True)
 with concurrent.futures.ProcessPoolExecutor(8) as pool:points=list(pool.map(worker,paths,chunksize=2))
 byid={p['sample_id']:p for p in points};out=[]
 for c in targets:
  source=byid[c['sample_id']];same=[p for p in points if p['fixed_context_sha256']==source['fixed_context_sha256']];ivs,groups=intervals(same,'original_full_chain');observations=[]
  for g in groups:
   rr=g['endpoints'];observations.append(dict(theta=g['theta'],consensus_label=g['label'],full_chain_labels=[p['labels']['original_full_chain'] for p in rr],support_clearance_labels=[p['auxiliary_support_clearance_observation']['reaches_declared_clearance'] for p in rr],source_seeds=[p['source_seed'] for p in rr],samples=[p['sample_id'] for p in rr]))
  old=[{'bracket':b['bracket'],'endpoint_labels':b['endpoint_labels']} for b in c['boundary_records']];new=[{'bracket':b['bracket'],'endpoint_labels':b['labels']} for b in ivs]
  assert old==new,(c['clip_id'],old,new)
  out.append(dict(clip_id=c['clip_id'],reference_video_sha256=c['reference_video_sha256'],registered_source_state_matches=source['state_sha256']==c.get('source_state_sha256'),reference_label=source['labels']['original_full_chain'],theta=source['theta'],fixed_context_sha256=source['fixed_context_sha256'],normalization_domain=c['normalization_domain'],original_event='original_full_chain',formal_support_release_event_registered=False,source=source,matched_points=len(same),point_observations=observations,confirmed_intervals=new,all_previous_intervals_reproduced=True,intervals=ivs,original_scores_modified=False))
 (O/'ORIGINAL_STATE_READBACK.json').write_text(json.dumps({'state_files_read':len(paths),'cases':out,'simulations_started':0,'new_thresholds':0},ensure_ascii=False,indent=2),encoding='utf8');(O/'STATE_POINTS.json').write_text(json.dumps(points,ensure_ascii=False,indent=2),encoding='utf8');print(json.dumps([{'clip_id':r['clip_id'],'points':r['matched_points'],'intervals':r['confirmed_intervals'],'point_observations':r['point_observations']} for r in out],ensure_ascii=True),flush=True)
