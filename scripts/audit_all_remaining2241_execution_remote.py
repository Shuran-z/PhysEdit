"""Audit original execution artifacts for every remaining source group, without inventing inputs."""
import collections,gzip,hashlib,json,re,concurrent.futures
from pathlib import Path
R=Path('/data_cached/wangzijun_p25/config_bindings_20261031');BASE=R/'remaining6767';O=R/'remaining2241';B=Path('/data2/wangzijun_p25/phy2_standardization_20261027');ART=B/'phy2_release_v1.0.0_rc1'
def load(p):return list(map(json.loads,gzip.open(p,'rt')))
def sha(raw):return hashlib.sha256(raw).hexdigest()
pending=load(BASE/'stage/releases/physedit/checks/unresolved_configs.jsonl.gz');ids={x['canonical_video_id'] for x in pending};tasks=[x for x in load(R/'TASKS.jsonl.gz') if x['canonical_video_id'] in ids];names={x['native_sample_id'] for x in tasks};sources={};artifacts=collections.defaultdict(list)
for l in (B/'processed.jsonl').open():
 a=json.loads(l)
 if a['engine']!='genesis':continue
 if a['kind']=='video':sources[a['source_key']]=a
 else:
  native=next((p for p in Path(a['logical_path']).parts if p in names),None)
  if native:artifacts[a['release_id'],native].append(a)
def raw(a):
 p=ART/a['path'];b=p.read_bytes();assert sha(b)==a['sha256'];b=gzip.decompress(b) if p.suffix=='.gz' else b
 if a.get('storage_transform')=='gzip_lossless':assert sha(b)==a['source_sha256']
 return b
cache={}
for t in tasks:
 key=(t['source_repo']+'@'+t['source_revision']+':'+t['source_path']);source=sources[key];assert source['source_sha256']==t['video_sha256'];group=(source['release_id'],t['native_sample_id'])
 if group in cache:continue
 evidence={'native_sample_id':t['native_sample_id'],'scene':t['scene'],'source_release_id':source['release_id'],'logs':[],'receipts':[],'config_sha256_tokens':[]}
 for a in artifacts[group]:
  if a['logical_path'].endswith('.log'):
   b=raw(a);text=b.decode(errors='replace');lines=text.splitlines();hits=[l for l in lines if re.search(r'(config|cfg).{0,90}(sha256|sha-256|digest|hash)|(sha256|digest).{0,90}(config|cfg)',l,re.I)]
   hashes=sorted({x.lower() for l in hits for x in re.findall(r'\b[a-fA-F0-9]{64}\b',l)})
   evidence['config_sha256_tokens']+=hashes;evidence['logs'].append(dict(source_key=a['source_key'],source_sha256=a['source_sha256'],artifact_sha256=a['sha256'],raw_sha256=sha(b),original_artifact_path=a['path'],seed_records=re.findall(r'physics random_seed applied = (\d+) raw_config_seed=(\d+)',text),background_profile_ids=sorted(set(re.findall(r'Loaded background profile: (\S+)',text))),config_hash_lines=hits,bytes=len(b)))
  elif Path(a['logical_path']).name in ['FORMAL_COMPLETED.json','COMPLETED.json']:
   b=raw(a);c=json.loads(b);command=c.get('command') or [];configs=[command[i+1] for i,x in enumerate(command[:-1]) if x in ['--config','--extra-camera-config']];evidence['receipts'].append(dict(source_key=a['source_key'],source_sha256=a['source_sha256'],artifact_sha256=a['sha256'],raw_sha256=sha(b),executed_config_paths=configs,explicit_config_sha256=c.get('config_sha256'),command_present=bool(command),sample_id=c.get('sample_id'),status=c.get('status')))
 evidence['config_sha256_tokens']=sorted(set(evidence['config_sha256_tokens']));cache[group]=evidence
rows=[]
for t in tasks:
 key=t['source_repo']+'@'+t['source_revision']+':'+t['source_path'];source=sources[key];e=cache[source['release_id'],t['native_sample_id']];rows.append(dict(canonical_video_id=t['canonical_video_id'],video_sha256=t['video_sha256'],native_sample_id=t['native_sample_id'],scene=t['scene'],camera=t['camera'],execution_evidence=e,status='ORIGINAL_CONFIG_BYTES_UNRESOLVED'))
with gzip.open(O/'EXECUTION_AUDIT.jsonl.gz','wt') as f:
 for row in rows:f.write(json.dumps(row)+'\n')
summary=dict(videos=len(rows),source_groups=len(cache),by_scene=dict(collections.Counter(t['scene'] for t in tasks)),original_logs=sum(len(v['logs']) for v in cache.values()),original_receipts=sum(len(v['receipts']) for v in cache.values()),groups_with_config_sha256=sum(bool(v['config_sha256_tokens']) for v in cache.values()),groups_missing_logs=sum(not v['logs'] for v in cache.values()),groups_missing_receipts=sum(not v['receipts'] for v in cache.values()),all_artifact_hashes_checked=True,recovered_original_config_bindings=0,training_membership_changes=0)
(O/'EXECUTION_AUDIT_SUMMARY.json').write_text(json.dumps(summary,indent=2));print(json.dumps(summary),flush=True)
