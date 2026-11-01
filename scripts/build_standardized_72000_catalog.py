"""Uniform scene entry points and canonical download names; preserve original identities."""
import collections
import gzip
import hashlib
import json
import shutil
from pathlib import Path

REPO=Path(__file__).resolve().parents[1]
ROOT=REPO.parent/'release_72000_active'
OUT=ROOT/'standardized_catalog_20261029'
STAGE=OUT/'metadata'
PREFIX='releases/72000_standardized_20261029'
PROMPT_REVISION='ced0cf6057a3281f19ea961d63132bffd2d81560'
TITLES={
 'T01':('Ramp, book, cans and mug','Controlled ramp and object spacing in a book, two-can and mug setup.'),
 'T02':('Striker, door and probe','Controlled striker motion and impact geometry in a door-and-probe setup.'),
 'T03':('Two-level object arrangement','Controlled initial motion and edge positions across two support levels.'),
 'T04':('Removable support and book stack','Controlled support withdrawal and material conditions in a supported stack.'),
 'T05':('Moving object and narrow passage','Controlled initial motion, opening width and object orientation.'),
 'T06':('Book domino arrangement','Controlled actuation and spacing of a row of upright books.'),
 'T07':('Phone on inclined support','Controlled friction, initial position and inclination of the support.'),
 'T08':('Offset impact arrangement','Controlled impactor motion, lateral offset and target properties.'),
 'T09':('Book withdrawal from a stack','Controlled withdrawal of a selected book and stack material conditions.'),
 'T10':('Tape roll, support and folder','Controlled roll motion and support configuration around a folder.'),
 'T11':('Object relay near an edge','Controlled actuation, inter-object gaps, masses and edge distances.'),
 'T12':('Stapler and tissue box','Controlled stapler initial motion and tissue-box material conditions.'),
 'T13':('Book, target and table edge','Version-specific initial motion and prescribed controls near a table edge.'),
 'T14':('Passage and launcher variants','Genesis T14 passage setup; Isaac T14S spring-launcher setup. Distinct native scenes.'),
 'T14S':('Spring launcher and hinged gate','Isaac T14S marker, eraser, ball and spring-return gate; occupies the Isaac T14 quota.'),
 'T15':('Book, laptop and phone','Controlled book initial motion and book-laptop-phone geometry near a table edge.'),
 'T16':('Side support and folder','Controlled support withdrawal and contact geometry around a supported folder.'),
 'T17':('Moving object and tissue box','Version-specific moving-object initial conditions, lateral alignment and target properties.'),
 'T18':('Book-stack extraction and sliding','Version-specific book counts, support geometry, friction and withdrawal controls.'),
 'T19':('Object impact arrangements','Version-specific object composition, initial motion, impact geometry, mass and restitution.'),
 'T20':('Book, can, box and cup','Controlled initial motion and gaps in a book-can-box-cup arrangement.'),
}


def dump(path,value):
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(value,ensure_ascii=False,indent=2),encoding='utf-8')


def write_rows(path,rows):
    path.parent.mkdir(parents=True,exist_ok=True)
    with gzip.open(path,'wt',encoding='utf-8') as f:
        for r in rows:f.write(json.dumps(r,ensure_ascii=False)+'\n')


