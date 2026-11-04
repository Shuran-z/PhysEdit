import unittest,math
from scripts.prompt_semantic_rules import expected_unit,format_numbers,controller_coverage,semantic_fact

class PromptSemanticRulesTests(unittest.TestCase):
    def test_dimensionless_ratios_including_historical_requested_fields(self):
        for key in ['prescribed_parameters.gap_ratio','prescribed_parameters.requested_gap_ratio','prescribed_parameters.requested_gap_ratio_before_contact_stability_fix']:
            self.assertEqual(expected_unit(key,1.11),'')
    def test_gravity_in_object_name_does_not_turn_geometry_into_acceleration(self):
        self.assertEqual(expected_unit('prescribed_parameters.high_gravity_support_pad_size_m',[.2,.2,.03]),'m')
        self.assertEqual(expected_unit('prescribed_parameters.high_gravity_support_pad_top_z_m',-.355),'m')
        self.assertEqual(expected_unit('prescribed_parameters.gravity_vector_mps2',[0,0,-9.81]),'m/s^2')
    def test_momentum_damping_times_and_angles_have_dimensions(self):
        self.assertEqual(expected_unit('prescribed_parameters.initial_support_bar_linear_momentum_kg_mps',[0,.0165,0]),'kg*m/s')
        self.assertEqual(expected_unit('prescribed_parameters.phone_linear_damping',.03),'1/s')
        self.assertEqual(expected_unit('prescribed_parameters.timeline_target_s.initial_state',[0,.8]),'s')
        self.assertEqual(expected_unit('body.initial_euler_xyz',[0,3,4]),'deg')
    def test_unknown_dimension_fails_closed(self):
        with self.assertRaises(ValueError):expected_unit('future_unknown_parameter',3)
    def test_original_fact_producer_no_longer_reintroduces_bad_units(self):
        from physedit.prompt_contract import from_config
        p={'gap_ratio':1.11,'requested_gap_ratio_before_contact_stability_fix':1.134,'high_gravity_support_pad_size_m':[.2,.2,.03],'phone_linear_damping':.03,'initial_support_bar_linear_momentum_kg_mps':[0,.0165,0],'runtime_force_count':0,'configured_impulse_applicable':True,'timeline_target_s':{'initial_state':[0,.9]}}
        facts={f[0]:(f[-2],f[-1])for f in from_config({'gravity':9.81,'experiment':{'parameter':p}})}
        for key,value in p.items():
            if isinstance(value,dict):continue
            if 'prescribed_parameters.'+key in facts:self.assertEqual(facts['prescribed_parameters.'+key][-1],expected_unit('prescribed_parameters.'+key,value))
        self.assertEqual(facts['prescribed_parameters.timeline_target_s.initial_state'][-1],'s')
    def test_float_noise_fraction_and_scientific_notation(self):
        self.assertEqual(format_numbers('Gap 0.24999999999999994 m; gap 0.006000000000000089 m.'),'Gap 0.25 m; gap 0.006 m.')
        self.assertEqual(format_numbers('Hold 4/5 s. Book 03: frames 0-47 at 30 Hz.'),'Hold 0.8 s. Book 03: frames 0-47 at 30 Hz.')
        self.assertEqual(format_numbers('Very small velocity 1.234567891234e-12 m/s.'),'Very small velocity 1.2345679e-12 m/s.')
    def test_equal_values_for_different_actors_are_not_semantic_duplicates(self):
        ctx=({}, {'left_book':{'name':'left_book','mass':.58,'motion':{'initial_velocity':[1,0,0]}},'right_book':{'name':'right_book','mass':.58,'motion':{'initial_velocity':[1,0,0]}}},{},{})
        a,_=semantic_fact('left_book.mass',.58,ctx);b,_=semantic_fact('right_book.mass',.58,ctx)
        self.assertNotEqual(a,b)
        self.assertIsNone(controller_coverage('right_book.initial_speed',1,ctx,{'left_book.initial_velocity'}))
        self.assertIsNotNone(controller_coverage('left_book.initial_speed',1,ctx,{'left_book.initial_velocity'}))
    def test_axis_and_sign_cannot_be_discarded_by_speed_equality(self):
        ctx=({}, {'marker':{'motion':{'initial_velocity':[1,0,0]}}},{},{})
        self.assertIsNone(controller_coverage('marker.initial_velocity',[0,1,0],ctx,{'marker.initial_velocity'}))
        self.assertIsNone(controller_coverage('marker.initial_velocity',[-1,0,0],ctx,{'marker.initial_velocity'}))
if __name__=='__main__':unittest.main()
