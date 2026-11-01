"""Wrong intervention axes and mixed observation windows change the benchmark."""
import ast
import copy
import gzip
import json
from pathlib import Path

R=Path(__file__).resolve().parents[1]/'review/cvpr_experiments_20261031/critical_t05_friction'


def helpers():
    tree=ast.parse((R/'run_probe.py').read_text(encoding='utf8'))
    fns=[x for x in tree.body if isinstance(x,ast.FunctionDef)and x.name in {'intervene','labels'}]
    ns={'copy':copy};exec(compile(ast.Module(body=fns,type_ignores=[]),'t05_helpers','exec'),ns)
    return ns


def test_friction_changes_only_original_contact_materials_and_metadata():
    job=json.loads((R/'PLAN.json').read_text(encoding='utf8'))['jobs'][0]
    source=copy.deepcopy(job['base_config']);changed=helpers()['intervene'](source,.025)
    expected=copy.deepcopy(source)
    for o in expected['dynamic_objects']:
        if o['name']in {'t05v2_pbr_wood_sorting_tray','t05v2_moving_phone'}:o['friction']=.025
    expected['experiment']['parameter']['phone_tray_friction_coefficient']=.025
    assert changed==expected
    assert source==job['base_config']
    assert changed['experiment']['geometry_contract']==source['experiment']['geometry_contract']


def test_current_t05_c03_source_is_negative_at_5s_positive_at_full_window():
    job=next(j for j in json.loads((R/'PLAN.json').read_text(encoding='utf8'))['jobs']if j['clip_id']=='T05_C03')
    state=json.loads(gzip.decompress((R/job['source_state_file']).read_bytes()))
    labels,first=helpers()['labels'](state,job)
    assert labels=={'primary_5s':0,'secondary_full':1}
    assert first==173 and job['primary_window_frames']==[5,154]


def test_event_after_frozen_last_frame_is_excluded_from_primary():
    job={'base_config':{'experiment':{'geometry_contract':{'phone_center_full_pass_x_m':1}}},'primary_window_frames':[5,154],'secondary_window_frames':[5,209]}
    state={'frames':[{'frame_index':i,'objects':[{'name':'t05v2_moving_phone','position':[x,0,0]}]}for i,x in [(154,0),(155,1)]]}
    result,first=helpers()['labels'](state,job)
    assert result=={'primary_5s':0,'secondary_full':1}and first==155
