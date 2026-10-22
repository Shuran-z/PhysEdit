"""Bind completed seed-control probes, independently of original published truth."""
import collections
import hashlib
import inspect
import json
from scripts.boundary_ssh import remote_text
from scripts.export_original_boundary_distances import ROOT, distances
from scripts.probe_verification_cache import verify_probe_files


def bind(job,result,probes):
    if result['status']!='supplemental_grid_completed' or result['supplemental_init_seed']!=0:raise ValueError('wrong seed-control contract')
    if result['source_state_sha256']!=[e['state_sha256'] for e in job['endpoints']]:raise ValueError('source context changed')
    event=job['target_event'];bytheta={p['theta']:p for p in probes}
    if len(bytheta)!=len(probes):raise ValueError('duplicate probe parameters')
    domain=[min(p['theta'] for p in job['supplemental_grid']),max(p['theta'] for p in job['supplemental_grid'])];span=domain[1]-domain[0]
    if span<=0:raise ValueError('empty normalization domain')
    for w in result['local_intervals']:
        a,b=w['bracket']
        if not domain[0]<=a<b<=domain[1] or b-a>.000500001:raise ValueError('invalid conditional interval')
        labels=[bytheta[t]['events'][event] for t in [a,b]]
        if labels!=w['endpoint_labels'] or labels[0]==labels[1]:raise ValueError('supplemental bracket lacks opposite endpoint evidence')
    rows=[]
    for p in probes:
        if p.get('supplemental_init_seed')!=0:raise ValueError('mixed probe seeds')
        row=dict(scene_id='T13',engine='genesis',sample_id='T13_seed0_'+job['job_id']+'_'+format(p['theta'],'.12g'),
            family_id=job['family'],theta=p['theta'],target_event=event,reference_label=p['events'][event],
            state_sha256=p['state_sha256'],config_sha256=p['config_sha256'],state_path=p['state_path'],
            revision='supplemental_seed0_20261021',simulation_seed=0,source_job_id=job['job_id'],
            reference_origin='new_fixed_seed_full_renderer_probe',normalization_domain=domain,normalization_span=span,
            original_publication_reference=False,formal_nearacc_eligible=False,
            source_reference_ids=[e['sample_id'] for e in job['endpoints']],
            boundary_status='observed_conditional_intervals' if result['local_intervals'] else 'no_flip_observed_at_sampled_points')
        row['distances']=[dict(boundary_interval=w['bracket'],**distances(p['theta'],bracket=w['bracket'])) for w in result['local_intervals']]
        for d in row['distances']:
            d.update(normalized_distance_lower=d['distance_lower']/span,normalized_distance_upper=d['distance_upper']/span)
        rows.append(row)
    return rows


def main():
    launch_path=ROOT/'t13_remaining_seeded_scans_launch_20261021.json'
    if not launch_path.exists():return
    launch=json.loads(launch_path.read_text());jobs=json.loads((ROOT/'t13_remaining_seeded_scans_plan_20261021.json').read_text())
    code=r'''
import pathlib,json,hashlib,os,re
VERIFY
r=pathlib.Path(DIRECTORY);rows=json.loads((r/'status.json').read_text()) if (r/'status.json').exists() else [];out=[]
renderer=pathlib.Path('/home/wangzijun_p25/liyuhan/phydataset/ase_asset_importer/scripts/12_render_motion_sequence_t13_realasset_v6_sync3cam.py')
cp=r/'collector_probe_digest_cache.json';cache=json.loads(cp.read_text()) if cp.exists() else {}
for row in rows:
 if row['status']!='supplemental_grid_completed':continue
 folder=r/row['job_id'];p=folder/'receipt.json';actual=json.loads(p.read_text())
 if actual!=row:raise ValueError('noncanonical supplemental result')
 if hashlib.sha256(renderer.read_bytes()).hexdigest()!=row['backend_sha256']:raise ValueError('original full renderer changed')
 bootstrap=r.parent/'genesis_seed_bootstrap.py'
 if hashlib.sha256(bootstrap.read_bytes()).hexdigest()!=row['seed_bootstrap_sha256']:raise ValueError('seed bootstrap changed')
 probes=[]
 for p in folder.glob('*/receipt.json'):
  v=json.loads(p.read_text());v['state_path']=verify_probe_files(v,p.parent,cache)
  if v['backend_sha256']!=row['backend_sha256'] or v['seed_bootstrap_sha256']!=row['seed_bootstrap_sha256']:raise ValueError('probe provenance mismatch')
  if v['supplemental_init_seed']!=0:raise ValueError('wrong probe seed')
  text=re.sub(r'\x1b\[[0-9;]*m','',(p.parent/'run.log').read_text(errors='replace'))
  if not re.search(r'seed:\s*0\b',text):raise ValueError('actual Genesis seed not verified')
  probes.append(v)
 out.append(dict(result=row,probes=probes,canonical_result_sha256=hashlib.sha256((folder/'receipt.json').read_bytes()).hexdigest()))
temp=cp.with_name(cp.name+'.'+str(os.getpid())+'.tmp');temp.write_text(json.dumps(cache));temp.replace(cp)
print(json.dumps(out))
'''.replace('VERIFY',inspect.getsource(verify_probe_files)).replace('DIRECTORY',repr(launch['root']))
    evidence=json.loads(remote_text(launch['host'],code,timeout=300));byid={j['job_id']:j for j in jobs};rows=[]
    for e in evidence:e['source_root']=launch['root']
    dense_path=ROOT/'t13_dense_seeded_scans_launch_20261021.json';dense_completed=0;dense_planned=0
    if dense_path.exists():
        dense=json.loads(dense_path.read_text());dense_jobs=json.loads((ROOT/'t13_dense_seeded_scans_plan_20261021.json').read_text());dense_planned=len(dense_jobs)
        extra=json.loads(remote_text(dense['host'],code.replace(repr(launch['root']),repr(dense['root'])),timeout=300))
        selected={e['result']['job_id']:e for e in evidence}
        for e in extra:
            e['source_root']=dense['root'];selected[e['result']['job_id']]=e
        evidence=list(selected.values());dense_completed=len(extra)
        byid.update({j['job_id']:j for j in dense_jobs})
    for e in evidence:rows.extend(bind(byid[e['result']['job_id']],e['result'],e['probes']))
    (ROOT/'t13_seeded_supplement_evidence_20261021.json').write_text(json.dumps(evidence,indent=2))
    output=ROOT/'original_value_distance_ledger/t13_seeded_supplement_probe_distances.jsonl'
    output.write_text(''.join(json.dumps(r)+'\n' for r in rows))
    summary=dict(completed_jobs=len(evidence),planned_jobs=len(jobs),jobs_with_intervals=sum(bool(e['result']['local_intervals']) for e in evidence),
        jobs_without_observed_flip=sum(not e['result']['local_intervals'] for e in evidence),local_intervals=sum(len(e['result']['local_intervals']) for e in evidence),
        completed_probe_videos=len(rows),probe_videos_with_distances=sum(bool(r['distances']) for r in rows),
        full_grid_planned_jobs=dense_planned,full_grid_completed_jobs=dense_completed,
        original_release_labels_overwritten=0,formal_admissions=0,seed_scope='new seed0 control; original seed was not recovered')
    (ROOT/'t13_seeded_supplement_summary_20261021.json').write_text(json.dumps(summary,indent=2));print(json.dumps(summary))


if __name__=='__main__':main()
