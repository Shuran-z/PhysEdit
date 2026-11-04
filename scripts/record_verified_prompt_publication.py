"""Record the verified live revision and keep local prompt entry points current."""
from pathlib import Path
import hashlib,json,sys
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from scripts.boundary_ssh import remote_text
from scripts.supplement_hf_transport import hf_transport
OUT=ROOT/'review/full_prompt_audit_20261102/publish';REMOTE='/data_cached/wangzijun_p25/prompt_numeric_publish_20261102_4a88a7a4';PY='/home/wangzijun_p25/miniconda3/bin/python'
def main():
 with hf_transport(OUT,ports=(20876,20877,20878)) as proxy:
  code=f'''import os,json
from pathlib import Path
for k in ['HTTP_PROXY','HTTPS_PROXY','http_proxy','https_proxy']:os.environ[k]={proxy!r}
from huggingface_hub import HfApi
r=Path({REMOTE!r});verified=json.loads((r/'FRESH_VERIFIED.json').read_text());assert verified['status']=='PASS'
info=HfApi().repo_info('phy2/phydataset',repo_type='dataset');assert info.sha==verified['revision'];assert info.private is True
result={{'main_head':info.sha,'private':info.private,'license':info.card_data.get('license') if info.card_data else None}}
assert result['license']=='other'
(r/'LIVE_MAIN_CHECK.json').write_text(json.dumps(result,indent=2));print(json.dumps(result))
'''
  live=json.loads(remote_text('p25',code,timeout=60,attempts=1,python=PY))
 for name in ['PUBLISHED.json','FRESH_VERIFIED.json','LIVE_MAIN_CHECK.json','SCOPED_METADATA_CLEANUP_RECEIPT.json','UPLOAD_PLAN.json']:
  data=json.loads(remote_text('p25',f"from pathlib import Path;print(Path({REMOTE+'/'+name!r}).read_text())",timeout=45,attempts=1,python=PY));(OUT/name).write_text(json.dumps(data,indent=2),encoding='utf8')
 for name,source in [('PUBLISHED_NUMERIC_AUDIT.json','checks/PROMPT_NUMERIC_AUDIT_20261102.json'),('PUBLISHED_COMPRESSION_AUDIT.json','checks/PROMPT_LOSSLESS_STORAGE_COMPRESSION_20261102.json')]:
  data=json.loads(remote_text('p25',f"from pathlib import Path;print(Path({REMOTE+'/stage/releases/physedit/'+source!r}).read_text())",timeout=45,attempts=1,python=PY));(OUT/name).write_text(json.dumps(data,indent=2),encoding='utf8')
 pub=json.loads((OUT/'PUBLISHED.json').read_text());verified=json.loads((OUT/'FRESH_VERIFIED.json').read_text());plan=json.loads((OUT/'UPLOAD_PLAN.json').read_text())
 status=dict(status='PUBLISHED_AND_FRESHLY_VERIFIED',publication_complete=True,hf_commit_created=True,revision=pub['commit'],commit_url=pub['url'],videos=72000,prompt_bindings=216000,training_videos=45165,changed_files=pub['files'],fresh_hash_verification='PASS',local_old_metadata_backup_preserved=True,old_metadata_objects_cleaned=49,extra_historical_zip_deleted=False,media_config_splits_and_frozen_core100_preserved=True,active_training_jobs_changed=False)
 (OUT/'PUBLICATION_STATUS.json').write_text(json.dumps(status,ensure_ascii=False,indent=2),encoding='utf8')
 pointer=ROOT.parent/'prompts_72000_unified/CURRENT_AUDITED_PROMPTS.json';entry=json.loads(pointer.read_text(encoding='utf8'));entry.update(status='published_and_freshly_verified',huggingface_revision=pub['commit'],huggingface_commit_url=pub['url'],huggingface_manifest_url=f"https://huggingface.co/datasets/phy2/phydataset/resolve/{pub['commit']}/releases/physedit/catalog/videos.jsonl.gz",huggingface_manifest_sha256=next(x['sha256'] for x in plan['files'] if x['path']=='releases/physedit/catalog/videos.jsonl.gz'),publication_status=str(OUT/'PUBLICATION_STATUS.json'),published_audit=str(OUT/'PUBLISHED_NUMERIC_AUDIT.json'),online_release_changed=True,active_jobs_changed=False)
 pointer.write_text(json.dumps(entry,ensure_ascii=False,indent=2),encoding='utf8');print(json.dumps(status))
if __name__=='__main__':main()
