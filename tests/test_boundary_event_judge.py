import unittest
from physedit.boundary_event_judge import normalize_observation, normalize_screened_observation


class ObservationTests(unittest.TestCase):
    def obs(self, state='edge_contact_uncertain', **kw):
        return dict(support_state=state, target_at_end='partially_visible', reason='observed',
                    evidence_image_indices=[0, 12], **kw)

    def test_old_contradiction_is_review(self):
        r=normalize_observation(self.obs(fall=None,event_gate='usable'),13)
        self.assertEqual((r['event_gate'],r['fall']),('review',None))
        self.assertIn('ignored_conflicting_model_event_gate',r['warnings'])

    def test_descent_alone_is_not_fall(self):
        r=normalize_observation(self.obs('detached_descending',descent_evidence_indices=[10,12]),13)
        self.assertEqual(r['event_gate'],'review')

    def test_evidenced_fall(self):
        r=normalize_observation(self.obs('detached_descending',detachment_evidence_indices=[10],descent_evidence_indices=[10,12]),13)
        self.assertEqual((r['event_gate'],r['fall']),('usable',1))

    def test_supported(self):
        self.assertEqual(normalize_observation(self.obs('supported'),13)['fall'],0)

    def test_unobservable_is_review(self):
        self.assertEqual(normalize_observation(self.obs('unobservable'),13)['fall'],None)

    def test_invalid_indices(self):
        for value in ([13],[True],[-1]):
            d=self.obs();d['evidence_image_indices']=value
            with self.assertRaises(ValueError):normalize_observation(d,13)

    def test_duplicate_evidence_is_not_temporal_support(self):
        d=self.obs('supported');d['evidence_image_indices']=[0,0]
        self.assertEqual(normalize_observation(d,13)['event_gate'],'review')

    def test_schema_does_not_certify_truth(self):
        r=normalize_observation(self.obs('detached_descending',detachment_evidence_indices=[10],descent_evidence_indices=[10,12]),13)
        self.assertEqual(r['truth_status'],'unverified_model_observation')

    def test_corruption_rejects_without_binary_label(self):
        d=self.obs('unobservable');d.update(integrity='definite_corruption',corruption_evidence_indices=[0,12])
        r=normalize_screened_observation(d,list(range(13)))
        self.assertEqual((r['event_gate'],r['fall']),('reject',None))

    def test_same_time_corruption_views_are_not_two_frames(self):
        d=self.obs('unobservable');d.update(integrity='definite_corruption',corruption_evidence_indices=[0,1])
        self.assertEqual(normalize_screened_observation(d,[0,0]+list(range(2,13)))['event_gate'],'review')

    def test_uncertain_integrity_never_passes(self):
        d=self.obs('supported');d.update(integrity='uncertain')
        self.assertEqual(normalize_screened_observation(d,list(range(13)))['event_gate'],'review')

if __name__=='__main__':unittest.main()
