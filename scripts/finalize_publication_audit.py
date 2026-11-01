"""Publishable current-state documentation and verified consolidated-media bindings."""
import collections
import gzip
import hashlib
import json
from pathlib import Path
import shutil

REPO=Path(__file__).resolve().parents[1]
ROOT=REPO.parent/'release_72000_active';OUT=ROOT/'publication_audit_20261029';STAGE=OUT/'metadata'
PREFIX='releases/72000_release_candidate_20261029'


def read(path):
    with gzip.open(path,'rt',encoding='utf-8') as f:return list(map(json.loads,f))


def write(path,rows):
    path.parent.mkdir(parents=True,exist_ok=True)
    with gzip.open(path,'wt',encoding='utf-8') as f:
        for r in rows:f.write(json.dumps(r,ensure_ascii=False)+'\n')


def dump(path,obj):
    path.parent.mkdir(parents=True,exist_ok=True);path.write_text(json.dumps(obj,indent=2,ensure_ascii=False),encoding='utf-8')


def main():
    media=json.loads((OUT/'MEDIA_CONSOLIDATED.json').read_text())
    assert media['all_destination_lfs_hashes_verified'] and media['completed_operations']==media['total_operations']==56185
    assert media['copied_objects']==54354 and media['skipped_retired_objects']==1831
    bindings={r['video_id']:r for r in read(OUT/'media_destination_bindings.jsonl.gz')}
    rows=read(STAGE/PREFIX/'videos.jsonl.gz');groups=collections.defaultdict(list)
    retired_count=0;current_count=0
    for row in rows:
        b=bindings[row['video_id']];assert b['video_sha256']==row['sha256']
        if row.get('quality_source_restriction_evidence'):row['source_quality_unchanged']=False
        if row.get('parameter_unit_corrections') and row.get('source_prompt_variant_sha256'):
            row['prompt_binding_method']='exact_media_source_facts_with_temporal_unit_correction'
            if row.get('prompt_source_catalog'):row['prompt_base_catalog']=row['prompt_source_catalog']
            row['prompt_source_catalog']=PREFIX+'/unit_corrections.jsonl.gz'
        row['source_download']=b['source_download']
        if row['quality_admission_status'].startswith('UNUSABLE_'):
            row['download']=b['source_download'];row['media_in_current_scene_directory']=False;retired_count+=1
        else:
            row['download']={'repo_id':'phy2/phydataset','revision':media['revision'],
                'path':b['destination_path'],'member':b['member']}
            row['media_in_current_scene_directory']=True;current_count+=1
        assert not row['download']['path'].startswith(('https://','http://'))
        assert row['download'].get('revision')
        groups[row['quota_scene']].append(row)
    assert len(rows)==72000 and current_count==69210 and retired_count==2790
    dest=STAGE/PREFIX;write(dest/'videos.jsonl.gz',rows)
    usable=[r for r in rows if r['quality_admission_status'].startswith('USABLE_')]
    assert len(usable)==32868;write(dest/'usable_videos.jsonl.gz',usable)
    summary=json.loads((OUT/'catalog_audit.json').read_text())
    summary.update(nonretired_entries_in_current_repository=current_count,
        excluded_records_kept_as_provenance=retired_count,current_media_files=media['copied_objects'],
        media_revision=media['revision'],current_media_lfs_hash_checks_passed=True,
        current_nonretired_review_directory_references=0,
        all_nonretired_media_in_single_repository=True,
        source_objects_moved_without_rerendering=True,
        publication_readiness='NOT_READY_AS_FULLY_ACCEPTED_72000_VIDEO_BENCHMARK',
        public_repository_enabled=False,license_decision='unchanged_at_author_request',
        manifest_sha256=hashlib.sha256((dest/'videos.jsonl.gz').read_bytes()).hexdigest())
    dump(dest/'validation.json',summary)
    scenes=[]
    for scene,items in sorted(groups.items()):
        root=STAGE/'data'/scene
        write(root/'videos.jsonl.gz',items)
        counts=collections.Counter(r['engine'] for r in items);quality=collections.Counter(r['quality_admission_status'] for r in items)
        title=items[0]['scene_title_en']
        index={'quota_scene_id':scene,'title_en':title,'video_entries':len(items),'by_engine':dict(counts),
            'native_scene_counts':dict(collections.Counter(r['scene'] for r in items)),
            'quality_states':dict(quality),'prompt_variants_per_video':3,
            'current_scene_media_records':sum(r['media_in_current_scene_directory'] for r in items),
            'media_revision':media['revision'],'manifest':'videos.jsonl.gz'}
        dump(root/'INDEX.json',index);scenes.append(index)
        for engine in ['genesis','isaac']:
            selected=[r for r in items if r['engine']==engine]
            write(root/f'videos_{engine}.jsonl.gz',selected)
            native=selected[0]['scene'];engine_root=STAGE/'data'/native/engine;engine_root.mkdir(parents=True,exist_ok=True)
            n=sum(r['media_in_current_scene_directory'] for r in selected)
            (engine_root/'README.md').write_text(f'''# {native} / {engine}

This index contains {len(selected):,} selected records and {n:,} records with media
in this scene/engine directory. Excluded records retain fixed source bindings
and are not copied into the current media directory. Direct MP4 files use the
canonical trajectory/video names; packed media is in `archives/` with exact
member mappings in the scene index. Every record carries its own SHA-256,
three English prompts and admission state.
''',encoding='utf-8')
        (root/'README.md').write_text(f'''# {scene} — {title}

{items[0]['scene_description_en']}

| Field | Records |
|---|---:|
| Genesis | {counts['genesis']:,} |
| Isaac | {counts['isaac']:,} |
| Total | {len(items):,} |
| Media in current scene directories | {index['current_scene_media_records']:,} |
| Registered usable | {sum(v for k,v in quality.items() if k.startswith('USABLE_')):,} |
| Pending review | {quality['PENDING_REVIEW']:,} |
| Excluded | {sum(v for k,v in quality.items() if k.startswith('UNUSABLE_')):,} |

[Complete index](videos.jsonl.gz) · [Genesis index](videos_genesis.jsonl.gz) · [Isaac index](videos_isaac.jsonl.gz)

Each row binds media, three English prompts, exact parameters, canonical names
and admission state. Current non-excluded media is stored under the native
scene's `genesis/` or `isaac/` directory. Archive members are resolved by the
download tool. Excluded records are provenance entries and are not part of the
default download. Use `quality_admission_status` to select the intended subset.
'''+('\nIsaac uses the distinct native [T14S scene](../T14S/README.md) for this quota.\n' if scene=='T14' else ''),encoding='utf-8')
    native=[r for r in rows if r['scene']=='T14S'];write(STAGE/'data/T14S/videos.jsonl.gz',native)
    dump(STAGE/'data/T14S/INDEX.json',{'native_scene_id':'T14S','quota_scene_id':'T14','engine':'isaac','video_entries':960,'media_directory':'isaac/','manifest':'videos.jsonl.gz'})
    (STAGE/'data/T14S/README.md').write_text('# T14S — Spring launcher and hinged gate\n\nT14S has 960 Isaac records and occupies the Isaac T14 quota. Its media is in\n[isaac/](isaac/); [videos.jsonl.gz](videos.jsonl.gz) contains exact inputs,\nthree English prompts and source bindings. It retains its native identity and\ndoes not share Genesis T14 event definitions or boundary values.\n',encoding='utf-8')
    alias=STAGE/'data/T14/isaac';alias.mkdir(parents=True,exist_ok=True)
    (alias/'README.md').write_text('# T14 quota / Isaac\n\nThis quota uses the distinct native [T14S](../../T14S/README.md) scene.\nIts current media is in [T14S/isaac](../../T14S/isaac/), counted once.\n',encoding='utf-8')
    table='\n'.join(f"| [{x['quota_scene_id']}]({x['quota_scene_id']}/README.md) | 2,640 | 960 | {x['current_scene_media_records']:,} |" for x in scenes)
    (STAGE/'data/README.md').write_text('''# PhysEdit 场景目录

20个配额场景，共72,000条记录。当前场景目录存放69,210条未停用记录的媒体，
其余2,790条只保留固定来源绑定。训练与评测需进一步筛选可用状态，不能把
“文件已收录”直接作为质量验收结论。

| 场景 | Genesis记录 | Isaac记录 | 当前目录中的媒体记录 |
|---|---:|---:|---:|
'''+table+'''

Isaac T14配额采用独立标识的T14S；两处索引不重复计数。
每条记录提供三个英文prompt、物理参数、规范名称和SHA-256。
[完整清单与下载工具](../releases/72000_release_candidate_20261029/README.md)。
''',encoding='utf-8')
    dump(dest/'scene_index.json',scenes)
    dump(STAGE/'catalog/active_72000.json',{'repo':'phy2/phydataset','manifest_path':PREFIX+'/videos.jsonl.gz',
        'usable_manifest_path':PREFIX+'/usable_videos.jsonl.gz','record_count':72000,'usable_records':32868,
        'resolve_manifest_at_same_commit_as_pointer':True,'media_revision':media['revision'],'core100_prompt_policy':'frozen_v6'})
    shutil.copyfile(REPO/'scripts/download_standardized_72000.py',dest/'download_standardized.py')
    (dest/'README.md').write_text('''# PhysEdit 数据清单与下载

`videos.jsonl.gz`包含72,000条记录，`usable_videos.jsonl.gz`包含当前登记为可用的
32,868条记录。视频文件按场景和引擎归集，未停用记录的下载绑定均指向本仓库的
固定版本。停用记录保留来源绑定，不在默认下载集合中。

每条记录包含三个英文prompt、物理参数、SHA-256、规范视频名、包内成员及审核状态。
规范文件名为`physedit_<engine>_<native_scene>_<trajectory_hash>__cam0N.mp4`。
压缩包通过成员映射解包为相同的目录规范。

```sh
pip install huggingface_hub
python download_standardized.py --manifest videos.jsonl.gz --scene T20 --admission usable --output ./PhysEdit
```

使用`--engine genesis`或`--engine isaac`选择引擎。`--admission nonretired`包括待复核记录；
`all`还包括停用记录，仅用于按来源开展检查。下载过程逐视频核对SHA-256。
仓库认证使用Hugging Face账号或HF_TOKEN环境变量。

`validation.json`提供当前目录检查，`unit_corrections.jsonl.gz`记录时间参数单位修正。
普通数据prompt的单位修正涉及3,600条记录，固定Core100 v6输入保持不变。
许可设置按作者要求保持不变。完整检查见[PUBLICATION_CHECK.md](PUBLICATION_CHECK.md)。
''',encoding='utf-8')
    report=f'''# PhysEdit 发布检查

## 结论

目录和文本可以作为带明确准入状态的数据目录使用。当前不满足“72,000条均已完成
质量验收、可直接作为正式训练与评测集合”的标准。仓库保持私有，授权设置不变。

| 检查项 | 当前结果 |
|---|---|
| 目录记录 | 72,000条；20个配额场景，每场景3,600条 |
| 三机位分组 | 24,000组，每组cam01/cam02/cam03齐全 |
| 背景与重力单元 | 800个场景×引擎×背景×重力单元，配额齐全 |
| 规范ID与路径 | 72,000条均无冲突 |
| 视频内容 | 按SHA-256为67,532种内容 |
| 英文prompt | 216,000段；18,339种文本逐项核验，无token长度或哈希错误 |
| 时间参数单位 | 3,600条记录已修正，涉及10,800段文本 |
| 下载字段 | 3,840条完整网址已改为正确的仓库路径 |
| 当前媒体归集 | 69,210条未停用记录，54,354个文件／视频包，目的LFS哈希全部核验 |
| 停用对象 | 2,790条只保留固定来源绑定，未复制到当前媒体目录 |
| 当前review目录 | 无；未停用成员对该目录的下载引用为零 |
| 来源停用状态 | 960条Isaac T19按明确来源限制恢复停用 |
| 可用登记 | 32,868条；31,399种不同视频内容 |
| 待复核 | 36,342条 |
| 全量画面质量审核 | 未完成；本轮没有把哈希检查记作画面审核 |
| 全量重新解码／包内重算哈希 | 未执行；包内容沿用已绑定来源及保存回执 |
| 固定Core100 | v6条件与成员未改动 |
| 训练集同源组隔离 | 本轮未取得已完成排除的最终训练成员清单 |
| 仓库访问 | 私有；本轮未变更可见性 |
| 数据授权 | 保持现有other设置；本轮不变更授权 |

T01的Genesis 2,640条此前仅有跨仓库索引；当前归集在`data/T01/genesis/`，
Isaac媒体归集在`data/T01/isaac/`。每条未停用成员的下载路径均绑定归集后的固定提交。

本轮按固定版本检查了56,185个来源对象。56,127个直接视频的LFS哈希与登记一致；
四个“缺失”结果来自将完整URL误作仓库路径，实际文件存在于已固定的来源版本。
修正后对复制目的逐项验LFS哈希。归集过程不重新渲染，不修改视频内容或参考事件。

完整正式集合仍需完成待复核成员的画面与物理检查，处理停用成员对应的正式配额，
核定训练／测试来源组排除，并明确对外访问与使用条款。发布时按已完成范围报告数量。
'''
    assert '历史' not in report
    (dest/'PUBLICATION_CHECK.md').write_text(report,encoding='utf-8')
    (REPO/'docs/PUBLICATION_CHECK_20261029.md').write_text(report,encoding='utf-8')
    (OUT/'final_catalog_audit.json').write_text(json.dumps(summary,indent=2),encoding='utf-8')
    print(json.dumps(summary))


if __name__=='__main__':main()
