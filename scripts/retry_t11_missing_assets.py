"""Run missing-asset T11 attempts where the original snapshot assets exist."""
import base64
import gzip
import hashlib
import json
from pathlib import Path
from scripts.boundary_ssh import remote_text
from scripts.export_original_boundary_distances import ROOT


def main():
    marker=ROOT/'t11_asset_host_retry_v3_launch_20261025.json'
    if marker.exists():
        print(marker.read_text());return
    all_launches=json.loads((ROOT/'conditional_family_launches_20261023.json').read_text())
    sources=[l for l in all_launches if 'five_scene_own_seed' in l['root']]
    code="""import pathlib,json
rows=[]
for l in LAUNCHES:
 p=pathlib.Path(l['root'])/'status.json'
 if p.exists():rows.extend(r['job_id'] for r in json.loads(p.read_text()) if r.get('scene_id')=='T11' and r.get('status')=='failed' and r.get('error','').startswith('original renderer failed:'))
print(json.dumps(rows))
""".replace('LAUNCHES',repr(sources))
    ids=set(json.loads(remote_text('p25',code,timeout=60)))
    jobs=[j for l in sources for j in json.loads(gzip.decompress((ROOT/l['local_plan']).read_bytes())) if j['job_id'] in ids]
    jobs=list({j['job_id']:j for j in jobs}.values())
    if not jobs:raise ValueError('no missing-asset T11 jobs remain')
    base='/21231_data1/liyuhan_t11_asset_retry_20261025_v3'
    bootstrap='/21231_data1/liyuhan_t11_genesis_20261016/critical_boundaries_20261020/egl_renderer_bootstrap.py'
    bootstrap_hash=remote_text('p26',"import pathlib,hashlib;print(hashlib.sha256(pathlib.Path("+repr(bootstrap)+").read_bytes()).hexdigest())",timeout=90).strip()
    helpers={n:Path('scripts',n).read_bytes() for n in ['conditional_family_search.py','conditional_family_pipeline.py','five_scene_boundary_rules.py','published_contact_vectors.py']}
    paths=set()
    for job in jobs:
        renderer=job['renderer'];parent=renderer.rsplit('/scripts/',1)[0]
        paths.update(parent+'/'+n for n in ['scripts/render_t11_r010_slow_chain.py','scripts/06_run_genesis_import.py','scripts/09_render_scene_video.py','scripts/placement_utils.py','t15_edge_fall.py'])
    query="import pathlib,json,base64;print(json.dumps({p:base64.b64encode(pathlib.Path(p).read_bytes()).decode() for p in PATHS}))".replace('PATHS',repr(sorted(paths)))
    originals={p:base64.b64decode(v) for p,v in json.loads(remote_text('p25',query,timeout=60)).items()}
    query=r'''
import ast,pathlib,json,base64
b=pathlib.Path('/21231_data1/liyuhan_t11_genesis_20261016/importer/scripts');pending=['common','material_utils','visual_quality'];out={}
while pending:
 name=pending.pop();p=b/(name+'.py')
 if name in out or not p.exists():continue
 raw=p.read_bytes();out[name]=base64.b64encode(raw).decode()
 for node in ast.walk(ast.parse(raw)):
  if isinstance(node,ast.ImportFrom) and node.module:pending.append(node.module.split('.')[0])
  elif isinstance(node,ast.Import):pending.extend(n.name.split('.')[0] for n in node.names)
print(json.dumps(out))
'''
    dependencies={n:base64.b64decode(v) for n,v in json.loads(remote_text('p26',query,timeout=90)).items()}
    relocation={};payload={n:base64.b64encode(raw).decode() for n,raw in helpers.items()}
    for p,raw in originals.items():
        if '/frozen_t11_importer/' in p:relative='frozen_t11_importer/'+p.split('/frozen_t11_importer/',1)[1]
        else:relative='canonical_importer/'+p.split('/ase_asset_importer/',1)[1]
        relocation[p]=base+'/'+relative;payload[relative]=base64.b64encode(raw).decode()
    for name,raw in dependencies.items():
        for prefix in ['frozen_t11_importer','canonical_importer']:
            relative=prefix+'/scripts/'+name+'.py'
            if relative not in payload:payload[relative]=base64.b64encode(raw).decode()
    mapping={}
    for job in jobs:
        old=job['job_id'];sources={}
        for p,digest in job['backend_sources'].items():
            if p in relocation:
                q=relocation[p]
            elif Path(p).name in helpers:
                q=base+'/'+Path(p).name;digest=hashlib.sha256(helpers[Path(p).name]).hexdigest()
            else:q=p
            sources[q]=digest
            if job['renderer']==p:job['renderer']=q
        for p,raw in originals.items():sources[relocation[p]]=hashlib.sha256(raw).hexdigest()
        for name,data in payload.items():
            if name.startswith(('frozen_t11_importer/','canonical_importer/')):sources[base+'/'+name]=hashlib.sha256(base64.b64decode(data)).hexdigest()
        job['backend_sources']=sources
        job['renderer_bootstrap']=bootstrap;sources[bootstrap]=bootstrap_hash
        job['job_id']=hashlib.sha256(json.dumps(dict(original_job_id=old,backend_sources=sources),sort_keys=True).encode()).hexdigest()[:24]
        job['infrastructure_retry_of']=old;mapping[job['job_id']]=old
    plan='t11_asset_host_retry_v3_jobs_20261025.json.gz'
    (ROOT/plan).write_bytes(gzip.compress(json.dumps(jobs).encode(),mtime=0))
    payload['jobs.json']=base64.b64encode(json.dumps(jobs).encode()).decode()
    code=r'''
import pathlib,json,base64,hashlib,subprocess,os
b=pathlib.Path(BASE);b.mkdir(exist_ok=True)
if (b/'launch.json').exists():print((b/'launch.json').read_text());raise SystemExit
for n,data in FILES.items():
 p=b/n;p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(base64.b64decode(data))
jobs=json.loads((b/'jobs.json').read_text())
for j in jobs:
 for p,h in j['backend_sources'].items():
  if hashlib.sha256(pathlib.Path(p).read_bytes()).hexdigest()!=h:raise ValueError('original snapshot mismatch: '+p)
 profile=j['base_config']['experiment'].get('background_profile_path')
 if profile and not pathlib.Path(profile).exists():raise ValueError('original profile unavailable')
r=b/'run';r.mkdir();python='/home/wangzijun_p25/miniconda3/envs/genesis/bin/python'
env=dict(os.environ,PYOPENGL_PLATFORM='egl',OMP_NUM_THREADS='2',MKL_NUM_THREADS='2',GENESIS_DISABLE_CV2='1',__EGL_VENDOR_LIBRARY_FILENAMES='/usr/share/glvnd/egl_vendor.d/10_nvidia.json')
env['LD_PRELOAD']=':'.join('/usr/lib/x86_64-linux-gnu/'+n for n in ['libGLdispatch.so.0','libGLX.so.0','libGL.so.1','libEGL.so.1','libOpenGL.so.0'])
with (r/'worker.log').open('w') as log:
 p=subprocess.Popen([python,str(b/'conditional_family_search.py'),'--plan',str(b/'jobs.json'),'--root',str(r),'--gpu','auto','--python',python],stdout=log,stderr=subprocess.STDOUT,start_new_session=True,env=env)
out=dict(host='p26',root=str(r),pipeline_root=str(b),pid=p.pid,kind='five_scene',plan=str(b/'jobs.json'),plan_sha256=hashlib.sha256((b/'jobs.json').read_bytes()).hexdigest(),planned_jobs=len(jobs),gpu='auto_per_probe')
(b/'launch.json').write_text(json.dumps(out,indent=2));print(json.dumps(out))
'''.replace('BASE',repr(base)).replace('FILES',repr(payload))
    launch=json.loads(remote_text('p26',code,timeout=90));launch['local_plan']=plan;launch['retry_mapping']=mapping
    marker.write_text(json.dumps(launch,indent=2))
    all_launches.append(launch)
    (ROOT/'conditional_family_launches_20261023.json').write_text(json.dumps(all_launches,indent=2))
    print(json.dumps(launch))


if __name__=='__main__':main()
