"""Rebind the existing release to flat scene paths; preserve all scientific rows."""
import collections
import copy
import gzip
import hashlib
import json
from pathlib import Path
import shutil
import zipfile
import pyarrow as pa
import pyarrow.parquet as pq

ROOT = Path('/data_cached/wangzijun_p25/scene_videos_20261031')
ORIGINAL = Path('/data_cached/wangzijun_p25/t19_final_release_20261030/stage/releases/physedit')
STAGE = ROOT/'metadata'
D = STAGE/'releases/physedit'


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read(path):
    return json.loads(Path(path).read_text())


def dump(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2)+'\n')


def lines(path):
    with gzip.open(path,'rt',encoding='utf8') as stream:
        for line in stream:
            if line.strip():
                yield json.loads(line)


def write_rows(path, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    with gzip.open(path,'wt',encoding='utf8') as stream:
        for row in rows:
            stream.write(json.dumps(row,ensure_ascii=False,separators=(',',':'))+'\n')


PATH_FIELDS = {'canonical_path','relative_path','download','media_in_current_scene_directory',
    'canonical_path_storage','metadata_download','config_download','prompt_downloads','native_media_prefix',
    'metadata_reference'}


def scientific_digest(row):
    return hashlib.sha256(json.dumps({k:v for k,v in row.items() if k not in PATH_FIELDS},
        ensure_ascii=False,sort_keys=True,separators=(',',':')).encode()).hexdigest()


def main():
    state,plan = read(ROOT/'STATE.json'),read(ROOT/'PLAN.json')
    assert len(set(state['completed_ids'])) == 72000 and not state.get('pending_verification')
    auxiliary = read(ROOT/'AUXILIARY.json')
    media_revision = auxiliary['revision']
    assert state['head'] == media_revision
    mapping = {r['id']:r for r in plan['rows']}
    if D.exists():
        raise RuntimeError('Do not overwrite a prepared package')
    shutil.copytree(ORIGINAL,D,ignore=shutil.ignore_patterns('__pycache__'))
    shutil.copy2(Path('/data_cached/wangzijun_p25/t19_final_release_20261030/stage/README.md'),STAGE/'README.md')
    shutil.copy2(Path('/data_cached/wangzijun_p25/t19_final_release_20261030/stage/release_status.json'),STAGE/'release_status.json')
    changed = 0

    def rebind(old):
        nonlocal changed
        row = copy.deepcopy(old)
        task = mapping[row['canonical_video_id']]
        assert row['sha256'] == task['sha256']
        row.update(canonical_path=task['path'],relative_path=task['path'],
            download=dict(repo_id=plan['repo'],revision=media_revision,path=task['path'],member=''),
            canonical_path_storage='direct_mp4',media_in_current_scene_directory=True,
            native_media_prefix='data/'+row['quota_scene'],
            metadata_reference=dict(manifest='releases/physedit/catalog/videos.jsonl.gz',video_id=row['canonical_video_id']))
        for key in ['metadata_download','config_download','prompt_downloads']:
            row.pop(key,None)
        assert scientific_digest(row) == scientific_digest(old),row['canonical_video_id']
        changed += 1
        return row

    records = [rebind(row) for row in lines(ORIGINAL/'catalog/videos.jsonl.gz')]
    assert len(records) == 72000
    byid = {r['canonical_video_id']:r for r in records}
    counts = collections.Counter(r['quota_scene']for r in records)
    assert counts == {f'T{i:02}':3600 for i in range(1,21)}
    write_rows(D/'catalog/videos.jsonl.gz',records)
    for name in ['train_final.jsonl.gz','train_unique_declared_triplets.jsonl.gz']:
        write_rows(D/'catalog'/name,(rebind(row)for row in lines(ORIGINAL/'catalog'/name)))
    for scene in counts:
        for engine in ['genesis','isaac']:
            write_rows(D/f'catalog/by_scene/{engine}__{scene}.jsonl.gz',
                (r for r in records if r['quota_scene']==scene and r['engine']==engine))
    bindings=[]
    for old in lines(ORIGINAL/'prompts/video_prompt_bindings.jsonl.gz'):
        row=copy.deepcopy(old);current=byid[row['video_id']]
        assert row['video_sha256']==current['sha256'] and row['prompt_sha256']==current['prompt_variant_sha256']
        row['video_path']=current['canonical_path'];row['download']=current['download'];row.pop('prompt_downloads',None)
        bindings.append(row)
    assert len(bindings)==72000
    write_rows(D/'prompts/video_prompt_bindings.jsonl.gz',bindings)
    for path in (D/'catalog/parquet').glob('*.parquet'):
        original_table=pq.read_table(path); rows=original_table.to_pylist()
        for row in rows:
            current=byid[row['video_id']]
            assert row['video_sha256']==current['sha256']
            row.update(canonical_path=current['canonical_path'],media_repo=plan['repo'],
                media_revision=media_revision,media_path=current['canonical_path'],archive_member='')
        pq.write_table(pa.Table.from_pylist(rows,schema=original_table.schema),path,compression='zstd')
    index=read(D/'catalog/scene_index.json')
    for row in index['entries']:
        scene=row['quota_scene']
        if scene in counts:
            row.update(video_directory='data/'+scene,native_direct_mp4=row['videos'],
                       archive_member_videos=0)
            if 'media_prefix' in row:
                row['media_prefix']='data/'+scene
    dump(D/'catalog/scene_index.json',index)
    # Local materialization also keeps metadata outside the twenty video folders.
    tool=D/'tools/download_standardized.py'
    text=tool.read_text().replace("meta=target.parent.parent/'metadata'/(row['canonical_video_id']+'.json')",
        "meta=root/'metadata'/row['quota_scene']/(row['canonical_video_id']+'.json')")
    text=text.replace('meta.parent.mkdir(exist_ok=True)','meta.parent.mkdir(parents=True,exist_ok=True)')
    tool.write_text(text)
    for name in ['download_release.py','prepare_core100_current.py']:
        path=D/'tools'/name
        path.write_text(path.read_text().replace("REVISION = 'v1.0.2'","REVISION = 'main'"))
    prompt_manifest=read(D/'prompts/PROMPT_MANIFEST.json')
    prompt_manifest.update(current_video_prompt_bindings_sha256=sha(D/'prompts/video_prompt_bindings.jsonl.gz'),
        video_layout='data/T01..T20/<existing video filename>.mp4',scene_layout_changes_text_or_parameters=False)
    dump(D/'prompts/PROMPT_MANIFEST.json',prompt_manifest)
    quickstart='''# 下载和使用

视频直接放在 `data/T01/` 到 `data/T20/`，每个场景3,600个MP4，共72,000个。文件名、视频内容、三条提示词和物理参数保持不变。

下载全部视频：

```bash
python -m pip install -U huggingface_hub
hf auth login
hf download phy2/phydataset --repo-type dataset --include "data/T*/*.mp4" --local-dir ./dataset
```

只下载一个场景，把上述include改为 `data/T01/*.mp4`。所有视频都是独立文件，可在HF网页直接打开，不需要解压视频归档。

提示词、原始配置、训练测试划分放在 `releases/physedit/`。全量权威清单是 `catalog/videos.jsonl.gz`；每条视频有自己的 `parameter_facts`、物理输入、控制说明和三条英文 `prompt_variants_en`。`prompt_en` 等于第1条。比较模型时使用相同变体和seed，不改写冻结文本。

训练完整成员为45,357条；现有去重训练视图为42,207条。两者沿用相同的16类训练/留出规则，不拼接重复使用。T03/T20为OOD-1、T11/T19为OOD-2，全部不进入训练；测试、候补及已登记同源组排除，无另设验证集。

需要按训练清单下载时，解压元数据包后运行：

```bash
python tools/download_standardized.py --manifest catalog/train_final.jsonl.gz --output ./dataset
```

新Genesis T19的原始物理配置、轨迹、各背景渲染元数据及哈希绑定在 `provenance/t19_gen_new_20261030/`。完整参数不能只靠短prompt恢复。原始状态源文件保留在元数据区，不作为另加的视频样本。

当前Core100输入由 `tools/prepare_core100_current.py --output NEW_DIRECTORY` 导出：95条原实际输入＋5条当前Isaac T19输入，条件图和prompt逐项核验。原 `core100/` 目录供复现历史实际输入；不把旧T19成绩转给新视频。生成用的T19完整观察窗至209/30秒。

下载工具会将main解析为固定提交并记录回执。需要复现实验时保存该提交，不依赖之后变化的main。
'''
    (D/'docs/QUICKSTART_ZH.md').write_text(quickstart)
    (D/'docs/DOWNLOAD.md').write_text(quickstart)
    root_text=(STAGE/'README.md').read_text()
    yaml_end=root_text.find('\n---',4)+4 if root_text.startswith('---') else 0
    front=root_text[:yaml_end]+'\n\n' if yaml_end else ''
    intro='''# PhysEdit

**72,000 videos, organized in 20 scene folders.**

Open `data/T01/` through `data/T20/`. Each folder contains **3,600 individual MP4 files**. Existing filenames, video bytes, physical inputs and three short English prompts are preserved.

```bash
hf auth login
hf download phy2/phydataset --repo-type dataset --include "data/T*/*.mp4" --local-dir ./dataset
```

Prompts, original configurations and train/test manifests: [releases/physedit](releases/physedit/README.md).

[下载和使用说明](releases/physedit/docs/QUICKSTART_ZH.md)

Genesis and Isaac are jointly trained. T03/T20 and T11/T19 are held out. Core100 contains 80 ID + 10 OOD-1 + 10 OOD-2 cases; reserve/source groups stay excluded from training. No additional validation split is introduced.
'''
    (STAGE/'README.md').write_text(front+intro)
    (D/'README.md').write_text('# 元数据\n\n视频在仓库的 `data/T01/` 至 `data/T20/`，各3,600个独立MP4。\n\n'
        '- `catalog/videos.jsonl.gz`：72,000条完整元数据及当前视频路径。\n'
        '- `prompts/`：每条视频的三条英文prompt及哈希绑定。\n'
        '- `catalog/train_final.jsonl.gz`：原训练成员；其他划分和现有去重视图保留原规则。\n'
        '- `provenance/` 和 `shards/`：原始配置、轨迹和状态来源，不额外计入视频数。\n'
        '- `core100/` 与当前参考登记：保留原输入与当前5条Isaac T19的区别。\n\n'
        '[下载和使用](docs/QUICKSTART_ZH.md)\n')
    (STAGE/'DIRECTORY.md').write_text('# 目录\n\n`data/T01/` 至 `data/T20/`：每类3,600个独立MP4。\n\n'
        '`releases/physedit/`：提示词、原始配置、状态来源和训练测试划分。\n\n'
        '`benchmarks/`、`catalog/`：Core100参考登记；不另计入72,000条视频。\n')
    storage=read(D/'checks/STORAGE_INTEGRITY.json')
    storage.update(direct_video_records=72000,archived_video_records=0,archives=[],
        video_directory_layout='data/T01..T20/<existing video filename>.mp4',
        original_state_source_files=auxiliary['files'])
    for key in ['archive_objects','archives_total','selected_archive_video_records','direct_video_objects_current']:
        storage.pop(key,None)
    dump(D/'checks/STORAGE_INTEGRITY.json',storage)
    schema=D/'docs/SCHEMA.md'
    text=schema.read_text().replace('Materialized output name; an archive-stored video need not exist online as an individual MP4 at this path.',
        'Current directly hosted MP4 path: data/T01..T20 followed by the unchanged existing video filename.')
    text='\n'.join(line for line in text.splitlines()if not line.startswith('T19 direct files:'))+'\n'
    text+='\nEvery current download binding points to one directly hosted MP4 with an empty archive member. '
    text+='Full physical inputs and prompt bindings are in the common catalog. Original source/state provenance is separate from the current video download path.\n'
    schema.write_text(text)
    identity=D/'docs/CONTENT_IDENTITY.md'
    text=identity.read_text();mark=text.find('## T19 storage')
    if mark>=0:text=text[:mark]
    text+='\n## Current video locations\n\nAll 72,000 videos are directly hosted in data/T01..T20. '
    text+='The existing IDs, per-video hashes, declared inputs, prompts and training/holdout decisions are unchanged. '
    text+='Earlier review receipts retain their original source paths; current downloads use the catalog.\n'
    identity.write_text(text)
    status=read(STAGE/'release_status.json')
    status.pop('current_package_tag',None)
    status.update(current_reference='main',video_layout='data/T01..T20/<existing video filename>.mp4',
        direct_video_records=72000,archived_video_records=0,video_files_per_scene=3600,
        media_revision=media_revision,t19_genesis_directory='data/T19')
    report=dict(status='PASS',videos=72000,scene_counts=dict(counts),direct_videos=72000,
        archived_video_records=0,existing_video_ids_preserved=True,existing_video_bytes_sha256_preserved=True,
        scientific_inputs_and_all_other_nonpath_fields_preserved=True,
        prompt_texts_and_hashes_preserved=True,train_test_membership_preserved=True,
        media_revision=media_revision,original_state_payloads_preserved=len(auxiliary['files']))
    dump(D/'checks/SCENE_VIDEO_LAYOUT.json',report)
    audit=read(D/'checks/FINAL_USAGE_AUDIT.json')
    audit['scene_video_layout']=report
    audit['download_objects']=dict(status='PASS',objects=72000,direct_lfs_hashes=72000,
        archive_objects_required_for_video_download=0,missing_objects=0,hash_mismatches=0,
        verification_source='Every file was verified after its staging commit; the complete tree is checked before publication.')
    audit.pop('canonical_hosted_t19',None)
    dump(D/'checks/FINAL_USAGE_AUDIT.json',audit)
    files=[dict(path=p.relative_to(D).as_posix(),bytes=p.stat().st_size,sha256=sha(p))
        for p in sorted(D.rglob('*')) if p.is_file() and p.relative_to(D).parts[0]!='downloads'
        and p!=D/'checks/FILES_SHA256.json']
    dump(D/'checks/FILES_SHA256.json',dict(algorithm='SHA-256',scope='Metadata package excluding this file and downloads.',files=files))
    archive=D/'downloads/physedit_metadata.zip'
    with zipfile.ZipFile(archive,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=6)as z:
        for p in sorted(D.rglob('*')):
            if p.is_file()and p.relative_to(D).parts[0]!='downloads':z.write(p,'physedit/'+p.relative_to(D).as_posix())
    with zipfile.ZipFile(archive)as z:
        assert z.testzip()is None
        for item in files:assert hashlib.sha256(z.read('physedit/'+item['path'])).hexdigest()==item['sha256']
    status['offline_metadata_sha256']=sha(archive)
    dump(STAGE/'release_status.json',status)
    dump(ROOT/'METADATA_READY.json',report)
    print(json.dumps(report),flush=True)


if __name__=='__main__':
    main()
