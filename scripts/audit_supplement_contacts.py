"""Audit recorded contact depths; diagnostic prioritization, never auto rejection."""
import argparse,collections,gzip,json,time
from pathlib import Path

def save(p,d):
    p.parent.mkdir(parents=True,exist_ok=True);q=p.with_suffix('.tmp');q.write_text(json.dumps(d,indent=2));q.replace(p)

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--roots',nargs='+',required=True);ap.add_argument('--out',required=True);ap.add_argument('--expected',type=int,required=True);args=ap.parse_args()
    out=Path(args.out);out.mkdir(exist_ok=True)
    import fcntl
    lock=(out/'audit.lock').open('w');fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
    while True:
        rs={}
        for root in map(Path,args.roots):
            for p in (root/'receipts').glob('*.json'):
                r=json.loads(p.read_text())
                if r.get('media_complete'):rs[r['sample']]=(r,root)
        for sid,(r,root) in rs.items():
            dest=out/'results'/(sid+'.json')
            if dest.exists():
                previous=json.loads(dest.read_text())
                if (not previous.get('error') and previous.get('video_hashes') ==
                    {v['camera']:v['sha256'] for v in r['results']} and
                    previous.get('state_path') == r.get('trajectory',{}).get('path')):
                    continue
            try:
                sp=r.get('trajectory',{}).get('path')
                if not sp:
                    c=json.loads((root/'configs'/sid/'cam01.json').read_text());sp=c['annotations']['save_path']
                    if not Path(sp).exists() and Path(sp+'.gz').exists():sp+='.gz'
                d=json.load(gzip.open(sp,'rt') if sp.endswith('.gz') else open(sp))
                names={o['name'] for o in d['dynamic_objects']};peaks={};count=0;frames=[]
                for f in d['frames']:
                    contacts=f.get('contacts')
                    if contacts is None:continue
                    frames.append(f['frame_index'])
                    for c in contacts:
                        dep=c.get('penetration_m')
                        if dep is None:continue
                        count+=1;a=c.get('entity_a');b=c.get('entity_b');key=' / '.join(sorted([str(a),str(b)]))
                        if dep>peaks.get(key,{}).get('penetration_m',-1):
                            peaks[key]=dict(pair=key,penetration_m=dep,frame=f['frame_index'],physics_step=c.get('physics_step_index'),dynamic_pair=a in names and b in names)
                save(dest,dict(sample=sid,state_path=sp,video_hashes={v['camera']:v['sha256'] for v in r['results']},
                    contacts=count,contact_frame_count=len(frames),peaks=sorted(peaks.values(),key=lambda x:-x['penetration_m']),
                    formal_acceptance=False,interpretation='Recorded solver penetration, not directly proven visible overlap. No rejection threshold applied.'))
            except Exception as e:save(dest,dict(sample=sid,error=str(e),formal_acceptance=False))
        allrows=[json.loads(p.read_text()) for p in (out/'results').glob('*.json')]
        save(out/'status.json',dict(updated=time.time(),expected=args.expected,rendered=len(rs),audited=len(allrows),
            errors=sum('error' in r for r in allrows),complete=len(allrows)==args.expected,
            formal_acceptance=False))
        if len(allrows)==args.expected:break
        time.sleep(60)

if __name__=='__main__':main()
