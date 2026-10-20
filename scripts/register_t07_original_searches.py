"""Join completed original-backend T07 searches to all three published branches."""
import hashlib
import json
import math
import collections
from pathlib import Path
import subprocess

from physedit.boundary import digest,distance

ROOT=Path('review/scene_family_completion_20261018')


def main():
    evidence=[];jobs={}
    for token,launch,plan in [('A','t07_search_launch_20261019.json','t07_original_A_search_plan_20261019.json'),
        ('C','t07_C_search_launch_20261019.json','t07_original_C_search_plan_20261019.json'),
        ('C_home_retry','t07_C_home_retry_launch_20261019.json','t07_original_C_search_plan_20261019.json')]:
        root=json.loads((ROOT/launch).read_text())['root']
        jobs.update({r['sample_id']:r for r in json.loads((ROOT/plan).read_text())})
        code='''import pathlib,json
root=pathlib.Path(ROOT);rows=[]
for result in json.loads((root/'results.json').read_text()) if (root/'results.json').exists() else []:
 if result['status']!='local_transition_bracket':continue
 receipts=[json.loads(p.read_text()) for p in (root/result['sample_id']).glob('*/receipt.json')]
 rows.append(dict(result=result,receipts=receipts))
print(json.dumps(rows))
'''.replace('ROOT',repr(root))
        proc=subprocess.run(['ssh','-o','BatchMode=yes','-o','ConnectTimeout=12','p25','python3 -'],input=code.encode(),capture_output=True,timeout=45)
        proc.check_returncode();evidence.extend(json.loads(proc.stdout))
    proof=ROOT/'t07_original_search_evidence_20261019.json'
    proof.write_text(json.dumps(evidence,indent=2),encoding='utf-8')
    observed={r['sample_id']:r for r in json.loads((ROOT/'t07_measured_published_events.json').read_text())}
    repeats=collections.defaultdict(list)
    for record in evidence:
        result=record['result'];job=jobs[result['sample_id']]
        anchor=next(r['config'] for r in record['receipts'] if r['theta']==job['published_endpoint_states'][-1]['theta'])
        # The original renderer consumes experiment.random_seed, not the
        # declarative top-level seed. Include its actual consumed value.
        context=dict(objects=anchor['dynamic_objects'],scene_overrides=anchor['scene_overrides'],runtime_forces=anchor.get('runtime_forces'),
            random_seed=anchor['experiment'].get('random_seed'),family=job.get('family','A_surface_friction'),
            timing={k:anchor['render'].get(k) for k in ['fps','frames','pre_static_frames','physics_steps_per_render_frame']})
        key=hashlib.sha256(json.dumps(context,sort_keys=True).encode()).hexdigest()
        record['context_sha256']=key;repeats[key].append(record)
    bindings={}
    for record in evidence:
        result=record['result'];job=jobs[result['sample_id']]
        if result['source_state_sha256']!=job['state_sha256']:raise ValueError('search/published reference identity mismatch')
        receipts={r['theta']:r for r in record['receipts']}
        if not all(math.isfinite(r['max_displacement_m']) and r['label']==int(r['max_displacement_m']>=.01) for r in receipts.values()):raise ValueError('nonfinite or inconsistent search motion metric')
        for endpoint in job['published_endpoint_states']:
            if receipts[endpoint['theta']]['label']!=endpoint['label']:raise ValueError('published endpoint not reproduced')
        for theta in result['interval']:
            if theta not in receipts:raise ValueError('boundary endpoint missing actual solver receipt')
        family=job.get('family','A_surface_friction');span=.08 if family=='A_surface_friction' else 8.
        repeated=repeats[record['context_sha256']]
        repeat_ok=len(repeated)>=3 and len({r['result']['sample_id'] for r in repeated})>=3 and len({tuple(r['result']['endpoint_labels']) for r in repeated})==1 and max(r['result']['interval'][0] for r in repeated)<=min(r['result']['interval'][1] for r in repeated)
        interval=[min(r['result']['interval'][0] for r in repeated),max(r['result']['interval'][1] for r in repeated)] if repeat_ok else result['interval']
        for region in ['theta_minus','theta_star','theta_plus']:
            sid=result['sample_id'].replace('_theta_star__','_'+region+'__');r=observed[sid]
            if digest(r['local_path'])!=r['sha256']:raise ValueError('published state bytes changed')
            numerical=distance(dict(theta=r['theta'],boundary=dict(status='verified',bracket=interval,normalization_span=span,source=str(proof.resolve()))))
            bindings[sid]=dict(engine='genesis',scene_id='T07',sample_id=sid,revision=r['revision'],repo_id=r['repo_id'],family_id=family,theta=r['theta'],target_event='motion_ge_1cm',reference_label=r['events']['motion_ge_1cm'],reference_state_sha256=r['sha256'],
                boundary=dict(status='verified' if repeat_ok else 'pending_repeatability',bracket=interval,normalization_span=span,source=str(proof.resolve())),
                distance=numerical,normalization_basis=dict(domain=[.2,.28] if family=='A_surface_friction' else [10.,18.],normalization_span=span,source='original published T07 three-branch design range'),
                numerical_reference_verified=repeat_ok,near_numerical_eligible=repeat_ok and numerical.get('bin')=='near',repeat_contexts=len(repeated),
                blocking_reasons=['reference_rgb_observability_pending']+([] if repeat_ok else ['boundary_repeatability_pending']),bracket_evidence_sha256=digest(proof),
                scope='distance to this named local transition; not a globally unique physical threshold',formal_nearacc_eligible=False)
    (ROOT/'t07_original_search_distance_registry.json').write_text(json.dumps(list(bindings.values()),indent=2),encoding='utf-8')
    print(json.dumps(dict(completed_contexts=len(evidence),published_branches_bound=len(bindings),formal_new_near=0)))


if __name__=='__main__':main()
