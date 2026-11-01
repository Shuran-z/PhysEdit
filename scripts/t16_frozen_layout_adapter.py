"""Conditional angle slice with the exact released C04 layout held fixed.

The old C05 layout (0.45) must not be substituted for C04's released layout.
The recorded sealing/control wrappers are passed in the immutable job plan.
"""
import copy
import importlib.util
import math
from pathlib import Path
from t12_contact_replay_worker import acquire
from t16_reference_geometry import folder_support_clearance

path=Path(__file__).with_name('conditional_window_search_video.py')
spec=importlib.util.spec_from_file_location('frozen_t16_engine',path)
engine=importlib.util.module_from_spec(spec);spec.loader.exec_module(engine)


def intervene(job,theta,check_geometry=True):
    c=copy.deepcopy(job['base_config']);layout=job['frozen_contact_position_normalized']
    if theta!=job['theta']:
        build,backgrounds=engine.original_builder()
        objects,meta=build.scene_objects('T16','support_angle',theta,backgrounds[c['experiment']['background_id']],c['experiment']['trajectory_id'])
        c['dynamic_objects']=objects;c['experiment'].update(meta)
        actors={o['name']:o for o in objects};folder=actors['t16_folder'];book=actors['t16_support_book']
        span=math.cos(math.radians(theta))*folder['size'][0]
        if abs(span)<1e-10:raise ValueError('normalized layout undefined at this angle')
        desired=folder['pose']['position'][0]-span/2+layout*span+book['size'][2]/2+.002
        delta=desired-book['pose']['position'][0];book['pose']['position'][0]=desired
        for key in book['motion']['keyframes']:key['position'][0]+=delta
        c['experiment']['contact_position_normalized']=layout
        c['experiment']['support_angle_deg']=theta;c['experiment']['parameter']['parameter_value']=theta
    actors={o['name']:o for o in c['dynamic_objects']};folder=actors['t16_folder'];book=actors['t16_support_book']
    span=math.cos(math.radians(theta))*folder['size'][0]
    actual=(book['pose']['position'][0]-book['size'][2]/2-.002-(folder['pose']['position'][0]-span/2))/span
    if abs(actual-layout)>1e-10:raise ValueError('released normalized layout changed')
    if check_geometry and folder_support_clearance(c)['intersects']:
        raise ValueError('angle probe has initial proxy overlap; not an admissible boundary endpoint')
    return c


engine.intervene=intervene
engine.acquire_gpu=lambda root,preferred:acquire(root)
original_events=engine.events


def checked_events(job,config,state,state_path=None):
    depths=[p['penetration_m']for f in state['frames']for p in f.get('contacts',[])if 'penetration_m'in p]
    if not depths or max(depths)>.001:
        raise ValueError('probe failed existing 1 mm native-contact quality gate')
    return original_events(job,config,state,state_path)


engine.events=checked_events
if __name__=='__main__':engine.main()
