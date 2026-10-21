import copy
import pytest
from scripts.five_scene_boundary_rules import intervene,t11_intervention,event
from scripts.register_five_scene_refinements import bind,identity
from scripts.prepare_five_scene_boundaries import metadata_header
from scripts.five_scene_boundary_worker import numeric_render
import json
import gzip


def job():
    c={'dynamic_objects':[{'name':'t04v3_folder_ramp_pbr','friction':.1},{'name':'t04v3_stack_book_bottom','friction':.1}],
       'scene_overrides':{'gravity':[0,0,-9.81]},'render':{'frames':210,'fps':30},'experiment':{},'runtime_forces':[]}
    right=copy.deepcopy(c)
    for o in right['dynamic_objects']:o['friction']=.2
    return {'scene_id':'T04','family_id':'stack_sliding','bracket':[.1,.2],'endpoints':[{'config':c},{'config':right}]}


def test_restricted_intervention_preserves_other_physics_and_exact_endpoints():
    j=job();out=intervene(j,.15)
    assert [o['friction'] for o in out['dynamic_objects']]==[.15,.15]
    assert out['scene_overrides']==j['endpoints'][0]['config']['scene_overrides']
    assert intervene(j,.2)['dynamic_objects']==j['endpoints'][1]['config']['dynamic_objects']
    assert j==job()


def test_repaired_mass_or_other_context_changes_cannot_silently_join():
    j=job();j['endpoints'][0]['config']['dynamic_objects'][0]['mass']=1
    j['endpoints'][1]['config']['dynamic_objects'][0]['mass']=2
    with pytest.raises(ValueError):intervene(j,.15)


def test_refinement_holds_source_seed_even_at_opposite_published_endpoint():
    j=job();j['endpoints'][0]['config']['random_seed']=123;j['endpoints'][1]['config']['random_seed']=456
    assert intervene(j,.2)['random_seed']==123
    assert intervene(j,.15)['random_seed']==123
    j['seed_endpoint']=1
    assert intervene(j,.1)['random_seed']==456
    assert intervene(j,.15)['random_seed']==456
    j['seed_endpoint']=2
    with pytest.raises(ValueError,match='published endpoint'):intervene(j,.15)


def test_t11_uses_original_piecewise_force_and_integer_delay_recipe():
    c={'dynamic_objects':[],'runtime_forces':[{'target':'t11_driver_eraser','force_world':[.18,0,0],
       'force_world_after_contact':[0,0,0],'stop_after_contact_delay_frames':0}]}
    out=t11_intervention(c,'driver_initial_speed_mps',1.8,2.7)
    force=out['runtime_forces'][0]
    assert force['force_world'][0]==pytest.approx(.24)
    assert force['force_world_after_contact'][0]==pytest.approx(.3)
    assert force['stop_after_contact_delay_frames']==10
    assert c['runtime_forces'][0]['stop_after_contact_delay_frames']==0


def test_gate_event_is_full_passage_without_requiring_a_floor_frame():
    c={'experiment':{'geometry_contract':{'phone_center_full_pass_x_m':.3}}}
    frames=[{'objects':[{'name':'t05v2_moving_phone','position':[i/500,0,0]}]} for i in range(210)]
    assert event(c,{'frames':frames},'gate_passage')==1
    frames[120]['objects'][0]['position'][0]=float('nan')
    with pytest.raises(ValueError,match='nonfinite'):event(c,{'frames':frames},'gate_passage')


def test_refinement_binding_retains_both_sides_labels_and_unfinished_rows():
    base=dict(scene_id='T04',family_id='stack_sliding',target_event='stack_motion',
              endpoint_sample_ids=['a','b'],original_boundary_interval=[.1,.2])
    rows=[dict(base,sample_id='a',theta=.1,reference_label=1),
          dict(base,sample_id='b',theta=.2,reference_label=0),
          dict(base,sample_id='c',theta=.3,target_event='other',reference_label=0)]
    j=dict(job_id='job',normalization_domain=[0,1],endpoints=[dict(config=dict(random_seed=7))])
    result=dict(bracket=[.14,.15],backend_sources={'backend':'hash'},execution_sources={'worker':'hash'})
    output,count=bind(rows,{identity(rows[0]):(j,result)})
    assert len(output)==3 and count==2
    assert [r['reference_label'] for r in output]==[1,0,0]
    assert output[0]['original_boundary_interval']==[.14,.15]
    assert output[1]['normalized_distance_lower']==pytest.approx(.05)
    assert output[2]==rows[2]
    assert rows[0]['original_boundary_interval']==[.1,.2]
    assert output[0]['formal_nearacc_eligible'] is False


def test_fast_header_reads_top_level_fields_even_after_large_frames():
    source=dict(experiment={'nested':{'manifest':'wrong'}},manifest='original',render={},scene_overrides={},
                frames=[{'experiment':{'manifest':'also wrong'}}],dynamic_objects=[{'name':'target'}],runtime_forces=[])
    raw=gzip.compress(json.dumps(source,indent=2).encode())
    assert metadata_header(raw)=={k:v for k,v in source.items() if k!='frames'}


def test_original_render_mode_retains_raytracer_and_all_physics_timing():
    c=dict(scene_overrides=dict(raytracing=True,dt=.001,substeps=4,gravity=[0,0,-15]),
           render=dict(render_backend='raytracing',fps=30,frames=210,physics_steps_per_render_frame=67,pre_static_frames=60),dynamic_objects=[dict(mass=.1)])
    original=copy.deepcopy(c);numeric_render(c,'original')
    assert c['scene_overrides']==original['scene_overrides']
    assert c['render']['render_backend']=='raytracing'
    assert c['dynamic_objects']==original['dynamic_objects']
    assert all(c['render'][k]==v for k,v in original['render'].items())
    numeric_render(c,'raster');assert c['render']['render_backend']=='raster' and c['scene_overrides']['raytracing'] is False
