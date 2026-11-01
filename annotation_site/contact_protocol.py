"""Author-approved new contact targets and conservative legacy-label migration.

This is a separate contact diagnostic, not a NearAcc/PairAcc score package.
"""
import collections
import hashlib
import json
from pathlib import Path
from workflow import final_annotation
from input_contract import matches_frozen_input

RES = Path(__file__).parent/'resources'
SEMANTIC_FIELDS = ('definition', 'actors', 'minimum_evidence_times', 'time_semantics', 'applicable')


def calculate(tasks):
    definition = RES/'core100_contact_protocol_20261027.json'
    truth = RES/'core100_contact_reference_truth_20261027.json'
    if not definition.exists() or not truth.exists():
        return {'status':'not_registered', 'summary':{}, 'outputs':[], 'per_model':[]}
    catalog = json.loads(definition.read_text(encoding='utf-8'))
    reference = json.loads(truth.read_text(encoding='utf-8'))
    if reference['definition_sha256'] != hashlib.sha256(definition.read_bytes()).hexdigest():
        raise ValueError('new contact truth belongs to a different frozen definition')
    refs = {r['clip_id']:r for r in reference['references']}
    inputs = json.loads((RES/'core100_v6_prompt_contract.json').read_text(encoding='utf-8'))['tasks']
    actual_policy = json.loads((RES/'core100_final_input_policy.json').read_text(encoding='utf-8'))
    outputs = []
    for task in tasks:
        p = task['payload']; cid = p['clip_id']
        if cid not in refs: continue
        ref = refs[cid]; new = catalog['clips'][cid]; old = p['protocol']; human = final_annotation(task)
        prompt = p.get('source',{}).get('generation_metadata',{}).get('prompt')
        expected = inputs[cid]['prompt_variant_sha256'][int(p['prompt_variant'])-1]
        legacy_v6 = (isinstance(prompt,str) and hashlib.sha256(prompt.encode()).hexdigest()==expected
                    and p['seed']==0)
        input_ok = matches_frozen_input(p,actual_policy)
        media = p.get('remote_media',{})
        media_ok = media.get('lfs_sha256')==p['video_sha256'] and bool(media.get('revision')) and bool(media.get('path'))
        semantics_ok = all(all(old.get('events',{}).get(k,{}).get(f)==new['events'][k].get(f) for f in SEMANTIC_FIELDS)
                           for k in ref['reference_label_events'])
        window_ok = p['duration_s']+1e-6>=ref['horizon_s'] and abs(p['window_s']-ref['horizon_s'])<=1e-6
        identity_ok = bool(human) and human.get('video_sha256')==p['video_sha256'] and human.get('protocol_sha256')==p['protocol_sha256']
        reason = ('registered_actual_input_pending' if not input_ok else 'immutable_media_binding_pending' if not media_ok else
                  'event_semantics_changed' if not semantics_ok else 'native_or_annotation_window_pending' if not window_ok else
                  'final_human_identity_pending' if not identity_ok else 'ready')
        event_values = {}; exact = None; quality = (human or {}).get('quality',{}).get('status')
        if reason=='ready':
            if quality!='pass':
                reason='confirmed_quality_failure_reported_separately' if quality=='failure' else 'measurability_pending'
            else:
                for key, expected_label in ref['reference_label_events'].items():
                    label=human.get('events',{}).get(key,{}).get('label')
                    event_values[key]=int(int(label=='yes')==expected_label) if label in ('yes','no') else None
                known=list(event_values.values())
                if any(v==0 for v in known): exact=0
                elif all(v==1 for v in known) and not ref['required_order']: exact=1
                # Existing binary records contain no generated contact order.
                # Matching two labels is not evidence for the chain order.
                reason='component_labels_inherited_order_pending' if ref['required_order'] and exact is None else 'component_labels_inherited'
        outputs.append(dict(task_id=task['id'],clip_id=cid,model=p['model'],seed=p['seed'],prompt_variant=p['prompt_variant'],
                            video_sha256=p['video_sha256'],parent_protocol_sha256=p['protocol_sha256'],
                            semantic_fields_exact=semantics_ok,input_matches_frozen_v6=legacy_v6,input_matches_current_policy=input_ok,
                            immutable_media_binding=media_ok,registered_window_matches=window_ok,
                            human_quality=quality,status=reason,event_correct=event_values,
                            contact_EventExact=exact,NearAcc=None,PairAcc=None))
    models=[]
    for model in sorted({r['model'] for r in outputs}):
        own=[r for r in outputs if r['model']==model]
        vals=[v for r in own for v in r['event_correct'].values() if v is not None]
        exact=[r['contact_EventExact'] for r in own if r['contact_EventExact'] is not None]
        models.append(dict(model=model,registered=len(own),known_component_events=len(vals),
                           component_correct=sum(vals),conditional_component_accuracy=sum(vals)/len(vals) if vals else None,
                           conclusive_contact_EventExact=len(exact),contact_EventExact_correct=sum(exact),
                           contact_EventExact=None,NearAcc=None,PairAcc=None,
                           status='diagnostic_only_incomplete_reference_boundary_or_human_coverage'))
    distance_path=RES/'core100_contact_boundaries_20261027.json'
    distances=json.loads(distance_path.read_text(encoding='utf-8')) if distance_path.exists() else {'records':[],'completed':0}
    t13_path=RES/'core100_t13_contact_boundaries_20261027.json'
    t13=json.loads(t13_path.read_text(encoding='utf-8')) if t13_path.exists() else {'records':[],'completed_cases':0}
    numerical_records=distances['records']+t13['records']
    for row in numerical_records:
        if row.get('probe_evidence_verified'):
            if row['clip_id'] not in refs or row['horizon_s']!=refs[row['clip_id']]['horizon_s']:
                raise ValueError('contact boundary reference/window mismatch')
            if row.get('reference_admitted') or row.get('pair_admitted'):
                raise ValueError('numerical collector cannot grant reference or pair admission')
            if row['clip_id'].startswith('T13'):
                if row['source_state_sha256']!=refs[row['clip_id']]['reference_state_sha256']:
                    raise ValueError('T13 boundary belongs to another source state')
    return dict(schema=catalog['schema'],status='approved_new_contact_reference_diagnostic',
                summary=dict(target_definition_cases=catalog['summary']['target_definition_cases'],
                             new_contact_reference_cases=len(refs),new_boundary_admissions=0,new_pairs=0,
                             numerical_contact_boundaries=distances['completed'],
                             numerical_contact_boundary_cases=len({r['clip_id']for r in numerical_records}),
                             T12_boundary_cases=distances['completed'],T13_boundary_cases=t13['completed_cases'],
                             registered_outputs=len(outputs),input_matches_frozen_v6=sum(r['input_matches_frozen_v6'] for r in outputs),
                             input_matches_current_policy=sum(r['input_matches_current_policy'] for r in outputs),
                             statuses=dict(collections.Counter(r['status'] for r in outputs))),
                per_model=models,outputs=outputs,numerical_contact_distances=numerical_records,
                provenance=dict(definition_sha256=hashlib.sha256(definition.read_bytes()).hexdigest(),
                                reference_truth_sha256=hashlib.sha256(truth.read_bytes()).hexdigest()),
                note='Ten registered contact targets, not historical terminal recovery. Actual author-selected text and output identity, exact event semantics, native/annotation windows and final human identities are required. Quality failures remain separate. Missing order never becomes a positive EventExact. No numerical collector grants NearAcc or PairAcc admission.')
