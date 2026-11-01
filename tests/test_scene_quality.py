import copy
import unittest

from physedit.scene_quality import CHECKS, normalize_quality, scene_quality_route
from physedit.boundary_pipeline import quality_route


class SceneQualityTests(unittest.TestCase):
    def payload(self):
        return dict(initial_inventory='Books on a table; empty sofa behind.', contradictions=[],
            checks={name:dict(label='absent',evidence_indices=[0,2],reason='Initial objects and setting remain visible.') for name in CHECKS})

    def test_new_head_blocks_even_when_books_remain_intact(self):
        data=self.payload()
        data['checks']['foreign_objects']=dict(label='present',evidence_indices=[1,2],reason='A giant head absent from the initial scene appears behind the intact books.')
        result=normalize_quality(data,[0.,1.,2.])
        self.assertEqual(result['failure'],'new_object_intrusion')
        self.assertEqual(quality_route({'status':'ok','quality':result},{'window_s':2.},.9),'auto_rejected')

    def test_scene_replacement_is_an_independent_rejection(self):
        data=self.payload();data['checks']['scene_replacement'].update(label='present',evidence_indices=[1,2])
        self.assertEqual(scene_quality_route(normalize_quality(data,[0.,1.,2.]),2.),'auto_rejected')

    def test_observable_wrong_physics_can_pass_scene_integrity(self):
        data=self.payload();data['checks']['geometry_corruption']['reason']='Books float but retain identities and shape; the original scene is unchanged.'
        self.assertEqual(scene_quality_route(normalize_quality(data,[0.,1.,2.]),2.),'pass')

    def test_duplicate_crops_do_not_make_two_temporal_observations(self):
        data=self.payload();data['checks']['foreign_objects'].update(label='present',evidence_indices=[1,2])
        result=normalize_quality(data,[0.,1.,1.])
        self.assertEqual(scene_quality_route(result,1.),'review')

    def test_absent_requires_initial_and_final_evidence(self):
        data=self.payload();data['checks']['foreign_objects']['evidence_indices']=[0,1]
        self.assertEqual(scene_quality_route(normalize_quality(data,[0.,1.,2.]),2.),'review')

    def test_initial_anchor_is_not_a_second_post_intrusion_frame(self):
        data=self.payload();data['checks']['foreign_objects'].update(label='present',evidence_indices=[0,2])
        self.assertEqual(scene_quality_route(normalize_quality(data,[0.,1.,2.]),2.),'review')

    def test_conflicts_and_uncertainty_cannot_pass(self):
        data=self.payload();data['contradictions']=['Identity cannot be followed at the end.']
        self.assertEqual(scene_quality_route(normalize_quality(data,[0.,1.,2.]),2.),'review')
        data=self.payload();data['checks']['identity_loss']['label']='uncertain'
        self.assertEqual(scene_quality_route(normalize_quality(data,[0.,1.,2.]),2.),'review')

    def test_invalid_or_unsupplied_evidence_is_not_silently_repaired(self):
        for indices in ([3],[True],[-1],[1.5]):
            data=self.payload();data['checks']['foreign_objects']['evidence_indices']=indices
            with self.assertRaises(ValueError):normalize_quality(data,[0.,1.,2.])
        data=self.payload();del data['checks']['foreign_objects']
        with self.assertRaises(ValueError):normalize_quality(data,[0.,1.,2.])

    def test_failed_vlm_cannot_become_a_rejection(self):
        data=self.payload();data['checks']['foreign_objects'].update(label='present',evidence_indices=[1,2])
        result=normalize_quality(data,[0.,1.,2.])
        self.assertEqual(quality_route({'status':'evaluator_failure','quality':result},{'window_s':2.},.9),'review')

    def test_legacy_quality_gate_is_unchanged(self):
        legacy=dict(status='measurable',failure='none',target_integrity='intact',support_integrity='intact',confidence=.95,evidence_times_s=[0,2],reason='Visible target')
        self.assertEqual(quality_route({'status':'ok','quality':legacy},{'window_s':2.},.9),'pass')
        legacy=copy.deepcopy(legacy);legacy['confidence']=0
        self.assertEqual(quality_route({'status':'ok','quality':legacy},{'window_s':2.},.9),'review')


if __name__=='__main__':unittest.main()
