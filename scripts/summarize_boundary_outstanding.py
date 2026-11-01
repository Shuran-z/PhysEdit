"""Count unique registered conditional search jobs, separating optional refinement."""
import collections,gzip,hashlib,json
from pathlib import Path
from scripts.export_original_boundary_distances import ROOT

def main():
    launches=json.loads((ROOT/'conditional_family_launches_20261023.json').read_text(encoding='utf8'))
    jobs={};done=set();failed=set();source_mismatch=set();stale=[]
    for launch in launches:
        plan=ROOT/launch.get('local_plan','conditional_'+launch['kind']+'_jobs_20261023.json.gz')
        for job in json.loads(gzip.decompress(plan.read_bytes())):
            jobs.setdefault(job['job_id'],job)
        identity={k:launch[k] for k in ['host','root','plan_sha256']}
        key=hashlib.sha256(json.dumps(identity,sort_keys=True).encode()).hexdigest()
        path=ROOT/'conditional_collector_checkpoints'/(key+'.json.gz')
        if not path.exists():stale.append(launch['root']);continue
        data=json.loads(gzip.decompress(path.read_bytes()));assert data['identity']==identity
        data=data['data'];done.update(r['job_id'] for r in data['results'])
        failed.update(r['job_id'] for r in data['status'] if r['status']=='failed')
        source_mismatch.update(r['job_id'] for r in data['source_checks'] if r.get('source_event_mismatches'))
    assert done<=jobs.keys()
    scenes={f'T{i:02}':{'registered_conditional_jobs':0,'completed_conditional_jobs':0,'unfinished_conditional_jobs':0,'failed_attempts_unresolved':0,'source_event_mismatch_unresolved':0} for i in range(1,21)}
    unresolved=[]
    for key,job in jobs.items():
        c=scenes[job['scene_id']];c['registered_conditional_jobs']+=1
        if key in done:c['completed_conditional_jobs']+=1
        else:
            c['unfinished_conditional_jobs']+=1
            if key in failed:c['failed_attempts_unresolved']+=1
            if key in source_mismatch:c['source_event_mismatch_unresolved']+=1
            unresolved.append({'job_id':key,'scene_id':job['scene_id'],'family_id':job['family_id'],'sample_id':job['sample_id'],'failed_attempt':key in failed,'source_mismatch':key in source_mismatch})
    t18=json.loads((ROOT/'t18_event_distance_summary_20261020.json').read_text(encoding='utf8'))
    summary={'scope':'Unique registered conditional jobs only. Optional refinement, publication mapping and unregistered contexts are not counted as missing critical values. Completed scans may contain no observed transition.','conditional_registered':len(jobs),'conditional_completed':len(done),'conditional_unfinished':len(jobs)-len(done),'t18_registered':t18['source_candidates'],'t18_completed':t18['completed_contexts'],'t18_unfinished':t18['pending_contexts']+t18['failed_contexts'],'T07_B_unresolved_endpoint':1,'by_scene':scenes,'missing_checkpoints':stale,'unresolved_jobs':unresolved}
    path=ROOT/'OUTSTANDING_REGISTERED_JOBS_20261030.json';path.write_text(json.dumps(summary,indent=2),encoding='utf8')
    print(json.dumps({k:v for k,v in summary.items() if k not in ['by_scene','unresolved_jobs']}))
if __name__=='__main__':main()
