"""Freeze and launch two fair, resumable, own-source-seed search queues."""
import base64
import copy
import gzip
import hashlib
import json
from pathlib import Path
from scripts.boundary_ssh import remote_text
from scripts.export_original_boundary_distances import ROOT


def main():
    jobs=json.loads(gzip.decompress((ROOT/'five_scene_conditional_source_jobs_20261023.json.gz').read_bytes()))
    canonical='/home/wangzijun_p25/liyuhan/phydataset/ase_asset_importer/scripts/render_t11_r010_slow_chain.py'
    expected={p:d for j in jobs for p,d in j['backend_sources'].items()};expected[canonical]=None
    code="import pathlib,hashlib,json;print(json.dumps({p:(hashlib.sha256(pathlib.Path(p).read_bytes()).hexdigest() if pathlib.Path(p).is_file() else None) for p in PATHS}))".replace('PATHS',repr(list(expected)))
    actual=json.loads(remote_text('p25',code,timeout=45))
    relocated={p:d for p,d in expected.items() if d and actual.get(p)!=d and p.startswith('/21231_data1/')}
    bundle={}
    if relocated:
        parent='/21231_data1/liyuhan_t11_genesis_20261016/importer'
        names=['scripts/render_t11_r010_slow_chain.py','scripts/06_run_genesis_import.py','scripts/09_render_scene_video.py','scripts/placement_utils.py','t15_edge_fall.py']
        code="import pathlib,json,base64;root=pathlib.Path(BASE);print(json.dumps({n:base64.b64encode((root/n).read_bytes()).decode() for n in NAMES}))".replace('BASE',repr(parent)).replace('NAMES',repr(names))
        bundle={n:base64.b64decode(s) for n,s in json.loads(remote_text('p26',code,timeout=45)).items()}
        if any(hashlib.sha256(bundle['scripts/render_t11_r010_slow_chain.py']).hexdigest()!=d for d in relocated.values()):raise ValueError('original T11 snapshot changed')
    helpers={n:Path('scripts',n).read_bytes() for n in ['conditional_family_search.py','conditional_family_pipeline.py','five_scene_boundary_rules.py','published_contact_vectors.py']}
    launches=[]
    for shard in range(2):
        base='/data_cached/wangzijun_p25/liyuhan/five_scene_own_seed_20261023/shard_'+str(shard)
        selected=copy.deepcopy(jobs[shard::2])
        files=dict(helpers)
        files.update({'frozen_t11_importer/'+n:raw for n,raw in bundle.items()})
        for job in selected:
            sources={}
            for p,d in job['backend_sources'].items():
                resolved=p
                if actual.get(p)!=d:
                    if p in relocated:
                        resolved=base+'/frozen_t11_importer/scripts/render_t11_r010_slow_chain.py'
                        job['backend_path_relocation']=dict(original=p,execution=resolved,sha256=d)
                        for n,raw in bundle.items():sources[base+'/frozen_t11_importer/'+n]=hashlib.sha256(raw).hexdigest()
                    elif job['scene_id']=='T11' and actual[canonical]==d:resolved=canonical
                    else:raise ValueError('original backend unavailable or changed: '+p)
                sources[resolved]=d
                if job['renderer']==p:job['renderer']=resolved
            for name,raw in helpers.items():sources[base+'/'+name]=hashlib.sha256(raw).hexdigest()
            job['backend_sources']=sources
            identity={k:job[k] for k in ['scene_id','family_id','source_state_sha256','source_config_sha256','expected','grid','backend_sources']}
            job['job_id']=hashlib.sha256(json.dumps(identity,sort_keys=True).encode()).hexdigest()[:24]
        local='five_scene_own_seed_shard_'+str(shard)+'_20261023.json.gz'
        (ROOT/local).write_bytes(gzip.compress(json.dumps(selected).encode(),mtime=0))
        payload={n:base64.b64encode(raw).decode() for n,raw in files.items()}
        payload['jobs.json']=base64.b64encode(gzip.compress(json.dumps(selected).encode(),mtime=0)).decode()
        code=r'''
import pathlib,json,base64,subprocess,os,hashlib,gzip
b=pathlib.Path(BASE);b.mkdir(parents=True,exist_ok=True);marker=b/'launch.json'
if marker.exists():raise ValueError('inspect previous queue before restarting')
for n,s in FILES.items():
 p=b/n;p.parent.mkdir(parents=True,exist_ok=True);raw=base64.b64decode(s);p.write_bytes(gzip.decompress(raw) if n=='jobs.json' else raw)
root=b/'run';root.mkdir();python='/home/wangzijun_p25/miniconda3/envs/genesis/bin/python'
env=dict(os.environ,PYOPENGL_PLATFORM='egl',OMP_NUM_THREADS='2',MKL_NUM_THREADS='2')
with (b/'pipeline.log').open('w') as log:
 p=subprocess.Popen([python,str(b/'conditional_family_pipeline.py'),'--plan',str(b/'jobs.json'),'--root',str(root),'--gpu','auto','--python',python,'--worker',str(b/'conditional_family_search.py')],env=env,stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
out=dict(host='p25',root=str(root),pipeline_root=str(b),pid=p.pid,kind='five_scene',plan=str(b/'jobs.json'),plan_sha256=hashlib.sha256((b/'jobs.json').read_bytes()).hexdigest(),planned_jobs=len(json.loads((b/'jobs.json').read_text())),gpu='auto_per_probe')
marker.write_text(json.dumps(out));print(json.dumps(out))
'''.replace('BASE',repr(base)).replace('FILES',repr(payload))
        launch=json.loads(remote_text('p25',code,timeout=60,python='/home/wangzijun_p25/miniconda3/envs/genesis/bin/python'));launch['local_plan']=local
        (ROOT/('five_scene_own_seed_'+str(shard)+'_launch_20261023.json')).write_text(json.dumps(launch,indent=2));launches.append(launch)
    marker=ROOT/'conditional_family_launches_20261023.json';previous=json.loads(marker.read_text())
    marker.write_text(json.dumps(previous+launches,indent=2));print(json.dumps(launches))


if __name__=='__main__':main()
