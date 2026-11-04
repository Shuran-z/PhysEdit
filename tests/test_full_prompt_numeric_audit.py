import copy
import unittest
import json
from pathlib import Path
from scripts.full_prompt_config_audit import context,resolve,equal
from scripts.repair_and_verify_all_prompts import fact_patterns,match_fact,source_controls,force_number,numeric_value,supplemental_clause
from scripts.repair_prompt_fact_units import typed_unit
from scripts.build_current_prompt_publication import current_context,covered_by_controller


class FullPromptNumericAuditTests(unittest.TestCase):
    def test_runtime_material_override_is_not_source_restitution(self):
        c={'physics':{'source_config':{'dynamic_objects':[{'name':'book','restitution':.4}]},
                      'runtime':{'material_policy':{'restitution':0.}}}}
        self.assertEqual(resolve('book.restitution',0,c,context(c)),(0.,'object.book.restitution'))

    def test_actual_body_overrides_stale_declared_mass(self):
        c={'experiment':{'parameter':{'case_mass_kg':.2}},'dynamic_objects':[{'name':'t11_eyeglasses_case','mass':.2}],
           'actual_physical_parameters':{'bodies':[{'name':'t11_eyeglasses_case','mass':.12}]}}
        self.assertEqual(resolve('prescribed_parameters.case_mass_kg',.2,c,context(c))[0],.12)

    def test_hash_bound_executed_request_outranks_inherited_actual_snapshot(self):
        raw={'objects':[{'name':'book','pose':{'position':[.17273,0,0]},'motion':{'initial_velocity':[1.6107,0,0]}}],
             'actual_physical_parameters':{'bodies':[{'name':'book','pose':{'position':[.149,0,0]},'motion':{'initial_velocity':[1.77,0,0]}}]}}
        row={'config_download':{'sha256':'executed-hash'},'current_render':{'executed_request_sha256':'executed-hash'}}
        ctx=current_context(row,raw)
        self.assertEqual(ctx[1]['book']['motion']['initial_velocity'],[1.6107,0,0])
        row['current_render']['executed_request_sha256']='other-hash'
        self.assertEqual(current_context(row,raw)[1]['book']['motion']['initial_velocity'],[1.77,0,0])

    def test_controller_deduplication_preserves_object_identity_and_axis(self):
        raw={'objects':[{'name':'t02v2_striker_eraser','motion':{'initial_velocity':[0,.17,0]}},
                        {'name':'t02v2_probe_marble','motion':{'initial_velocity':[.17,0,0]}}]}
        ctx=context(raw);keys=['t02v2_striker_eraser.initial_velocity','t02v2_probe_marble.initial_velocity']
        self.assertTrue(covered_by_controller('striker_speed_mps_fixed',.17,ctx,keys))
        self.assertFalse(covered_by_controller('t02v2_striker_eraser.initial_velocity',[.17,0,0],ctx,keys))
        self.assertFalse(covered_by_controller('unrelated_speed_mps',.17,ctx,keys))

    def test_t10_geometry_is_derived_from_own_body(self):
        c={'objects':[{'name':'t10_supported_folder','pose':{'euler_xyz':[0,-39.14,0]}},
                      {'name':'t10_support_pen','pose':{'position':[.1844,.08,.16]}}]}
        self.assertEqual(resolve('t10_supported_folder.initial_angle',38,c,context(c))[0],39.14)
        self.assertEqual(resolve('t10_support_pen.initial_X',.201,c,context(c))[0],.1844)

    def test_unmapped_field_is_not_verified_by_same_number_elsewhere(self):
        c={'unrelated':{'value':3}}
        self.assertIsNone(resolve('book.initial_speed',3,c,context(c))[0])

    def test_numeric_clause_binds_label_not_just_number(self):
        pats=fact_patterns([['t10_support_pen.mass',.095,'kg']])
        self.assertIsNone(match_fact('Tape roll mass 0.095 kg.',pats))
        match=match_fact('Support pen mass 0.18 kg.',pats)
        self.assertEqual(match[0],'t10_support_pen.mass')
        self.assertFalse(equal(match[1],match[2]))

    def test_gravity_label_does_not_consume_magnitude_label(self):
        pats=fact_patterns([['gravity_vector',[0,0,-1.62],'m/s^2'],['prescribed_parameters.gravity_magnitude_mps2',1.62,'m/s^2']])
        m=match_fact('Gravity magnitude mps2 1.62 m/s^2.',pats)
        self.assertEqual(m[0],'prescribed_parameters.gravity_magnitude_mps2')
        m=match_fact('Gravity 1.62 m/s^2.',pats)
        self.assertTrue(equal(m[1],m[2]))

    def test_vector_comparison_preserves_axis_and_sign(self):
        self.assertFalse(equal([1,0,0],[0,1,0]))
        self.assertFalse(equal([1,0,0],[-1,0,0]))
        self.assertTrue(equal([0,.1,0],[0,.10000000000000001,0]))

    def test_fraction_shortening_preserves_force_value(self):
        value=.19333333333333333
        self.assertEqual(force_number(value),'29/150')
        self.assertTrue(equal(numeric_value(force_number(value)),value))
        self.assertNotIn('/',force_number(.19333123456789))

    def test_force_related_counts_are_not_newtons(self):
        self.assertEqual(typed_unit('prescribed_parameters.runtime_force_count',0,'N'),'')
        self.assertEqual(typed_unit('prescribed_parameters.driver_force_after_second_contact_frames',2,'N'),'frames')
        self.assertEqual(typed_unit('prescribed_parameters.support_pull_force_active_frame_range',[0,32],'N'),'frame index')
        self.assertEqual(typed_unit('prescribed_parameters.configured_impulse_applicable',True,'N*s'),'')
        self.assertEqual(typed_unit('support_pull_force_magnitude_n',.46,'N'),'N')

    def test_kinematic_ordinal_is_checked_against_own_config(self):
        c={'experiment':{'extracted_book_name':'t18_book_03','extraction_index_zero_based':3,'extraction_position_one_based':4,'book_count':6},
           'objects':[{'name':'t18_book_03','fixed':True,'motion':{'type':'scripted_keyframes'}}]}
        r={'scene':'T18'};ctx=context(c)
        result=supplemental_clause('Book 4 of 6 stays kinematic.',r,c,ctx)
        self.assertEqual(result['replacement'],'Book 03 kinematic; 6 books.')
        with self.assertRaises(AssertionError):supplemental_clause('Book 5 of 6 stays kinematic.',r,c,ctx)

    def test_isaac_actual_push_does_not_inherit_contact_feedback(self):
        root=Path(__file__).resolve().parents[1]
        fixture=json.loads((root/'review/full_prompt_audit_20261102/SCHEMAS.json').read_text(encoding='utf8'))['isaac/T11']
        row={'canonical_video_id':fixture['id'],'engine':'isaac','scene':'T11','parameter_facts':fixture['facts'],
             'external_control_inputs':fixture['external'],'prompt_variants_en':['Fixed camera.']*3}
        n,_,_=source_controls(row,fixture['config'],context(fixture['config']))
        text=' '.join(n['source_control_clauses'])
        self.assertIn('frames 0-47 at 30 Hz',text)
        self.assertNotIn('if eraser',text)
        self.assertNotIn('0.55 N',text)

if __name__=='__main__':unittest.main()
