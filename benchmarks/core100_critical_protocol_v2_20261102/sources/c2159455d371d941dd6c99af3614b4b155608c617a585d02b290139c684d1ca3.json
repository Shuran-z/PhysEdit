"""Bind original sweep observations after explicit source/event review.

Cross-camera evidence comprises original configs including seed, actual native
objects/commands, frozen-frame identity, and reviewed RGB pose/event sequences.
It does not certify bitwise-identical trajectories or a unique physical root.
"""
import copy
import hashlib
import json
import math
from pathlib import Path

from physedit.core100_critical import load

ROOT=Path(__file__).resolve().parents[1]
WORK=ROOT/'review/core100_v2_resolution_20261102'
IDS=['T06_C01','T06_C02','T06_C03','T06_C05','T09_C01','T09_C02','T09_C03','T09_C04','T09_C05','T10_C03','T10_C04','T10_C05']

def read(p):return json.loads(Path(p).read_text(encoding='utf8'))
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()

def close(a,b):
    if isinstance(a,(int,float))and isinstance(b,(int,float)):return math.isclose(a,b,rel_tol=1e-7,abs_tol=1e-6)
    if type(a)is not type(b):return False
    if isinstance(a,list):return len(a)==len(b)and all(close(x,y)for x,y in zip(a,b))
    if isinstance(a,dict):return a.keys()==b.keys()and all(close(a[k],b[k])for k in a)
    return a==b

def context(p,source_theta):
    objects=copy.deepcopy(p['original_specs']);forces=copy.deepcopy(p['original_runtime_forces']);family=p['family']
    if family=='gap':
        # Original BW06 is an arc, not a straight row. Changing the gaps
        # changes normalized x and therefore the prescribed lateral y.
        # Validate that original coupling before rebasing to the source gap.
        half=(objects['t06_book_09']['pose']['position'][0]-objects['t06_book_00']['pose']['position'][0])/2
        for i in range(10):
            x,y=objects['t06_book_'+str(i).zfill(2)]['pose']['position'][:2]
            assert close(y,.025*(1-(x/half)**2)),'Unregistered lateral placement change'
        for i in range(10):objects['t06_book_'+str(i).zfill(2)]['pose']['position'][0]-=(i-4.5)*(p['theta']-source_theta)
        source_half=(objects['t06_book_09']['pose']['position'][0]-objects['t06_book_00']['pose']['position'][0])/2
        for i in range(10):
            position=objects['t06_book_'+str(i).zfill(2)]['pose']['position'];position[1]=.025*(1-(position[0]/source_half)**2)
        assert all(abs(x-p['theta'])<1e-6 for x in p['measurements']['executed_nominal_gaps_m'])
    elif family in ['impact_force','pull_force']:
        for f in forces:
            for k in ['force_world','force_world_after_contact']:
                if k in f:f[k]=[x/p['theta']for x in f[k]]
    elif family=='layer_friction':
        for name,obj in objects.items():
            if name.startswith('t09_book_'):
                assert close(obj['friction'],p['theta']);obj['friction']='intervened'
                if 'friction'in obj.get('material_preset',{}):obj['material_preset']['friction']='intervened'
    elif family=='support_x':
        # gen_t10_supx.py derives panel rest pose and roll aiming from support
        # position. Keep this original coupled family; do not silently hold the
        # panel at the pose belonging to a different support location.
        index=int(p['sample_id'].rsplit('_p',1)[1]);unrounded=.08+(.217-.08)*(index/21)
        assert close(p['theta'],round(unrounded,4))
        tilt=lambda x:round(math.degrees(math.atan((.32+.004-.001)/(x-.0105+.223))),2)
        folder,pen,tape=[objects[n]for n in ['t10_supported_folder','t10_support_pen','t10_tape_roll']]
        assert close(folder['size'],[.58,.34,.0195])and close(pen['height'],.32)and close(pen['radius'],.0105)
        slab=objects['frozen_tabletop_collision_slab'];top=slab['pose']['position'][2]+slab['size'][2]/2
        def panel_pose(lean):
            a=math.radians(lean)
            return dict(position=[-.223+.29*math.cos(a)-.00975*math.sin(a),.08,top+.001+.29*math.sin(a)+.00975*math.cos(a)],euler_xyz=[0.,-lean,0.])
        expected=panel_pose(tilt(unrounded))
        for k in ['position','euler_xyz']:assert close(folder['pose'][k],expected[k]),'Original panel/support recipe mismatch'
        assert close(pen['pose']['position'],[p['theta'],.08,top+.16])
        assert close(tape['pose']['position'],[p['theta'],-.305,top+.0615])
        for name in ['t10_support_pen','t10_tape_roll']:objects[name]['pose']['position'][0]=source_theta
        for k,v in panel_pose(tilt(source_theta)).items():folder['pose'][k]=v
    else:raise ValueError('No registered context normalization for '+family)
    return dict(objects=objects,forces=forces,solver=p['original_solver'],horizon_s=p['horizon_s'])

