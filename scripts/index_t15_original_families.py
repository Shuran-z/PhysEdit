"""Index T15 by recorded search family, not by a velocity-only context hash."""
import collections,hashlib,json
from pathlib import Path
OUT=Path('review/original_search_tasks_20261018')
source=Path('review/t15_boundary_pilot_20261014/reference_audit.json')
audit=json.loads(source.read_text(encoding='utf-8'))
fields={'A_force_transfer':'initial_velocity_mps','B_support_loss':'laptop_edge_margin_m','C_floor_target':'phone_offset_y_scan_m'}
groups=collections.defaultdict(list)
for r in audit['rows']:
 m=r['metadata'];family=m.get('counterfactual_boundary')
 if family not in fields:continue
 key=(m['formal_revision'],m['background_id'],m['gravity_id'],family)
 groups[key].append({'sample_id':r['sample_id'],'original_branch':m['theta'],'repeat':m['repeat'],
   'parameter_field':fields[family],'declared_parameter_value':m.get(fields[family]),
   'actual_phone_xy':[m.get('phone_x_m'),m.get('phone_offset_y_m')],
   'calibrated_source_id':m.get('calibrated_source_id'),'refined_from_sample_id':m.get('refined_from_sample_id'),
   'config':r.get('config'),'output':r.get('output'),'config_sha256':r['config_sha256'],'state_sha256':r['state_sha256'],
   'events':r['events'],'event_frames':r['event_frames']})
rows=[]
for key,points in sorted(groups.items()):
 rows.append(dict(zip(['version','background_id','gravity_id','original_family'],key),
   original_parameter_field=fields[key[-1]],samples=points,
   three_branches_present={p['original_branch'] for p in points}=={'theta_minus','theta_star','theta_plus'},
   sample_count=len(points),binding_status='original_family_recovered_search_result_link_pending',
   note='C uses declared scan coordinate; map to actual physical phone pose before computing distances. No numerical threshold inferred from branch names.'))
result={'source':str(source),'source_sha256':hashlib.sha256(source.read_bytes()).hexdigest(),
        'groups':rows,'counterfactual_samples':sum(len(r['samples']) for r in rows),
        'global_samples':len(audit['rows'])-sum(len(r['samples']) for r in rows)}
(OUT/'t15_original_family_registry.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps({'groups':len(rows),'per_family':dict(collections.Counter(r['original_family'] for r in rows)),
 'counterfactual_samples':result['counterfactual_samples'],'global_samples':result['global_samples']}))
