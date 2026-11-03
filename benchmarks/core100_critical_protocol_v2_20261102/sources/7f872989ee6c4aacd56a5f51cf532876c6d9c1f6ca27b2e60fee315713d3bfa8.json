"""Hash-check F5 contact probes; keep numerical and visual admission separate."""
import argparse
import gzip
import hashlib
import json
import math
from pathlib import Path

EVENTS={'first_contact':'driver_to_falling_book_contact',
        'second_contact':'falling_book_to_drink_contact',
        'ordered_chain':'registered_two_contact_conjunction_and_order'}


def collect(root):
    rows=[];completed=[];failures=[]
    plans={r['clip_id']:r for r in json.loads((root.parent/'t13_contact_plan.json').read_text())}
    status=root/'status.json'
    if status.exists():failures=[r for r in json.loads(status.read_text())if r['status']=='failed']
    for path in sorted(root.glob('T13_C*/result.json')):
        result=json.loads(path.read_text());assert result['status']=='contact_domain_scan_completed'
        probes={p['theta']:p for p in result['probes']}
        assert result['source_theta'] in probes
        anchor=probes[result['source_theta']]
        assert anchor['source_prefix_max_position_error_m']<=.001
        plan=plans[result['clip_id']]
        source_raw=Path(plan['state_path']).read_bytes()
        assert hashlib.sha256(source_raw).hexdigest()==result['source_state_sha256']==plan['state_sha256']
        assert hashlib.sha256(Path(plan['config_path']).read_bytes()).hexdigest()==result['source_config_sha256']==plan['config_sha256']
        original=json.loads(source_raw)
        for theta,probe in probes.items():
            statepath=Path(probe['state_path']);raw=gzip.decompress(statepath.read_bytes())
            assert hashlib.sha256(raw).hexdigest()==probe['state_sha256']
            assert hashlib.sha256((statepath.parent/'config.json').read_bytes()).hexdigest()==probe['config_sha256']
            frames=[f for f in json.loads(raw)['frames'] if 4<=f['frame_index']<=124]
            assert len(frames)==121 and all('contacts'in f for f in frames)
            first=[]
            for pair in [{'t13_driver_book','t13_falling_book'},{'t13_falling_book','t13_drink_box'}]:
                times=[(f['frame_index'],c.get('physics_step_index',-1))for f in frames for c in f['contacts']if {c.get('entity_a'),c.get('entity_b')}==pair]
                first.append(min(times)if times else None)
            expected=dict(first_contact=int(first[0]is not None),second_contact=int(first[1]is not None),ordered_chain=int(all(first)and first[0]<first[1]))
            assert probe['labels']==expected
            if theta==result['source_theta']:
                original_frames={f['frame_index']:f for f in original['frames']}
                stop=anchor['source_prefix_last_frame'];errors=[]
                for f in json.loads(raw)['frames']:
                    if f['frame_index']>stop:continue
                    source_positions={o['name']:o['position']for o in original_frames[f['frame_index']]['objects']}
                    errors.extend(math.dist(o['position'],source_positions[o['name']])for o in f['objects'])
                assert max(errors)<=.001 and abs(max(errors)-anchor['source_prefix_max_position_error_m'])<1e-10
        lo_domain,hi_domain=result['domain'];span=hi_domain-lo_domain;theta=result['source_theta']
        for interval in result['intervals']:
            lo,hi=interval['bracket'];event=interval['event']
            assert lo_domain<=lo<hi<=hi_domain and hi-lo<=.00050000001
            assert [probes[t]['labels'][event]for t in [lo,hi]]==interval['labels'] and len(set(interval['labels']))==2
            lower=max(lo-theta,theta-hi,0)/span;upper=max(abs(theta-lo),abs(theta-hi))/span
            bucket='near'if upper<=.05 else'mid'if lower>.05 and upper<=.15 else'far'if lower>.15 else'bucket_uncertain'
            rows.append(dict(clip_id=result['clip_id'],target_event=EVENTS[event],worker_event=event,
                             horizon_s=5.,condition_frame_index=4,bracket=[lo,hi],labels=interval['labels'],
                             source_theta=theta,normalization_domain=result['domain'],normalization_span=span,
                             normalized_distance_interval=[lower,upper],distance_bin=bucket,
                             source_state_sha256=result['source_state_sha256'],source_config_sha256=result['source_config_sha256'],
                             renderer_sha256=result['renderer_sha256'],result_sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
                             source_prefix_max_position_error_m=anchor['source_prefix_max_position_error_m'],
                             probe_evidence_verified=True,reference_admitted=False,pair_admitted=False,
                             scope='New contact protocol only. Original terminal-fall boundary is not recovered.'))
        completed.append(dict(clip_id=result['clip_id'],status=result['status'],probes=len(probes),
                              intervals=len(result['intervals']),events_without_observed_grid_flip=[EVENTS[e]for e in EVENTS if not any(i['event']==e for i in result['intervals'])],
                              no_flip_scope='An observed constant grid is not proof of no hidden root.'))
    return dict(schema='verified-f5-contact-boundaries-v1',completed_cases=len(completed),expected_cases=5,
                cases=completed,records=rows,failures=failures,
                reference_admissions=0,pair_admissions=0)


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--root',required=True);p.add_argument('--output',required=True);a=p.parse_args()
    out=Path(a.output);result=collect(Path(a.root));tmp=out.with_suffix('.tmp');tmp.write_text(json.dumps(result,indent=2));tmp.replace(out)
    print(json.dumps({'completed_cases':result['completed_cases'],'records':len(result['records']),'failures':len(result['failures'])}))
