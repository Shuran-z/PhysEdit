"""Audit submitted prompts without confusing exact identity with input changes.

This is a prompt-level audit, not reference/media or final scoring admission.
Only sentence order and the explicit 'material friction' wording are normalized.
No values, actor names, units, controls or timing are normalized or inferred.
"""
import collections
import csv
import hashlib
import io
import json
import re
from decimal import Decimal
from pathlib import Path

ROOT = Path('review/core100_admission_20261023')
OUT = Path('review/v6_prompt_compatibility_20261024')
MANIFEST = Path('review/formal3600_hf_20261023/formal_manifest.json')
PATCH31 = {f'{s}_C{i:02}' for s in ('T04','T06','T09','T11','T13','T16') for i in range(1,6)} | {'T18_C04'}
EXTRA_FACTS = {
    'Signal brass ball friction 0.008.': ('t02v2_signal_brass_ball.friction', '0.008'),
    'Lower phone restitution 0.02.': ('t03v5_lower_edge_phone.restitution', '0.02'),
    'Upper can restitution 0.02.': ('t03v5_upper_edge_can.restitution', '0.02'),
    'Guide friction 0.08.': ('guide_friction_coefficient', '0.08'),
    'Moving phone restitution 0.025.': ('t05v2_moving_phone.restitution', '0.025'),
    'Upper payload book friction 0.34.': ('t08_upper_payload_book.friction', '0.34'),
    'Lower impactor book restitution 0.04.': ('t08_lower_impactor_book.restitution', '0.04'),
}


def digest(data):
    return hashlib.sha256(data).hexdigest()


def clauses(text):
    return collections.Counter(re.split(r'(?<=\.)\s+(?=[A-Z])', text.replace(' material friction', ' friction')))


def write_csv(path, rows):
    stream = io.StringIO(newline='')
    writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
    writer.writeheader()
    for row in rows:
        writer.writerow({k: json.dumps(v, ensure_ascii=False) if isinstance(v, (dict,list)) else v for k,v in row.items()})
    path.write_text('\ufeff'+stream.getvalue(), encoding='utf-8')


