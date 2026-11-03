"""Separate published boundary pilot; never change or merge Core100 inputs."""
import argparse
import copy
import hashlib
import json
import math
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
ACTIVE=ROOT/'catalog/active_critical_supplement.json'
DEFAULT=((ACTIVE.parent/json.loads(ACTIVE.read_text(encoding='utf8'))['release_root']).resolve()
    if ACTIVE.exists()else ROOT/'benchmarks/critical_supplement_v1_20261101')


def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def load(release=DEFAULT):
    release=Path(release).resolve();manifest=json.loads((release/'MANIFEST.json').read_text(encoding='utf8'))
    if ACTIVE.exists():
        active=json.loads(ACTIVE.read_text(encoding='utf8'))
        if (ACTIVE.parent/active['release_root']).resolve()==release and sha(release/active['manifest'])!=active['manifest_sha256']:
            raise ValueError('supplement_active_manifest_changed')
    for name,digest in manifest['files'].items():
        path=(release/name).resolve()
        if not path.is_relative_to(release)or sha(path)!=digest:raise ValueError('supplement_file_changed:'+name)
    for name,digest in manifest['core100_preserved'].items():
        path=(ROOT/name).resolve()
        if not path.is_relative_to(ROOT)or sha(path)!=digest:raise ValueError('frozen_core100_changed')
    conditions=json.loads((release/'conditions.json').read_text(encoding='utf8'))['tasks']
    truth=json.loads((release/'answers.json').read_text(encoding='utf8'))
    inputs={r['point_id']:r for r in conditions};answers={r['point_id']:r for r in truth['points']}
    if len(inputs)!=len(conditions)or set(inputs)!=set(answers):raise ValueError('supplement_roster_mismatch')
    from .core100_release import load as load_core
    core_samples={r['sample_id']for r in load_core()[2]['tasks']}
    for cid,row in inputs.items():
        if row['native_sample_id']in core_samples:raise ValueError('frozen_core100_reference_reused')
        if row['reference_video_sha256']!=answers[cid]['reference_video_sha256']:raise ValueError('supplement_source_identity_changed')
        if row['theta']!=answers[cid]['theta']:raise ValueError('supplement_parameter_changed')
        if sha(release/row['condition_image'])!=row['condition_image_sha256']:raise ValueError('supplement_condition_changed')
    for pair in truth['pairs']:
        own=[answers[c]for c in pair['points']]
        if len(own)!=2 or own[0]['events'][own[0]['target_event']]==own[1]['events'][own[1]['target_event']]:
            raise ValueError('supplement_pair_not_opposite')
        for name in ['source_group_id','family_id','fixed_context_sha256','evaluation_duration_s']:
            if own[0][name]!=own[1][name]:raise ValueError('supplement_pair_context_changed')
    return manifest,conditions,truth


def export(release,out,model,*,fps,variant=1,seeds=(0,)):
    """Export only first-frame images and declared prompts to the runner."""
    release=Path(release).resolve();manifest,conditions,truth=load(release)
    if not math.isfinite(fps)or fps<=0 or variant not in [1,2,3]:raise ValueError('invalid_supplement_generation_clock_or_variant')
    if len(set(seeds))!=len(seeds)or any(type(s)is not int or s<0 or s>=100000 for s in seeds):
        raise ValueError('supplement_seed_offsets_must_be_unique_in_0_to_99999')
    by_id={a['point_id']:a for a in truth['points']};rows=[];answers=[]
    if any(k['reference_admission']['status']!='admitted'for k in by_id.values()):
        raise ValueError('supplement_reference_admission_pending')
    out=Path(out).resolve();out.mkdir(parents=True,exist_ok=False)
    for index,row in enumerate(conditions):
        key=by_id[row['point_id']]
        if key['reference_admission']['status']!='admitted':raise ValueError('supplement_reference_admission_pending')
        for base_seed in seeds:
            seed=base_seed+100000*index
            sample=row['point_id']+'_v'+str(variant)+'_s'+str(seed)
            frames=4*math.ceil(row['evaluation_duration_s']*fps/4)+1
            rows.append(dict(sample_id=sample,point_id=row['point_id'],seed=seed,fps=fps,num_frames=frames,
                evaluation_duration_s=row['evaluation_duration_s'],
                prompt=row['prompt_variants_en'][variant-1],prompt_variant=variant,
                prompt_sha256=row['prompt_sha256'][variant-1],
                condition_image=str(release/row['condition_image']),condition_image_sha256=row['condition_image_sha256'],
                condition_sha256=row['condition_image_sha256'],source_width=row['source_width'],source_height=row['source_height'],
                input_release=manifest['version']))
            answers.append(dict(copy.deepcopy(key),sample_id=sample))
    def write_rows(name,data):
        (out/name).write_text(''.join(json.dumps(r,ensure_ascii=False)+'\n'for r in data),encoding='utf8')
    write_rows('inputs.jsonl',rows);write_rows('answers.jsonl',answers)
    spec=dict(model=model,inputs=str(out/'inputs.jsonl'),answers=str(out/'answers.jsonl'),
        input_release=manifest['version'],input_release_manifest_sha256=sha(release/'MANIFEST.json'),
        EventExact_applicable=False,reference_source_scope='published_local_intervals',
        actual_model_frames_and_native_fps_must_be_supported=True)
    (out/'spec.json').write_text(json.dumps(spec,indent=2),encoding='utf8')
    from .boundary import plan
    result=plan(spec)
    (out/'PRECHECK.json').write_text(json.dumps(result,indent=2),encoding='utf8')
    return result


