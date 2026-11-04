"""Read-only audit: missing config bytes do not remove videos or training members."""
import collections,gzip,hashlib,json,math,multiprocessing,re
from pathlib import Path
R=Path('/data_cached/wangzijun_p25/config_bindings_20261031');BASE=R/'remaining2241';D=BASE/'stage/releases/physedit';O=R/'missing_config_training_audit';O.mkdir(exist_ok=True);B=Path('/data2/wangzijun_p25/phy2_standardization_20261027');ART=B/'phy2_release_v1.0.0_rc1'
def load(p):return list(map(json.loads,gzip.open(p,'rt')))
def sha(raw):return hashlib.sha256(raw).hexdigest()
ids={x['canonical_video_id'] for x in load(D/'checks/unresolved_configs.jsonl.gz')};allvideos=load(D/'catalog/videos.jsonl.gz');videos=[x for x in allvideos if x['canonical_video_id'] in ids];assert len(videos)==2640
bindings={x['video_id']:x for x in load(D/'prompts/video_prompt_bindings.jsonl.gz') if x['video_id'] in ids};texts={x['sha256']:x['prompt'] for x in load(D/'prompts/prompt_texts.jsonl.gz')};train={x['canonical_video_id'] for x in load(D/'catalog/train_final.jsonl.gz')};sources={};metas=collections.defaultdict(list)
for line in (B/'processed.jsonl').open():
 a=json.loads(line)
 if a['engine']!='genesis' or a['scene_id'] not in ['t01','t04']:continue
 if a['kind']=='video':sources[a['source_key']]=a
 elif '/metadata/' in a['logical_path']:metas[a['release_id']].append(a)
def label(k):
 s=re.sub(r'\bt\d+s?(?:v\d+)?_', '',k.lower())
 replacements={'initial_speed':'initial speed','friction_coefficient':'friction','coefficient':'','sliding_book':'book','chain_':'','commanded_extraction':'support extraction','release_position_along_ramp_m':'ramp release position'}
 for a,b in replacements.items():s=s.replace(a,b)
 s=re.sub(r'_(?:mps|kg|deg|m|n|s|fixed)$','',s);return ' '.join(s.replace('_',' ').replace('.',' ').split())
def number(v):return str(int(v)) if isinstance(v,float) and v.is_integer() else json.dumps(v,allow_nan=False,separators=(',',':'))
def sentence(k,v,u):return label(k).capitalize()+' '+number(v)+((' '+str(u).replace('m/s²','m/s^2').replace('°','deg')) if u else '')+'.'
def header(a):
 p=ART/a['path'];packed=p.read_bytes();assert sha(packed)==a['sha256'];raw=gzip.decompress(packed) if p.suffix=='.gz' else packed
 if a.get('storage_transform')=='gzip_lossless':assert sha(raw)==a['source_sha256']
 text=raw.decode();decoder=json.JSONDecoder();m={}
 for k in ['experiment','manifest','render','scene_overrides','dynamic_objects','runtime_forces']:
  needle='\n  '+json.dumps(k)+':';at=text.rfind(needle)
  if at<0:m[k]=None;continue
  at+=len(needle)
  while text[at].isspace():at+=1
  m[k]=decoder.raw_decode(text,at)[0]
 return m

