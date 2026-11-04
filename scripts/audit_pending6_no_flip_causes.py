"""Audit original sample design and executed mechanisms; no new model inputs."""
import ast
import hashlib
import json
from pathlib import Path

from scripts.boundary_ssh import remote_text

ROOT=Path(__file__).resolve().parents[1]
WORK=ROOT/'review/core100_continue_20261031'
REMOTE=r'''
import gzip,hashlib,json,math
from pathlib import Path
out=dict(selected_native_readbacks=[],original_t11_published_states=[])
specs=[('T04_C01','core100_continue_original_20261031/T04_C01',['0','0.1','0.15','0.2','2']),
 ('T05_C01','core100_continue_families_20261031/T05_C01',['0.01','0.03125','0.049']),
 ('T10_C01','core100_continue_original_20261031/T10_C01',['0.08','0.217']),
 ('T10_C02','core100_continue_original_20261031/T10_C02',['0.08','0.217']),
 ('T11_C01','core100_continue_families_20261031/T11_C01__G_global_original',['0','1']),
 ('T11_C02','core100_continue_families_20261031/T11_C02__G_global_original',['0','1'])]
for cid,name,values in specs:
 root=Path('/data2/liyuhan')/name;job=json.loads((root/'jobs.json').read_text())[0]
 for value in values:
  p=root/cid/'profile_0'/value/'receipt.json'
  if not p.exists():
   p=next(q for q in (root/cid/'profile_0').glob('*/receipt.json')if q.parent.name!='source_repeat'and abs(json.loads(q.read_text())['theta']-float(value))<1e-9)
  receipt=json.loads(p.read_text());sp=Path(receipt['state_path']);raw=gzip.decompress(sp.read_bytes())
  assert hashlib.sha256(raw).hexdigest()==receipt['state_sha256']
  cp=sp.parent/'config.json';assert hashlib.sha256(cp.read_bytes()).hexdigest()==receipt['config_sha256']
  state=json.loads(raw);c=json.loads(cp.read_text());frames=state['frames'];assert len(frames)==210
  item=dict(clip_id=cid,theta=receipt['theta'],receipt=str(p),state_sha256=receipt['state_sha256'],config_sha256=receipt['config_sha256'],
   source_reference_video_sha256=job['reference_video_sha256'],labels=receipt['labels'],
   effective_entity_properties=state.get('physics_debug',{}).get('effective_entity_properties'),
   runtime_force_summary=state.get('runtime_force_summary',[]),parameter=c['experiment']['parameter'])
  if cid.startswith('T04'):
   track=[next(o['position']for o in f['objects']if o['name']=='t04v3_removable_support_bar')for f in frames]
   threshold=c['experiment']['parameter']['estimated_support_release_threshold_m']
   item['support_release_geometry_diagnostic']=dict(original_threshold_m=threshold,
    first_threshold_cross_frame=next((i for i,v in enumerate(track[:155])if v[1]-track[4][1]>=threshold),None),
    maximum_extraction_m=max(v[1]-track[4][1]for v in track[:155]),
    substitutes_for_full_chain=False)
  elif cid.startswith('T05'):
   track=[next(o for o in f['objects']if o['name']=='t05v2_moving_phone')for f in frames]
   pairs=[(f['frame_index'],a['entity_a'],a['entity_b'])for f in frames[5:155]for a in f.get('contacts',[])if
    't05v2_moving_phone'in[a['entity_a'],a['entity_b']]and any('guide'in n for n in [a['entity_a'],a['entity_b']])]
   item['full_passage_diagnostic']=dict(maximum_center_x_m=max(o['position'][0]for o in track[5:155]),
    full_passage_center_x_m=job['full_pass_x_m'],first_guide_contact_frame=min([a[0]for a in pairs],default=None),
    initial_center=track[4]['position'],initial_projected_width_m=c['experiment']['parameter']['phone_projected_width_at_initial_yaw_m'],
    declared_gap_width_m=c['experiment']['parameter']['gap_width_m'],entry_is_not_a_positive_label=True)
  elif cid.startswith('T10'):
   baseline=next(o['position']for o in frames[4]['objects']if o['name']=='t10_support_pen')
   distance=[(f['frame_index'],math.dist(baseline,o['position']))for f in frames[5:210]for o in f['objects']if o['name']=='t10_support_pen']
   hit=[f['frame_index']for f in frames[5:210]for a in f.get('contacts',[])if {a['entity_a'],a['entity_b']}=={'t10_tape_roll','t10_support_pen'}]
   item['pen_diagnostic']=dict(first_contact_frame=min(hit,default=None),first_threshold_frame=next((i for i,d in distance if d>=.04),None),
    maximum_displacement_m=max(d for i,d in distance),threshold_m=.04,actual_support_x_m=c['experiment']['t10_design']['support_x_m'])
  out['selected_native_readbacks'].append(item)
for record in ORIGINAL_T11:
 p=Path(record['source_state']);packed=p.read_bytes();raw=gzip.decompress(packed)if p.suffix=='.gz'else packed
 digest=hashlib.sha256(raw).hexdigest();stored=hashlib.sha256(packed).hexdigest()
 assert record['state_sha256']in[digest,stored],str(p)
 state=json.loads(raw);assert len(state['frames'])==210
 positions={o['name']:o['position']for o in state['frames'][154]['objects']}
 labels={n:int(positions[n][2]<-.1)for n in ['t11_driver_eraser','t11_relay_pencil_case','t11_eyeglasses_case']}
 out['original_t11_published_states'].append(dict(sample_id=record['sample_id'],state_path=str(p),raw_state_sha256=digest,
  stored_sha256=stored,end_frame_index=154,labels=labels,original_parameter=state['experiment']['parameter']))
print(json.dumps(out))
'''


def main():
    original=json.loads((ROOT/'review/scene_family_completion_20261018/t11_published_final_states.json').read_text())
    selected=[r for r in original if any('__bg01_home_ase__'+g+'__G_global_'in r['sample_id']for g in ['g01_moon','g02_mars'])]
    assert len(selected)==16
    report=json.loads(remote_text('p25',REMOTE.replace('ORIGINAL_T11',repr(selected)),timeout=180,attempts=1))
    builder=json.loads((WORK/'original_friction_sampling_contract.json').read_text())
    text=builder['source_text'];assert hashlib.sha256(text.encode()).hexdigest()==builder['source_sha256']
    tree=ast.parse(text)
    report['original_builder_design']={node.name:ast.get_source_segment(text,node)
        for node in tree.body if isinstance(node,ast.FunctionDef)and node.name in ['t04_profiles','t05_profiles']}
    report['original_builder_sha256']=builder['source_sha256']
    report['frozen_inputs_modified']=False
    raw=json.dumps(report,indent=2).encode();digest=hashlib.sha256(raw).hexdigest()
    path=WORK/('pending_six_cause_evidence_'+digest[:12]+'.json')
    if path.exists():assert path.read_bytes()==raw
    else:path.write_bytes(raw)
    pointer=dict(evidence=path.relative_to(ROOT).as_posix(),sha256=digest,
        native_selected_points=len(report['selected_native_readbacks']),original_t11_states=len(selected))
    (WORK/'pending_six_cause_latest.json').write_text(json.dumps(pointer,indent=2),encoding='utf8')
    print(json.dumps(pointer))


if __name__=='__main__':main()
