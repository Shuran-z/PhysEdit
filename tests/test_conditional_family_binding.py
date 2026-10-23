import copy
import hashlib
import json
import pytest
from scripts.register_remaining_family_distances import bind
from scripts.conditional_family_search import restore_visual_manifest


def evidence():
    job=dict(job_id='j',scene_id='T03',family_id='A',sample_id='selected_source',revision='release',
        theta=.2,parameter_unit='m/s',source_state_sha256='state',source_config_sha256='config',
        fixed_context_sha256='context',backend_sources={'renderer':'hash'},base_config={'seed':7},
        expected={'contact':0},grid=[.2,.8],normalization_domain=[0,1],tolerance=.02)
    result=dict(**{k:job[k] for k in ['job_id','scene_id','family_id','sample_id','source_state_sha256','source_config_sha256','backend_sources']},
        source_seed=7,eligible_events=['contact'],intervals=[{'target_event':'contact','bracket':[.45,.46],'labels':[0,1]}],
        probes=[{'theta':t,'labels':{'contact':v}} for t,v in [(.2,0),(.45,0),(.46,1),(.8,1)]])
    return job,result


def test_conditional_distance_only_binds_its_source_without_granting_admission():
    job,result=evidence();rows=bind(job,result)
    assert [r['sample_id'] for r in rows]==['selected_source']
    assert rows[0]['distance_lower']==pytest.approx(.25)
    assert rows[0]['distance_upper']==pytest.approx(.26)
    assert rows[0]['formal_nearacc_eligible'] is False


@pytest.mark.parametrize('field,value', [('source_seed',8),('source_state_sha256','another_state'),('sample_id','another_video')])
def test_other_seed_state_or_video_cannot_inherit_conditional_boundary(field,value):
    job,result=evidence();result[field]=value
    with pytest.raises(ValueError):bind(job,result)


def test_partial_grid_and_same_label_endpoints_cannot_claim_finished_search():
    job,result=evidence();incomplete=copy.deepcopy(result);incomplete['probes'].pop()
    with pytest.raises(ValueError,match='grid incomplete'):bind(job,incomplete)
    result['probes'][2]['labels']['contact']=0
    with pytest.raises(ValueError,match='opposite endpoint'):bind(job,result)


def test_restored_visual_asset_preserves_scene_settings_and_rejects_colliders(tmp_path):
    mesh=tmp_path/'original.obj';mesh.write_bytes(b'original recorded geometry')
    digest=hashlib.sha256(mesh.read_bytes()).hexdigest();manifest=tmp_path/'manifest.json'
    data={'background_metadata':{'all_decor_visual_only':True},'objects':[
        {'decor_collision_policy':'visual_only','collision_mesh_path':None,'mesh_path':str(mesh)}]}
    def job():
        manifest.write_text(json.dumps(data))
        return {'visual_manifest_restoration':{'manifest_path':str(manifest),
            'manifest_sha256':hashlib.sha256(manifest.read_bytes()).hexdigest(),
            'geometry_sha256':digest,'recorded_geometry_sha256':digest}}
    config={'manifest':'missing_original_path','scene_overrides':{'static_scene_collision':True},'dynamic_objects':[{'mass':1}]}
    before=copy.deepcopy(config);restore_visual_manifest(config,job())
    assert config['scene_overrides']==before['scene_overrides']
    assert config['dynamic_objects']==before['dynamic_objects']
    data['objects'][0]['collision_mesh_path']='another_collision_mesh'
    with pytest.raises(ValueError,match='collision object'):restore_visual_manifest(config,job())
