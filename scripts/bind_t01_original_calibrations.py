"""Join original T01 calibrated runtime contracts to current published state outcomes."""
import collections
import copy
import gzip
import hashlib
import json
from pathlib import Path

from physedit.boundary import digest

ROOT=Path('review/scene_family_completion_20261018')


def context(config,family):
    objects=copy.deepcopy(config['dynamic_objects'])
    objects=[o.get('spec',o) for o in objects]
    for obj in objects:
        name=obj['name']
        if family=='A' and name in ['t01v2_folder_ramp','t01v2_sliding_book']:obj['friction']='<intervention>'
        if family=='B' and name in ['t01v2_chain_can_2','t01v2_chain_mug']:
            obj['pose']['position'][0]-=config['experiment']['parameter']['can_1_can_2_gap_control_m']
        if family=='C' and name in ['t01v2_tabletop_collision_slab','t01v2_chain_can_1','t01v2_chain_can_2','t01v2_chain_mug']:obj['friction']='<intervention>'
    def rounded(value):
        if isinstance(value,float):return round(value,10)
        if isinstance(value,list):return [rounded(v) for v in value]
        if isinstance(value,dict):return {k:rounded(v) for k,v in value.items()}
        return value
    c=dict(objects=objects,scene={k:v for k,v in config['scene_overrides'].items() if not k.startswith('raytracing')},manifest=config['manifest'],
        runtime_forces=config.get('runtime_forces') or [],random_seed=config['experiment'].get('random_seed'),timing={k:config['render'].get(k) for k in ['fps','frames','pre_static_frames','physics_steps_per_render_frame']})
    return hashlib.sha256(json.dumps(rounded(c),sort_keys=True).encode()).hexdigest()


def label(audit,family):
    if family=='C':return int(audit['outcome_label']=='full_chain')
    return int(audit['stage_frames']['book_can_1' if family=='A' else 'can_1_can_2'] is not None)


def main():
    sources=[r for p in ROOT.glob('t01_original_calibration_contracts_*_20261019.json') for r in json.loads(p.read_text(encoding='utf-8')) if 'original_config' in r]
    current=json.loads((ROOT/'t01_measured_published_events_20261019.json').read_text(encoding='utf-8'))
    if len(current)!=880:raise ValueError('T01 state audit incomplete')
    groups=collections.defaultdict(list)
    for source in sources:
        c=source['original_config'];p=c['experiment']['parameter']
        for family,key in [('A','ramp_friction_coefficient'),('B','can_1_can_2_gap_control_m'),('C','chain_surface_friction_coefficient')]:
            theta=p.get(key)
            if not isinstance(theta,(float,int)):continue
            groups[(family,context(c,family))].append(dict(theta=theta,label=label(source['original_audit'],family),original_audit=source['original_audit'],config_sha256=source['config_sha256'],report_sha256=source['report_sha256']))
    result=[];conflicts=[];matched=0
    for row in current:
        b=row['original_family'];family=b['family']
        if not family:continue
        raw=Path(row['local_path']).read_bytes()
        if hashlib.sha256(raw).hexdigest()!=row['sha256']:raise ValueError('T01 state identity changed')
        d=json.loads(gzip.decompress(raw) if raw[:2]==b'\x1f\x8b' else raw)
        candidates=groups.get((family,context(d,family)))
        if not candidates:continue
        matched+=1;values=collections.defaultdict(list)
        for c in candidates:values[c['theta']].append(c)
        consistent={t:rr for t,rr in values.items() if len({r['label'] for r in rr})==1}
        if b['theta'] in consistent and consistent[b['theta']][0]['label']!=label(row['audit'],family):
            conflicts.append(row['sample_id']);continue
        intervals=[]
        for a,z in zip(sorted(consistent),sorted(consistent)[1:]):
            left,right=consistent[a][0],consistent[z][0]
            if left['label']!=right['label']:intervals.append(dict(bracket=[a,z],labels=[left['label'],right['label']],config_sha256=[left['config_sha256'],right['config_sha256']],report_sha256=[left['report_sha256'],right['report_sha256']]))
        if intervals:result.append(dict(scene_id='T01',engine='genesis',sample_id=row['sample_id'],family_id=family,theta=b['theta'],target_event={'A':'book_can_1_contact','B':'can_1_can_2_contact','C':'full_chain'}[family],reference_label=label(row['audit'],family),reference_state_sha256=row['sha256'],original_intervals=intervals,original_calibrated_star=b['original_calibrated_star'],
            quality_gate_pass=row['audit']['quality_gate_pass'],status='original_calibration_contract_matched_missing_source_states_repeat_and_rgb_review_pending',formal_nearacc_eligible=False))
    (ROOT/'t01_original_calibration_bindings_20261019.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
    summary=dict(published_states=880,source_configs=len(sources),physical_context_matches=matched,bound_original_intervals=len(result),conflicting_reference_labels=conflicts,formal_new_near=0)
    (ROOT/'t01_original_calibration_summary_20261019.json').write_text(json.dumps(summary,indent=2),encoding='utf-8');print(json.dumps(summary))


if __name__=='__main__':main()
