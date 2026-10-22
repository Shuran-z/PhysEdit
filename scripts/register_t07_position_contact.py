"""Collect E4 refinements without gating the original B contact answers."""
import hashlib
import inspect
import json
from scripts.boundary_ssh import remote_text
from scripts.export_original_boundary_distances import ROOT, distances
from scripts.probe_verification_cache import verify_probe_files


def main():
    launch_path=ROOT/'t07_B_E4_search_launch_20261022.json'
    if not launch_path.exists():return
    launch=json.loads(launch_path.read_text());jobs=json.loads((ROOT/'t07_B_E4_search_plan_20261022.json').read_text());byid={j['sample_id']:j for j in jobs}
    code=r'''
import pathlib,json,hashlib,os
VERIFY
r=pathlib.Path(DIRECTORY);p=r/'results.json';rows=json.loads(p.read_text()) if p.exists() else [];out=[]
cp=r/'collector_probe_digest_cache.json';cache=json.loads(cp.read_text()) if cp.exists() else {}
for row in rows:
 probes=[]
 for path in (r/row['sample_id']).glob('*/receipt.json'):
  v=json.loads(path.read_text());v['state_path']=verify_probe_files(v,path.parent,cache);v.pop('config',None);probes.append(v)
 out.append(dict(result=row,probes=probes))
temp=cp.with_name(cp.name+'.'+str(os.getpid())+'.tmp');temp.write_text(json.dumps(cache));temp.replace(cp)
print(json.dumps(out))
'''.replace('VERIFY',inspect.getsource(verify_probe_files)).replace('DIRECTORY',repr(launch['root']))
    evidence=json.loads(remote_text(launch['host'],code,timeout=180));matches={}
    for e in evidence:
        result=e['result']
        if result['status']!='local_transition_bracket':continue
        job=byid[result['sample_id']];probes={p['theta']:p for p in e['probes']}
        if result['target_event']!='phone_table_contact_after_release' or result['source_state_sha256']!=job['state_sha256']:raise ValueError('E4 source or event mismatch')
        for theta,label in zip(job['endpoints'],job['endpoint_labels']):
            p=probes[theta]
            if p['label']!=label or p['label']!=p['contact_evidence']['label'] or p['target_event']!=result['target_event']:raise ValueError('E4 endpoint not reproduced')
        a,b=result['interval']
        if not job['endpoints'][0]<=a<b<=job['endpoints'][1] or b-a>.000500001:raise ValueError('invalid E4 refinement interval')
        if probes[a]['label']==probes[b]['label']:raise ValueError('E4 interval endpoints have same label')
        matches[result['sample_id']]=result
    base=ROOT/'original_value_distance_ledger/t07_B_E4_sample_distances.jsonl';rows=[]
    for line in base.read_text().splitlines():
        row=json.loads(line);result=matches.get(row['source_interval_id'])
        if result:
            d=distances(row['theta'],bracket=result['interval']);span=row['normalization_span']
            row.update(published_scan_interval=row['original_boundary_interval'],original_boundary_interval=result['interval'],**d,
                normalized_distance_lower=d['distance_lower']/span,normalized_distance_upper=d['distance_upper']/span,
                refinement_source='original_T07_renderer_E4_contact_search',formal_nearacc_eligible=False)
        rows.append(row)
    target=base.with_name(base.stem+'_refined.jsonl');target.write_text(''.join(json.dumps(r)+'\n' for r in rows))
    endpoint_failures=[]
    for e in evidence:
        if e['result']['status']!='failed':continue
        job=byid[e['result']['sample_id']];probes={p['theta']:p for p in e['probes']}
        endpoint_failures.append(dict(sample_id=job['sample_id'],error=e['result'].get('error'),endpoints=[
            dict(theta=theta,published_label=label,replay_label=probes.get(theta,{}).get('label'),
                first_table_contact_frame=probes.get(theta,{}).get('contact_evidence',{}).get('first_table_contact_frame'))
            for theta,label in zip(job['endpoints'],job['endpoint_labels'])]))
    summary=dict(planned=len(jobs),refined=len(matches),failed=sum(e['result']['status']=='failed' for e in evidence),pending=len(jobs)-len(evidence),endpoint_failures=endpoint_failures,
        original_reference_answers=180,bound_sample_rows=len(rows),base_sha256=hashlib.sha256(base.read_bytes()).hexdigest(),overlay_sha256=hashlib.sha256(target.read_bytes()).hexdigest(),formal_admissions=0)
    (ROOT/'t07_B_E4_refinement_summary_20261022.json').write_text(json.dumps(summary,indent=2));(ROOT/'t07_B_E4_solver_evidence_20261022.json').write_text(json.dumps(evidence,indent=2));print(json.dumps(summary))


if __name__=='__main__':main()
