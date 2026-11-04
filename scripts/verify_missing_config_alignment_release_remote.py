import json,hashlib
from pathlib import Path
from huggingface_hub import HfApi
D=Path('/data_cached/wangzijun_p25/config_bindings_20261031/remaining2241/stage');O=Path('/data_cached/wangzijun_p25/config_bindings_20261031/missing_config_training_audit');api=HfApi();rev=api.repo_info('phy2/phydataset',repo_type='dataset').sha;paths=['releases/physedit/catalog/videos.jsonl.gz','releases/physedit/catalog/train_final.jsonl.gz','releases/physedit/catalog/split_assignments.csv','releases/physedit/prompts/video_prompt_bindings.jsonl.gz','releases/physedit/prompts/prompt_texts.jsonl.gz'];rows=[]
for info in api.get_paths_info('phy2/phydataset',paths,repo_type='dataset',revision=rev):
 raw=(D/info.path).read_bytes();h=hashlib.sha256(raw).hexdigest();ok=info.lfs.sha256==h if info.lfs else info.blob_id==hashlib.sha1(b'blob '+str(len(raw)).encode()+b'\0'+raw).hexdigest();assert ok;rows.append(dict(path=info.path,sha256=h,unchanged_from_audited_snapshot=True))
r=dict(current_revision=rev,audited_release_revision='88f8fde1d1c240cec2cc0c201a4310cd8d4c5cbc',files=rows,all_remote_files_match=True,no_training_or_prompt_files_written=True);(O/'CURRENT_RELEASE_VERIFIED.json').write_text(json.dumps(r,indent=2));print(json.dumps(r),flush=True)
