"""Read-only live inventory audit for parameter/event response experiments."""
import base64,collections,csv,datetime,gzip,hashlib,json,subprocess
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'review/response_cohorts_20261030'
OUT.mkdir(exist_ok=True)
REMOTE=r'''
import sqlite3,json,gzip,base64
c=sqlite3.connect('file:/srv/phylabel/data/annotations.sqlite3?mode=ro',uri=True);c.row_factory=sqlite3.Row
tasks=[]
for r in c.execute("select * from tasks where batch_id='formal3600_v1' order by id"):
 t=dict(r);t['payload']=json.loads(t['payload']);t['annotations']={}
 for a in c.execute('select stage,payload,submitted,updated from annotations where task_id=?',(r['id'],)):
  v=dict(a);v['payload']=json.loads(v['payload']);t['annotations'][a['stage']]=v
 tasks.append(t)
print(base64.b64encode(gzip.compress(json.dumps(tasks).encode())).decode())
'''
cmd=['ssh','-o','BatchMode=yes','-o','ProxyCommand=ssh -o BatchMode=yes p25 python3 /home/wangzijun_p25/.ssh/phylabel_proxy.py','tx173','sudo','-n','python3','-']
p=subprocess.run(cmd,input=REMOTE.encode(),capture_output=True,timeout=90,check=True)
raw=base64.b64decode(p.stdout.strip());(OUT/'live_tasks.json.gz').write_bytes(raw);tasks=json.loads(gzip.decompress(raw));assert len(tasks)==3600
refs=json.loads((ROOT/'annotation_site/resources/reference_window_admission.json').read_text(encoding='utf8'));refmap={r['clip_id']:r for r in refs['references']}
bindings={}
for l in (ROOT.parent/'prompts_72000_unified/core100_generation_input_bindings.jsonl').open(encoding='utf8'):
 r=json.loads(l);bindings[r.get('clip_id',r.get('id',''))]=r
def writecsv(name,rows):
 if not rows:return
 with (OUT/name).open('w',encoding='utf-8-sig',newline='') as f:
  w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
inventory=[];t17=[];counts=collections.Counter()
for t in tasks:
 x=t['payload'];ann=t['annotations'].get('primary',{});h=ann.get('payload',{}) if ann.get('submitted') else {};ref=refmap.get(x['clip_id']);events=h.get('events',{})
 row={'task_id':t['id'],'model':x['model'],'clip_id':x['clip_id'],'seed':x['seed'],'prompt_variant':x['prompt_variant'],'video_sha256':x['video_sha256'],'state':t['state'],'human_quality':h.get('quality',{}).get('status','pending'),'human_event_labels':json.dumps({k:v.get('label') for k,v in events.items()}),'native_duration_s':x['duration_s'],'annotation_window_s':x['window_s'],'protocol_sha256':x.get('protocol_sha256'),'url':f"https://huggingface.co/datasets/{x['remote_media']['repository']}/resolve/{x['remote_media']['revision']}/{x['remote_media']['path']}"}
 inventory.append(row)
 if ref:
  reason=[]
  if x['duration_s']+1e-6<ref['horizon_s']:reason.append('native_horizon_short')
  if abs(x['window_s']-ref['horizon_s'])>1e-6:reason.append('annotation_window_mismatch')
  if t['state']!='resolved':reason.append('human_not_final')
  if events.get(ref['target_event'],{}).get('label') not in ('yes','no'):reason.append('binary_target_label_missing')
  if h and (h.get('video_sha256')!=x['video_sha256'] or h.get('protocol_sha256')!=x.get('protocol_sha256')):reason.append('annotation_identity_mismatch')
  counts.update(reason)
  t17.append({**row,'target_event':ref['target_event'],'reference_label':ref['reference_label'],'required_horizon_s':ref['horizon_s'],'blockers':'|'.join(reason),'formal_score':None})
writecsv('video_inventory.csv',inventory);writecsv('t17_review_and_generation_gaps.csv',t17)
# Same prompt/seed is necessary for controlled output pairing; no Cartesian pairs.
group=collections.defaultdict(dict)
for r in t17:group[r['model'],r['prompt_variant'],r['seed']][r['clip_id']]=r
pairs=[]
for (model,prompt,seed),d in sorted(group.items()):
 a=d.get('T17_C04');b=d.get('T17_C05');pairs.append({'model':model,'prompt_variant':prompt,'seed':seed,'negative_task':a['task_id'] if a else '', 'positive_task':b['task_id'] if b else '', 'both_outputs_present':bool(a and b),'both_native_windows_cover':bool(a and b and a['native_duration_s']>=6.4 and b['native_duration_s']>=6.4),'blockers':'|'.join(sorted(set((a['blockers'].split('|') if a else ['negative_output_missing'])+(b['blockers'].split('|') if b else ['positive_output_missing']))))})
writecsv('t17_same_prompt_seed_pairs.csv',pairs)
summary={'checked_at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'tasks':len(tasks),'models':len({r['model'] for r in inventory}),'source_snapshot_sha256':hashlib.sha256(raw).hexdigest(),'reference_registry_sha256':hashlib.sha256((ROOT/'annotation_site/resources/reference_window_admission.json').read_bytes()).hexdigest(),'t17_outputs':len(t17),'t17_blockers':dict(counts),'t17_same_prompt_seed_slots':len(pairs),'t17_complete_output_pairs':sum(r['both_outputs_present'] for r in pairs),'t17_complete_horizon_pairs':sum(r['both_native_windows_cover'] for r in pairs),'note':'Reference registry is local snapshot. No new reference admission, score, threshold or label created. Native full horizon alone does not establish formal scoring readiness. Random output slots are not guaranteed controlled physical groups.'}
(OUT/'summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding='utf8');print(json.dumps(summary,ensure_ascii=False,indent=2))

if __name__=='__main__':pass
