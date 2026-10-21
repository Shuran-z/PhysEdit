"""Build exact published-event refinement tasks for five previously pending scenes."""
import collections
import argparse
import copy
import gzip
import hashlib
import json
from pathlib import Path
import re
import subprocess
from scripts.bind_t01_original_calibrations import context as t01_context,label as t01_label
from scripts.export_original_boundary_distances import ROOT,distances

BASE='/home/wangzijun_p25/liyuhan/phydataset/ase_asset_importer'
REMOTE_ROOT='/data_cached/wangzijun_p25/liyuhan/five_scene_boundary_20261020'


def load(name):return json.loads((ROOT/name).read_text(encoding='utf-8'))


def metadata_header(raw):
    text=(gzip.decompress(raw) if raw[:2]==b'\x1f\x8b' else raw).decode('utf-8');decoder=json.JSONDecoder();result={}
    wanted='experiment|manifest|render|scene_overrides|room_boundary|dynamic_objects|runtime_forces|camera_id|camera_bundle'
    for match in re.finditer(r'(?m)^  "('+wanted+r')"\s*:\s*',text):
        result[match[1]]=decoder.raw_decode(text,match.end())[0]
    if not {'experiment','manifest','render','scene_overrides','dynamic_objects'}<=result.keys():
        result=json.loads(text);result.pop('frames')
    return result


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--first-five',action='store_true');args=parser.parse_args()
    out=ROOT/'five_scene_first_five_20261020' if args.first_five else ROOT;out.mkdir(exist_ok=True)
    (out/'original_value_distance_ledger').mkdir(exist_ok=True)
    remote_root=REMOTE_ROOT+'/first_five' if args.first_five else REMOTE_ROOT
    sources={s:{r['sample_id']:r for r in load('t01_measured_published_events_20261019.json' if s=='T01' else s.lower()+'_measured_published_events.json')} for s in ['T01','T04','T05','T08']}
    cache_path=out/'five_scene_source_headers_20261020.json'
    initial=cache_path if cache_path.exists() else ROOT/cache_path.name
    headers=json.loads(initial.read_text()) if initial.exists() else {}
    def header(s,sid):
        r=sources[s][sid]
        if sid not in headers or headers[sid]['sha256']!=r['sha256']:
            raw=Path(r['local_path']).read_bytes()
            if hashlib.sha256(raw).hexdigest()!=r['sha256']:raise ValueError('published state changed')
            d=metadata_header(raw)
            headers[sid]=dict(sha256=r['sha256'],header=d)
            if len(headers)%25==0:
                temporary=cache_path.with_suffix('.tmp');temporary.write_text(json.dumps(headers));temporary.replace(cache_path)
                print(json.dumps(dict(source_headers=len(headers))),flush=True)
        return headers[sid]['header']
    configs11={r['sample_id']:next(f['data'] for f in r['files'] if '/configs/' in f['archive_path']) for p in ROOT.glob('t11_latest_*_evidence_20261019.json') for r in json.loads(p.read_text())}
    hosts11={r['sample_id']:r['source_host'] for r in load('t11_latest_selection_20261019.json')}
    params11={r['sample_id']:r for r in map(json.loads,(ROOT/'original_value_distance_ledger/t11_current_published_parameters.jsonl').read_text().splitlines())}
    states11={r['sample_id']:r for r in load('t11_published_final_states.json') if 'error' not in r}
    domains=collections.defaultdict(list)
    def group(s,f,sid):
        # Source IDs consistently contain the background/gravity as separate fields.
        parts=sid.split('__');return (s,f,parts[1],parts[2])
    for s,items in sources.items():
        for sid,r in items.items():
            family=r['original_family']['family'] if s=='T01' else r['family_id']
            theta=r['original_family'].get('theta') if s=='T01' else r['theta']
            if family and theta is not None:domains[group(s,family,sid)].append(theta)
    for sid,r in params11.items():
        if r['family_id']!='joint_global_configuration':domains[group('T11',r['family_id'],sid)].append(r['theta'])
    windows=[];t01_groups=collections.defaultdict(list)
    first_context=next(iter(sources['T01'])).split('__')[1:3]
    for sid,r in sources['T01'].items():
        if args.first_five and sid.split('__')[1:3]!=first_context:continue
        family=r['original_family']['family']
        if not family:continue
        h=header('T01',sid);t01_groups[(family,t01_context(h,family))].append(dict(sample_id=sid,theta=r['original_family']['theta'],label=t01_label(r['audit'],family),state_sha256=r['sha256']))
    t01_base=[];t01_no_flip=[]
    for (family,key),items in t01_groups.items():
        byvalue=collections.defaultdict(list)
        for r in items:byvalue[r['theta']].append(r)
        consistent={t:rr[0] for t,rr in byvalue.items() if len({r['label'] for r in rr})==1};found=False
        for a,b in zip(sorted(byvalue),sorted(byvalue)[1:]):
            if a not in consistent or b not in consistent or consistent[a]['label']==consistent[b]['label']:continue
            found=True;left,right=consistent[a],consistent[b];target={'A':'book_can_1_contact','B':'can_1_can_2_contact','C':'full_chain'}[family]
            w=dict(scene_id='T01',family_id=family,target_event=target,bracket=[a,b],labels=[left['label'],right['label']],endpoint_sample_ids=[left['sample_id'],right['sample_id']],fixed_context_sha256=key)
            windows.append(w)
            for r in items:
                source=sources['T01'][r['sample_id']];domain=domains[group('T01',family,r['sample_id'])];domain=[min(domain),max(domain)]
                t01_base.append(dict(scene_id='T01',engine='genesis',repo_id=source['repo_id'],revision=source['revision'],sample_id=r['sample_id'],family_id=family,theta=r['theta'],target_event=target,
                    reference_label=r['label'],reference_state_sha256=r['state_sha256'],original_boundary_interval=[a,b],**distances(r['theta'],bracket=[a,b]),
                    normalization_domain=domain,normalization_span=domain[1]-domain[0],endpoint_sample_ids=w['endpoint_sample_ids'],fixed_context_sha256=key,
                    original_reference_kind='original_published_event_scan_interval',formal_nearacc_eligible=False))
        if not found:t01_no_flip.append(dict(family_id=family,context=key,samples=len(items),reason='no_consistent_opposite_outcomes_in_published_points'))
    windows+=load('t04_t05_supplemental_windows.json')
    windows+=[dict(w,scene_id='T08') for w in load('t08_supplemental_windows.json')]
    windows+=[dict(w,scene_id='T11') for w in load('t11_supplemental_windows.json')]
    if args.first_five:
        chosen={}
        for w in windows:
            if w['scene_id']=='T11' and any(hosts11[sid]!='p25' for sid in w['endpoint_sample_ids']):continue
            chosen.setdefault(w['scene_id'],w)
        windows=list(chosen.values())
    candidates=[]
    for w in windows:
        s=w['scene_id'];family=w['family_id'];ends=[]
        for i,sid in enumerate(w['endpoint_sample_ids']):
            if s=='T11':
                cfg=configs11[sid];source=params11[sid];state=states11[sid];name=w['target_event'][:-len('_final_center_below_minus_20cm')]
                ends.append(dict(sample_id=sid,theta=w['bracket'][i],label=state['fallen'][name],state_sha256=state['state_sha256'],config=cfg,source_host=hosts11[sid],revision=source['revision'],repo_id=source['repo_id']))
            else:
                r=sources[s][sid];h=header(s,sid);labels=w.get('labels',w.get('endpoint_labels'))
                ends.append(dict(sample_id=sid,theta=w['bracket'][i],label=labels[i],state_sha256=r['sha256'],header=h,revision=r['revision'],repo_id=r['repo_id'],original_rule_sha256=r.get('auditor_sha256',r.get('original_rule_sha256'))))
        domain=domains[group(s,family,ends[0]['sample_id'])];domain=[min(domain),max(domain)]
        identity=dict(scene=s,family=family,event=w['target_event'],bracket=w['bracket'],source_states=[e['state_sha256'] for e in ends])
        job_id=hashlib.sha256(json.dumps(identity,sort_keys=True).encode()).hexdigest()[:24]
        candidates.append(dict(job_id=job_id,scene_id=s,family_id=family,target_event=w['target_event'],bracket=w['bracket'],endpoints=ends,
            normalization_domain=domain,tolerance=.0005 if s!='T08' or not family.startswith('A_') else .001,source_window=w))
    cache_path.write_text(json.dumps(headers))
    (out/'t01_published_slices_without_flip_20261020.json').write_text(json.dumps(t01_no_flip,indent=2))
    (out/'original_value_distance_ledger/t01_published_event_sample_distances.jsonl').write_text(''.join(json.dumps(r)+'\n' for r in t01_base))
    pack=out/'five_scene_boundary_candidates_20261020.json';pack.write_text(json.dumps(candidates))
    subprocess.run(['ssh','-o','BatchMode=yes','p25','mkdir','-p',remote_root],check=True)
    subprocess.run(['scp','-q',str(pack.resolve()),'p25:'+remote_root+'/candidates.json'],check=True)
    subprocess.run(['scp','-q',str((ROOT/'t01_current_sources/audit_t01_v2.py').resolve()),'p25:'+remote_root+'/audit_t01_v2.py'],check=True)
    remote=r'''
import copy,hashlib,json,pathlib
root=pathlib.Path(REMOTE_DIRECTORY);base=pathlib.Path(BASE_DIRECTORY);jobs=json.loads((root/'candidates.json').read_text());ready=[];pending=[]
projects={'T01':base/'everyday_bifurcation_T01_v2_7s','T04':base/'everyday_bifurcation_T04_v3_7s','T05':base/'everyday_bifurcation_T05_v2_7s','T08':base/'everyday_bifurcation_T07_T08_v2_independent'}
dirs={'T01':'formal_52800_v2_full_chain','T04':'formal_880_v1_480p','T05':'formal_880_v1_480p','T08':'formal_v4_480p'}
renderers={'T01':projects['T01']/'scripts/render_t01_t05_production_v3_multicam.py','T04':base/'scripts/render_t04_t05_live_multicam.py','T05':base/'scripts/render_t04_t05_live_multicam.py','T08':projects['T08']/'scripts/render_t08_v3_multicam.py','T11':base/'scripts/render_t11_r010_slow_chain.py'}
for job in jobs:
 try:
  s=job['scene_id']
  if s=='T11' and any(e['source_host']!='p25' for e in job['endpoints']):raise ValueError('p29 original backend/asset paths require separate source-host execution')
  for e in job['endpoints']:
   if s=='T11':continue
   sid=e['sample_id'];h=e['header'];project=projects[s];path=project/'configs'/dirs[s]/sid/'cam01.json'
   if path.exists():c=json.loads(path.read_text());template_path=str(path)
   elif s in ['T04','T05']:
    bg=h['experiment']['background_id'];pattern='*'+bg+'*'+('gap1134*' if s=='T05' else '')+'/cam01.json'
    paths=list((project/'configs/pilot_ready_r002').glob(pattern))
    if len(paths)!=1:raise ValueError('original per-background template not uniquely recovered')
    c=json.loads(paths[0].read_text());template_path=str(paths[0])
   elif s=='T08':
    bg=h['experiment']['background_id'];paths=sorted((project/'configs/formal_v4_480p').glob('*'+bg+'*/cam01.json'))
    if not paths:raise ValueError('original T08 background template missing')
    c=json.loads(paths[0].read_text());template_path=str(paths[0])
   else:raise ValueError('original config missing: '+str(path))
   for k in ['experiment','manifest','render','scene_overrides','room_boundary','runtime_forces']:
    if k in h:c[k]=copy.deepcopy(h[k])
   c['dynamic_objects']=[copy.deepcopy(o['spec']) for o in h['dynamic_objects']];c['sample_id']=sid
   if s in ['T04','T05']:c['random_seed']=h['experiment']['seed']
   if s=='T08':c['random_seed']=h['experiment']['random_seed']
   c.setdefault('annotations',{})['enabled']=True;e['config']=c;e['config_reconstruction']=dict(template=template_path,physical_fields='exact selected published metadata specs and consumed fields')
   del e['header']
  renderer=renderers[s]
  if not renderer.exists():raise ValueError('original renderer missing')
  job['renderer']=str(renderer);job['backend_sources']={str(renderer):hashlib.sha256(renderer.read_bytes()).hexdigest()}
  if s=='T01':
   auditor=root/'audit_t01_v2.py'
   if not auditor.exists():raise ValueError('original auditor missing')
   job['auditor']=str(auditor);job['backend_sources'][str(auditor)]=hashlib.sha256(auditor.read_bytes()).hexdigest()
   if any(e['original_rule_sha256']!=job['backend_sources'][str(auditor)] for e in job['endpoints']):raise ValueError('T01 event rule differs from published-state extraction')
  ready.append(job)
 except Exception as exc:pending.append(dict(job_id=job['job_id'],scene_id=job['scene_id'],family_id=job['family_id'],error=str(exc)))
# Alternate scenes and parameter families rather than placing one whole scene first.
queues={s:[] for s in ['T01','T04','T05','T08','T11']}
for j in ready:queues[j['scene_id']].append(j)
for s,items in queues.items():
 families={f:[] for f in dict.fromkeys(j['family_id'] for j in items)}
 for j in items:families[j['family_id']].append(j)
 queues[s]=[]
 while any(families.values()):
  for q in families.values():
   if q:queues[s].append(q.pop(0))
ordered=[]
while any(queues.values()):
 for s,q in queues.items():
  if q:ordered.append(q.pop(0))
(root/'plan.json').write_text(json.dumps(ordered));(root/'pending.json').write_text(json.dumps(pending,indent=2))
print(json.dumps(dict(ready=ordered,pending=pending)))
'''.replace('REMOTE_DIRECTORY',repr(remote_root)).replace('BASE_DIRECTORY',repr(BASE))
    result=subprocess.run(['ssh','-o','BatchMode=yes','p25','python3 -'],input=remote.encode(),capture_output=True,timeout=180)
    if result.returncode:raise RuntimeError(result.stderr.decode(errors='replace'))
    prepared=json.loads(result.stdout);(out/'five_scene_prepared_plan_20261020.json').write_text(json.dumps(prepared['ready']))
    (out/'five_scene_preparation_pending_20261020.json').write_text(json.dumps(prepared['pending'],indent=2))
    summary=dict(candidate_intervals=len(candidates),ready_intervals=len(prepared['ready']),pending_intervals=len(prepared['pending']),
        ready_by_scene=dict(collections.Counter(j['scene_id'] for j in prepared['ready'])),pending_by_scene=dict(collections.Counter(j['scene_id'] for j in prepared['pending'])),
        t01_published_scan_bound_samples=len({r['sample_id'] for r in t01_base}),t01_original_scanned_contexts=len(t01_groups),t01_contexts_without_observed_flip=len(t01_no_flip))
    (out/'five_scene_preparation_summary_20261020.json').write_text(json.dumps(summary,indent=2));print(json.dumps(summary))


if __name__=='__main__':main()
