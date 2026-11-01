"""Attach audited boundary references without mutating frozen answer keys."""
import copy
import json
from pathlib import Path


def bind(keys, path, answers_path):
    from .boundary import digest, distance
    path=Path(path)
    data=json.loads(path.read_text(encoding='utf-8'))
    if data.get('answers_sha256')!=digest(answers_path):
        raise ValueError('boundary bindings belong to another answer snapshot')
    rows=data['bindings']; ids=[r['sample_id'] for r in rows]
    known={k['sample_id']:k for k in keys}
    if len(ids)!=len(set(ids)) or set(ids)-set(known):
        raise ValueError('duplicate or unknown boundary binding ID')
    result=copy.deepcopy(keys);out={k['sample_id']:k for k in result}
    for row in rows:
        key=out[row['sample_id']]
        # Exact reference-state and fixed-context binding, not event-name matching.
        for field in ('reference_sample_id','reference_state_sha256','source_group_id','target_event','theta'):
            if key.get(field) is None or row.get(field)!=key[field]:
                raise ValueError('boundary binding mismatch: '+field)
        source=(path.parent/row['source_file']).resolve()
        if digest(source)!=row['source_sha256']:
            raise ValueError('boundary source hash mismatch')
        boundary=copy.deepcopy(row['boundary'])
        if boundary.get('status')=='verified':
            if row.get('mapping_status')!='matched' or not row.get('mapping_evidence'):
                raise ValueError('verified boundary requires audited mapping')
            if not row.get('parameter_name') or not row.get('parameter_unit') or not row.get('normalization_basis'):
                raise ValueError('parameter unit and normalization basis required')
            if ('theta_star' in boundary)==('bracket' in boundary):
                raise ValueError('supply exactly one boundary point or bracket')
        elif boundary.get('status')=='observed':
            if row.get('mapping_status')!='matched' or not row.get('mapping_evidence') or not row.get('parameter_unit'):
                raise ValueError('observed boundary requires matched evidence and units')
        elif boundary.get('status')!='unavailable':
            raise ValueError('unsupported boundary status')
        boundary['source']=str(source)
        boundary['source_sha256']=row['source_sha256']
        boundary['mapping_status']=row['mapping_status']
        boundary['reason']=row.get('reason','')
        key['boundary']=boundary
        distance(key)
    return result, dict(path=str(path.resolve()),sha256=digest(path),
        bound=sum(k.get('boundary',{}).get('status')=='verified' for k in result),
        observed_bound=sum(k.get('boundary',{}).get('status')=='observed' for k in result),
        registered=len(result))
