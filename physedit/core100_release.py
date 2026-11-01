"""Read the active, hash-bound Core100 reference release and prepare its new runs.

python -m physedit.core100_release status
python -m physedit.core100_release prepare --model H3 --variant 1 --out NEW
"""
import argparse
import copy
import hashlib
import json
from pathlib import Path

ACTIVE = Path(__file__).resolve().parents[1]/'catalog/active_core100_conditions.json'


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def load(pointer=None):
    pointer = Path(pointer or ACTIVE)
    policy = json.loads(pointer.read_text(encoding='utf8'))
    root = (pointer.parent/policy['release_root']).resolve()
    manifest_path = root/policy['manifest']
    if digest(manifest_path) != policy['manifest_sha256']:
        raise ValueError('active_core100_manifest_changed')
    manifest = json.loads(manifest_path.read_text(encoding='utf8'))
    for name, expected in manifest['files'].items():
        path = (root/name).resolve()
        if not path.is_relative_to(root) or digest(path) != expected:
            raise ValueError('active_core100_file_changed:'+name)
    if manifest['version'] != policy['version']:
        raise ValueError('active_core100_version_mismatch')
    conditions = json.loads((root/'known_conditions.json').read_text(encoding='utf8'))
    rows = [json.loads(s) for s in (root/'assignments.jsonl').read_text(encoding='utf8').splitlines()]
    wanted = {f'T{i:02}_C{j:02}' for i in range(1,21) for j in range(1,6)}
    if len(rows) != 100 or {r['clip_id'] for r in rows} != wanted:
        raise ValueError('active_core100_roster_invalid')
    if len(conditions['tasks']) != 100 or {r['clip_id'] for r in conditions['tasks']} != wanted:
        raise ValueError('active_core100_conditions_invalid')
    for case in manifest['replacements']:
        condition = next(c for c in conditions['tasks'] if c['clip_id'] == case['clip_id'])
        if condition['reference']['sha256'] != case['video_sha256']:
            raise ValueError('active_core100_reference_mismatch')
        for text, expected in zip(condition['prompt_variants_en'], condition['prompt_variant_sha256']):
            if hashlib.sha256(text.encode()).hexdigest() != expected:
                raise ValueError('active_core100_prompt_changed')
    return root, manifest, conditions, rows


def status(tasks=(), pointer=None):
    path = Path(pointer or ACTIVE)
    if not path.exists():
        return dict(status='not_installed')
    root, manifest, conditions, rows = load(path)
    replacements = {r['clip_id']:r for r in manifest['replacements']}
    matching, historical = 0, 0
    for task in tasks:
        payload = task.get('payload', task)
        if payload.get('clip_id') not in replacements:
            continue
        case = replacements[payload['clip_id']]
        if (payload.get('reference_release_version') == manifest['version'] and
                payload.get('reference_video_sha256') == case['video_sha256'] and
                payload.get('condition_sha256') == case['condition_sha256']):
            matching += 1
        else:
            historical += 1
    answers = [json.loads(s) for s in (root/'answers_t19.jsonl').read_text(encoding='utf8').splitlines()]
    from .boundary import distance
    return dict(status='active', version=manifest['version'], registered_reference_cases=100,
                replaced_cases=5, unchanged_cases=95, new_generation_variants=15,
                bound_distances=[dict(clip_id=r['point_id'],theta=r['theta'],
                    boundary=r['boundary'],distance=distance(r)) for r in answers],
                near_reference_cases=sum(distance(r)['bin']=='near' for r in answers),
                registered_cross_boundary_pairs=len(manifest['pairs']),
                matching_generated_records=matching,historical_T19_records_not_relabelled=historical,
                model_scores_computed=False, old_reference_records_preserved=True)


def prepare(out, model, variant=1, seed=0, pointer=None, pairing_mode='coupled_seed'):
    if variant not in (1,2,3) or type(seed) is not int:
        raise ValueError('invalid_variant_or_seed')
    if pairing_mode not in ('coupled_seed','independent'):
        raise ValueError('invalid_pairing_mode')
    root, manifest, conditions, rows = load(pointer)
    out = Path(out).resolve()
    out.mkdir(parents=True, exist_ok=False)
    answers = [json.loads(s) for s in (root/'answers_t19.jsonl').read_text(encoding='utf8').splitlines()]
    inputs, keys = [], []
    for case, answer in zip(manifest['replacements'],answers):
        cid = case['clip_id']
        assert cid == answer['point_id']
        condition = next(c for c in conditions['tasks'] if c['clip_id']==cid)
        point_seed = (seed + 1000003*answer['events'][answer['target_event']]
                      if pairing_mode=='independent' else seed)
        sid = 'core100_t19_v1_'+cid+f'_p{variant}_s{point_seed}'
        key = copy.deepcopy(answer)
        key.update(sample_id=sid,pairing_mode=pairing_mode)
        key['boundary'].update(source=str(root/'source_evidence.json'),
                               source_sha256=digest(root/'source_evidence.json'))
        keys.append(key)
        inputs.append(dict(sample_id=sid,clip_id=cid,reference_release_version=manifest['version'],
            source_video=str(root/case['reference_video']),source_video_sha256=case['video_sha256'],
            condition_image=str(root/case['condition_image']),condition_sha256=case['condition_sha256'],
            condition_frame_index=0,prompt=condition['prompt_variants_en'][variant-1],
            prompt_sha256=condition['prompt_variant_sha256'][variant-1],prompt_variant=variant,
            seed=point_seed,num_frames=210,fps=30.,source_native_fps=30.,source_width=case['width'],
            source_height=case['height'],evaluation_duration_s=209/30.,
            known_conditions=condition))
    for name, data in [('inputs.jsonl',inputs),('answers.jsonl',keys)]:
        (out/name).write_text(''.join(json.dumps(r,ensure_ascii=False)+'\n' for r in data),encoding='utf8')
    spec = dict(model=model,inputs=str(out/'inputs.jsonl'),answers=str(out/'answers.jsonl'),
                reference_release_version=manifest['version'],pairing_mode=pairing_mode)
    from .boundary import plan
    receipt = plan(spec)
    (out/'spec.json').write_text(json.dumps(spec,indent=2),encoding='utf8')
    (out/'plan.json').write_text(json.dumps(receipt,indent=2),encoding='utf8')
    return receipt


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action',choices=['status','prepare'])
    parser.add_argument('--pointer')
    parser.add_argument('--out')
    parser.add_argument('--model')
    parser.add_argument('--variant',type=int,default=1)
    parser.add_argument('--seed',type=int,default=0)
    parser.add_argument('--pairing-mode',choices=['coupled_seed','independent'],default='coupled_seed')
    args = parser.parse_args()
    if args.action == 'prepare' and not (args.out and args.model):
        parser.error('prepare requires --out and --model')
    value = status(pointer=args.pointer) if args.action=='status' else prepare(args.out,args.model,args.variant,args.seed,args.pointer,args.pairing_mode)
    print(json.dumps(value,ensure_ascii=False,indent=2))


if __name__ == '__main__':
    main()
