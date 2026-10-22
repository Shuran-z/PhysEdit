"""Bind completed new T12 grids; keep no-flip and failure records separate."""
import hashlib,inspect,json
from scripts.boundary_ssh import remote_text
from scripts.export_original_boundary_distances import ROOT,distances
from scripts.probe_verification_cache import verify_probe_files


def bind(job,result):
    if result['status']!='remaining_grid_completed' or result['fixed_context_sha256']!=job['fixed_context_sha256'] or result['axis']!=job['axis']:raise ValueError('wrong slice result')
    if result['member_reference_state_sha256']!=[m['state_sha256'] for m in job['members']]:raise ValueError('published member identities changed')
    probes={p['theta']:p for p in result['verified_probes']};span=job['normalization_domain'][1]-job['normalization_domain'][0]
    for m in job['members']:
        if probes[m['theta']]['label']!=m['reference_label']:raise ValueError('published member event not reproduced')
    if any(t not in probes for t in job['grid']):raise ValueError('incomplete original parameter grid')
    out=[]
    for interval in result['intervals']:
        a,b=interval['bracket'];tolerance=.001 if job['axis']=='speed' else .0005
        if not job['normalization_domain'][0]<=a<b<=job['normalization_domain'][1] or b-a>tolerance+1e-9:raise ValueError('invalid interval')
        if [probes[t]['label'] for t in [a,b]]!=interval['labels'] or interval['labels'][0]==interval['labels'][1]:raise ValueError('interval endpoints do not cross')
        for member in job['members']:
            d=distances(member['theta'],bracket=[a,b])
            out.append(dict(member,scene_id='T12',engine='genesis',revision=job['revision'],family_id=job['axis'],target_event=job['target_event'],
                reference_state_sha256=member['state_sha256'],original_boundary_interval=[a,b],**d,
                normalization_domain=job['normalization_domain'],normalization_span=span,normalized_distance_lower=d['distance_lower']/span,normalized_distance_upper=d['distance_upper']/span,
                parameter_unit={'speed':'m/s','friction':'dimensionless','target_mass':'kg'}[job['axis']],fixed_context_sha256=job['fixed_context_sha256'],
                original_reference_kind=job['reference_kind'],normalization_scope='full actual released axis grid; distinct from an older narrower slice span',
                search_scope='All released axis values scanned; local sign changes refined. Hidden between-sample transitions are not ruled out.',
                source_job_id=job['job_id'],backend_sha256=result['backend_sha256'],inversion_eligibility='independent',formal_nearacc_eligible=False))
    return out


def main():
    marker=ROOT/'t12_remaining_grid_launch_20261022.json'
    if not marker.exists():return
    launches=json.loads(marker.read_text());jobs=json.loads((ROOT/'t12_remaining_grid_plan_20261022.json').read_text());byid={j['job_id']:j for j in jobs}
    code=r'''
import pathlib,json,hashlib,os
VERIFY
out=[]
for l in LAUNCHES:
 if hashlib.sha256(pathlib.Path(l['active_plan']).read_bytes()).hexdigest()!=l['active_plan_sha256']:raise ValueError('active search plan changed')
 if hashlib.sha256((pathlib.Path(l['source'])/'12_render_motion_sequence.py').read_bytes()).hexdigest()!=l['backend_sha256']:raise ValueError('original backend changed')
 root=pathlib.Path(l['root']);p=root/'status.json';rows=json.loads(p.read_text()) if p.exists() else [];indexed={r['job_id']:r for r in rows}
 for p in root.glob('*/result.json'):indexed[p.parent.name]=json.loads(p.read_text())
 cache_path=root/'collector_probe_digest_cache.json';cache=json.loads(cache_path.read_text()) if cache_path.exists() else {}
 for row in indexed.values():
  if row['status']=='remaining_grid_completed':
   if row['backend_sha256']!=l['backend_sha256']:raise ValueError('backend identity changed')
   verified=[]
   for expected in row['probes']:
    folder=root/row['job_id']/format(expected['theta'],'.12g');receipt=json.loads((folder/'receipt.json').read_text())
    if receipt!=expected:raise ValueError('probe receipt changed')
    receipt['state_path']=verify_probe_files(receipt,folder,cache)
    if receipt['label']!=int(receipt['max_displacement_m']>=.01):raise ValueError('event rule changed')
    verified.append(receipt)
   row['verified_probes']=verified;row.pop('probes',None)
  out.append(row)
 temp=cache_path.with_name(cache_path.name+'.'+str(os.getpid())+'.tmp');temp.write_text(json.dumps(cache));temp.replace(cache_path)
print(json.dumps(out))
'''.replace('VERIFY',inspect.getsource(verify_probe_files)).replace('LAUNCHES',repr(launches))
    evidence=json.loads(remote_text('p25',code,timeout=300));bindings=[]
    for row in evidence:
        if row['status']=='remaining_grid_completed':bindings.extend(bind(byid[row['job_id']],row))
    (ROOT/'t12_remaining_grid_evidence_20261022.json').write_text(json.dumps(evidence))
    (ROOT/'original_value_distance_ledger/t12_remaining_grid_sample_distances.jsonl').write_text(''.join(json.dumps(r)+'\n' for r in bindings))
    completed=[r for r in evidence if r['status']=='remaining_grid_completed'];summary=dict(planned=len(jobs),completed=len(completed),failed=sum(r['status']=='failed' for r in evidence),pending=len(jobs)-len(evidence),with_intervals=sum(bool(r['intervals']) for r in completed),no_observed_flip=sum(not r['intervals'] for r in completed),bound_unique_samples=len({r['sample_id'] for r in bindings}),formal_admissions=0)
    (ROOT/'t12_remaining_grid_summary_20261022.json').write_text(json.dumps(summary,indent=2));print(json.dumps(summary))


if __name__=='__main__':main()
