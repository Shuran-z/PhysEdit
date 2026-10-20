"""Original V11 backend scan for every published T15 parameter context on p25.

Uses the released physical profile and its original intervention mapping. Retains
all outcome flips and all failures. A scan with no flip is reported as such.
"""
import argparse
import copy
import fcntl
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import time

BASE=Path('/home/wangzijun_p25/liyuhan/phydataset/ase_asset_importer/everyday_bifurcation_T15_v4_edge_transfer')
PYTHON='/home/wangzijun_p25/miniconda3/envs/genesis/bin/python'
FIELDS={'cfA':'initial_velocity_mps','cfB':'laptop_edge_margin_m','cfC':'phone_offset_y_scan_m'}
ALLOWED={'cfA':{('t15v4_driver_book','motion','initial_velocity',0)},
 'cfB':{('t15v4_driver_book','pose','position',0),('t15v4_closed_laptop','pose','position',0)},
 'cfC':{('t15v4_floor_phone','pose','position',1)}}


def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()


def differences(a,b,path=()):
    if isinstance(a,dict) and isinstance(b,dict):
        if set(a)!=set(b):return [path]
        return [p for k in a for p in differences(a[k],b[k],path+(k,))]
    if isinstance(a,list) and isinstance(b,list):
        if len(a)!=len(b):return [path]
        return [p for k in range(len(a)) for p in differences(a[k],b[k],path+(k,))]
    return [] if a==b else [path]


def get(value,path):
    for key in path:value=value[key]
    return value


def put(value,path,item):
    for key in path[:-1]:value=value[key]
    value[path[-1]]=item


def save(path,data):
    temp=path.with_suffix('.tmp');temp.write_text(json.dumps(data,indent=2));temp.replace(path)


