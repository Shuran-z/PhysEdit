import gzip,json,hashlib,collections
from pathlib import Path
R=Path('/data_cached/wangzijun_p25/config_bindings_20261031');O=R/'remaining2241';B=Path('/data2/wangzijun_p25/phy2_standardization_20261027');ART=B/'phy2_release_v1.0.0_rc1';pending={x['canonical_video_id'] for x in map(json.loads,gzip.open(R/'remaining6767/REMAINING.jsonl.gz','rt')) if x['scene']=='T01'};tasks=[x for x in map(json.loads,gzip.open(R/'TASKS.jsonl.gz','rt')) if x['canonical_video_id'] in pending];sources={};metas=collections.defaultdict(list)
for l in (B/'processed.jsonl').open():
 a=json.loads(l)
 if a['engine']!='genesis' or a['scene_id']!='t01':continue
 if a['kind']=='video':sources[a['source_key']]=a
 elif '/metadata/' in a['logical_path']:metas[a['release_id']].append(a)
def diff(a,b,path=''):
 if isinstance(a,dict) and isinstance(b,dict):
  return sum((diff(a.get(k),b.get(k),path+'/'+k) for k in a.keys()|b.keys()),[])
 if a!=b:return [{'path':path,'retained':a,'recorded':b}]
 return []
out=[]
for t in tasks:
 key=t['source_repo']+'@'+t['source_revision']+':'+t['source_path'];s=sources[key];ma=next(x for x in metas[s['release_id']] if t['native_sample_id'] in x['logical_path'] and '__'+t['camera']+'.json' in x['logical_path']);p=ART/ma['path'];raw=p.read_bytes();assert hashlib.sha256(raw).hexdigest()==ma['sha256'];m=json.loads(gzip.decompress(raw));cfg=Path('/home/wangzijun_p25/liyuhan/phydataset/ase_asset_importer/everyday_bifurcation_T01_v2_7s/configs/formal_52800_v2_full_chain')/t['native_sample_id']/(t['camera']+'.json');c=json.loads(cfg.read_bytes());ce=c['experiment'].copy();me=m['experiment'].copy();ce.pop('production_qa_mode',None);me.pop('production_qa_mode',None);d=diff(ce,me,'/experiment');r=dict(canonical_video_id=t['canonical_video_id'],native_sample_id=t['native_sample_id'],camera=t['camera'],video_sha256=t['video_sha256'],config_path=str(cfg),config_sha256=hashlib.sha256(cfg.read_bytes()).hexdigest(),metadata_source_key=ma['source_key'],metadata_artifact_sha256=ma['sha256'],differences=d);out.append(r)
(O/'T01_VERSION_DIFFERENCES.json').write_text(json.dumps(out,indent=2));print('difference_paths',collections.Counter(x['path'] for r in out for x in r['differences']));print(json.dumps(out[::3],indent=2)[:6500])
