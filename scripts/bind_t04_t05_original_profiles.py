"""Match original T04/T05 profile functions to recovered configurations.

The builder supplies intervention designs, not solved thresholds or event truth.
"""
import collections,gzip,importlib.util,json,math
from pathlib import Path
from physedit.boundary import digest
from scripts.audit_t02_runtime_contexts import diff
OUT=Path('review/scene_family_completion_20261018')

def main():
 source=OUT/'t04_t05_original_builder.py'
 spec=importlib.util.spec_from_file_location('original_t04_t05_profiles',source)
 builder=importlib.util.module_from_spec(spec);spec.loader.exec_module(builder)
 candidates={}
 for f in [OUT/'p25_configs.json',OUT/'p26_configs.json',*sorted(OUT.glob('recovered_sidecar_local_*.json'))]:
  for r in json.loads(f.read_text(encoding='utf-8')):
   c=r.get('config',{});e=c.get('experiment',{});sid=e.get('trajectory_id')
   if sid and sid.startswith(('T04F880V1__','T05F880V1__')):candidates[sid]=(r,c,f)
 # Fill gaps from exact-release full states recovered after the original projection.
 for scene in ['T04','T05']:
  for f in sorted((OUT/'completion_states').glob(scene+'_*.json')):
   for record in json.loads(f.read_text(encoding='utf-8')):
    sid=record['sample_id']
    if sid in candidates or not record.get('local_path'):continue
    path=Path(record['local_path'])
    if digest(path)!=record['sha256']:raise ValueError('recovered state identity changed')
    raw=path.read_bytes();state=json.loads(gzip.decompress(raw) if raw[:2]==b'\x1f\x8b' else raw)
    c={k:v for k,v in state.items() if k in ['experiment','manifest','scene_overrides','dynamic_objects','runtime_forces','render','time_diagnostic']}
    c['dynamic_objects']=[o.get('spec',o) for o in c['dynamic_objects']]
    if c['experiment'].get('trajectory_id')!=sid:raise ValueError('state sample identity mismatch')
    candidates[sid]=({'path':record['sidecar'],'sha256':record['sha256']},c,f)
 rows=[]
 for sid,(r,c,f) in sorted(candidates.items()):
  scene=sid[:3];e=c['experiment'];d=e['formal_design'];g=e['gravity_id'];bg=e['background_id']
  profiles=builder.t04_profiles() if scene=='T04' else builder.t05_profiles(g,abs(builder.GRAVITY_VECTORS[g][2]))
  p=next(x for x in profiles if x['design_id']==d['design_id'] and x['repeat']==d['repeat'])
  clone=json.loads(json.dumps(c))
  (builder.apply_t04_physics if scene=='T04' else builder.apply_t05_physics)(clone,g,p['parameters'])
  changes=[]
  for field in ['dynamic_objects','scene_overrides']:
   if clone[field]!=c[field]:changes.append(field)
  for field in ['parameter','geometry_contract']:
   if clone['experiment'][field]!=e[field]:changes.append('experiment.'+field)
  name=p['changed_variable'];values=[x['parameters'][name] for x in profiles if x['changed_variable']==name]
  domain=[min(values),max(values)]
  repair=e.get('contact_stability_fix')
  rows.append(dict(sample_id=sid,scene_id=scene,engine='genesis',family_id=p['boundary_role'],
   parameter_name=name,theta=p['parameters'][name],parameter_unit='m/s' if name in ['extraction_speed_mps','initial_speed_mps'] else 'm' if name.endswith('_m') else 'dimensionless',
   profile_matches_physical_fields=not changes,physical_mismatch_fields=changes,
   physical_differences=diff(c,clone),
   original_seed_matches=e.get('seed')==builder.stable_seed(scene,bg,g,p['design_id'],p['repeat']),
   repair_record=repair,
   effective_parameter_value=e['parameter'].get('gap_ratio') if name=='gap_ratio' else p['parameters'][name],
   fixed_context_effective_gap_ratio=e['parameter'].get('gap_ratio') if scene=='T05' and name!='gap_ratio' else None,
   repair_requires_separate_boundary=bool(repair or changes),
   physical_revision_evidence='explicit_repair_record' if repair else 'unmarked_physical_profile_difference' if changes else 'original_profile_match',
   source_group_id='__'.join([scene,bg,g]),repeat=p['repeat'],design=p['design'],
   normalization_basis=dict(domain=domain,normalization_span=domain[1]-domain[0],rule='original formal profile range for the same changed variable and gravity',source=str(source.resolve()),source_sha256=digest(source)),
   config_source=str(f.resolve()),config_path=r['path'],config_source_sha256=r['sha256'],
   boundary={'status':'unavailable'},reference_label=None,
   status='matched_original_design_not_solved_boundary' if not changes else 'physical_contract_mismatch',
   note='minus/star/plus are original profile names, not measured outcome labels; preserve all branches'))
 (OUT/'t04_t05_profile_bindings.json').write_text(json.dumps(rows,indent=2),encoding='utf-8')
 summary={s:dict(configs=sum(r['scene_id']==s for r in rows),physical_profile_matches=sum(r['scene_id']==s and r['profile_matches_physical_fields'] for r in rows),families=dict(collections.Counter(str(r['family_id']) for r in rows if r['scene_id']==s))) for s in ['T04','T05']}
 (OUT/'t04_t05_profile_binding_summary.json').write_text(json.dumps(summary,indent=2),encoding='utf-8');print(json.dumps(summary))
if __name__=='__main__':main()
