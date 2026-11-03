"""Restore T10_C05's executed old-version inputs without editing its prompt."""
import hashlib
import json
import math
from pathlib import Path
from physedit.core100_rebalanced import load

ROOT=Path(__file__).resolve().parents[1];WORK=ROOT/'review/core100_v2_resolution_20261102'
def read(p):return json.loads(Path(p).read_text(encoding='utf8'))
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()

def main():
    roster,manifest,tasks,_=load();task=next(t for t in tasks if t['clip_id']=='T10_C05')
    states_path=WORK/'t10_old_executed_version_states.json';states=read(states_path)
    for s in states:
        index=int(s['sample_id'].rsplit('_p',1)[1]);assert abs(s['actual_support_x']-(-.05+.33*index/21))<1e-7
        assert s['actual_roll_speed']==3. and s['actual_folder_angle']==38.
    source=next(s for s in states if s['sample_id']==task['sample_id']);objects=source['original_native_specs'];checks=[]
    for name,value,unit in task['parameter_facts']:
        if name=='gravity':actual=math.dist(source['original_native_solver']['gravity'],[0,0,0])
        else:
            actor,field=name.split('.',1);o=objects[actor]
            if field in ['mass','friction','restitution']:actual=o[field]
            elif field=='initial_angle':actual=abs(o['pose']['euler_xyz'][1])
            elif field in ['initial_X','initial_Y','initial_Z']:actual=o['pose']['position']['XYZ'.index(field[-1])]
            elif field=='initial_speed':actual=math.dist(o['motion']['initial_velocity'],[0,0,0])
            else:raise ValueError('Unverified frozen fact '+name)
        assert math.isclose(actual,value,rel_tol=1e-7,abs_tol=1e-7),(name,actual,value)
        checks.append(dict(field=name,frozen=value,executed=actual,unit=unit))
    generator=read(WORK/'t10_original_generator_sources.json')['gen_prod_cfg.py']
    assert '"support_x","key",-0.05,0.28,22'in generator['text']
    projection=read(WORK/'T10_C05_camera_projection.json')
    assert projection['frozen_video_sha256']==task['reference']['sha256']
    result=dict(clip_id='T10_C05',reference_video_sha256=task['reference']['sha256'],
        parameter='support_x',theta=source['actual_support_x'],normalization_domain=[-.05,.28],
        source_state_path=source['state_path'],source_state_sha256=source['state_decoded_sha256'],
        source_physical_context=source,frozen_physical_facts_verified=checks,
        actual_fixed_controls=dict(tape_initial_speed_mps=3.,folder_initial_angle_deg=38.),
        original_range_evidence='Original b10/gen_prod_cfg support_x range[-.05,.28],22 indices; native p16 and p17 agree with that exact mapping.',
        matching_version_boundary_recovered=False,reference_event_admission_changed=False,
        old_other_version_candidate_retained=True,frozen_inputs_modified=False,
        reason='Frozen prompt and executed native state both specify x0.2171429, speed3, angle38. Current same-ID cam01 config specifies x0.1909, speed1.8, angle38.68 and belongs to another production version. Its interval cannot be transferred.',
        limitations='Original cam01 trajectory/producer correspondence and a matching old-version boundary remain pending. Reconstructed range is disclosed, not an original solved critical value.',
        source_hashes={p.relative_to(ROOT).as_posix():sha(p)for p in [states_path,roster/'MANIFEST.json',WORK/'t10_original_generator_sources.json',WORK/'T10_C05_camera_projection.json',Path(__file__)]})
    raw=json.dumps(result,indent=2).encode();digest=hashlib.sha256(raw).hexdigest();path=WORK/('t10_c05_executed_version_'+digest[:12]+'.json');path.write_bytes(raw)
    (WORK/'T10_C05_EXECUTED_VERSION.json').write_text(json.dumps(dict(path=path.relative_to(ROOT).as_posix(),sha256=digest),indent=2),encoding='utf8')
    print(json.dumps(dict(clip_id='T10_C05',theta=result['theta'],normalization_domain=result['normalization_domain'],frozen_facts_verified=len(checks),matching_version_boundary_recovered=False)))

if __name__=='__main__':main()