def main():
    STAGE.mkdir(parents=True,exist_ok=True)
    groups=collections.defaultdict(list);rows=[];ids=set();names=set()
    with gzip.open(ROOT/'prompt_completion_20261029/videos.jsonl.gz','rt',encoding='utf-8') as f:
        for line in f:
            old=json.loads(line);r=dict(old);scene=r['scene'];engine=r['engine']
            digest=hashlib.sha256((engine+'\0'+scene+'\0'+r['native_sample_id']).encode()).hexdigest()[:16]
            trajectory=f'physedit_{engine}_{scene.lower()}_{digest}'
            video=trajectory+'__'+r['camera']
            canonical=f'data/{scene}/{engine}/{trajectory}/videos/{video}.mp4'
            assert video not in ids and canonical not in names;ids.add(video);names.add(canonical)
            r.update(canonical_trajectory_id=trajectory,canonical_video_id=video,
                canonical_filename=video+'.mp4',canonical_path=canonical,native_scene_id=scene,
                scene_title_en=TITLES[scene][0],scene_description_en=TITLES[scene][1],
                naming_schema='physedit-canonical-video-names-v1-20261029',
                canonical_path_storage='materialized_by_download_script; source archive members retained')
            assert all(r[k]==v for k,v in old.items())
            assert len(r['prompt_variants_en'])==3 and r['download'].get('revision')
            groups[r['quota_scene']].append(r);rows.append(r)
    assert len(rows)==72000 and all(len(groups[f'T{i:02d}'])==3600 for i in range(1,21))
    release=STAGE/PREFIX;release.mkdir(parents=True,exist_ok=True)
    write_rows(release/'videos.jsonl.gz',rows)
    summary=[]
    for scene,items in sorted(groups.items()):
        root=STAGE/'data'/scene;root.mkdir(parents=True,exist_ok=True)
        counts=collections.Counter(r['engine'] for r in items)
        native=collections.Counter(r['scene'] for r in items)
        quality=collections.Counter(r['quality_admission_status'] for r in items)
        title,description=TITLES[scene]
        index={'quota_scene_id':scene,'title_en':title,'description_en':description,
            'video_entries':len(items),'by_engine':dict(counts),'native_scene_counts':dict(native),
            'quality_states':dict(quality),'prompt_variants_per_video':3,
            'current_inventory':'videos.jsonl.gz','prompt_revision':PROMPT_REVISION,
            'naming_schema':'physedit-canonical-video-names-v1-20261029',
            'source_files_renamed':False,'historical_files_retained':True}
        dump(root/'INDEX.json',index);write_rows(root/'videos.jsonl.gz',items)
        for engine in sorted(counts):
            write_rows(root/f'videos_{engine}.jsonl.gz',[r for r in items if r['engine']==engine])
        text=f'''# {scene} — {title}

{description}

| Field | Current 72,000-entry release |
|---|---|
| Quota scene | {scene} |
| Video entries | {len(items):,} |
| Genesis | {counts['genesis']:,} |
| Isaac | {counts['isaac']:,} |
| English prompts | Three per video, bound by SHA-256 |
| Native scene IDs | {', '.join(f'{k}: {v:,}' for k,v in native.items())} |

Use [videos.jsonl.gz](videos.jsonl.gz) for this scene's complete current inventory,
or the separate [Genesis](videos_genesis.jsonl.gz) / [Isaac](videos_isaac.jsonl.gz)
indexes. Every row includes exact source revision, download file/member, video
SHA-256, three prompts, parameters and quality admission status.

Canonical filenames use `physedit_<engine>_<native_scene>_<trajectory_hash>__cam0N.mp4`.
`canonical_path` is the uniform materialized layout; `native_sample_id`, legacy IDs,
source filenames and archive members remain available in each row. Source media
is linked at fixed revisions rather than silently relabeled or overwritten.
See [dataset organization](../README.md) for the download tool and quality rules.

Different engines and scene versions are not automatically physical pairs.
Presence in this inventory does not imply quality acceptance; inspect
`quality_admission_status`. Historical files/subdirectories remain for provenance;
the indexes above define this release's selected entries.
'''
        if scene=='T14':text+='\nGenesis T14 remains the passage scene. Isaac T14S is a distinct spring-launcher\nscene assigned to the Isaac T14 quota. See [T14S](../T14S/README.md); do not\nreuse Genesis T14 event definitions or critical values for T14S.\n'
        if scene=='T19':text+='\nThe 1,830 previously retired Genesis entries retain their quality state pending\nvisual review. Their prompt availability does not reactivate them.\n'
        (root/'README.md').write_text(text,encoding='utf-8')
        summary.append(index)
    # Preserve native T14S identity as an explicit alias to its 960 selected records.
    t14s=[r for r in rows if r['scene']=='T14S'];root=STAGE/'data/T14S';root.mkdir(parents=True,exist_ok=True)
    write_rows(root/'videos.jsonl.gz',t14s)
    dump(root/'INDEX.json',{'native_scene_id':'T14S','quota_scene_id':'T14','engine':'isaac',
        'video_entries':len(t14s),'title_en':TITLES['T14S'][0],'description_en':TITLES['T14S'][1],
        'counted_once_in':'data/T14/videos.jsonl.gz','canonical_native_directory':'data/T14S/isaac'})
    (root/'README.md').write_text('''# T14S — Spring launcher and hinged gate

T14S is a distinct native scene, occupying the Isaac part of the T14 quota.
It has 960 selected videos and three English prompts per video.
Use [videos.jsonl.gz](videos.jsonl.gz) for the native T14S index and
[T14](../T14/README.md) for the combined quota overview. These are the same 960
records, counted once in the 72,000-entry release. Genesis T14 remains distinct.
Canonical video names retain `isaac_t14s`; no critical values or labels are shared
by renaming. Existing historical directories remain for provenance.
''',encoding='utf-8')
    table='\n'.join(f"| [{x['quota_scene_id']}]({x['quota_scene_id']}/README.md) | {x['title_en']} | 2,640 | 960 | 3,600 |" for x in summary)
    (STAGE/'data/README.md').write_text('''# PhysEdit — scene directory

The current catalog has 20 quota scenes, T01–T20, each with 2,640 Genesis and
960 Isaac entries (72,000 total). Native Isaac T14S replaces the Isaac T14 quota
and is also listed separately for identity/provenance; it is not an extra quota.

| Quota scene | Description | Genesis | Isaac | Total |
|---|---|---:|---:|---:|
'''+table+'''

Each scene uses the same README, INDEX.json and videos.jsonl.gz schema, plus
separate engine indexes. The full standardized catalog and executable download
tool are under [the current organized release](../releases/72000_standardized_20261029/README.md).

## Naming

`physedit_<engine>_<native_scene>_<trajectory_hash>__cam0N.mp4`

The hash is the first 16 hexadecimal characters of SHA-256 over engine, native
scene and original sample ID, separated by NUL. The source identity is retained.
All 72,000 canonical IDs and paths have been checked for collisions.
The download tool creates this uniform layout; historical source objects and
compressed archive members retain their original names and fixed revisions.

## Admission and prompts

All entries have three English prompt variants. Author acceptance: 1,953;
historical acceptance: 31,722; other pending: 36,495; retired T19: 1,830.
Text completion does not approve pending/retired video quality. Filter the
explicit quality state for the intended use. Core100 uses its frozen v6 prompts.
''',encoding='utf-8')
    dump(release/'scene_index.json',summary)
    validation={'video_entries':72000,'scene_quotas':20,'canonical_ids_unique':True,
        'canonical_paths_unique':True,'source_media_and_prompts_preserved':True,
        't20_entries':len(groups['T20']),'t14s_entries':len(t14s),'prompt_variants':216000,
        'quality_states':dict(collections.Counter(r['quality_admission_status'] for r in rows)),
        'manifest_sha256':hashlib.sha256((release/'videos.jsonl.gz').read_bytes()).hexdigest(),
        'source_prompt_revision':PROMPT_REVISION}
    dump(release/'validation.json',validation)
    (release/'README.md').write_text('''# PhysEdit — standardized 72,000-entry release

All 20 quota scenes now have consistent browse entries under [data](../../data/README.md),
including [T20](../../data/T20/README.md). Each uses the same title/description
schema and provides complete and per-engine indexes. Isaac T14S retains its
native identity within the T14 quota and is not counted twice.

Download `videos.jsonl.gz` for all 72,000 entries, 216,000 English prompt texts,
canonical names, source IDs, exact media revisions, archive members and SHA-256.
Canonical IDs/paths are unique. The existing video bytes, released prompt texts,
labels, Core100 v6 and old source versions are preserved. `validation.json`
records the checks. Original README documents, when present, are retained in
`previous_scene_readmes` at the pre-update fixed repository revision.

Canonical media layout:

```
data/<native_scene>/<engine>/<canonical_trajectory_id>/videos/<canonical_video_id>.mp4
```

Source media remains in original files/shards; `canonical_path` is materialized
by `download_standardized.py`. This is not a claim that every historical archive
member has been renamed. To download selected usable T20 videos with canonical
names and one metadata JSON per video:

```sh
pip install huggingface_hub
python download_standardized.py --manifest videos.jsonl.gz --scene T20 --admission usable --output ./PhysEdit
```

Authentication for private source repositories uses the normal Hugging Face
login/token. `--admission nonretired` includes pending review entries; `all`
also includes retired entries for diagnostic use. Every materialized video is
checked against its registered SHA-256 before admission to the output directory.
There are 1,953 author-accepted, 31,722 historically accepted, 36,495 pending and
1,830 retired entries. Prompt availability does not grant quality approval.
''',encoding='utf-8')
    shutil.copyfile(REPO/'scripts/download_standardized_72000.py',release/'download_standardized.py')
    print(json.dumps(validation))


if __name__=='__main__':main()
