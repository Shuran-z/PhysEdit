"""Explain old local-bracket failures using separately registered seed controls."""
import hashlib
import json
from scripts.export_original_boundary_distances import ROOT


def compare_intervals(original,controls):
    a,b=original
    if not a<b or any(not c<d for c,d in controls):raise ValueError('invalid boundary interval')
    if not controls:return dict(status='no_observed_control_boundary',nearest_interval_gap=None)
    gap=min(max(c-b,a-d,0) for c,d in controls)
    return dict(status='new_seed_boundary_outside_original_interval' if gap>1e-12 else 'overlap_or_touch',nearest_interval_gap=gap)


def main():
    plan=ROOT/'t13_remaining_seeded_scans_plan_20261021.json'
    evidence=ROOT/'t13_seeded_supplement_evidence_20261021.json'
    jobs={j['job_id']:j for j in json.loads(plan.read_text())};rows=[]
    for bundle in json.loads(evidence.read_text()):
        result=bundle['result'];job=jobs[result['job_id']]
        if result['supplemental_init_seed']!=0:raise ValueError('mixed seed-control contract')
        if result['source_state_sha256']!=[e['state_sha256'] for e in job['endpoints']]:raise ValueError('wrong source context')
        intervals=[w['bracket'] for w in result['local_intervals']]
        checks=[]
        for endpoint,theta in zip(job['endpoints'],job['bracket']):
            matches=[p for p in bundle['probes'] if abs(p['theta']-theta)<1e-12]
            checks.append(dict(theta=theta,original_label=endpoint['label'],seed0_label=matches[0]['events'][job['target_event']] if len(matches)==1 else None))
        rows.append(dict(job_id=job['job_id'],family=job['family'],target_event=job['target_event'],original_interval=job['bracket'],
            seed0_intervals=intervals,source_endpoint_comparisons=checks,**compare_intervals(job['bracket'],intervals)))
    summary=dict(examined=len(rows),outside_original_interval=sum(r['status']=='new_seed_boundary_outside_original_interval' for r in rows),
        overlap_or_touch=sum(r['status']=='overlap_or_touch' for r in rows),
        endpoint_labels_changed=sum(c['seed0_label'] is not None and c['seed0_label']!=c['original_label'] for r in rows for c in r['source_endpoint_comparisons']),
        plan_sha256=hashlib.sha256(plan.read_bytes()).hexdigest(),evidence_sha256=hashlib.sha256(evidence.read_bytes()).hexdigest(),
        root_cause_uniquely_identified=False,original_labels_or_intervals_overwritten=0,
        scope='New seed0 conditional boundaries explain observed bracket shifts; they are not recovered original seeds or replacement truth.')
    (ROOT/'t13_conditional_boundary_shift_20261024.json').write_text(json.dumps(dict(summary=summary,rows=rows),indent=2));print(json.dumps(summary))


if __name__=='__main__':main()
