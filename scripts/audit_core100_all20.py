"""Read-only per-case audit of all twenty scenes against live site resources."""
import base64,collections,csv,datetime,gzip,hashlib,json,subprocess,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'review/core100_all20_audit_20261030';OUT.mkdir(exist_ok=True)
CODE='''import pathlib,sqlite3,json,gzip,base64,hashlib
db=sqlite3.connect('file:/srv/phylabel/data/annotations.sqlite3?mode=ro',uri=True);db.row_factory=sqlite3.Row
tasks=[]
for r in db.execute("select * from tasks where batch_id='formal3600_v1' order by id"):
 t=dict(r);t['payload']=json.loads(t['payload']);t['annotations']={}
 for a in db.execute('select stage,payload,submitted,updated from annotations where task_id=?',(r['id'],)):
  x=dict(a);x['payload']=json.loads(x['payload']);t['annotations'][a['stage']]=x
 tasks.append(t)
resources={}
for p in pathlib.Path('/srv/phylabel/current/resources').glob('*.json'):
 raw=p.read_bytes()
 try:resources[p.name]={'sha256':hashlib.sha256(raw).hexdigest(),'data':json.loads(raw)}
 except ValueError:pass
out={'tasks':tasks,'resources':resources,'release':str(pathlib.Path('/srv/phylabel/current').resolve()),'review16':list(map(tuple,db.execute("select state,count(*) from tasks where batch_id='t17_window5_review_20261030' group by state")))}
print(base64.b64encode(gzip.compress(json.dumps(out).encode())).decode())
'''
cmd=['ssh','-o','BatchMode=yes','-o','ProxyCommand=ssh -o BatchMode=yes p25 python3 /home/wangzijun_p25/.ssh/phylabel_proxy.py','tx173','sudo','-n','python3','-']
if '--cached' in sys.argv:raw=(OUT/'live_snapshot.json.gz').read_bytes()
else:
 p=subprocess.run(cmd,input=CODE.encode(),capture_output=True,timeout=120,check=True);raw=base64.b64decode(p.stdout.strip());(OUT/'live_snapshot.json.gz').write_bytes(raw)
live=json.loads(gzip.decompress(raw));tasks=live['tasks'];assert len(tasks)==3600
def resource(n,default=None):return live['resources'].get(n,{}).get('data',default)
admission=resource('core100_admission.json');points={p['clip_id']:p for p in admission['points']};assert len(points)==100
protocols=resource('core100_contact_protocol_20261027.json')['clips'];clocks={r['clip_id']:r for r in resource('reference_clocks100.json')}
refs={r['clip_id']:r for r in resource('reference_window_admission.json')['references']}
truth={r['clip_id']:r for r in resource('core100_contact_reference_truth_20261027.json',{}).get('references',[])}
physical=resource('core100_physical_windows_20261027.json',{}).get('cases',{})
binding=json.loads((ROOT/'review/core100_binding_20261028/binding.json').read_text(encoding='utf8'));bind={r['clip_id']:r for r in binding['cases']}
source_configs={r['clip_id']:r for r in json.loads(gzip.decompress((ROOT/'review/response_cohorts_20261030/source_configs.json.gz').read_bytes()))}
prompts=collections.defaultdict(dict)
for l in (ROOT.parent/'core100_prompt_unified/prompts.jsonl').open(encoding='utf8'):
 r=json.loads(l);prompts[r['clip_id']][r['variant']]=r['prompt_sha256']
