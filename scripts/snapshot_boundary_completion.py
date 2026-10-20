"""Refresh current evidence and live numerical job progress, without admitting samples."""
import collections
import gzip
import json
from pathlib import Path
import subprocess

ROOT=Path('review/scene_family_completion_20261018')


def main():
    jobs=[]
    for token,launch in [('A','t07_search_launch_20261019.json'),('C','t07_C_search_launch_20261019.json'),('C_home_retry','t07_C_home_retry_launch_20261019.json')]:
        registration=json.loads((ROOT/launch).read_text(encoding='utf-8'))
        code='''import pathlib,json,hashlib
root=pathlib.Path(ROOT);pid=PID
command=pathlib.Path('/proc')/str(pid)/'cmdline'
running=command.exists() and str(root).encode() in command.read_bytes()
rows=json.loads((root/'results.json').read_text()) if (root/'results.json').exists() else []
print(json.dumps(dict(root=str(root),pid=pid,running=running,worker_sha256=hashlib.sha256((root/'worker.py').read_bytes()).hexdigest(),results=rows)))
'''.replace('ROOT',repr(registration['root'])).replace('PID',str(registration['pid']))
        p=subprocess.run(['ssh','-o','BatchMode=yes','-o','ConnectTimeout=12','p25','python3 -'],input=code.encode(),capture_output=True,timeout=30)
        p.check_returncode();data=json.loads(p.stdout)
        (ROOT/('t07_original_'+token+'_results_20261019.json')).write_text(json.dumps(data['results'],indent=2),encoding='utf-8')
        jobs.append(dict(family=token,planned=registration.get('planned_contexts',60),completed=sum(r['status']=='local_transition_bracket' for r in data['results']),failed=sum(r['status']=='failed' for r in data['results']),running=data['running'],pid=data['pid'],root=data['root'],worker_sha256=data['worker_sha256']))
    for scene,launch in [('T15','t15_all_context_search_launch_20261019.json'),('T15_expanded','t15_expanded_context_search_launch_20261019.json'),('T13','t13_full_search_launch_20261019.json'),('T14','t14_formal_search_launch_20261019.json')]:
        path=ROOT/launch
        if not path.exists():continue
        registration=json.loads(path.read_text(encoding='utf-8'))
        code='''import pathlib,json,hashlib
root=pathlib.Path(ROOT);pid=PID
proc=pathlib.Path('/proc')/str(pid)/'cmdline'
rows=json.loads((root/'status.json').read_text()) if (root/'status.json').exists() else []
dependency=DEPENDENCY
waiting=dependency is not None and (pathlib.Path('/proc')/str(dependency)/'cmdline').exists()
print(json.dumps(dict(running=proc.exists() and str(root).encode() in proc.read_bytes(),waiting_for_dependency=waiting,rows=rows)))
'''.replace('ROOT',repr(registration['root'])).replace('PID',str(registration['pid'])).replace('DEPENDENCY',repr(registration.get('wait_for_pid')))
        p=subprocess.run(['ssh','-o','BatchMode=yes','-o','ConnectTimeout=12','p25','python3 -'],input=code.encode(),capture_output=True,timeout=30)
        p.check_returncode();data=json.loads(p.stdout)
        (ROOT/(scene.lower()+'_all_context_status_20261019.json')).write_text(json.dumps(data['rows'],indent=2),encoding='utf-8')
        jobs.append(dict(scene=scene,planned=registration.get('planned_contexts',registration.get('planned_intervals')),
            completed=sum(r['status'] in ['scanned_original_domain','scanned_expanded_domain','scanned_original_triplet','local_transition_bracket'] for r in data['rows']),
            failed=sum(r['status']=='failed' for r in data['rows']),running=data['running'],waiting_for_dependency=data['waiting_for_dependency'],pid=registration['pid'],root=registration['root']))
    recovered={}
    for scene in ['T01','T04','T05','T07','T08','T11','T12']:
        rows=[r for path in (ROOT/'completion_states').glob(scene+'_*.json') for r in json.loads(path.read_text(encoding='utf-8'))]
        ids=[r['sample_id'] for r in rows]
        if len(ids)!=len(set(ids)):raise ValueError('duplicate state receipts for '+scene)
        recovered[scene]=dict(records=len(rows),recovered=sum(bool(r.get('local_path')) for r in rows))
    latest_t11=[r for p in ROOT.glob('t11_latest_*_evidence_20261019.json') for r in json.loads(p.read_text(encoding='utf-8'))]
    families=collections.Counter(next(f['data']['experiment']['formal_design']['changed_variable'] for f in r['files'] if '/configs/' in f['archive_path']) for r in latest_t11)
    t12=collections.Counter()
    with gzip.open(ROOT/'t12_latest_verified_records_20261019.jsonl.gz','rt',encoding='utf-8') as stream:
        for line in stream:
            r=json.loads(line);t12['configs' if '/configs/' in r['path'] else 'states' if '/metadata_shared/' in r['path'] else 'success_records']+=1
    t13=collections.Counter()
    for line in (ROOT/'t13_latest_archive_records_20261019.jsonl').open(encoding='utf-8'):
        r=json.loads(line);t13['configs' if 'config' in r else 'states']+=1
    code="""import pathlib,json
p=pathlib.Path('/data_cached/wangzijun_p25/liyuhan/t03_current_recovery_20261019/status.json')
rows=json.loads(p.read_text()) if p.exists() else []
print(json.dumps(dict(selected=880,recovered=sum(r['status']=='verified_published_state' for r in rows),failed=sum(r['status']=='failed' for r in rows),status='recovery_in_progress' if len(rows)<880 else 'recovery_finished')))
"""
    p=subprocess.run(['ssh','-o','BatchMode=yes','-o','ConnectTimeout=12','p25','python3 -'],input=code.encode(),capture_output=True,timeout=30)
    p.check_returncode();t03=json.loads(p.stdout)
    additional_jobs=[]
    for token,filename,default_host in [('T15_refined','t15_refined_missing_launch_20261019.json','p25'),('T12_refined','t12_supplemental_refinement_launch.json','p26')]:
        launch_path=ROOT/filename
        if not launch_path.exists():continue
        launch=json.loads(launch_path.read_text());host=launch.get('host',default_host)
        code='''import pathlib,json,collections
root=pathlib.Path(ROOT);pid=PID;p=pathlib.Path('/proc')/str(pid)/'cmdline'
rows=json.loads((root/'status.json').read_text()) if (root/'status.json').exists() else []
resource=json.loads((root/'resource_status.json').read_text()) if (root/'resource_status.json').exists() else {}
print(json.dumps(dict(running=p.exists() and str(root).encode() in p.read_bytes(),statuses=dict(collections.Counter(r['status'] for r in rows)),resource=resource)))
'''.replace('ROOT',repr(launch['root'])).replace('PID',str(launch['pid']))
        run=subprocess.run(['ssh','-o','BatchMode=yes',host,'python3 -'],input=code.encode(),capture_output=True,timeout=30);run.check_returncode()
        additional_jobs.append(dict(scene=token,host=host,root=launch['root'],pid=launch['pid'],**json.loads(run.stdout)))
    summaries={p.stem:json.loads(p.read_text()) for p in (ROOT/'original_value_distance_ledger').glob('*summary.json')}
    snapshot=dict(date='2026-10-19',all_scenes_completed=False,
        live_releases=[{k:r[k] for k in ['repo','revision','last_modified']} for r in json.loads((ROOT/'live_release_layout_20261019.json').read_text(encoding='utf-8'))],
        existing_release_state_recovery=recovered,
        latest_release_recovery=dict(T03=t03,T11=dict(configs=len(latest_t11),quality_records=len(latest_t11),families=dict(families),binding='published per-file SHA256'),
          T12=dict(**t12,binding='HF Git/LFS IDs; see t12_latest_verified_records_20261019.jsonl.gz'),
          T13=dict(**t13,binding='four published archive SHA256 values')),
        numerical_jobs=jobs,additional_numerical_jobs=additional_jobs,numerical_distance_outputs=summaries,
        T19='user confirmed replacement still rendering; old release retired',
        release_selection=json.loads(Path('docs/critical_boundary/RELEASE_SELECTION.json').read_text(encoding='utf-8')),
        formal_near_reference_count=json.loads((ROOT/'nearacc_readiness_summary.json').read_text(encoding='utf-8'))['completed_formal_near_reference_registrations'],
        important='Recovered current release configs/states are evidence inputs; do not equate them with completed thresholds or formal NearAcc references.')
    (ROOT/'LATEST_EXECUTION_STATUS_20261019.json').write_text(json.dumps(snapshot,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(snapshot,ensure_ascii=False,indent=2))


if __name__=='__main__':main()
