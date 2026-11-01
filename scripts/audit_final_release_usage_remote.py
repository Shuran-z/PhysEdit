"""Independent read-only final catalog/prompt/config/split audit (p25)."""
import collections
import csv
import gzip
import hashlib
import json
from pathlib import Path
import zipfile
import pyarrow.parquet as pq

R = Path('/data_cached/wangzijun_p25/t19_final_release_20261030')
D = R/'stage/releases/physedit'
OUT = R/'usage_audit'


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=False).encode()).hexdigest()


def loadrows(path):
    with gzip.open(path, 'rt', encoding='utf8') as f:
        for line in f:
            if line.strip():
                yield json.loads(line)


def main():
    OUT.mkdir(exist_ok=True)
    plan = json.loads((R/'PLAN.json').read_text())
    deleted = {r['path'] for r in plan['delete']}
    texts = {r['sha256']:r['prompt'] for r in loadrows(D/'prompts/prompt_texts.jsonl.gz')}
    assert all(hashlib.sha256(t.encode()).hexdigest() == h for h,t in texts.items())
    sourcezip = zipfile.ZipFile(D/'provenance/t19_gen_new_20261030/source_metadata.zip')
    bindings = [json.loads(s) for s in (D/'provenance/t19_gen_new_20261030/SOURCE_BINDINGS.jsonl').read_text().splitlines()]
    assert len(bindings) == 880
    configs = {}
    sources = {}
    for binding in bindings:
        key = binding['group']+'/'+binding['sample_id']
        raw = sourcezip.read('physics/'+key+'/config.json')
        assert hashlib.sha256(raw).hexdigest() == binding['source_config_sha256']
        config = json.loads(raw)
        assert config == binding['physical_inputs']
        trajectory_raw = sourcezip.read('physics/'+key+'/trajectory.json')
        assert hashlib.sha256(trajectory_raw).hexdigest() == binding['trajectory_sha256']
        trajectory = json.loads(trajectory_raw)
        meta_raw = sourcezip.read('metadata/'+binding['scene']+'/'+key+'.json')
        assert hashlib.sha256(meta_raw).hexdigest() == binding['metadata_sha256']
        metadata = json.loads(meta_raw)
        assert metadata['trajectory_sha256'] == binding['trajectory_sha256']
        configs[key] = config
        for video in binding['videos']:
            assert video['repo_path'] not in sources
            sources[video['repo_path']] = (binding, config, trajectory, video)
    assert len(configs) == 220 and len(sources) == 2640
    sources_by_sha = {value[3]['sha256']:value for value in sources.values()}
    assert len(sources_by_sha) == 2640
    # Retain compact expected projections, not all large original records.
    index = {}
    bylegacy = {}
    splits = collections.Counter()
    scenes = collections.Counter()
    groups = collections.defaultdict(set)
    train_groups = set()
    holdout_groups = set()
    train_hashes = set()
    holdout_hashes = set()
    new_count = 0
    for row in loadrows(D/'catalog/videos.jsonl.gz'):
        cid = row['canonical_video_id']
        assert cid not in index
        for text,h in zip(row['prompt_variants_en'], row['prompt_variant_sha256']):
            assert texts[h] == text and hashlib.sha256(text.encode()).hexdigest() == h
        assert len(row['prompt_variants_en']) == 3 and row['prompt_en'] == row['prompt_variants_en'][0]
        for field in ('download', 'source_download'):
            binding = row.get(field) or {}
            assert binding.get('path') not in deleted
        split = row['split']
        splits[split] += 1
        scenes[row['engine'],row['quota_scene']] += 1
        groups[row['canonical_trajectory_id']].add((row['camera'],split))
        (train_groups if split == 'train_final' else holdout_groups).add(row['source_group_id'])
        (train_hashes if split == 'train_final' else holdout_hashes).add(row['sha256'])
        if split == 'train_final':
            assert row['quota_scene'] not in ('T03','T20','T11','T19')
            assert row['training_ready']
        if row['engine'] == 'genesis' and row['quota_scene'] == 'T19':
            new_count += 1
            binding,config,trajectory,video = sources_by_sha[row['sha256']]
            assert row['sha256'] == video['sha256']
            assert row['physical_inputs']['config'] == config
            assert row['physical_inputs']['specifications'] == trajectory['specifications']
            assert row['physical_inputs']['actual_masses_kg'] == trajectory['actual_masses_kg']
            evidence = row['prompt_binding_evidence']
            assert evidence['source_config_sha256'] == binding['source_config_sha256']
            assert evidence['trajectory_sha256'] == binding['trajectory_sha256']
            assert evidence['render_metadata_sha256'] == binding['metadata_sha256']
            assert row['external_control_inputs']['time_s'] == config['common']['action_start_s']
            assert row['external_control_inputs']['no_subsequent_external_drive'] is True
            assert row['gravity_vector_mps2'] == config['common']['physics']['gravity']
            facts = {k:v for k,v,u in row['parameter_facts']}
            assert facts['gravity'] == config['common']['physics']['gravity']
            assert facts['striker.initial_speed'] == config['experiment']['speed_m_s']
            assert facts['table_friction'] == trajectory['table_friction']
            assert split == 'ood_holdout' and not row['training_ready']
        index[cid] = dict(sha256=row['sha256'], prompts=row['prompt_variant_sha256'],
            parameters=digest(row['parameter_facts']), controls=digest(row.get('external_control_inputs')),
            group=row['source_group_id'], split=split, scene=row['quota_scene'], engine=row['engine'],
            camera=row['camera'], trajectory=row['canonical_trajectory_id'], download=row['download'])
        bylegacy[row['video_id']] = cid
    assert len(index) == 72000 and new_count == 2640
    assert not train_groups & holdout_groups and not train_hashes & holdout_hashes
    assert len(groups) == 24000
    assert all({c for c,s in entries} == {'cam01','cam02','cam03'} and len({s for c,s in entries}) == 1 for entries in groups.values())
    bound = set()
    for binding in loadrows(D/'prompts/video_prompt_bindings.jsonl.gz'):
        cid = binding['video_id']
        row = index[cid]
        assert binding['video_sha256'] == row['sha256'] and binding['prompt_sha256'] == row['prompts']
        assert binding['download'] == row['download']
        bound.add(cid)
    assert bound == set(index)
    csv_ids = set()
    with (D/'catalog/split_assignments.csv').open(encoding='utf-8-sig') as f:
        for row in csv.DictReader(f):
            expected = index[row['canonical_video_id']]
            assert all(row[k] == expected[k] for k in ['split','sha256'])
            assert row['source_group_id'] == expected['group']
            if row.get('protected_member_ids'):
                assert row['split'] != 'train_final'
            csv_ids.add(row['canonical_video_id'])
    assert csv_ids == set(index)
    parquet_counts = {}
    for path in (D/'catalog/parquet').glob('*.parquet'):
        count = 0
        for batch in pq.ParquetFile(path).iter_batches(batch_size=1000):
            for row in batch.to_pylist():
                expected = index[row['video_id']]
                assert row['video_sha256'] == expected['sha256']
                assert [hashlib.sha256(row[f'prompt_{i}'].encode()).hexdigest() for i in (1,2,3)] == expected['prompts']
                assert digest(json.loads(row['physical_parameters_json'])) == expected['parameters']
                assert digest(json.loads(row['external_controls_json'])) == expected['controls'], (row['video_id'], 'external_controls_projection', row['external_controls_json'][:100])
                assert row['source_group_id'] == expected['group']
                assert row['media_path'] == expected['download']['path']
                assert row['media_revision'] == expected['download']['revision']
                count += 1
        parquet_counts[path.name] = count
    train_ids = set()
    for row in loadrows(D/'catalog/train_final.jsonl.gz'):
        cid = bylegacy[row['video_id']]
        assert row['sha256'] == index[cid]['sha256']
        assert row['download'] == index[cid]['download']
        assert row['prompt_variant_sha256'] == index[cid]['prompts']
        train_ids.add(cid)
    assert train_ids == {k for k,r in index.items() if r['split'] == 'train_final'}
    unique_rows = list(loadrows(D/'catalog/train_unique_declared_triplets.jsonl.gz'))
    unique_ids = {r['canonical_video_id'] for r in unique_rows}
    for row in unique_rows:
        assert row['sha256'] == index[row['canonical_video_id']]['sha256']
        assert row['download'] == index[row['canonical_video_id']]['download']
        assert row['prompt_variant_sha256'] == index[row['canonical_video_id']]['prompts']
    assert len(unique_ids) == 42207 and unique_ids <= train_ids
    assert {r['quota_scene'] for r in unique_rows} == {f'T{i:02}' for i in range(1,21)}-{'T03','T20','T11','T19'}
    result = dict(status='PASS', video_records=len(index), prompt_bindings=3*len(bound),
        prompt_pool_texts_hash_verified=len(texts), genesis_t19_records_verified=new_count,
        t19_source_binding_cases=880, t19_unique_original_configs=220,
        t19_raw_config_trajectory_and_metadata_hashes_verified=True,
        train_holdout_sha256_overlap=0,train_holdout_source_group_overlap=0,
        complete_three_view_groups=len(groups), split_counts=dict(splits),
        original_train_records=len(train_ids), recommended_train_records=len(unique_ids),
        parquet_counts=parquet_counts, deleted_object_references_in_active_catalog=0,
        no_new_thresholds_or_event_truths_added=True)
    (OUT/'AUDIT.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(result),flush=True)


if __name__ == '__main__':
    main()
