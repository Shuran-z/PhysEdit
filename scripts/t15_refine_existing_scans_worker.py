"""Refine missing T15 boundaries from completed original-backend scans.

Batch only compatible material/shape/solver profiles, preserve all named local
windows, and retain failures. This computes references; no visual or inversion
admission is performed here.
"""
import argparse
import copy
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess

BASE=Path('/home/wangzijun_p25/liyuhan/phydataset/ase_asset_importer/everyday_bifurcation_T15_v4_edge_transfer')
BACKEND=BASE/'scripts/t15_v11_physics.py'
PYTHON='/home/wangzijun_p25/miniconda3/envs/genesis/bin/python'
FIELDS={'cfA':'initial_velocity_mps','cfB':'laptop_edge_margin_m','cfC':'phone_offset_y_scan_m'}
PATHS={'cfA': [('t15v4_driver_book','motion','initial_velocity',0)],
 'cfB':[('t15v4_driver_book','pose','position',0),('t15v4_closed_laptop','pose','position',0)],
 'cfC':[('t15v4_floor_phone','pose','position',1)]}


def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def save(path,data):
    temp=path.with_suffix('.tmp');temp.write_text(json.dumps(data,indent=2));temp.replace(path)


def at(value,path):
    for key in path:value=value[key]
    return value


def put(value,path,new):
    for key in path[:-1]:value=value[key]
    value[path[-1]]=new


def interpolate(left,right,theta,family):
    c=copy.deepcopy(left);field=FIELDS[family];a,b=left['sample_metadata'][field],right['sample_metadata'][field]
    if not a<b:raise ValueError('unordered source endpoints')
    lo={o['name']:o for o in left['dynamic_objects']};hi={o['name']:o for o in right['dynamic_objects']};out={o['name']:o for o in c['dynamic_objects']}
    for path in PATHS[family]:put(out,path,at(lo,path)+(theta-a)/(b-a)*(at(hi,path)-at(lo,path)))
    # Only these physical paths may differ across an original parameter slice.
    masked=copy.deepcopy(hi)
    for path in PATHS[family]:put(masked,path,at(lo,path))
    if masked!=lo:raise ValueError('source endpoints change fixed physics')
    c['sample_metadata'][field]=theta
    return c


def compatibility(config):
    return dict(profile={k:v for k,v in config['sample_metadata']['physics_profile'].items() if k!='config_sha256'},
        specs=[{k:o.get(k) for k in ['name','size','mass','friction','fixed']} for o in config['dynamic_objects']])