def audit(v):
 cid=v['canonical_video_id'];errors=[];key=v['source_repo']+'@'+v['source_revision']+':'+v['source_path'];source=sources.get(key);assert source and source['source_sha256']==v['sha256']
 a=next(x for x in metas[source['release_id']] if v['native_sample_id'] in Path(x['logical_path']).parts and '__'+v['camera']+'.json' in x['logical_path']);m=header(a);objects={x['spec']['name']:x['spec'] for x in m['dynamic_objects']};params=m['experiment']['parameter'];forces=m.get('runtime_forces') or []
 facts={x[0]:(x[1],x[2]) for x in v['parameter_facts']};checks=0
 for k,(value,unit) in facts.items():
  if k=='gravity':expected=math.sqrt(sum(x*x for x in m['scene_overrides']['gravity']))
  elif k in params:expected=params[k]
  elif '.' in k:
   name,field=k.rsplit('.',1);spec=objects[name]
   if field=='initial_speed':expected=math.sqrt(sum(x*x for x in spec.get('motion',{}).get('initial_velocity',[0,0,0])))
   elif field=='force_peak':expected=max((math.sqrt(sum(x*x for x in f.get('force_world',[0,0,0]))) for f in forces if f.get('target')==name),default=0)
   else:expected=spec.get(field,'MISSING')
  else:expected='UNRESOLVED_SOURCE_FIELD'
  checks+=1
  if expected!=value:errors.append(dict(kind='parameter_source_mismatch',key=k,catalog=value,original=expected))
 prompts=v['prompt_variants_en'];hashes=[sha(x.encode()) for x in prompts];b=bindings.get(cid)
 if not b or b['video_sha256']!=v['sha256'] or b['video_path']!=v['canonical_path']:errors.append(dict(kind='prompt_video_binding_mismatch'))
 if hashes!=v['prompt_variant_sha256'] or (b and hashes!=b['prompt_sha256']):errors.append(dict(kind='prompt_hash_mismatch'))
 if any(texts.get(h)!=p for h,p in zip(hashes,prompts)):errors.append(dict(kind='prompt_pool_mismatch'))
 facts_sha=sha(json.dumps([[k,'',value,unit] for k,value,unit in v['parameter_facts']],ensure_ascii=True,sort_keys=True,separators=(',',':')).encode())
 if b and b.get('parameter_facts_sha256') is not None and facts_sha!=b['parameter_facts_sha256']:errors.append(dict(kind='parameter_facts_binding_hash_mismatch',actual=facts_sha,recorded=b.get('parameter_facts_sha256')))
 for k in v['selected_parameter_keys']:
  if k not in facts:errors.append(dict(kind='selected_parameter_missing',key=k));continue
  value,unit=facts[k];expected=sentence(k,value,unit)
  if not all(expected in p for p in prompts):errors.append(dict(kind='selected_parameter_not_expressed',key=k,sentence=expected))
 control=v.get('external_control_inputs') or {};control_errors=[]
 for obj in control.get('objects',[]):
  spec=objects.get(obj['name'])
  if spec is None:control_errors.append(dict(object=obj['name'],field='object_missing'));continue
  for k,value in obj.items():
   if k=='name':continue
   expected=spec.get(k,{'motion':{'type':'none'},'fixed':False,'visualization':True,'collision':True,'mass':0.0}.get(k,'MISSING'))
   if value!=expected:control_errors.append(dict(object=obj['name'],field=k,catalog=value,source=expected))
 if control.get('runtime_forces') is not None and control['runtime_forces']!=forces:control_errors.append(dict(field='runtime_forces'))
 errors+= [dict(kind='control_source_mismatch',**x) for x in control_errors]
 path=Path(v['local_source']);video_hash=sha(path.read_bytes()) if path.is_file() else None
 if video_hash!=v['sha256']:errors.append(dict(kind='local_video_bytes_not_confirmed',path=str(path),actual=video_hash))
 in_train=cid in train
 if in_train!=(v.get('split')=='train_final'):errors.append(dict(kind='training_membership_mismatch'))
 return dict(canonical_video_id=cid,scene=v['quota_scene'],native_sample_id=v['native_sample_id'],camera=v['camera'],video_sha256=v['sha256'],source_video_key=source['source_key'],metadata_source_key=a['source_key'],metadata_source_sha256=a['source_sha256'],metadata_artifact_sha256=a['sha256'],parameter_facts_checked=checks,selected_parameter_count=len(v['selected_parameter_keys']),variants_checked=len(prompts),control_keys=list(control),split=v['split'],in_training=in_train,errors=errors,video_prompt_parameter_consistent=not errors)
if __name__=='__main__':
 results=[]
 with multiprocessing.get_context('fork').Pool(16) as pool:
  for i,r in enumerate(pool.imap_unordered(audit,videos,chunksize=4)):
   results.append(r)
   if (i+1)%400==0:print(json.dumps({'checked':i+1,'errors':sum(bool(x['errors']) for x in results)}),flush=True)
 with gzip.open(O/'VIDEO_PROMPT_PARAMETER_AUDIT.jsonl.gz','wt') as f:
  for r in results:f.write(json.dumps(r)+'\n')
 summary=dict(videos=len(results),by_scene=dict(collections.Counter(x['scene'] for x in results)),all_checks_passed=sum(x['video_prompt_parameter_consistent'] for x in results),videos_with_issues=sum(bool(x['errors']) for x in results),issues=dict(collections.Counter(e['kind'] for x in results for e in x['errors'])),parameter_facts_checked=sum(x['parameter_facts_checked'] for x in results),prompt_variants_checked=sum(x['variants_checked'] for x in results),splits=dict(collections.Counter(x['split'] for x in results)),training_videos_total=len(train),training_membership_changed=False,prompt_and_parameter_values_changed=False)
 (O/'SUMMARY.json').write_text(json.dumps(summary,indent=2));print(json.dumps(summary),flush=True)
 if summary['videos_with_issues']:(O/'ISSUES_SAMPLE.json').write_text(json.dumps([r for r in results if r['errors']][:12],indent=2))
