import unittest
from physedit.known_conditions import reference_times,generated_times,effective_friction,require_parameter_truth

class KnownConditionContracts(unittest.TestCase):
    def setUp(self):
        self.c={'clock':{'status':'verified','physical_dt_s':0.02,'media_fps':30,'release_frame':18,'frame_count':210},'verified_parameter_truth':{}}
    def test_reference_release_origin(self):
        self.assertEqual(reference_times(self.c,[18,19,23]),[0,0.02,0.1])
        with self.assertRaisesRegex(ValueError,'held_prefix'):
            reference_times(self.c,[17,18])
    def test_realtime_does_not_inherit_reference_slowdown(self):
        self.assertEqual(generated_times(self.c,[0,25],25),[0,1])
        with self.assertRaisesRegex(ValueError,'explicit_generation'):
            generated_times(self.c,[0,25],25,time_contract='legacy_media')
        self.assertEqual(generated_times(self.c,[0,25],25,time_contract='legacy_media',legacy_rate_disclosed=True),[0,0.6])
    def test_unknown_background_is_not_promoted_to_one(self):
        with self.assertRaisesRegex(ValueError,'not_verified'):
            effective_friction({'status':'historical_runtime_unverified','current_code_default_candidate':1})
    def test_contact_combination_and_hidden_object_coefficient(self):
        pair={'status':'verified','material_a':0.2,'material_b':0.52,'combine_rule':'genesis_max_floor_0.01'}
        self.assertEqual(effective_friction(pair),0.52)
        with self.assertRaisesRegex(ValueError,'masked'):
            require_parameter_truth(self.c,'object_friction',pair=pair)
    def test_conflicting_config_rejected(self):
        self.c['configuration_status']='conflicting_historical_versions'
        with self.assertRaisesRegex(ValueError,'provenance_conflict'):
            require_parameter_truth(self.c,'gravity')

if __name__=='__main__':unittest.main()