def main():
    p=argparse.ArgumentParser();p.add_argument('--root',required=True);p.add_argument('--gpu',default='3');p.add_argument('--grid',type=int,default=9)
    p.add_argument('--expand-after-root');p.add_argument('--wait-pid',type=int)
    args=p.parse_args();root=Path(args.root);root.mkdir(parents=True,exist_ok=True)
    lock=(root/'worker.lock').open('w');fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
    manifest_path=BASE/'configs/v11_20260914/delivery/manifest.json';manifest=json.loads(manifest_path.read_text());source=BASE/'scripts/t15_v11_physics.py'
    groups={}
    for r in manifest:
        if r['slot'].startswith('cf') and r['slot'].endswith('rep01'):
            key=(r['background_id'],r['gravity_id'],r['slot'].split('_')[0]);groups.setdefault(key,[]).append(r)
    if len(groups)!=60:raise ValueError('expected original T15 60 family contexts')
    if args.expand_after_root:
        parent=Path(args.expand_after_root);deadline=time.monotonic()+8*3600
        while args.wait_pid:
            proc=Path('/proc')/str(args.wait_pid)/'cmdline'
            if not proc.exists() or str(parent).encode() not in proc.read_bytes():break
            if time.monotonic()>deadline:raise TimeoutError('original-domain worker still running after eight hours')
            time.sleep(20)
        prior=json.loads((parent/'status.json').read_text())
        if len(prior)!=60:raise ValueError('original-domain scan is incomplete; do not infer missing results')
        selected={tuple(r['context']) for r in prior if r['status']=='scanned_original_domain' and not r['transitions']}
        groups={key:entries for key,entries in groups.items() if key in selected}
    result=[]
    for key,entries in sorted(groups.items()):
        folder=root/('__'.join(key));folder.mkdir(exist_ok=True)
        receipt=folder/'receipt.json'
        if receipt.exists():
            old=json.loads(receipt.read_text())
            if old['backend_sha256']!=sha(source):raise ValueError('backend changed')
            result.append(old);save(root/'status.json',result);continue
        try:
            if shutil.disk_usage(root).free<30*1024**3:raise RuntimeError('stop: less than 30GiB free')
            family=key[2];field=FIELDS[family]
            items=sorted([(r,json.loads(Path(r['config']).read_text())) for r in entries],key=lambda x:x[1]['sample_metadata'][field])
            if len(items)!=3:raise ValueError('missing original triplet')
            lo,mid,hi=[c for _,c in items];a,b=lo['sample_metadata'][field],hi['sample_metadata'][field]
            objects=[{o['name']:o for o in c['dynamic_objects']} for _,c in items]
            changed=differences(objects[0],objects[2])
            if not changed or set(changed)-ALLOWED[family]:raise ValueError('unexpected original physical intervention')
            reconstructed=copy.deepcopy(objects[0]);ratio=(mid['sample_metadata'][field]-a)/(b-a)
            for path in changed:put(reconstructed,path,get(objects[0],path)+ratio*(get(objects[2],path)-get(objects[0],path)))
            for path in differences(reconstructed,objects[1]):
                x,y=get(reconstructed,path),get(objects[1],path)
                if not isinstance(x,(int,float)) or abs(x-y)>1e-9:raise ValueError('nonaffine original intervention')
            profile=lo['sample_metadata']['physics_profile']
            if any(c['sample_metadata']['physics_profile']!=profile for _,c in items):raise ValueError('original solver profile changes across triplet')
            theta_values=sorted(set([a+(b-a)*i/(args.grid-1) for i in range(args.grid)]+[c['sample_metadata'][field] for _,c in items]))
            domain=[a,b]
            if args.expand_after_root:
                domain={'cfA':[max(0.,.75*a),1.3*b],'cfB':[.02,.30],'cfC':[-.30,.40]}[family]
                theta_values=sorted(set([domain[0]+(domain[1]-domain[0])*i/(args.grid-1) for i in range(args.grid)]+[c['sample_metadata'][field] for _,c in items]))
            probes=[]
            for i,theta in enumerate(theta_values):
                c=copy.deepcopy(lo);byname={o['name']:o for o in c['dynamic_objects']}
                for path in changed:put(byname,path,get(objects[0],path)+(theta-a)/(b-a)*(get(objects[2],path)-get(objects[0],path)))
                sid='T15_supplemental_'+('__'.join(key))+f'__p{i:02}'
                out=folder/sid;cp=folder/(sid+'.json');c['sample_id']=sid;c['sample_metadata'][field]=theta
                c['sample_metadata'].update(calibration_only=True,formal_candidate=False,supplemental_search=True)
                c['annotations']['save_path']=str(out/'metadata/physics.json');save(cp,c)
                probes.append(dict(sample_id=sid,config=str(cp),config_sha256=sha(cp),output=str(out),theta=theta))
            plan=folder/'manifest.json';save(plan,probes)
            steps=round(1/(30*profile['solver_dt_s']))
            command=[PYTHON,str(source),'--manifest',str(plan),'--steps',str(steps),'--timeconst',str(profile['constraint_timeconst']),'--precision',str(profile['precision_bits'])]
            if profile['box_box_detection']:command.append('--box')
            if profile['settle_seconds']==1:command.append('--settle')
            if profile['integrator']=='implicitfast':command.append('--exact')
            with (folder/'run.log').open('w') as log:
                run=subprocess.run(command,env=dict(os.environ,CUDA_VISIBLE_DEVICES=args.gpu),stdout=log,stderr=subprocess.STDOUT,timeout=1200)
            if run.returncode:raise RuntimeError('original backend failed: '+str(folder/'run.log'))
            outcomes=json.loads((folder/'results.json').read_text())
            references=[]
            event='laptop_contacts_phone' if family=='cfC' else 'laptop_falls_to_floor'
            for original,c in items:
                state=Path(original['output'])/'metadata/physics.json'
                qa=Path(original['output'])/'qa/physics_audit_scene_bounds.json'
                if not qa.exists():qa=qa.with_name('physics_audit.json')
                audit=json.loads(qa.read_text());value=c['sample_metadata'][field]
                match=next(r for r in outcomes if r['theta']==value)
                label=int(audit['event_frames'].get(event) is not None);replay=int(match['audit']['event_frames'].get(event) is not None)
                references.append(dict(sample_id=original['sample_id'],theta=value,config_sha256=sha(Path(original['config'])),state_sha256=sha(state),audit_sha256=sha(qa),reference_label=label,replay_label=replay,labels_match=label==replay))
            transitions=[]
            for left,right in zip(outcomes,outcomes[1:]):
                if not left['audit']['valid'] or not right['audit']['valid']:continue
                labels=[int(r['audit']['event_frames'].get(event) is not None) for r in [left,right]]
                if labels[0]!=labels[1]:transitions.append(dict(bracket=[left['theta'],right['theta']],labels=labels))
            row=dict(context=key,status='scanned_expanded_domain' if args.expand_after_root else 'scanned_original_domain',backend_sha256=sha(source),manifest_sha256=sha(manifest_path),target_event=event,domain=domain,original_domain=[a,b],points=len(outcomes),valid=sum(r['audit']['valid'] for r in outcomes),references=references,transitions=transitions,results_sha256=sha(folder/'results.json'),output=str(folder),profile=profile,scope='sampled local transitions only; a no-transition grid is not proof of absence between samples')
            save(receipt,row)
        except Exception as exc:row=dict(context=key,status='failed',error=str(exc),output=str(folder))
        result.append(row);save(root/'status.json',result)
        print(json.dumps({k:row[k] for k in ['context','status']}|dict(points=row.get('points'),transitions=len(row.get('transitions',[])),error=row.get('error'))),flush=True)


if __name__=='__main__':main()
