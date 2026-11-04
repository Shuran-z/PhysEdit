"""Bind the original released T14-A bracket, not a different-context refinement."""
import copy
import hashlib
import json
from pathlib import Path
from physedit.core100_critical import load
from scripts.recover_core100_released_scans import normalized

ROOT=Path(__file__).resolve().parents[1];WORK=ROOT/'review/core100_v2_resolution_20261102'


def read(path):return json.loads(path.read_text(encoding='utf8'))
def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    registry,_=load()
    contract_path=ROOT/'review/original_search_tasks_20261018/t14_original_family_bindings.json'
    identity_path=ROOT/'review/original_search_tasks_20261018/t14_source_identity.json'
    config_path=ROOT/'review/scene_family_completion_20261018/p26_configs.json'
    readback_path=ROOT/'review/core100_remaining74_admission_20261101/sealed_readbacks/177d1346ea0267e18b96d98737e4c5325fdc6e7071e03e4000f2208fc7ce8430.json'
    contracts=read(contract_path);identities=read(identity_path);configs=read(config_path)
    readbacks={r['clip_id']:r['points'][0]for r in read(readback_path)}
    cases=[]
    for cid in ['T14_C04','T14_C05']:
        r=next(x for x in registry['cases']if x['clip_id']==cid)
        binding=next(x for x in contracts if x['sample_id']==r['sample_id'])
        identity=next(x for x in identities if x['sample_id']==r['sample_id'])
        assert binding['release_video_hashes_match']and binding['family']=='A'
        assert identity['videos']['cam01']['sha256']==r['reference_video_sha256']
        assert binding['config_sha256']==identity['config_sha256']
        config=next(x['config']for x in configs if x['sha256']==binding['config_sha256'])
        point=readbacks[cid]
        assert point['condition_frame_index']==r['condition_frame_index']==4
        assert point['end_frame_index']==r['end_frame_index']==154
        assert abs(point['physical_frame_period_s']*150-r['horizon_s'])<1e-12
        assert point['original_gate_event']['label']==r['reference_events']['passed_channel']
        if r.get('source_state_sha256'):assert point['decoded_state_sha256']==r['source_state_sha256']
        objects={o['name']:copy.deepcopy(o)for o in config['dynamic_objects']}
        assert objects=={o['name']:o.get('spec',o)for o in point['dynamic_objects']}
        theta=config['experiment']['parameter']['channel_throat_width_m']
        assert theta==r['theta']==binding['theta']
        for name in ['t14v2_corridor_book_left','t14v2_corridor_book_right']:
            y=objects[name]['pose']['position'][1]
            objects[name]['pose']['position'][1]-=(1 if y>0 else-1)*theta/2
        parameters=copy.deepcopy(config['experiment']['parameter']);parameters.pop('channel_throat_width_m')
        context=normalized(dict(objects=objects,physics=config['scene_overrides'],parameters=parameters,
            camera=config['render']['fixed_view'],fps=config['render']['fps'],pre_static_frames=config['render']['pre_static_frames'],
            runtime_forces=config.get('runtime_forces'),runtime_impulses=config.get('runtime_impulses')))
        ctx=hashlib.sha256(json.dumps(context,sort_keys=True).encode()).hexdigest()
        cases.append(dict(clip_id=cid,sample_id=r['sample_id'],reference_video_sha256=r['reference_video_sha256'],
            source_state_sha256=point['decoded_state_sha256'],config_sha256=binding['config_sha256'],theta=theta,
            fixed_context_sha256=ctx,source_calibration_contract_sha256=binding['contract_sha256'],
            bracket=binding['original_search_interval'],event='passed_channel',label=point['original_gate_event']['label'],
            original_gate_event=point['original_gate_event'],horizon_s=r['horizon_s'],
            declared_intervention='Symmetric lateral translation of the two corridor books; all other source physical inputs and camera fixed.',
            scope='Original released observed interval. Fine historical probes are retained separately and not transferred across contexts.'))
    assert cases[0]['fixed_context_sha256']==cases[1]['fixed_context_sha256']
    assert [c['label']for c in cases]==[0,1]and all(c['bracket']==[.018,.019]for c in cases)
    report=dict(cases=cases,source_hashes={p.relative_to(ROOT).as_posix():sha(p)for p in[contract_path,identity_path,config_path,readback_path]},
        new_simulations=0,original_files_modified=False)
    raw=json.dumps(report,indent=2).encode();digest=hashlib.sha256(raw).hexdigest();path=WORK/('t14_original_a_'+digest[:12]+'.json')
    if not path.exists():path.write_bytes(raw)
    else:assert path.read_bytes()==raw
    (WORK/'T14_ORIGINAL_A.json').write_text(json.dumps(dict(path=path.relative_to(ROOT).as_posix(),sha256=digest),indent=2),encoding='utf8')
    print(json.dumps([dict(clip_id=c['clip_id'],bracket=c['bracket'],label=c['label'])for c in cases]))


if __name__=='__main__':main()
