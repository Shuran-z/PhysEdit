"""Recover original audit predicates, keeping event semantics and sources explicit."""
import argparse,gzip,hashlib,json,math
from pathlib import Path

ROOT=Path('review/scene_family_completion_20261018')

def track(data,name):
    return [next(o for o in f['objects'] if o['name']==name) for f in data['frames']]

def measure_t07(data):
    positions=[o['position'] for o in track(data,'t07_smartphone')]
    maximum=max(math.dist(positions[0],p) for p in positions)
    return dict(events={'motion_ge_1cm':int(maximum>=.01)},max_displacement_m=maximum,
                path_length_m=sum(math.dist(a,b) for a,b in zip(positions,positions[1:])))

def measure_t08(data):
    if data['experiment']['scene_family_id']!='T08_TWO_BOOK_STACK_MUG_EDGE_CASCADE_V4':
        raise ValueError('T08 family/version mismatch')
    names=['t08_lower_impactor_book','t08_upper_payload_book','t08_target_mug']
    events={};first_frames={}
    contact_available=data.get('scene_overrides',{}).get('record_contacts') is True or any('contacts' in f for f in data['frames'])
    def contact(a,b):
        hits=[i for i,f in enumerate(data['frames']) if any({c.get('entity_a'),c.get('entity_b')}=={a,b} for c in f.get('contacts',[]))]
        return (int(bool(hits)) if contact_available else None,hits[0] if hits else None)
    for n in names:
        # Original audit's 'left_table' means center >8 cm below tabletop.
        # Do not relabel this as the exact instant of support loss or floor impact.
        hits=[i for i,o in enumerate(track(data,n)) if o['position'][2]<data['experiment']['table_top_z']-.08]
        key=n+'_below_table_8cm';events[key]=int(bool(hits));first_frames[key]=hits[0] if hits else None
        key=n+'_floor_contact';events[key],first_frames[key]=contact(n,'t08_floor_collision_slab')
    for a,b,key in [(names[0],names[1],'book_book_contact'),(names[0],names[2],'book_mug_contact')]:
        events[key],first_frames[key]=contact(a,b)
    return dict(events=events,first_event_frames=first_frames)

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--scenes',nargs='+',default=['T07','T08']);args=parser.parse_args()
    for scene in args.scenes:
        source=ROOT/'original_completion_sources'/('audit_t07_motion.py' if scene=='T07' else 'analyze_t08_v3_metrics.py')
        result=[]
        for receipt in sorted((ROOT/'completion_states').glob(scene+'_*.json')):
            for r in json.loads(receipt.read_text(encoding='utf-8')):
                if not r.get('local_path'):continue
                raw=Path(r['local_path']).read_bytes()
                if hashlib.sha256(raw).hexdigest()!=r['sha256']:raise ValueError('state hash mismatch')
                data=json.loads(gzip.decompress(raw));exp=data['experiment']
                measured=(measure_t07 if scene=='T07' else measure_t08)(data)
                family=exp.get('counterfactual_group')
                theta=exp.get('controlled_value') if scene=='T07' else {'A_book_initial_speed_mps':exp.get('book_initial_speed_mps'),'B_impact_eccentricity_m':exp.get('impact_eccentricity_m'),'C_mug_total_mass_kg':exp.get('mug_total_mass_kg')}.get(family)
                result.append(dict(**r,**measured,family_id=family,theta=theta,background=exp.get('background_id'),gravity=exp.get('gravity_id'),original_rule_source=str(source.resolve()),original_rule_sha256=hashlib.sha256(source.read_bytes()).hexdigest(),status='published_event_measured_boundary_and_visual_review_pending'))
        (ROOT/(scene.lower()+'_measured_published_events.json')).write_text(json.dumps(result,indent=2),encoding='utf-8')
        print(json.dumps(dict(scene=scene,states=len(result),events=[r['events'] for r in result[:3]])))

if __name__=='__main__':main()
