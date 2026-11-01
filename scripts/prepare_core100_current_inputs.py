"""Export the 95 actual frozen inputs plus the 5 active Isaac T19 inputs."""
import argparse
import copy
import hashlib
import json
from pathlib import Path, PurePosixPath
import tempfile

from huggingface_hub import HfApi, hf_hub_download

REPO = 'phy2/phydataset'
REVISION = 'v1.0.2'


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--package', type=Path, default=Path(__file__).resolve().parents[1])
    p.add_argument('--output', required=True, type=Path)
    p.add_argument('--revision', default=REVISION)
    args = p.parse_args()
    output = args.output.resolve()
    if output.exists():
        raise SystemExit('Choose a new output directory: '+str(output))
    revision = HfApi().repo_info(REPO, repo_type='dataset', revision=args.revision).sha

    def fetch(name, expected=None):
        raw = Path(hf_hub_download(REPO, filename=name, repo_type='dataset', revision=revision)).read_bytes()
        if expected and hashlib.sha256(raw).hexdigest() != expected:
            raise ValueError('Source hash mismatch: '+name)
        return raw

    pointer = json.loads(fetch('catalog/active_core100_conditions.json'))
    manifest_path = pointer['release_manifest_path']
    prefix = str(PurePosixPath(manifest_path).parent)
    manifest = json.loads(fetch(manifest_path, pointer['manifest_sha256']))
    current = json.loads(fetch(pointer['known_conditions'], pointer['known_conditions_sha256']))
    conditions = {r['clip_id']:r for r in current['tasks']}
    replacements = {r['clip_id']:r for r in manifest['replacements']}
    assert set(replacements) == {f'T19_C{i:02}' for i in range(1,6)}
    source = args.package/'core100'
    inputs = json.loads((source/'inputs.json').read_text(encoding='utf8'))['tasks']
    assert len(inputs) == 100
    output.parent.mkdir(parents=True, exist_ok=True)
    exported = []
    with tempfile.TemporaryDirectory(prefix='.core100_inputs_', dir=output.parent) as temp:
        stage = Path(temp)
        for original in inputs:
            cid = original['clip_id']
            if cid in replacements:
                r = replacements[cid]
                condition = conditions[cid]
                raw = fetch(prefix+'/'+r['condition_image'], r['condition_sha256'])
                row = dict(clip_id=cid, scene='T19', split=original['split'],
                    physical_parameters_json=json.dumps(condition['parameter_facts'], ensure_ascii=False),
                    condition_source_repo=REPO, condition_source_revision=revision,
                    reference_release_version=pointer['version'],
                    reference_video_path=prefix+'/'+r['reference_video'], reference_video_sha256=r['video_sha256'])
                texts = condition['prompt_variants_en']
                hashes = condition['prompt_variant_sha256']
                expected_image = r['condition_sha256']
            else:
                row = copy.deepcopy(original)
                raw = (source/'conditions'/(cid+'.png')).read_bytes()
                texts = [row[f'prompt_{i}'] for i in (1,2,3)]
                hashes = row['prompt_sha256']
                expected_image = row['condition_image_sha256']
            assert hashlib.sha256(raw).hexdigest() == expected_image
            image_path = stage/'conditions'/(cid+'.png')
            image_path.parent.mkdir(exist_ok=True)
            image_path.write_bytes(raw)
            row.update(condition_image_path='conditions/'+cid+'.png',
                       condition_image_sha256=expected_image, prompt_sha256=hashes)
            for i,(text,h) in enumerate(zip(texts,hashes),1):
                assert hashlib.sha256(text.encode()).hexdigest() == h
                row[f'prompt_{i}'] = text
                prompt = stage/'prompts'/(cid+f'__p{i:02}.txt')
                prompt.parent.mkdir(exist_ok=True)
                prompt.write_bytes(text.encode())
            exported.append(row)
        receipt = dict(tasks=100, unchanged_actual_inputs=95, active_isaac_t19_inputs=5,
            conditions=100, prompt_files=300, all_exported_hashes_verified=True,
            resolved_revision=revision, active_reference_version=pointer['version'],
            historical_scores_or_annotations_modified=False)
        (stage/'inputs.json').write_text(json.dumps(dict(tasks=exported),ensure_ascii=False,indent=2)+'\n',encoding='utf8')
        (stage/'RECEIPT.json').write_text(json.dumps(receipt,indent=2)+'\n',encoding='utf8')
        stage.rename(output)
    print(json.dumps(receipt))


if __name__ == '__main__':
    main()
