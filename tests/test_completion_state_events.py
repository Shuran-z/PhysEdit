import unittest
import copy
from scripts.audit_t05_completion_states import measure,fixed_context as t05_context
from scripts.audit_t04_completion_states import fixed_context
from scripts.audit_t07_t08_completion_states import measure_t07,measure_t08
from scripts.audit_nearacc_readiness import readiness

class CompletionEventsTests(unittest.TestCase):
    def test_computed_near_distance_does_not_bypass_boundary_verification(self):
        eligible,reasons,_=readiness({'reference_label':1,'distance':{'bin':'near'},'boundary':{'status':'pending_repeatability','normalization_span':.15}})
        self.assertFalse(eligible)
        self.assertIn('boundary_not_verified',reasons)

    def test_t05_friction_pair_rejects_hidden_gap_revision(self):
        d={'dynamic_objects':[{'spec':{'name':'t05v2_guide_left','friction':.05,'pose':{'position':[0,-.05,0]}}}], 'scene_overrides':{}, 'experiment':{}, 'render':{}}
        changed=copy.deepcopy(d);changed['dynamic_objects'][0]['spec']['friction']=.08
        self.assertEqual(t05_context(d,'terminal_transfer'),t05_context(changed,'terminal_transfer'))
        changed['dynamic_objects'][0]['spec']['pose']['position'][1]=-.06
        self.assertNotEqual(t05_context(d,'terminal_transfer'),t05_context(changed,'terminal_transfer'))

    def test_motion_uses_peak_not_final_and_original_threshold(self):
        d={'frames':[{'objects':[{'name':'t07_smartphone','position':[x,0,0]}]} for x in [0,.01,0]]}
        self.assertEqual(measure_t07(d)['events']['motion_ge_1cm'],1)
        d['frames'][1]['objects'][0]['position'][0]=.009
        self.assertEqual(measure_t07(d)['events']['motion_ge_1cm'],0)

    def test_t08_departure_does_not_require_floor_contact(self):
        names=['t08_lower_impactor_book','t08_upper_payload_book','t08_target_mug']
        d={'experiment':{'scene_family_id':'T08_TWO_BOOK_STACK_MUG_EDGE_CASCADE_V4','table_top_z':0},'frames':[{'objects':[{'name':n,'position':[0,0,z]} for n in names]} for z in [0,-.09]]}
        result=measure_t08(d)['events']
        self.assertEqual(result['t08_target_mug_below_table_8cm'],1)
        self.assertIsNone(result['t08_target_mug_floor_contact'])
        d['scene_overrides']={'record_contacts':True}
        self.assertEqual(measure_t08(d)['events']['t08_target_mug_floor_contact'],0)

    def test_intervention_mask_keeps_mass_timing_and_runtime_seed(self):
        d={'dynamic_objects':[{'spec':{'name':'t04v3_stack_book_bottom','friction':.1,'mass':.4}}], 'scene_overrides':{'gravity':[0,0,-9.81]}, 'experiment':{'seed':1}, 'render':{'physics_steps_per_render_frame':16}}
        baseline=fixed_context(d,'stack_sliding'); changed=copy.deepcopy(d)
        changed['dynamic_objects'][0]['spec']['friction']=.2
        changed['experiment']['seed']=2
        self.assertEqual(baseline,fixed_context(changed,'stack_sliding'))
        changed['dynamic_objects'][0]['spec']['mass']=.5
        self.assertNotEqual(baseline,fixed_context(changed,'stack_sliding'))
        for group,key,value in [('render','physics_steps_per_render_frame',8),('experiment','random_seed',12)]:
            changed=copy.deepcopy(d);changed[group][key]=value
            self.assertNotEqual(baseline,fixed_context(changed,'stack_sliding'))

    def test_contact_missing_is_unknown_and_passage_uses_original_geometry(self):
        data={'experiment':{'geometry_contract':{'phone_center_full_pass_x_m':.4}},'frames':[{'objects':[{'name':'t05v2_moving_phone','position':[x,0,0]}]} for x in [.1,.4,.2]]}
        result=measure(data)
        self.assertEqual(result['events']['gate_passage'],1)
        self.assertIsNone(result['events']['terminal_contact'])
        data['frames'][1]['contacts']=[{'entity_a':'t05v2_downstream_can','entity_b':'t05v2_moving_phone'}]
        self.assertEqual(measure(data)['events']['terminal_contact'],1)
        data['experiment']['geometry_contract']['phone_center_full_pass_x_m']=.41
        self.assertEqual(measure(data)['events']['gate_passage'],0)

if __name__=='__main__':unittest.main()
