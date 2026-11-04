"""Merge newly evidenced configs, preserving every earlier video and config binding."""
import collections,gzip,hashlib,json,shutil,zipfile,os
from pathlib import Path
from huggingface_hub import HfApi
R=Path('/data_cached/wangzijun_p25/config_bindings_20261031');O=Path(os.environ.get('CONFIG_RECOVERY_OUT',str(R/'followup')));BASE=Path(os.environ.get('CONFIG_RECOVERY_BASE',str(R)))
BINDINGS=BASE/'stage/releases/physedit/catalog/config_bindings.jsonl.gz' if (BASE/'stage').exists() else BASE/'config_bindings.jsonl.gz'
PENDING=BASE/'stage/releases/physedit/checks/unresolved_configs.jsonl.gz' if (BASE/'stage').exists() else BASE/'unresolved_configs.jsonl.gz'
def load(p):
    with gzip.open(p,'rt') as f:return list(map(json.loads,f))
def sha(raw):return hashlib.sha256(raw).hexdigest()
old=load(BINDINGS);new=load(O/'NEW_RECOVERIES.jsonl.gz');added={x['canonical_video_id']:x for x in new}
tasks={x['canonical_video_id']:x for x in load(R/'TASKS.jsonl.gz')}
before={x['canonical_video_id']:x for x in old};assert len(before)==72000
assert all(before[cid]['status']=='UNRESOLVED' for cid in added)
source=json.loads((BASE/'PUBLISHED.json').read_text());api=HfApi();base=api.repo_info('phy2/phydataset',repo_type='dataset').sha
assert base==source['revision'],'Current source changed; reconcile before publishing'
archive=O/'configs.zip';seen=set()
with zipfile.ZipFile(BASE/'configs.zip') as src,zipfile.ZipFile(archive,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=6) as dst:
    assert sha((BASE/'configs.zip').read_bytes())==source['zip_sha256']
    for info in src.infolist():
        raw=src.read(info);assert sha(raw)==Path(info.filename).stem;dst.writestr(info,raw);seen.add(Path(info.filename).stem)
    for cid,x in added.items():
        raw=Path(x['local_path']).read_bytes();h=sha(raw);assert h==x['sha256'];json.loads(raw)
        if h not in seen:dst.writestr('configs/'+h+'.json',raw);seen.add(h)
        oldrow=before[cid];t=tasks[cid];assert t['video_sha256']==oldrow['video_sha256']
        before[cid]=dict(canonical_video_id=cid,video_sha256=t['video_sha256'],engine=t['engine'],scene=t['scene'],status='VERIFIED',config_sha256=h,archive_member='configs/'+h+'.json',method=x['method'],source_evidence=x['evidence'])
        if x.get('config_document_type'):before[cid]['config_document_type']=x['config_document_type']
with zipfile.ZipFile(archive) as z:
    assert z.testzip() is None
    for h in seen:assert sha(z.read('configs/'+h+'.json'))==h
with gzip.open(O/'config_bindings.jsonl.gz','wt') as f:
    for b in before.values():f.write(json.dumps(b)+'\n')
remaining_check={x['canonical_video_id']:x for x in load(O/'REMAINING.jsonl.gz')}
missing=[]
for x in load(PENDING):
    cid=x['canonical_video_id']
    if cid in added:continue
    if cid in remaining_check:x['source_recheck']=remaining_check[cid]
    if x['scene']=='T04':x['remaining_action']='Recover original formal_880_v1_480p config bytes; normalized metadata-derived Isaac copies are not original Genesis inputs'
    if x['scene']=='T01':x['remaining_action']='Recover actual executed config version; retained candidates fail complete input comparison'
    missing.append(x)
with gzip.open(O/'unresolved_configs.jsonl.gz','wt') as f:
    for x in missing:f.write(json.dumps(x)+'\n')
counts=collections.Counter(b['status'] for b in before.values())
summary=dict(total=72000,counts=dict(counts),unique_configs=len(seen),zip_sha256=sha(archive.read_bytes()),zip_bytes=archive.stat().st_size,all_four_sample_gaps_recovered=True,newly_recovered=len(added),original_matrix_record_bindings=sum(b.get('config_document_type')=='original_generation_matrix_record' for b in before.values()),
    by_scene=[dict(engine=e,scene=s,status=k,videos=n) for (e,s,k),n in sorted(collections.Counter((b['engine'],b['scene'],b['status']) for b in before.values()).items())])
(O/'PACKAGE.json').write_text(json.dumps(summary,indent=2));(O/'INVENTORY.json').write_text(json.dumps({'revision':base}))
shutil.copyfile(R/'download_original_configs.py',O/'download_original_configs.py')
print(json.dumps({k:v for k,v in summary.items() if k!='by_scene'}),flush=True)
