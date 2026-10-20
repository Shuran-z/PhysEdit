"""Bind completed current-release T13 solver intervals to original reference IDs.

Keep every local transition and its normalization. The numerical replay does not
replace independent repeat/visual checks, and never imports labels for generated
videos. Source receipts are hash checked on the server before being collected.
"""
import collections
import json
from pathlib import Path
import subprocess

from physedit.boundary import digest,distance

ROOT=Path('review/scene_family_completion_20261018')


def registrations(evidence,plan,current,source):
    jobs={r['job_id']:r for r in plan};byid={r['sample_id']:r for r in current};groups=collections.defaultdict(list)
    for row in current:groups[(row['family'],row['fixed_context_sha256'])].append(row)
    intervals=collections.defaultdict(list)
    for record in evidence:
        r=record['result'];job=jobs[r['job_id']];receipts={x['theta']:x for x in record['receipts']}
        if r['status']!='local_transition_bracket':continue
        if r['source_state_sha256']!=[e['state_sha256'] for e in job['endpoints']]:raise ValueError('source state mismatch')
        refs=[byid[e['sample_id']] for e in job['endpoints']]
        if len({x['fixed_context_sha256'] for x in refs})!=1:raise ValueError('mixed reference contexts')
        event=r['target_event']
        for theta,endpoint,ref in zip(job['bracket'],job['endpoints'],refs):
            receipt=receipts[theta]
            if not receipt.get('label_matches') or receipt['precontact_max_position_error_m']>.005:raise ValueError('endpoint replay inconsistent')
            if receipt['events'][event]!=ref['events'][event]:raise ValueError('published label mismatch')
        a,b=r['interval']
        if a not in receipts or b not in receipts or receipts[a]['events'][event]==receipts[b]['events'][event]:raise ValueError('missing actual opposite solver endpoints')
        if not job['bracket'][0]<=a<b<=job['bracket'][1]:raise ValueError('interval outside source range')
        intervals[(r['family'],refs[0]['fixed_context_sha256'],event)].append(dict(bracket=[a,b],job_id=r['job_id'],
            endpoint_labels=[receipts[a]['events'][event],receipts[b]['events'][event]],backend_sha256=r['backend_sha256'],reference_kind='refined_replay_interval'))
    # Original published opposite outcomes remain valid scan evidence even when
    # a new replay fails. Refinement failure must not erase the released bracket.
    solved={w['job_id'] for windows in intervals.values() for w in windows}
    for job in plan:
        if job['job_id'] in solved:continue
        refs=[byid[e['sample_id']] for e in job['endpoints']];event=job['target_event']
        if len({x['fixed_context_sha256'] for x in refs})!=1:raise ValueError('mixed published contexts')
        if [x['state_sha256'] for x in refs]!=[x['state_sha256'] for x in job['endpoints']]:raise ValueError('published state identity changed')
        labels=[x['events'][event] for x in refs]
        if labels[0]==labels[1]:raise ValueError('published bracket has no opposite event results')
        intervals[(job['family'],refs[0]['fixed_context_sha256'],event)].append(dict(bracket=job['bracket'],job_id=job['job_id'],
            endpoint_labels=labels,reference_kind='original_published_opposite_outcomes_scan_interval',refinement_status='not_completed_or_not_reproduced'))
    rows=[]
    for (family,context,event),windows in intervals.items():
        points=groups[(family,context)];domain=[min(r['theta'] for r in points),max(r['theta'] for r in points)];span=domain[1]-domain[0]
        if span<=0:raise ValueError('empty normalization domain')
        for r in points:
            rows.append(dict(engine='genesis',scene_id='T13',sample_id=r['sample_id'],family_id=family,theta=r['theta'],parameter_unit='m',target_event=event,
                fixed_context_sha256=context,reference_label=r['events'][event],reference_state_sha256=r['state_sha256'],reference_config_sha256=r['config_sha256'],
                boundary=dict(status='observed',intervals=windows,source=str(source.resolve())),
                local_interval_distances=[dict(job_id=w['job_id'],bracket=w['bracket'],**distance(dict(theta=r['theta'],boundary=dict(status='verified',bracket=w['bracket'],normalization_span=span,source=str(source.resolve()))))) for w in windows],
                normalization_basis=dict(domain=domain,normalization_span=span,source='entire frozen published family at identical physical context'),
                bracket_evidence_sha256=digest(source),mapping_status='matched',numerical_reference_verified=False,formal_nearacc_eligible=False,
                blocking_reasons=['boundary_repeatability_pending','reference_rgb_observability_pending','remaining_local_transition_searches_pending'],
                scope='distance to each completed named local interval; no unique/global boundary or formal near assignment'))
    return rows


def main():
    launches=[json.loads((ROOT/'t13_full_search_launch_20261019.json').read_text())]
    for filename in ['t13_precontact_fix_launch_20261020.json','t13_original_full_retry_launch_20261020.json']:
        retry=ROOT/filename
        if retry.exists():launches.append(json.loads(retry.read_text()))
    code='''import pathlib,json,hashlib
root=pathlib.Path(ROOT);rows=[]
for result in json.loads((root/'status.json').read_text()) if (root/'status.json').exists() else []:
 if result['status']!='local_transition_bracket':continue
 receipts=[]
 for p in (root/result['job_id']).glob('*/receipt.json'):
  r=json.loads(p.read_text())
  for name,file in [('config_sha256','config.json'),('state_sha256','physics.json')]:
   assert hashlib.sha256((p.parent/file).read_bytes()).hexdigest()==r[name]
  assert r['backend_sha256']==result['backend_sha256']
  receipts.append(r)
 rows.append(dict(result=result,receipts=receipts))
print(json.dumps(rows))
'''
    merged={}
    for launch in launches:
        p=subprocess.run(['ssh','-o','BatchMode=yes',launch.get('host','p25'),'python3 -'],input=code.replace('ROOT',repr(launch['root'])).encode(),capture_output=True,timeout=90);p.check_returncode()
        for record in json.loads(p.stdout):
            record['source_root']=launch['root'];merged[record['result']['job_id']]=record
    evidence=list(merged.values());source=ROOT/'t13_current_solver_evidence_20261019.json';source.write_text(json.dumps(evidence,indent=2),encoding='utf-8')
    rows=registrations(evidence,json.loads((ROOT/'t13_current_search_plan_20261019.json').read_text()),json.loads((ROOT/'t13_current_measured_events_20261019.json').read_text()),source)
    (ROOT/'t13_current_solver_distance_registry.json').write_text(json.dumps(rows,indent=2),encoding='utf-8')
    summary=dict(completed_refined_intervals=len(evidence),original_published_intervals=len(json.loads((ROOT/'t13_current_search_plan_20261019.json').read_text())),
        sample_event_records=len(rows),unique_samples=len({r['sample_id'] for r in rows}),formal_new_near=0)
    (ROOT/'t13_current_solver_binding_summary.json').write_text(json.dumps(summary,indent=2));print(json.dumps(summary))


if __name__=='__main__':main()