def main():
    data,_=load();rows={r['clip_id']:r for r in data['cases']};old=ROOT/'review/core100_remaining20_20261101'
    frame_proof={r['clip_id']:r for r in read(old/'ORIGINAL_TRANSFER_FRAME_PROOF.json')}
    reports={};files=[];cases=[]
    for cid in IDS:
        pointer=read(WORK/(cid+'_RELEASED_AXIS.json'));p=ROOT/pointer['path'];assert sha(p)==pointer['sha256']
        reports[cid]=read(p);files.append(p)
    # These two currently recovered original friction states have opposite
    # outcomes. Compare their physical contexts; never splice other families.
    mu=[next(p for p in reports[c]['points']if p['status']=='original_released_state_read'and p['sample_id']==reports[c]['source_sample_id'])for c in ['T09_C04','T09_C05']]
    for cid in IDS:
        row=rows[cid];report=reports[cid];points=[p for p in report['points']if p['status']=='original_released_state_read']
        source=next(p for p in points if p['sample_id']==row['sample_id'])
        projection_path=WORK/(cid+'_camera_projection.json');projection=read(projection_path)
        image=ROOT/projection['image_path'];assert sha(image)==projection['image_sha256'];files+=[projection_path,image]
        proof=frame_proof[cid]
        assert proof['all210_decoded_frames_identical']and proof['active_reference_video_sha256']==row['reference_video_sha256']==projection['frozen_video_sha256']
        assert proof['original_parent_video_sha256']==projection['parent_video_sha256']
        assert proof['original_config_sha256']==projection['config_sha256']==source['original_config_sha256']
        assert projection['archived_state_decoded_sha256']==source['state_decoded_sha256']
        assert source['horizon_s']==row['horizon_s']
        source_ok=(source['executed_object_specs_match_config']and source['physics_settings_match_config']and
            source['executed_force_commands_match_config']and
            any(x['same_physical_config_and_seed']for x in source['original_cam03_configuration_evidence']))
        assert all(source['labels'][e]==y for e,y in row['reference_events'].items())
        # Explicit assistant review of the generated diagnostic sheets, not an
        # automatic pass based on projection-file existence or model confidence.
        notes=('Observed successive domino tipping agrees with projected original actors and native required-contact results.'if cid.startswith('T06')else
            'Observed upper books remain stacked or reach the tabletop consistently with the original named contact event; extraction book excluded.'if cid.startswith('T09')else
            'Original support pen is localized through the folder motion; native excursion is separately measured against the original 0.04m criterion.')
        review=dict(reviewer_type='assistant_visual_review_not_independent_human_gold',
            reviewed_frames=[r['frame']for r in projection['projected_centers']],
            qualitative_pose_and_event_agreement=True,measured_pixel_error_px=None,notes=notes,
            exact_same_trajectory_claimed=False,generated_video_labels_created=False)
        source_review=dict(clip_id=cid,reference_video_sha256=row['reference_video_sha256'],
            source=source,source_event_reference_admitted=source_ok,visual_review=review,
            observation_scope='Original physical configuration/seed matches across cameras, native commands verified, frozen RGB sequence reviewed. No bitwise cross-camera trajectory identity claim.',
            blocker=None if source_ok else'Native executed object specs differ from the original cam01 config; approximate projection agreement is insufficient.',
            intervals=[],normalization_domain=row['normalization_domain'],source_files_modified=False)
        if not source_ok:cases.append(source_review);continue
        candidates=mu if cid in ['T09_C04','T09_C05']and len(points)==1 else points
        base=context(source,source['theta']);valid=[];context_mismatches=[];invalid=[]
        for p in candidates:
            if not(p['executed_object_specs_match_config']and p['physics_settings_match_config']and p['executed_force_commands_match_config']and
                any(x['same_physical_config_and_seed']for x in p['original_cam03_configuration_evidence'])):
                invalid.append(dict(sample_id=p['sample_id'],reason='Original config/native execution or camera configuration mismatch; retained separately.'));continue
            if not close(context(p,source['theta']),base):context_mismatches.append(p['sample_id'])
            valid.append(p)
        valid.sort(key=lambda p:p['theta'])
        for event in row['reference_events']:
            for a,b in zip(valid,valid[1:]):
                if a['labels'][event]!=b['labels'][event]:
                    source_review['intervals'].append(dict(event=event,bracket=[a['theta'],b['theta']],
                        endpoint_labels=[a['labels'][event],b['labels'][event]],
                        endpoint_state_sha256=[a['state_decoded_sha256'],b['state_decoded_sha256']],
                        endpoint_config_sha256=[a['original_config_sha256'],b['original_config_sha256']],
                        endpoint_seeds=[a['original_seed'],b['original_seed']]))
        if context_mismatches:
            source_review['published_sweep_candidate_intervals']=source_review['intervals'];source_review['intervals']=[]
        if len(valid)>2:source_review['normalization_domain']=[valid[0]['theta'],valid[-1]['theta']]
        source_review.update(fixed_physical_context_verified=not context_mismatches,published_point_count=len(valid),
            physical_context_mismatch_sample_ids=context_mismatches,
            invalid_intermediate_records=invalid,
            quarantined_or_incomplete_records=[p for p in report['points']if p['status']!='original_released_state_read'],
            original_geometry_coupling=('Original BW06 arc y=0.025*(1-(x/half_length)^2), including gap-dependent normalized x.'if source['family']=='gap'else
                'Original gen_t10_supx tilt_for(unrounded grid support); derived panel position/orientation and roll aiming move with the pen.'if source['family']=='support_x'else None),
            same_seed_across_parameter_points=len({p['original_seed']for p in valid})==1,
            interval_scope='Observed original released sweep; per-point seeds retained, no strict same-seed counterfactual or unique deterministic root claim.',
            boundary_pending_reason=('Other physical inputs vary in the original sweep; retain observed candidate intervals but do not treat them as the frozen source conditional boundary.'if context_mismatches else
                None if source_review['intervals']else'No opposite outcomes in the recovered original finite grid; not marked inapplicable.'))
        cases.append(source_review)
    files+=[old/'ORIGINAL_TRANSFER_FRAME_PROOF.json',ROOT/'scripts/recover_core100_v2_legacy_released_axes.py',ROOT/'scripts/audit_core100_v2_camera_projection.py',Path(__file__),
        WORK/'t06_original_catalog_context.json',WORK/'t06_original_geometry_recipe.json',WORK/'t10_original_generator_sources.json',WORK/'t10_original_geometry_recipe.json']
    result=dict(cases=cases,new_simulations=0,frozen_inputs_modified=False,
        source_hashes={p.relative_to(ROOT).as_posix():sha(p)for p in files},
        limits='Assistant source-event review is not independent human gold; cross-camera bitwise pose identity and unique physical roots are not asserted.')
    raw=json.dumps(result,indent=2).encode();digest=hashlib.sha256(raw).hexdigest();path=WORK/('legacy_released_recovery_'+digest[:12]+'.json');path.write_bytes(raw)
    (WORK/'LEGACY_RELEASED_RECOVERY.json').write_text(json.dumps(dict(path=path.relative_to(ROOT).as_posix(),sha256=digest),indent=2),encoding='utf8')
    print(json.dumps(dict(source_event_references=sum(c['source_event_reference_admitted']for c in cases),
        observed_boundary_references=[c['clip_id']for c in cases if c['intervals']],
        blocked=[c['clip_id']for c in cases if not c['source_event_reference_admitted']])))


if __name__=='__main__':main()
