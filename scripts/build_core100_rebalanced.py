"""Prepare the author-requested 8-for-8 Core100 revision without rewriting live tasks."""
import copy
import hashlib
import json
from collections import Counter
from pathlib import Path

from physedit.core100_release import load as core_load
from physedit.critical_supplement import load as supplement_load,DEFAULT as SUPPLEMENT

ROOT=Path(__file__).resolve().parents[1]
VERSION='core100-critical-pairs-v2-20261101'
OUT=ROOT/'benchmarks/core100_critical_pairs_v2_20261101'
MAPPING={'T04_C01':'T04_S01','T04_C03':'T04_S02',
         'T05_C01':'T05_S01','T05_C03':'T05_S02',
         'T10_C01':'T10_S01','T10_C02':'T10_S02',
         'T11_C01':'T11_S01','T11_C02':'T11_S02'}

def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def write(path,data):path.write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding='utf8')

def main():
    if (OUT/'MANIFEST.json').exists():raise ValueError('sealed_release_exists_create_new_version')
    parent,old_manifest,old_conditions,_=core_load()
    sm,sc,sa=supplement_load();supp={r['point_id']:r for r in sc};truth={r['point_id']:r for r in sa['points']}
    OUT.mkdir(exist_ok=False)
    tasks=[];replacements=[];archived=[]
    for old in old_conditions['tasks']:
        cid=old['clip_id']
        if cid not in MAPPING:
            tasks.append(copy.deepcopy(old));continue
        point=MAPPING[cid];s=supp[point];key=truth[point]
        archived.append(copy.deepcopy(old))
        row=dict(clip_id=cid,sample_id=s['native_sample_id'],scene_id=s['scene_id'],
            source_video_sha256=s['reference_video_sha256'],reference=copy.deepcopy(s['reference_download']),
            condition_image=str((SUPPLEMENT/s['condition_image']).relative_to(ROOT)),
            condition_frame_index=4,condition_sha256=s['condition_image_sha256'],
            source_width=s['source_width'],source_height=s['source_height'],
            prompt_en=s['prompt_variants_en'][0],prompt_variants_en=s['prompt_variants_en'],
            prompt_variant_sha256=s['prompt_sha256'],prompt_policy=s['prompt_policy'],
            prompt_variant_token_counts=s['prompt_token_counts'],parameter_facts=s['parameter_facts'],
            verified_parameter_truth=dict(gravity=key['gravity'],**{s['family_id']:s['theta']}),
            clock=s['declared_schedule'],evaluation_duration_s=s['evaluation_duration_s'],
            source_group_id=s['source_group_id'],supplement_point_id=point,
            target_event=key['target_event'],reference_release_version=VERSION,
            inversion=key['inversion'],event_vector_scope=key['event_vector_scope'],
            new_generation_required=True,new_annotation_required=True,
            legacy_generated_outputs_reusable=False,legacy_annotations_reusable=False)
        row['reference']['sha256']=s['reference_video_sha256']
        tasks.append(row)
        replacements.append(dict(clip_id=cid,supplement_point_id=point,
            old_native_sample_id=old['sample_id'],old_reference_sha256=old['reference']['sha256'],
            new_native_sample_id=s['native_sample_id'],new_reference_sha256=s['reference_video_sha256'],
            reason=('replace_unresolved_original_context'if cid not in ['T04_C03','T05_C03']else
                'complete_opposite_pair_preserve_other_gravity_and_original_pair_coverage'),
            event=key['target_event'],label=key['events'][key['target_event']],
            family_id=s['family_id'],theta=s['theta'],distance=key['distance']))
    assert Counter(r['clip_id'][:3]for r in tasks)=={f'T{i:02}':5 for i in range(1,21)}
    assert len({r['sample_id']for r in tasks})==100
    assert all(a==b for a,b in zip(old_conditions['tasks'],tasks)if a['clip_id']not in MAPPING)
    write(OUT/'known_conditions.json',dict(version=VERSION,parent_version=old_manifest['version'],tasks=tasks))
    write(OUT/'replacement_map.json',replacements)
    write(OUT/'previous_eight_conditions.json',dict(parent_version=old_manifest['version'],tasks=archived))
    keys=[]
    for cid,point in MAPPING.items():
        key=copy.deepcopy(truth[point]);key['core100_clip_id']=cid;keys.append(key)
    write(OUT/'replacement_answers.json',dict(points=keys,pairs=sa['pairs']))
    old_registry=json.loads((ROOT/'annotation_site/resources/core100_distance_bindings.json').read_text(encoding='utf8'))
    # Preserve old source-specific references for 92 cases; never relabel a
    # numerical-only record as formal admission or a calibration as a root.
    retained=[copy.deepcopy(r)for r in old_registry['cases']if r['clip_id']not in MAPPING]
    write(OUT/'retained_distance_references.json',dict(cases=retained))
    manifest=dict(schema='core100-rebalanced-roster-v1',version=VERSION,
        registered_cases=100,scene_counts=dict(Counter(r['clip_id'][:3]for r in tasks)),
        retained=92,replaced=8,replacement_pairs=4,
        reference_selection_basis='source event contrast and dataset coverage; no generated-model scores used',
        model_generation_and_annotation_pending=list(MAPPING),
        legacy_tasks_outputs_annotations_modified=False,training_split_modified=False,
        parent_manifest=dict(path=str((parent/'MANIFEST.json').relative_to(ROOT)),sha256=sha(parent/'MANIFEST.json')),
        supplement_manifest=dict(path=str((SUPPLEMENT/'MANIFEST.json').relative_to(ROOT)),sha256=sha(SUPPLEMENT/'MANIFEST.json')),
        retained_reference_limits='Preserve original calibrations, numerical-only records and their admission limits.',
        new_reference_limits='Observed local contrast intervals; only T10 new pair is Near. Target-only events do not establish full EventExact; inversion pending.',
        files={p.name:sha(p)for p in OUT.iterdir()if p.is_file()})
    write(OUT/'MANIFEST.json',manifest)
    write(ROOT/'catalog/core100_critical_pairs_v2.json',dict(version=VERSION,
        release_root='../'+OUT.relative_to(ROOT).as_posix(),manifest='MANIFEST.json',manifest_sha256=sha(OUT/'MANIFEST.json'),
        status='prepared_new_100_case_roster; existing_live_tasks_preserved',
        unchanged_running_release='catalog/active_core100_conditions.json'))
    print(json.dumps(dict(version=VERSION,registered=100,retained=92,replaced=8,pairs=4)))

if __name__=='__main__':main()
