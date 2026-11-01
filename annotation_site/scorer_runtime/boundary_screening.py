"""Hash-bound VLM triage and separately adjudicated measurement routing."""
from collections import Counter

STATES = {'pass', 'suspect', 'confirmed_failure', 'evaluator_failure'}


def gate(record, observed, key, enabled):
    events = list(key['events'])
    if not enabled:
        return dict(status='legacy_not_screened', blocked_events=[], block_inversion=False, reason='')
    if not record:
        return dict(status='missing', blocked_events=events, block_inversion=True, reason='missing_screening')
    if record.get('video_sha256') != observed.get('video_sha256') or not observed.get('video_sha256'):
        raise ValueError('screening video hash mismatch')
    status = record.get('status')
    if status not in STATES or not record.get('method') or not record.get('evidence'):
        raise ValueError('invalid screening status/provenance')
    if status == 'confirmed_failure' and not record.get('reviewer'):
        raise ValueError('confirmed generation failure requires adjudicator')
    if status in ('suspect', 'evaluator_failure'):
        return dict(status=status, blocked_events=events, block_inversion=True, reason=record['evidence'])
    blocked = record.get('blocked_events', [])
    inv = record.get('block_inversion', False)
    if not isinstance(blocked, list) or any(e not in events for e in blocked) or type(inv) is not bool:
        raise ValueError('invalid screening measurement scope')
    if status == 'pass' and (blocked or inv):
        raise ValueError('pass cannot block measurement')
    if status == 'confirmed_failure' and not blocked and not inv:
        raise ValueError('failure must identify affected measurements')
    return dict(status=status, blocked_events=blocked, block_inversion=inv, reason=record['evidence'])


def prepare(root, judgements, reviews, out):
    """Import Qwen probe JSONL; export worklists, never prune the roster.

    A VLM quality flag or null outcome is a suspicion, not an adjudicated failure.
    Reviews may override with pass or scoped confirmed_failure plus evidence.
    """
    from pathlib import Path
    import json
    from .boundary import read_rows, _index_optional, digest, write_rows, write_json
    root, out = Path(root), Path(out)
    hashes = json.loads((root/'snapshot_hashes.json').read_text(encoding='utf-8'))
    if any(digest(root/name) != value for name, value in hashes.items()):
        raise ValueError('registered snapshots changed')
    keys = read_rows(root/'answers.jsonl')
    known = {k['sample_id'] for k in keys}
    observations = _index_optional(root/'observed_rows.jsonl', known)
    predictions = _index_optional(judgements, known)
    adjudications = _index_optional(reviews, known)
    records, routing = [], []
    for key in keys:
        sid = key['sample_id']; obs = observations.get(sid, {})
        pred = predictions.get(sid, {})
        if obs.get('status') != 'ok':
            routing.append(dict(sample_id=sid, status='media_unavailable', event_work=[], inversion_work=False))
            continue
        if digest(obs['video']) != obs['video_sha256']:
            raise ValueError('screening media changed')
        if pred and pred.get('video_sha256') != obs['video_sha256']:
            raise ValueError('VLM video hash mismatch')
        judgement = pred.get('judgement', {})
        flags = judgement.get('quality_flags')
        valid = (pred.get('status') == 'ok' and isinstance(flags, list)
                 and all(isinstance(f, str) for f in flags)
                 and type(judgement.get('assessable')) is bool and bool(judgement.get('reason')))
        state = ('suspect' if flags or not judgement['assessable'] else 'pass') if valid else 'evaluator_failure'
        record = dict(sample_id=sid, video_sha256=obs['video_sha256'], status=state,
                      method='vlm_triage', evidence=judgement.get('reason') or pred.get('error') or 'missing_or_invalid_vlm_result',
                      vlm_status=state, quality_flags=flags, blocked_events=[], block_inversion=False)
        if sid in adjudications:
            review = adjudications[sid]
            if review.get('video_sha256') != obs['video_sha256'] or not review.get('reviewer'):
                raise ValueError('review must bind video and adjudicator')
            if review.get('status') not in ('pass', 'confirmed_failure'):
                raise ValueError('review must resolve pass or confirmed_failure')
            record.update({k: review[k] for k in ('status','reviewer','evidence','blocked_events','block_inversion')})
            record['method'] = 'vlm_then_adjudication'
        decision = gate(record, obs, key, True)
        records.append(record)
        routing.append(dict(sample_id=sid, status=decision['status'],
                            event_work=[e for e in key['events'] if e not in decision['blocked_events']],
                            inversion_work=key['inversion']['status']=='eligible' and not decision['block_inversion']))
    out.mkdir(parents=True, exist_ok=False)
    write_rows(out/'screening.jsonl', records)
    write_rows(out/'routing.jsonl', routing)
    result = dict(registered=len(keys), routing_rows=len(routing),
                  statuses=dict(Counter(r['status'] for r in routing)),
                  judge_sha256=digest(judgements), review_sha256=digest(reviews) if reviews else None,
                  note='Worklists only: scoring denominator remains the full registered roster.')
    write_json(out/'receipt.json', result)
    return result