by=collections.defaultdict(list)
for t in tasks:by[t['payload']['clip_id']].append(t)
numeric_receipts=json.loads((OUT/'numeric_receipts_live.json').read_text(encoding='utf8')) if (OUT/'numeric_receipts_live.json').exists() else []
records=[];video_rows=[]
for clip in sorted(points):
 own=by[clip];assert len(own)==36 and len({t['payload']['model']for t in own})==12
 definition=protocols.get(clip,{});events=definition.get('events',{});ref=refs.get(clip);clock=clocks.get(clip,{});tr=truth.get(clip)
 numeric_online=[];numeric_local=[]
 for name in ['core100_contact_boundaries_20261027.json','core100_t13_contact_boundaries_20261027.json']:
  numeric_online.extend(r for r in resource(name,{}).get('records',[])if r['clip_id']==clip)
  path=ROOT/'annotation_site/resources'/name
  if path.exists():numeric_local.extend(r for r in json.loads(path.read_text(encoding='utf8')).get('records',[])if r['clip_id']==clip)
 # Merely joining a receipt is not an admission or a same-window proof.
 historical=points[clip].get('numerical_distance_records',[]);bb=bind.get(clip,{})
 q=collections.Counter();ev=collections.Counter();states=collections.Counter();windows=collections.Counter();input_status=collections.Counter();media=0
 for t in own:
  x=t['payload'];states[t['state']]+=1;windows[str(x['window_s'])]+=1
  a=t['annotations'].get('primary',{});h=a.get('payload',{})if a.get('submitted')else{};identity=bool(h)and h.get('video_sha256')==x['video_sha256']and h.get('protocol_sha256')==x.get('protocol_sha256')
  if t['state']=='resolved'and identity:
   q[h.get('quality',{}).get('status','missing')]+=1
   if h.get('quality',{}).get('status')=='pass':
    for k in events:ev[h.get('events',{}).get(k,{}).get('label','missing')]+=1
  submitted=x.get('source',{}).get('generation_metadata',{}).get('prompt')
  inputok=(hashlib.sha256(submitted.encode()).hexdigest()==prompts[clip].get(x['prompt_variant']))if isinstance(submitted,str)and submitted else None
  input_status['exact_actual_text'if inputok else'text_mismatch'if inputok is False else'actual_text_not_in_payload']+=1
  v=x.get('machine',{}).get('media_verified',{});verified=v.get('sha256')==x['video_sha256']and v.get('frames')==x['frames']and abs(v.get('fps',0)-x['fps'])<=.02 and v.get('size')==x['remote_media']['size'];media+=verified
  video_rows.append(dict(task_id=t['id'],scene=clip[:3],clip_id=clip,model=x['model'],prompt_variant=x['prompt_variant'],seed=x['seed'],native_duration_s=x['duration_s'],annotation_window_s=x['window_s'],state=t['state'],annotation_identity=identity,quality=h.get('quality',{}).get('status'),events=json.dumps(h.get('events',{}),ensure_ascii=False),actual_prompt_match=inputok,media_verified=verified,video_sha256=x['video_sha256']))
 source=source_configs.get(clip,{})
 blockers=[]
 if not ref:blockers.append('reference_not_formally_admitted')
 if not clock.get('clock_evidence_complete'):blockers.append('reference_clock_incomplete')
 receipt_rows=[r for r in numeric_receipts if r['clip_id']==clip and r.get('sha256')==r['expected_sha256']]
 interval_rows=[r for r in receipt_rows if r['kind']=='interval_candidate_versions']
 noflip_rows=[r for r in receipt_rows if r['kind']=='finite_grid_no_flip_versions']
 if not historical and not numeric_online and not numeric_local and not interval_rows:blockers.append('no_registered_boundary_for_this_case')
 if noflip_rows:blockers.append('finite_grid_no_flip_is_not_proof_of_global_no_boundary')
 if interval_rows:blockers.append('interval_receipts_exist;source_physics_window_and_visual_admission_still_required')
 if not(ref or tr or clip in physical):blockers.append('window_specific_reference_truth_not_registered')
 if ref and any(t['payload']['duration_s']+1e-6<ref['horizon_s']for t in own):blockers.append('some_outputs_shorter_than_registered_reference_window;recheck_shorter_window')
 if clip.startswith('T17')and clip in ('T17_C04','T17_C05'):blockers.append('5s_relabel_done_both_negative;positive_generated_case_missing')
 if states['disputed']or states['unstarted']or states['draft']:blockers.append('human_records_pending')
 if ev['missing']or ev['uncertain']or ev['not_observed']:blockers.append('some_event_labels_missing_or_unobservable')
 candidate_steps=[s for s in bb.get('required_next_steps',[])if 'v6'not in s.lower()]
 records.append(dict(clip_id=clip,scene=clip[:3],events=list(events),live_definition_present=bool(events),outputs=36,resolved=states['resolved'],disputed=states['disputed'],unstarted=states['unstarted'],quality_final=dict(q),event_labels_final=dict(ev),annotation_windows=dict(windows),media_verified=media,actual_prompt_status=dict(input_status),reference_admitted=bool(ref),reference_horizon_s=ref.get('horizon_s')if ref else None,same_window_reference_truth_record=bool(tr),clock_complete=bool(clock.get('clock_evidence_complete')),source_config_recovered='config'in source,source_config_hash_matches=bool(source.get('sha256')and source.get('sha256')==source.get('expected_sha256')),historical_numeric_records=len(historical),online_contact_boundary_records=len(numeric_online),local_contact_boundary_records=len(numeric_local),live_interval_receipts=len(interval_rows),live_no_flip_receipts=len(noflip_rows),supplement_search_candidates=len(bb.get('supplement_candidates',[])),window_reanalysis=bb.get('window_reanalysis'),blockers=blockers,source_recovery_next_steps=candidate_steps,NearAcc=None,PairAcc=None))
