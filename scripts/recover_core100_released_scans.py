"""Read released trajectories at the registered window; never run a simulator.

Grouping removes only the original intervention, with numerical rounding for
angle arithmetic. Unknown/conflicting outcomes never become negative endpoints.
"""
import argparse
import copy
import gzip
import hashlib
import json
import math
from pathlib import Path


def normalized(value):
    if isinstance(value,float):return round(value,9)
    if isinstance(value,list):return [normalized(v) for v in value]
    if isinstance(value,dict):return {k:normalized(v) for k,v in value.items()}
    return value


def context(state,scene):
    specs={r['name']:copy.deepcopy(r.get('spec',r)) for r in state['dynamic_objects']}
    if scene=='T01':
        for name in ['t01v2_tabletop_collision_slab','t01v2_chain_can_1','t01v2_chain_can_2','t01v2_chain_mug']:
            specs[name]['friction']=0.
    elif scene=='T08':
        motion=specs['t08_lower_impactor_book']['motion'];v=motion['initial_velocity']
        norm=math.sqrt(sum(x*x for x in v));motion['initial_velocity']=[x/norm for x in v] if norm else[0,0,0]
    elif scene=='T04':
        specs['t04v3_removable_support_bar']['motion']['initial_velocity'][1]=0.
    elif scene=='T05':
        p=state['experiment']['parameter'];half=p['gap_ratio']*p['phone_nominal_width_m']/2
        for name,spec in specs.items():
            if 'guide' in name and ('left' in name or 'right' in name):
                y=spec['pose']['position'][1]
                spec['pose']['position'][1]-=half*(1 if y>0 else -1)
    elif scene=='T16':
        e=state['experiment'];theta=e['parameter']['parameter_value'];a=math.radians(theta)
        folder=specs['t16_folder'];support=specs['t16_support_book'];size=folder['size']
        folder['pose']['position'][2]-=(abs(math.sin(a))*size[0]+abs(math.cos(a))*size[2])/2
        folder['pose']['euler_xyz'][1]+=theta
        dx=math.cos(a)*size[0]*(e['contact_position_normalized']-.5)
        support['pose']['position'][0]-=dx
        for row in support['motion'].get('keyframes',[]):row['position'][0]-=dx
    elif scene=='T17':
        specs['t17_can']['motion']['initial_velocity']=[0.,0.,0.]
    # Paths for visual assets, raytracing and camera output are not physics.
    physics_keys=['gravity','dt','substeps','settle_steps','use_gjk_collision','box_box_detection',
                  'enable_multi_contact','iterations','ls_iterations','noslip_iterations','constraint_timeconst',
                  'static_scene_collision','layout_collision','add_ground_plane']
    value=normalized(dict(objects=specs,physics={k:state['scene_overrides'].get(k) for k in physics_keys},
                          pre_static_frames=state['render'].get('pre_static_frames')))
    return hashlib.sha256(json.dumps(value,sort_keys=True).encode()).hexdigest()


def observe(state,scene):
    frames=state['frames'];assert len(frames)==210
    if scene=='T01':
        theta=state['experiment']['parameter']['chain_surface_friction_coefficient']
        def pos(f):return next(o['position']for o in f['objects']if o['name']=='t01v2_chain_mug')
        delta=math.dist(pos(frames[4]),pos(frames[154]))
        hit=any({c.get('entity_a'),c.get('entity_b')}=={'t01v2_chain_can_2','t01v2_chain_mug'}for f in frames[5:155]for c in f.get('contacts',[]))
        # Exterior samples alone cannot disprove a short contact if the mug moved.
        labels={'full_chain':0 if delta<=.03 else 1 if hit else None}
    elif scene=='T04':
        theta=state['experiment']['parameter']['commanded_extraction_speed_mps']
        def obj(f):return next(o for o in f['objects']if o['name']=='t04v3_chain_mug')
        first=obj(frames[4]);last=obj(frames[154]);q=first['quaternion_xyzw']
        angle=max(math.degrees(2*math.acos(min(1.,abs(sum(a*b for a,b in zip(q,obj(f)['quaternion_xyzw'])))/math.sqrt(sum(a*a for a in q)*sum(a*a for a in obj(f)['quaternion_xyzw'])))))for f in frames[5:155])
        moved=max(math.dist(first['position'],obj(f)['position'])for f in frames[4:155])>=.04 or angle>=18.
        hit=any({c.get('entity_a'),c.get('entity_b')}=={'t04v3_chain_can_2','t04v3_chain_mug'}for f in frames[5:155]for c in f.get('contacts',[]))
        labels={'original_full_chain':0 if not moved else 1 if hit else None}
    elif scene=='T05':
        theta=state['experiment']['parameter']['gap_ratio']
        threshold=state['experiment']['geometry_contract']['phone_center_full_pass_x_m']
        labels={'gate_passage':int(any(o['name']=='t05v2_moving_phone'and o['position'][0]>=threshold for f in frames[5:155]for o in f['objects']))}
    elif scene=='T08':
        specs={r['name']:r.get('spec',r)for r in state['dynamic_objects']}
        theta=math.sqrt(sum(x*x for x in specs['t08_lower_impactor_book']['motion']['initial_velocity']))
        z=state['experiment']['table_top_z']-.08
        labels={name+'_below_table_8cm':int(any(o['name']==name and o['position'][2]<z for f in frames[5:155]for o in f['objects']))
                for name in ['t08_lower_impactor_book','t08_upper_payload_book','t08_target_mug']}
    else:
        theta=state['experiment']['parameter']['parameter_value']
        pair={'t16_folder','t16_downstream_box'} if scene=='T16' else {'t17_can','t17_tissue_box'}
        hit=int(any({c.get('entity_a'),c.get('entity_b')}==pair for f in frames[5:155]for c in f.get('contacts',[])))
        labels={('folder_downstream_contact'if scene=='T16'else'can_tissue_box_contact'):hit}
    return float(theta),labels


