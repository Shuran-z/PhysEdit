"""Apply original T05 gate/contact predicates to exact published states."""
import copy,gzip,hashlib,json,math
from pathlib import Path
from scripts.audit_t04_completion_states import fixed_context as base_context
ROOT=Path('review/scene_family_completion_20261018')

def fixed_context(data,family):
    d=copy.deepcopy({k:v for k,v in data.items() if k!='frames'})
    for entry in d['dynamic_objects']:
        o=entry['spec']
        if o['name'] in ['t05v2_guide_left','t05v2_guide_right']:
            if family=='gate_passage':o['pose']['position'][1]='<intervention>'
            if family=='terminal_transfer':o['friction']='<intervention>'
    # Motion activation has no target predicate registered here; do not mask it.
    return base_context(d,None)

def measure(data):
    frames=data['frames'];exp=data['experiment'];geo=exp['geometry_contract']
    phone=[next(o for o in f['objects'] if o['name']=='t05v2_moving_phone') for f in frames]
    maximum=max(o['position'][0] for o in phone)
    threshold=geo['phone_center_full_pass_x_m']
    if not math.isfinite(threshold):raise ValueError('invalid passage threshold')
    contacts_present=any('contacts' in f for f in frames)
    hit=None if not contacts_present else int(any({c.get('entity_a'),c.get('entity_b')}=={'t05v2_moving_phone','t05v2_downstream_can'} for f in frames for c in f.get('contacts',[])))
    return dict(events=dict(gate_passage=int(maximum>=threshold),terminal_contact=hit),max_phone_x=maximum,full_pass_x=threshold)

def main():
    extractor_hash=hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    binding_hash=hashlib.sha256((ROOT/'t04_t05_profile_bindings.json').read_bytes()).hexdigest()
    bindings={r['sample_id']:r for r in json.loads((ROOT/'t04_t05_profile_bindings.json').read_text())}
    output=ROOT/'t05_measured_published_events.json'
    old={r['sample_id']:r for r in json.loads(output.read_text(encoding='utf-8'))} if output.exists() else {}
    rows=[]
    for receipt in sorted((ROOT/'completion_states').glob('T05_*.json')):
        for r in json.loads(receipt.read_text(encoding='utf-8')):
            if not r.get('local_path'):continue
            raw=Path(r['local_path']).read_bytes()
            if hashlib.sha256(raw).hexdigest()!=r['sha256']:raise ValueError('state identity changed')
            cached=old.get(r['sample_id'])
            if cached and cached.get('sha256')==r['sha256'] and cached.get('extractor_sha256')==extractor_hash and cached.get('binding_sha256')==binding_hash:
                rows.append(cached);continue
            d=json.loads(gzip.decompress(raw) if raw[:2]==b'\x1f\x8b' else raw);b=bindings[r['sample_id']]
            rows.append(dict(**r,**measure(d),fixed_context_sha256=fixed_context(d,b['family_id']),extractor_sha256=extractor_hash,binding_sha256=binding_hash,family_id=b['family_id'],theta=b['effective_parameter_value'],requested_theta=b['theta'],parameter_name=b['parameter_name'],repair_requires_separate_boundary=b['repair_requires_separate_boundary'],physical_revision_evidence=b['physical_revision_evidence'],source_group_id=b['source_group_id'],repeat=b['repeat'],status='measured_published_state_requires_context_binding'))
    (ROOT/'t05_measured_published_events.json').write_text(json.dumps(rows,indent=2),encoding='utf-8')
    print(json.dumps(dict(states=len(rows),passed=sum(r['events']['gate_passage'] for r in rows),contacts=sum(r['events']['terminal_contact']==1 for r in rows),repaired=sum(r['repair_requires_separate_boundary'] for r in rows))))

if __name__=='__main__':main()
