"""Seal actual physical-context equality for the new reference selections."""
import copy
import gzip
import hashlib
import json
from pathlib import Path

from physedit.core100_critical import load, sha
from scripts.build_core100_six_replacement_roster import ROOT,WORK,state,write


def verify():
    p=json.loads((ROOT/'review/core100_v2_resolution_20261102/T06_C05_RELEASED_AXIS.json').read_text())
    path=ROOT/p['path'];assert sha(path)==p['sha256'];ledger=json.loads(path.read_text())
    baseline=next(r for r in ledger['points']if r['sample_id'].endswith('_p03'))
    checks=[]
    for cid in ['T06_C02','T06_C03']:
        s=state(cid);objects={o['name']:o.get('spec',o)for o in s['dynamic_objects']}
        assert objects==baseline['original_specs']
        own={k:v for k,v in s['scene_overrides'].items()if not k.startswith('raytracing')}
        other={k:v for k,v in baseline['original_solver'].items()if not k.startswith('raytracing')}
        assert own==other
        forces=s['runtime_forces'];reference=baseline['original_runtime_forces'];theta=s['experiment']['parameter']['parameter_value']
        assert len(forces)==len(reference)==12
        error=0.
        for a,b in zip(forces,reference):
            assert all(a[k]==b[k]for k in ['target','frame_start','frame_end'])
            error=max(error,max(abs(x/theta-y/baseline['theta'])for x,y in zip(a['force_world'],b['force_world'])))
        assert error<1e-6
        checks.append(dict(clip_id=cid,compared_with='T06_C05',objects_and_physics_equal=True,
            normalized_force_pulse_maximum_difference=error,force_rounding_tolerance=1e-6,
            source_seed_is_not_claimed_identical=True,source_ledger=dict(path=path.relative_to(ROOT).as_posix(),sha256=sha(path))))
    cfg=[]
    for cid in ['T18_C01','T18_C02']:
        c=json.loads((WORK/'sources'/cid/'config.json').read_text());objects=copy.deepcopy(c['dynamic_objects'])
        for o in objects:
            if o['name'].startswith('t18_book_'):
                o['friction']=0.
                if'friction'in o.get('material_preset',{}):o['material_preset']['friction']=0.
        cfg.append(dict(objects=objects,physics=c['scene_overrides'],seed=c.get('seed'),forces=c.get('runtime_forces'),
            timing={k:c['render'][k]for k in ['fps','pre_static_frames','physics_steps_per_render_frame']},camera=c['render']['fixed_view']))
    assert cfg[0]==cfg[1],'T18_pair_changes_more_than_friction'
    pointer=json.loads((ROOT/'review/core100_v2_resolution_20261102/T18_GPU_ENDPOINTS_RESULT.json').read_text());path=ROOT/pointer['path'];assert sha(path)==pointer['sha256']
    points=json.loads(path.read_text())['points']
    for cid,theta in [('T18_C01',.04),('T18_C02',.08)]:
        point=next(p for p in points if p['clip_id']=='T18_C03'and p['theta']==theta)
        proof=json.loads((WORK/'sources'/cid/'SOURCE_PROOF.json').read_text())
        assert proof['source_state_sha256']==point['state_sha256']and proof['source_config_sha256']==point['config_sha256']
        assert point['actual_original_objects_axis_seed_solver_controller_and_clock_verified']
        checks.append(dict(clip_id=cid,theta=theta,objects_and_physics_equal_except_declared_book_friction=True,
            actual_source_seed_equal=True,camera_and_timing_equal=True,source_endpoint_label=point['measurement']['label'],
            native_endpoint_record=dict(path=path.relative_to(ROOT).as_posix(),sha256=sha(path)),
            source_state_sha256=point['state_sha256'],source_reference_video_sha256=point['reference_video_sha256']))
    return dict(checks=checks,scope='Additional source-context equality checks. Published T04/T10 are also checked in the roster builder; old references and model labels are not edited.')


def main():
    report=verify();raw=json.dumps(report,indent=2).encode();digest=hashlib.sha256(raw).hexdigest()
    path=WORK/('CONTEXT_VERIFICATION_'+digest[:12]+'.json');path.write_bytes(raw)
    pp=ROOT/'catalog/prepared_core100_critical_protocol_v3.json';pointer=json.loads(pp.read_text());registry=(pp.parent/pointer['registry']).resolve()
    data,_=load(registry,pointer['registry_sha256']);target=registry.parent/'sources';target.mkdir(exist_ok=True)
    copy_path=target/(digest+'.json');copy_path.write_bytes(raw)
    data['source_hashes'][copy_path.relative_to(ROOT).as_posix()]=digest
    data['new_reference_context_verification']=report
    payload=json.dumps(data,ensure_ascii=False,indent=2).encode();new_digest=hashlib.sha256(payload).hexdigest()
    new_path=registry.parent/('registry_'+new_digest[:12]+'.json');new_path.write_bytes(payload);load(new_path,new_digest)
    pointer.update(registry='../'+new_path.relative_to(ROOT).as_posix(),registry_sha256=new_digest);write(pp,pointer)
    print(json.dumps(dict(context_checks=len(report['checks']),registry=new_path.relative_to(ROOT).as_posix(),sha256=new_digest)))


if __name__=='__main__':main()