scenes=[]
for scene in [f'T{i:02d}'for i in range(1,21)]:
 rr=[r for r in records if r['scene']==scene];assert len(rr)==5
 scenes.append(dict(scene=scene,cases=5,definitions=sum(r['live_definition_present']for r in rr),resolved=sum(r['resolved']for r in rr),outputs=180,reference_admitted=sum(r['reference_admitted']for r in rr),window_truth_records=sum(r['same_window_reference_truth_record']for r in rr),historical_numeric_cases=sum(r['historical_numeric_records']>0 for r in rr),live_interval_candidate_cases=sum(r['live_interval_receipts']>0 for r in rr),live_finite_no_flip_cases=sum(r['live_no_flip_receipts']>0 for r in rr),online_new_boundary_cases=sum(r['online_contact_boundary_records']>0 for r in rr),local_new_boundary_cases=sum(r['local_contact_boundary_records']>0 for r in rr),source_configs_hash_verified=sum(r['source_config_hash_matches']for r in rr),clock_complete=sum(r['clock_complete']for r in rr),media_verified=sum(r['media_verified']for r in rr),unresolved=sum(r['disputed']+r['unstarted'] for r in rr),NearAcc=None,PairAcc=None))
drift=[]
for name,item in live['resources'].items():
 local=ROOT/'annotation_site/resources'/name
 if local.exists():
  h=hashlib.sha256(local.read_bytes()).hexdigest()
  if h!=item['sha256']:drift.append({'name':name,'local_sha256':h,'online_sha256':item['sha256']})
local_only=[p.name for p in (ROOT/'annotation_site/resources').glob('*.json')if p.name not in live['resources']]
def csvwrite(name,rows):
 with(OUT/name).open('w',encoding='utf-8-sig',newline='')as f:
  w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
csvwrite('scenes20.csv',scenes);csvwrite('videos3600.csv',video_rows)
(OUT/'cases100.json').write_text(json.dumps(records,ensure_ascii=False,indent=2),encoding='utf8')
summary={'checked_at_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'release':live['release'],'scenes':20,'cases':100,'outputs':3600,'live_definitions':sum(r['live_definition_present']for r in records),'admitted_reference_cases':len(refs),'reference_truth_cases':len(truth),'historical_numeric_cases':sum(r['historical_numeric_records']>0 for r in records),'source_configs_hash_verified':sum(r['source_config_hash_matches']for r in records),'resource_drift':drift,'local_only_resources':local_only,'snapshot_sha256':hashlib.sha256(raw).hexdigest(),'review16_states':live['review16'],'scenes20':scenes,'scope':'Registration/readiness audit only. No newly admitted case, inferred threshold or fabricated score. Same-window truth record alone is not full Near/Pair admission. Actual short English prompts used; obsolete all-v6/seed0 gate not applied.'}
(OUT/'summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding='utf8');print(json.dumps({k:summary[k]for k in ['scenes','cases','outputs','live_definitions','admitted_reference_cases','reference_truth_cases','historical_numeric_cases','source_configs_hash_verified','local_only_resources']},ensure_ascii=False,indent=2))
