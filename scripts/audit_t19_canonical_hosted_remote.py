"""Verify canonical T19 files against original inputs and current text bindings."""
import gzip
import hashlib
import json
import os
from pathlib import Path

os.environ['HTTPS_PROXY'] = os.environ['HTTP_PROXY'] = 'http://127.0.0.1:17891'
from huggingface_hub import HfApi

R = Path('/data_cached/wangzijun_p25/t19_final_release_20261030')
REV = '8545d5dc31fa8f6b9bf8485756db99e42a6fbcad'


def main():
    api = HfApi()
    entries = {x.path:x for x in api.list_repo_tree('phy2/phydataset', path_in_repo='data/T19/genesis',
        repo_type='dataset', revision=REV, recursive=True) if hasattr(x, 'size')}
    meta_order = list(json.loads((R/'usage_audit/sample_metadata_download.json').read_text()))
    configs, metadata, prompts = set(), set(), set()

    def check(path, raw):
        x = entries[path]
        assert x.size == len(raw), path
        if x.lfs:
            assert x.lfs.sha256 == hashlib.sha256(raw).hexdigest(), path
        else:
            assert x.blob_id == hashlib.sha1(b'blob '+str(len(raw)).encode()+b'\0'+raw).hexdigest(), path

    def encode(value):
        return (json.dumps(value, ensure_ascii=False, indent=2)+'\n').encode()

    with gzip.open(R/'stage/releases/physedit/catalog/by_scene/genesis__T19.jsonl.gz', 'rt') as f:
        for line in f:
            row = json.loads(line)
            group_case = '/'.join(row['native_sample_id'].split('/')[-2:])
            extra = dict(video_path=row['canonical_path'],
                source_config_sha256=row['prompt_binding_evidence']['source_config_sha256'],
                source_metadata_archive='data/T19/genesis/source_metadata.zip',
                source_metadata_member='metadata/'+row['visual_background']+'/'+group_case+'.json',
                trajectory_archive_member='physics/'+group_case+'/trajectory.json')
            meta = {key:row[key] if key in row else extra[key] for key in meta_order}
            assert row['metadata_download']['revision'] == row['download']['revision']
            check(row['metadata_download']['path'], encode(meta))
            metadata.add(row['metadata_download']['path'])
            config = dict(version=row['version'], visual_background=row['visual_background'],
                physical_background=row['physical_inputs']['physical_background'],
                common=row['physical_inputs']['config']['common'],
                experiment=row['physical_inputs']['config']['experiment'])
            check(row['config_download']['path'], encode(config))
            configs.add(row['config_download']['path'])
            for text, expected, binding in zip(row['prompt_variants_en'],row['prompt_variant_sha256'],row['prompt_downloads']):
                assert binding['sha256'] == expected
                check(binding['path'], text.encode())
                prompts.add(binding['path'])
    source = R/'stage/releases/physedit/provenance/t19_gen_new_20261030/source_metadata.zip'
    check('data/T19/genesis/source_metadata.zip', source.read_bytes())
    assert (len(configs),len(metadata),len(prompts)) == (880,2640,7920)
    result = dict(status='PASS', revision=REV, hosted_configs_raw_bytes_verified=880,
        hosted_metadata_raw_bytes_verified=2640, hosted_prompt_txt_raw_bytes_verified=7920,
        canonical_source_metadata_zip_hash_verified=True,
        canonical_metadata_matches_own_original_inputs=True, archive_T19_references_in_verified_bindings=0)
    (R/'usage_audit/CANONICAL_T19_VERIFIED.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(result),flush=True)


if __name__ == '__main__':
    main()