def read_point(path,scene):
    stored=path.read_bytes();raw=gzip.decompress(stored) if path.suffix=='.gz' else stored
    state=json.loads(raw);theta,labels=observe(state,scene)
    return dict(sample_id=path.name.split('.json')[0].removesuffix('__cam01'),theta=theta,
        labels=labels,fixed_context_sha256=context(state,scene),state_path=str(path),
        stored_state_sha256=hashlib.sha256(stored).hexdigest(),state_sha256=hashlib.sha256(raw).hexdigest())


def intervals(points,event):
    groups={}
    for p in points:groups.setdefault(round(p['theta'],10),[]).append(p)
    unique=[]
    for theta,rows in sorted(groups.items()):
        values={p['labels'][event]for p in rows}
        unique.append(dict(theta=theta,label=next(iter(values))if len(values)==1 else None,endpoints=rows))
    out=[]
    for a,b in zip(unique,unique[1:]):
        if a['label']in(0,1)and b['label']in(0,1)and a['label']!=b['label']:
            out.append(dict(event=event,bracket=[a['theta'],b['theta']],labels=[a['label'],b['label']],endpoints=[a['endpoints'],b['endpoints']]))
    return out,unique


def recover(scene,paths,targets):
    groups={};sources={}
    wanted={r['sample_id']:r for r in targets}
    for path in paths:
        row=read_point(path,scene)
        groups.setdefault(row['fixed_context_sha256'],[]).append(row)
        if row['sample_id'] in wanted:sources[row['sample_id']]=row
    cases=[]
    for target in targets:
        source=sources.get(target['sample_id'])
        if not source:
            cases.append(dict(clip_id=target['clip_id'],status='source_missing'));continue
        same=groups[source['fixed_context_sha256']];events=[]
        for event,label in source['labels'].items():
            iv,unique=intervals(same,event)
            events.append(dict(event=event,source_label=label,intervals=iv,
                unique_points=len(unique),ambiguous_points=sum(p['label']is None for p in unique),
                constant_observed_label=unique[0]['label'] if len({p['label']for p in unique})==1 else None))
        cases.append(dict(clip_id=target['clip_id'],sample_id=target['sample_id'],source=source,
            matched_points=len(same),events=events,horizon_s=5.,condition_frame_index=4,end_frame_index=154,
            status='released_state_window_recovered',simulations_started=0))
    return cases


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--mode',choices=['local','remote'],required=True)
    parser.add_argument('--targets',type=Path);parser.add_argument('--out',type=Path,required=True);parser.add_argument('--scenes',nargs='+',default=['T01','T08']);args=parser.parse_args()
    cases=[]
    if args.mode=='local':
        root=Path(__file__).resolve().parents[1];work=root/'review/core100_binding_20261028'
        targets=json.loads((work/'core100_priority_worklist_20261029.json').read_text(encoding='utf8'))['cases']
        for scene in args.scenes:
            selected=[dict(clip_id=r['clip_id'],sample_id=r['source_sample_id'])for r in targets if r['clip_id'].startswith(scene)]
            paths=list((root/'review/scene_family_completion_20261018/completion_states'/scene).glob('*.gz'))
            if scene=='T01':
                paths=[p for p in paths if'rmu150__g12006__g2m006'in p.name and any(g in p.name for g in ['bg01_home_ase__g01_moon','bg01_home_ase__g02_mars','bg01_home_ase__g03_earth'])]
            else:
                prefixes={r['sample_id'].split('__global_')[0].split('__cf_')[0]for r in selected}
                paths=[p for p in paths if any(p.name.startswith(prefix+'__')for prefix in prefixes)]
            cases+=recover(scene,paths,selected)
    else:
        targets=json.loads(args.targets.read_text())
        base=Path('/home/wangzijun_p25/liyuhan/phydataset/ase_asset_importer/everyday_bifurcation_72k_T16_T20_v1/production')
        for scene,family in [('T16','support_angle'),('T17','initial_speed')]:
            selected=[r for r in targets if r['clip_id'].startswith(scene)]
            prefixes={r['sample_id'].split('__'+family)[0]+'__'+family for r in selected}
            paths=[]
            for prefix in prefixes:
                for folder in base.glob(prefix+'__p*'):
                    p=folder/'metadata'/(folder.name+'__cam01.json.gz')
                    if p.exists():paths.append(p)
            cases+=recover(scene,paths,selected)
    args.out.parent.mkdir(parents=True,exist_ok=True)
    args.out.write_text(json.dumps(dict(cases=cases,simulations_started=0),indent=2),encoding='utf8')
    print(json.dumps([dict(clip_id=r['clip_id'],matched=r.get('matched_points'),events=[dict(event=e['event'],intervals=len(e['intervals']),points=e['unique_points'])for e in r.get('events',[])])for r in cases]))


if __name__=='__main__':main()
