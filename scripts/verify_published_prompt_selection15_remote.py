import json,hashlib,gzip
from pathlib import Path
from huggingface_hub import HfApi,hf_hub_download
R=Path('/data_cached/wangzijun_p25/config_bindings_20261031');O=R/'prompt_registration15';D=O/'stage/releases/physedit';pub=json.loads((O/'PUBLISHED.json').read_text());rev=pub['revision'];paths=['releases/physedit/checks/PROMPT_PARAMETER_SELECTION_FIX.json','releases/physedit/catalog/by_scene/genesis__T04.jsonl.gz'];downloaded=[]
for rel in paths:
 p=Path(hf_hub_download('phy2/phydataset',rel,repo_type='dataset',revision=rev,local_dir=O/'fresh_downloads',force_download=True));assert hashlib.sha256(p.read_bytes()).hexdigest()==hashlib.sha256((O/'stage'/rel).read_bytes()).hexdigest();downloaded.append(rel)
reg=json.loads((O/'fresh_downloads'/paths[0]).read_text());rows={x['canonical_video_id']:x for x in map(json.loads,gzip.open(O/'fresh_downloads'/paths[1],'rt'))}
for record in reg['records']:
 row=rows[record['canonical_video_id']];assert row['selected_parameter_keys']==record['selected_parameter_keys'];assert row['prompt_variant_sha256']==record['prompt_variant_sha256'];assert row['sha256']==record['video_sha256'];assert [hashlib.sha256(p.encode()).hexdigest() for p in row['prompt_variants_en']]==record['prompt_variant_sha256']
api=HfApi();remote={x.path:x for x in api.get_paths_info('phy2/phydataset',['releases/physedit/'+x['path'] for x in pub['protected_files']],repo_type='dataset',revision=rev)}
for rec in pub['protected_files']:
 x=remote['releases/physedit/'+rec['path']];local=(D/rec['path']).read_bytes();assert hashlib.sha256(local).hexdigest()==rec['sha256']
 if x.lfs:assert x.lfs.sha256==rec['sha256']
 else:assert x.blob_id==hashlib.sha1(b'blob '+str(len(local)).encode()+b'\0'+local).hexdigest()
r=dict(revision=rev,registry_sha256=pub['registry_sha256'],fresh_downloaded_files=downloaded,corrected_records_checked=15,all_selected_keys_match=True,all_prompt_and_video_hashes_unchanged=True,remote_train_split_and_prompt_files_byte_identical=True);(O/'FRESH_VERIFIED.json').write_text(json.dumps(r,indent=2));print(json.dumps(r),flush=True)