def main():
    import fcntl
    p=argparse.ArgumentParser();p.add_argument('--root',required=True);p.add_argument('--gpu',default='3');p.add_argument('--scans',nargs='+',required=True);args=p.parse_args()
    root=Path(args.root);root.mkdir(parents=True,exist_ok=True);lock=(root/'worker.lock').open('w');fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
    jobs=[]
    for source_root in args.scans:
        for row in json.loads((Path(source_root)/'status.json').read_text(encoding='utf-8')):
            if not row['status'].startswith('scanned_'):continue
            if any(not r['labels_match'] for r in row['references']):raise ValueError('scan anchor mismatch')
            if sha(BACKEND)!=row['backend_sha256']:raise ValueError('original backend changed')
            folder=Path(row['output']);probes=json.loads((folder/'manifest.json').read_text(encoding='utf-8'));points={r['theta']:r for r in probes}
            for window in row['transitions']:
                a,b=window['bracket'];left,right=[json.loads(Path(points[x]['config']).read_text(encoding='utf-8')) for x in [a,b]]
                family=row['context'][2];interpolate(left,right,(a+b)/2,family)
                key=hashlib.sha256(json.dumps(dict(context=row['context'],event=row['target_event'],source=str(folder),window=window),sort_keys=True).encode()).hexdigest()[:20]
                jobs.append(dict(job_id=key,context=row['context'],family=family,target_event=row['target_event'],source_scan_root=source_root,source_folder=str(folder),
                    source_bracket=[a,b],bracket=[a,b],labels=window['labels'],left_config=left,right_config=right,tolerance=.001 if family=='cfA' else .0005,
                    source_references=row['references'],status='refining',probes=[]))
    if len({r['job_id'] for r in jobs})!=len(jobs):raise ValueError('duplicate local window')
    state=root/'status.json'
    if state.exists():
        old={r['job_id']:r for r in json.loads(state.read_text(encoding='utf-8'))}
        for i,r in enumerate(jobs):
            if r['job_id'] in old:jobs[i]=old[r['job_id']]
    save(root/'plan.json',jobs)
    for round_index in range(20):
        active=[r for r in jobs if r['status']=='refining' and r['bracket'][1]-r['bracket'][0]>r['tolerance']]
        if not active:break
        groups={}
        for job in active:
            theta=sum(job['bracket'])/2;c=interpolate(job['left_config'],job['right_config'],theta,job['family'])
            key=hashlib.sha256(json.dumps(compatibility(c),sort_keys=True).encode()).hexdigest()[:16]
            groups.setdefault(key,[]).append((job,theta,c))
        for group,items in groups.items():
            if shutil.disk_usage(root).free<30*1024**3:raise RuntimeError('disk below 30GiB')
            out=root/('round%02d_'%round_index+group);out.mkdir(exist_ok=True);manifest=[]
            for job,theta,c in items:
                sid='T15_refine_'+job['job_id']+'_'+str(round_index);folder=out/sid;cp=out/(sid+'.json')
                c['sample_id']=sid;c['sample_metadata'].update(calibration_only=True,formal_candidate=False,supplemental_search=True)
                c['annotations']['save_path']=str(folder/'metadata/physics.json');save(cp,c)
                manifest.append(dict(sample_id=sid,theta=theta,config=str(cp),config_sha256=sha(cp),output=str(folder)))
            path=out/'manifest.json';save(path,manifest);profile=items[0][2]['sample_metadata']['physics_profile']
            command=[PYTHON,str(BACKEND),'--manifest',str(path),'--steps',str(round(1/(30*profile['solver_dt_s']))),'--timeconst',str(profile['constraint_timeconst']),'--precision',str(profile['precision_bits'])]
            if profile['box_box_detection']:command.append('--box')
            if profile['settle_seconds']==1:command.append('--settle')
            if profile['integrator']=='implicitfast':command.append('--exact')
            rp=out/'results.json'
            if not rp.exists():
                with (out/'run.log').open('w') as log:
                    run=subprocess.run(command,env=dict(os.environ,CUDA_VISIBLE_DEVICES=args.gpu),stdout=log,stderr=subprocess.STDOUT,timeout=1800)
                if run.returncode:raise RuntimeError('original backend failed; '+str(out/'run.log'))
            measured=json.loads(rp.read_text(encoding='utf-8'))
            if len(measured)!=len(items):raise ValueError('incomplete batch')
            for (job,theta,c),m,reference in zip(items,measured,manifest):
                if m['sample_id']!=reference['sample_id'] or m['theta']!=theta:raise ValueError('batch identity mismatch')
                event=job['target_event'];label=int(m['audit']['event_frames'].get(event) is not None)
                sp=Path(reference['output'])/'metadata/physics.json'
                job['probes'].append(dict(theta=theta,label=label,original_audit_valid=m['audit']['valid'],config_sha256=reference['config_sha256'],state_sha256=sha(sp),output=reference['output']))
                if not m['audit']['valid']:job['status']='stopped_at_original_audit_failure'
                elif label==job['labels'][0]:job['bracket'][0]=theta
                else:job['bracket'][1]=theta
                if job['status']=='refining' and job['bracket'][1]-job['bracket'][0]<=job['tolerance']:job['status']='refined_local_interval'
                job['backend_sha256']=sha(BACKEND)
            save(state,jobs)
            print(json.dumps(dict(round=round_index,batch=len(items),completed=sum(r['status']=='refined_local_interval' for r in jobs),stopped=sum(r['status']=='stopped_at_original_audit_failure' for r in jobs),total=len(jobs))),flush=True)
    save(state,jobs)


if __name__=='__main__':main()