def score(run_dir,*,release=DEFAULT,**kwargs):
    manifest,conditions,truth=load(release);by_id={r['point_id']:r for r in conditions}
    inputs=[json.loads(s)for s in (Path(run_dir)/'inputs.jsonl').read_text(encoding='utf8').splitlines()if s.strip()]
    if not inputs or {r.get('point_id')for r in inputs}!=set(by_id):
        raise ValueError('supplement_run_roster_changed')
    registered={r['point_id']:r for r in truth['points']}
    keys=[json.loads(s)for s in (Path(run_dir)/'answers.jsonl').read_text(encoding='utf8').splitlines()if s.strip()]
    expected_keys={r['sample_id']:dict(copy.deepcopy(registered[r['point_id']]),sample_id=r['sample_id'])for r in inputs}
    roster_version=None
    if any('core100_roster_release'in r for r in inputs):
        from .core100_rebalanced import load as load_roster
        _,roster,_,mapping=load_roster()
        mapping={r['supplement_point_id']:r['clip_id']for r in mapping}
        roster_version=roster['version']
        for row in inputs:
            if row.get('core100_roster_release')!=roster_version or row.get('clip_id')!=mapping.get(row['point_id']):
                raise ValueError('rebalanced_roster_binding_changed')
            expected_keys[row['sample_id']].update(clip_id=row['clip_id'],core100_roster_release=roster_version)
    if len(keys)!=len(inputs)or {r['sample_id']:r for r in keys}!=expected_keys:
        raise ValueError('supplement_reference_answers_changed')
    for row in inputs:
        ref=by_id.get(row.get('point_id'));variant=row.get('prompt_variant',0)
        if not ref or row.get('input_release')!=manifest['version']or variant not in [1,2,3]:
            raise ValueError('supplement_run_input_scope_changed')
        if row['prompt']!=ref['prompt_variants_en'][variant-1]or row['condition_image_sha256']!=ref['condition_image_sha256']:
            raise ValueError('supplement_run_input_changed')
        if row.get('evaluation_duration_s')!=ref['evaluation_duration_s']:
            raise ValueError('supplement_observation_window_changed')
    from .boundary import score as boundary_score
    result=boundary_score(run_dir,**kwargs)
    # This pilot registers target events, not the complete causal-chain vector.
    result['target_vector_match_diagnostic']=result.pop('event_exact')
    result['event_exact']=None;result['EventExact_applicable']=False
    result['event_measurement']['target_vector_match_diagnostic']=result['event_measurement'].pop('conditional_event_exact')
    for family in result['families']:
        family['target_vector_match_diagnostic']=family.pop('event_exact');family['event_exact']=None
    for row in result['rows']:
        row['target_vector_match_diagnostic']=row.pop('event_exact');row['event_exact']=None
    result['evaluation_scope']='critical_supplement_v1; separate from Core100'
    if roster_version:
        result['core100_roster_release']=roster_version
        result['evaluation_scope']='eight replacement cases within revised Core100; not the complete 100-case score'
    return result


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--release',type=Path,default=DEFAULT)
    sub=parser.add_subparsers(dest='command',required=True);sub.add_parser('status')
    p=sub.add_parser('export');p.add_argument('--out',type=Path,required=True);p.add_argument('--model',required=True)
    p.add_argument('--fps',type=float,required=True);p.add_argument('--variant',type=int,default=1)
    p.add_argument('--seeds',nargs='+',type=int,default=[0])
    p=sub.add_parser('score');p.add_argument('--run-dir',type=Path,required=True);p.add_argument('--annotations',type=Path)
    p.add_argument('--screening',type=Path);p.add_argument('--gravity',type=Path);p.add_argument('--out',type=Path,required=True)
    args=parser.parse_args()
    if args.command=='status':
        manifest,_,_=load(args.release);print(json.dumps(manifest['summary']))
    elif args.command=='export':print(json.dumps(export(args.release,args.out,args.model,fps=args.fps,variant=args.variant,seeds=args.seeds)))
    else:
        result=score(args.run_dir,release=args.release,annotations=args.annotations,screening=args.screening,gravity=args.gravity)
        with args.out.open('x',encoding='utf8')as handle:json.dump(result,handle,indent=2)
        print(json.dumps({k:v for k,v in result.items()if k not in ['rows','families']}))


if __name__=='__main__':main()
