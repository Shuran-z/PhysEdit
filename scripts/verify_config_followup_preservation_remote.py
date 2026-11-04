"""Verify publication changed only configuration bindings, never training or prompts."""
import gzip,hashlib,json,itertools,collections
from pathlib import Path
R=Path('/data_cached/wangzijun_p25/config_bindings_20261031');O=R/'remaining6767';OLD=R/'followup/stage/releases/physedit';NEW=O/'stage/releases/physedit'
def load(p):return list(map(json.loads,gzip.open(p,'rt')))
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
assert '"phase": "METADATA_PREPARED"' in (O/'publish.log').read_text(errors='replace')
exclude={'config_binding_status','config_download','config_sha256'};checked=[]
for a in sorted((OLD/'catalog').rglob('*.jsonl.gz')):
 if a.name in ['config_bindings.jsonl.gz','content_groups.jsonl.gz','content_identity.jsonl.gz']:continue
 b=NEW/a.relative_to(OLD);n=0
 with gzip.open(a,'rt') as f,gzip.open(b,'rt') as g:
  for left,right in itertools.zip_longest(f,g):
   assert left and right
   x=json.loads(left);y=json.loads(right);assert {k:v for k,v in x.items() if k not in exclude}=={k:v for k,v in y.items() if k not in exclude},x['canonical_video_id'];n+=1
 checked.append({'path':a.relative_to(OLD).as_posix(),'rows':n,'scientific_fields_identical':True})
files=[]
for p in ['catalog/split_assignments.csv','prompts/prompt_texts.jsonl.gz','prompts/video_prompt_bindings.jsonl.gz']:
 assert sha(OLD/p)==sha(NEW/p);files.append({'path':p,'sha256':sha(NEW/p),'unchanged':True})
train=load(NEW/'catalog/train_final.jsonl.gz');assert len(train)==45357
bindings=load(NEW/'catalog/config_bindings.jsonl.gz');assert len(bindings)==72000;assert len({x['canonical_video_id'] for x in bindings})==72000
report={'source_revision':json.loads((O/'INVENTORY.json').read_text())['revision'],'validated_metadata_zip_sha256':sha(NEW/'downloads/physedit_metadata.zip'),'training_videos':len(train),'training_scenes':len({x['quota_scene'] if 'quota_scene' in x else x['scene'] for x in train}),'training_membership_unchanged':True,'all_scientific_fields_unchanged':True,'checked_catalogs':checked,'prompt_and_split_files':files,'binding_counts':dict(collections.Counter(x['status'] for x in bindings))}
(O/'PRESERVATION_VERIFIED.json').write_text(json.dumps(report,indent=2));print(json.dumps({k:v for k,v in report.items() if k!='checked_catalogs'}),flush=True)