def main():
    OUT.mkdir(exist_ok=True, parents=True)
    conditions = {c['clip_id']: c for c in json.loads((ROOT/'v6_known_conditions.json').read_text(encoding='utf-8'))['tasks']}
    tasks = json.loads(MANIFEST.read_text(encoding='utf-8'))['tasks']
    variants = []
    lookup = {}
    for clip, cond in conditions.items():
        facts = {k: Decimal(str(v)) for k,v,_ in cond['parameter_facts'] if type(v) in (int,float)}
        for variant in (1,2,3):
            own = [t for t in tasks if t['clip_id']==clip and int(t['prompt_variant'])==variant]
            submitted = {t['source']['generation_metadata']['prompt'] for t in own}
            assert len(submitted)==1, (clip,variant,'multiple submitted texts')
            old = submitted.pop()
            new = cond['prompt_variants_en'][variant-1]
            assert digest(new.encode())==cond['prompt_variant_sha256'][variant-1]
            added = sorted((clauses(new)-clauses(old)).elements())
            removed = sorted((clauses(old)-clauses(new)).elements())
            evidence = []
            if not added and not removed:
                status = 'retain_prompt_semantics'
            elif not added:
                status = 'historical_extra_parameters'
                for sentence in removed:
                    key, value = EXTRA_FACTS[sentence]
                    assert facts[key]==Decimal(value), (clip,sentence,'config contradiction')
                    assert key.replace('friction','material friction') in cond['omitted_parameter_keys'] or key in cond['omitted_parameter_keys']
                    evidence.append({'sentence':sentence,'original_fact_key':key,'value_verified':True,'v6_omits_fact':True})
            else:
                status = 'rerun_for_frozen_v6_inputs'
            row = dict(clip_id=clip,prompt_variant=variant,status=status,v5_to_v6_patch31=clip in PATCH31,
                       output_count=len(own),submitted_prompt_sha256=digest(old.encode()),expected_v6_prompt_sha256=digest(new.encode()),
                       exact_v6=old==new,missing_v6_sentences=added,extra_old_sentences=removed,extra_fact_evidence=evidence,
                       submitted_prompt=old,v6_prompt=new)
            variants.append(row)
            lookup[clip,variant] = row
    outputs=[]
    for t in tasks:
        r=lookup[t['clip_id'],int(t['prompt_variant'])]
        gm=t['source']['generation_metadata'];cond=conditions[t['clip_id']]
        # Identifier correspondence is not proof of the condition PNG bytes.
        source_path=cond['reference'].get('source_video_path',cond.get('source_video_path'))
        ref_stem=Path(source_path).stem if source_path else None
        source_id=gm['source_video_id']
        source_match=(source_id==ref_stem or source_id.endswith('__'+ref_stem)) if ref_stem else None
        outputs.append(dict(task_id=t['id'],clip_id=t['clip_id'],model=t['model'],seed=t['seed'],prompt_variant=t['prompt_variant'],
                            prompt_status=r['status'],v5_to_v6_patch31=r['v5_to_v6_patch31'],native_prompt_truncation=bool(gm.get('native_prompt_truncation')),
                            encoder_verification_pending=bool(gm.get('native_prompt_truncation')),source_id_matches_reference_stem=source_match,
                            condition_png_bytes_verified=False,video_sha256=t['video_sha256'],video_path=t['remote_media']['path'],
                            submitted_prompt_sha256=r['submitted_prompt_sha256'],expected_v6_prompt_sha256=r['expected_v6_prompt_sha256'],
                            missing_v6_sentences=r['missing_v6_sentences'],extra_old_sentences=r['extra_old_sentences']))
    cases=[]
    for clip in conditions:
        vv=[r for r in variants if r['clip_id']==clip]; statuses={r['status'] for r in vv}
        assert len(statuses)==1, (clip,statuses)
        cases.append(dict(clip_id=clip,status=statuses.pop(),outputs=sum(r['output_count'] for r in vv),v5_to_v6_patch31=clip in PATCH31,
                          missing_v6_sentences=vv[0]['missing_v6_sentences'],extra_old_sentences=vv[0]['extra_old_sentences']))
    summary=dict(cases=100,variants=len(variants),outputs=len(outputs),exact_v6_outputs=sum(r['exact_v6']*r['output_count'] for r in variants),
                 case_status_counts=dict(collections.Counter(r['status'] for r in cases)),output_status_counts=dict(collections.Counter(r['prompt_status'] for r in outputs)),
                 patch31_outputs=sum(r['v5_to_v6_patch31'] for r in outputs),
                 additional_rerun_outputs=sum(r['prompt_status']=='rerun_for_frozen_v6_inputs' and not r['v5_to_v6_patch31'] for r in outputs),
                 source_id_matches_reference_stem=sum(r['source_id_matches_reference_stem'] is True for r in outputs),
                 truncated_outputs=sum(r['native_prompt_truncation'] for r in outputs),
                 truncated_by_status=dict(collections.Counter(r['prompt_status'] for r in outputs if r['native_prompt_truncation'])))
    result=dict(schema='core100-prompt-semantic-audit-v1',summary=summary,
                limitations=['No automatic v6 formal admission or prompt hash relabeling. Exact v6 policy remains frozen.',
                             'Retain means no prompt-semantic reason for immediate regeneration; native encoder and reference admission remain independent.',
                             'Extra true parameters make the historical condition set different; they are not certified identical v6 inputs.',
                             'Condition PNG byte identity and native encoder tokens are not attested by metadata source IDs.'],
                source_hashes={'manifest':digest(MANIFEST.read_bytes()),'v6_known_conditions':digest((ROOT/'v6_known_conditions.json').read_bytes())},
                cases=cases,variants=variants)
    (OUT/'audit.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    write_csv(OUT/'cases100.csv',cases);write_csv(OUT/'variants300.csv',variants);write_csv(OUT/'outputs3600.csv',outputs)
    for status in summary['output_status_counts']:
        write_csv(OUT/(status+'.csv'),[r for r in outputs if r['prompt_status']==status])
    print(json.dumps(summary,ensure_ascii=False,indent=2))


if __name__=='__main__':
    main()
