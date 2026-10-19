"""Resume exact published state recovery for unfinished scene families.

No inferred event labels; immutable release IDs and compressed-byte hashes retained.
"""
import argparse, concurrent.futures, gzip, hashlib, json, subprocess, urllib.request, base64, re
from pathlib import Path
from scripts.collect_sidecars_via_local_transport import REMOTE

OUT=Path('review/scene_family_completion_20261018/completion_states')

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--scenes',nargs='+',default=['T04','T05','T01','T07','T08','T11','T12'])
    parser.add_argument('--limit',type=int,default=0,help='Optional per-scene pilot count; zero recovers all selected states')
    args=parser.parse_args();OUT.mkdir(exist_ok=True)
    inventory=[json.loads(x) for x in Path('../dataset_splits_v2/all_selected_trajectories.jsonl').read_text(encoding='utf-8').splitlines()]
    def fetch(x):
        r=x['row'];dest=OUT/r['scene_id']/(r['sample_id']+'.json.gz');dest.parent.mkdir(exist_ok=True)
        try:
            if x.get('error'):return {**r,'error':x['error']}
            if x.get('inline') is not None:b=base64.b64decode(x['inline'])
            else:
                op=urllib.request.build_opener(urllib.request.ProxyHandler({'https':'http://127.0.0.1:7897'}))
                with op.open(x['url'],timeout=40) as response:b=response.read()
            d=json.loads(gzip.decompress(b))
            if not d.get('frames'):raise ValueError('no state frames')
            tmp=dest.with_suffix('.tmp');tmp.write_bytes(b);tmp.replace(dest)
            return {**r,'local_path':str(dest.resolve()),'sha256':hashlib.sha256(b).hexdigest(),'frames':len(d['frames'])}
        except Exception as e:return {**r,'error':type(e).__name__}
    consecutive_failures=0
    for scene in args.scenes:
        rows=[]
        for r in inventory:
            if r['event_id']!=scene or r['engine']!='genesis':continue
            paths=[p for p in r.get('sidecar_paths',[]) if 'cam01' in p and p.endswith('.json.gz')]
            if paths:rows.append(dict(scene_id=scene,sample_id=r['sample_id'],repo_id=r['repo_id'],revision=r['revision'],sidecar=paths[0]))
        rows.sort(key=lambda r:r['sample_id'])
        if args.limit:rows=rows[:args.limit]
        for i in range(0,len(rows),8):
            receipt=OUT/f'{scene}_{i//8:03}.json'
            old=json.loads(receipt.read_text()) if receipt.exists() else []
            good={r['sample_id']:r for r in old if r.get('local_path') and Path(r['local_path']).exists() and hashlib.sha256(Path(r['local_path']).read_bytes()).hexdigest()==r['sha256']}
            batch=[r for r in rows[i:i+8] if r['sample_id'] not in good]
            if not batch:continue
            try:
                code=REMOTE.replace('ROWS',repr(batch))
                proc=subprocess.Popen(['ssh','-o','BatchMode=yes','-o','ConnectTimeout=10','-o','ExitOnForwardFailure=yes','-R','127.0.0.1:0:127.0.0.1:7897','p25','/home/wangzijun_p25/miniconda3/envs/genesis/bin/python -'],stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
                try:
                    line=proc.stderr.readline()
                    match=re.search(rb'Allocated port (\d+)',line)
                    if not match:raise RuntimeError('dynamic SSH forwarding unavailable')
                    port=int(match[1])
                    prefix=f"import os\nos.environ['HTTPS_PROXY']='http://127.0.0.1:{port}'\n"
                    payload,errors=proc.communicate((prefix+code).encode(),timeout=60)
                    if proc.returncode:raise RuntimeError('remote state resolver failed')
                finally:
                    if proc.poll() is None:proc.kill();proc.communicate()
                with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:result=list(pool.map(fetch,json.loads(payload)))
                result+=list(good.values())
                receipt.write_text(json.dumps(result,ensure_ascii=False),encoding='utf-8')
                consecutive_failures=0
                print(json.dumps(dict(scene=scene,batch=i//8,recovered=sum('local_path' in r for r in result))),flush=True)
            except Exception as e:
                consecutive_failures+=1
                reason='remote_forward_unavailable' if isinstance(e,subprocess.CalledProcessError) and b'remote port forwarding failed' in (e.stderr or b'') else type(e).__name__
                print(json.dumps(dict(scene=scene,batch=i//8,error=reason)),flush=True)
                if consecutive_failures>=3:raise RuntimeError('Repeated transport failures; stop and diagnose rather than skipping every remaining batch')

if __name__=='__main__':main()
