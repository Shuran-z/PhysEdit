"""Publish verified original config downloads without modifying scientific inputs."""
import collections,gzip,hashlib,json,shutil,subprocess,sys,zipfile
from pathlib import Path
from huggingface_hub import HfApi,CommitOperationAdd,hf_hub_download

R=Path('/data_cached/wangzijun_p25/config_bindings_20261031')
STAGE=R/'stage'
D=STAGE/'releases/physedit'
REPO='phy2/phydataset'
def sha(p):
    h=hashlib.sha256()
    with p.open('rb') as f:
        for b in iter(lambda:f.read(1024*1024),b''):h.update(b)
    return h.hexdigest()
def dump(p,v):p.write_text(json.dumps(v,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
def main():
    api=HfApi();inventory=json.loads((R/'INVENTORY.json').read_text());base=inventory['revision']
    assert api.repo_info(REPO,repo_type='dataset').sha==base,'Main changed; rebase config audit before publishing'
    status=json.loads(Path(hf_hub_download(REPO,'release_status.json',repo_type='dataset',revision=base)).read_text())
    zpath=Path(hf_hub_download(REPO,status['offline_metadata'],repo_type='dataset',revision=base))
    assert sha(zpath)==status['offline_metadata_sha256']
    assert not STAGE.exists(),'Use a fresh stage'
    D.mkdir(parents=True)
    with zipfile.ZipFile(zpath) as z:
        assert z.testzip() is None
        for item in z.infolist():
            p=Path(item.filename);assert not p.is_absolute() and '..' not in p.parts and p.parts[0]=='physedit'
            if item.is_dir():continue
            dest=STAGE/'releases'/p;dest.parent.mkdir(parents=True,exist_ok=True);dest.write_bytes(z.read(item))
    old_checks=json.loads((D/'checks/FILES_SHA256.json').read_text())
    for x in old_checks['files']:assert sha(D/x['path'])==x['sha256']
    (D/'downloads').mkdir(exist_ok=True)
    shutil.copyfile(R/'configs.zip',D/'provenance/configs.zip')
    package=json.loads((R/'PACKAGE.json').read_text())
    assert sha(D/'provenance/configs.zip')==package['zip_sha256']
    first=api.create_commit(REPO,repo_type='dataset',parent_commit=base,commit_message='Provide verified original configuration bytes',
        operations=[CommitOperationAdd(path_in_repo='releases/physedit/provenance/configs.zip',path_or_fileobj=str(D/'provenance/configs.zip'))])
    configrev=first.oid
    print(json.dumps({'phase':'CONFIG_BYTES_PUBLISHED','revision':configrev}),flush=True)
    bindings={}
    with gzip.open(R/'config_bindings.jsonl.gz','rt') as f:
        for b in map(json.loads,f):
            if b['status']=='VERIFIED':b['download']=dict(repo_id=REPO,revision=configrev,path='releases/physedit/provenance/configs.zip',member=b['archive_member'],sha256=b['config_sha256'],archive_sha256=package['zip_sha256'])
            bindings[b['canonical_video_id']]=b
    with gzip.open(D/'catalog/config_bindings.jsonl.gz','wt',encoding='utf8') as f:
        for b in bindings.values():f.write(json.dumps(b,ensure_ascii=False)+'\n')
    shutil.copyfile(R/'unresolved_configs.jsonl.gz',D/'checks/unresolved_configs.jsonl.gz')
    changed=[]
    for p in sorted((D/'catalog').rglob('*.jsonl.gz')):
        if p.name in ['config_bindings.jsonl.gz','content_groups.jsonl.gz','content_identity.jsonl.gz']:continue
        temp=p.with_suffix('.writing');count=0
        with gzip.open(p,'rt',encoding='utf8') as src,gzip.open(temp,'wt',encoding='utf8') as dst:
            for line in src:
                row=json.loads(line);cid=row.get('canonical_video_id')
                assert cid in bindings,(str(p),cid)
                b=bindings[cid];assert row['sha256']==b['video_sha256'],cid
                binding_fields={'config_binding_status','config_download','config_sha256'}
                original=json.dumps({k:v for k,v in row.items() if k not in binding_fields},sort_keys=True,ensure_ascii=False)
                row['config_binding_status']=b['status'];row['config_download']=b.get('download')
                row['config_sha256']=b.get('config_sha256')
                assert json.dumps({k:v for k,v in row.items() if k not in binding_fields},sort_keys=True,ensure_ascii=False)==original
                dst.write(json.dumps(row,ensure_ascii=False)+'\n');count+=1
        temp.replace(p);changed.append(str(p.relative_to(D)))
    shutil.copyfile(R/'download_original_configs.py',D/'tools/download_original_configs.py')
    # The simple guide now gives an executable, checked config export command.
    for name in ['docs/QUICKSTART_ZH.md','docs/DOWNLOAD.md']:
        p=D/name;text=p.read_text();start=text.find('**原始配置下载仍有缺口：**')
        if start>=0:
            end=text.find('\n\n',start);text=text[:start]+text[end+2:]
        text+='\n## 原始配置下载\n\n'
        text+='全量逐视频配置登记在 `physedit/catalog/config_bindings.jsonl.gz`，用 `canonical_video_id` 对应视频。`VERIFIED` 表示原始配置字节已核验，`config_download` 给出固定提交、归档成员和原始配置SHA256；未核实的记录明确标为 `UNRESOLVED`，不以参数表代替。\n\n'
        text+='下载并解压本说明第2步的最新元数据包后，按视频编号导出原始配置：\n\n```bash\npython physedit/tools/download_original_configs.py --video-id physedit_genesis_t03_7b11b86fe8ac0134__cam01 --output ./dataset\n```\n\n'
        text+='得到 `dataset/configs/T03/physedit_genesis_t03_7b11b86fe8ac0134__cam01.json`。也可用 `--scene T03` 按场景导出；命令会检查请求的配置是否全部可用并逐条校验SHA256。\n\n'
        text+=f"本轮检查72,000条：已核实配置绑定 {package['counts'].get('VERIFIED',0):,} 条，待补 {package['counts'].get('UNRESOLVED',0):,} 条；逐条缺口在 `physedit/checks/unresolved_configs.jsonl.gz`。先前抽查的4条缺口已全部补齐。\n"
        p.write_text(text)
    dump(D/'checks/CONFIG_BINDINGS.json',dict(base_revision=base,config_revision=configrev,**package))
    samples=['physedit_genesis_t03_7b11b86fe8ac0134__cam01','physedit_isaac_t11_a4ea4e89bd9981be__cam01','physedit_isaac_t19_0987dd87acd0c6d0__cam01','physedit_isaac_t20_48df634f70618cca__cam01']
    command=[sys.executable,str(D/'tools/download_original_configs.py'),'--output',str(R/'export_test')]
    for cid in samples:command+=['--video-id',cid]
    subprocess.run(command,check=True)
    records=[dict(path=p.relative_to(D).as_posix(),bytes=p.stat().st_size,sha256=sha(p)) for p in sorted(D.rglob('*')) if p.is_file() and p.relative_to(D).parts[0]!='downloads' and p!=D/'checks/FILES_SHA256.json']
    dump(D/'checks/FILES_SHA256.json',dict(algorithm='SHA-256',scope='Metadata package excluding this file and downloads.',files=records))
    archive=D/'downloads/physedit_metadata.zip'
    with zipfile.ZipFile(archive,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=6) as z:
        for p in sorted(D.rglob('*')):
            if p.is_file() and p.relative_to(D).parts[0]!='downloads':z.write(p,'physedit/'+p.relative_to(D).as_posix())
    with zipfile.ZipFile(archive) as z:
        assert z.testzip() is None
        for r in records:assert hashlib.sha256(z.read('physedit/'+r['path'])).hexdigest()==r['sha256']
    status['offline_metadata_sha256']=sha(archive);status['config_bindings_verified']=package['counts']['VERIFIED'];status['config_bindings_unresolved']=package['counts'].get('UNRESOLVED',0)
    dump(STAGE/'release_status.json',status)
    # Upload only changed or newly added metadata; source input texts and media remain untouched.
    prior={x['path']:x['sha256'] for x in old_checks['files']}
    files=[D/x['path'] for x in records if prior.get(x['path'])!=x['sha256']]
    files += [D/'checks/FILES_SHA256.json',archive,STAGE/'release_status.json']
    files=[p for p in files if p!=D/'provenance/configs.zip']
    print(json.dumps({'phase':'METADATA_PREPARED','files_to_upload':len(files),'metadata_zip_bytes':archive.stat().st_size}),flush=True)
    final=api.create_commit(REPO,repo_type='dataset',parent_commit=configrev,
        commit_message='Bind original configurations to all 72000 video records and add verified downloader',
        operations=[CommitOperationAdd(path_in_repo=p.relative_to(STAGE).as_posix(),path_or_fileobj=str(p)) for p in files])
    for p in files:
        got=Path(hf_hub_download(REPO,p.relative_to(STAGE).as_posix(),repo_type='dataset',revision=final.oid));assert sha(got)==sha(p),str(p)
    receipt=dict(revision=final.oid,base=base,config_revision=configrev,**package,files_uploaded=len(files),all_remote_hashes_verified=True,four_sample_exports_verified=True)
    dump(R/'PUBLISHED.json',receipt);print(json.dumps(receipt),flush=True)

if __name__=='__main__':main()
