"""Readiness must be evidence-driven, not a constant-zero or distance-only count."""
import unittest
from scripts.audit_nearacc_readiness import readiness
class ReadinessTests(unittest.TestCase):
 def valid(self):
  return dict(theta=.02,reference_label=1,boundary=dict(status='verified',source='registered_search',theta_star=0,normalization_span=1),blocking_reasons=[])
 def test_verified_near_can_be_counted(self):
  ok,reasons,d=readiness(self.valid());self.assertTrue(ok);self.assertEqual(reasons,[]);self.assertEqual(d['bin'],'near')
 def test_observed_is_not_formal(self):
  e=self.valid();e['boundary']['status']='observed'
  ok,reasons,_=readiness(e);self.assertFalse(ok);self.assertIn('boundary_not_verified',reasons)
 def test_missing_answer_is_not_eligible(self):
  e=self.valid();del e['reference_label'];self.assertFalse(readiness(e)[0])
 def test_far_not_counted_as_near(self):
  e=self.valid();e['theta']=.3;self.assertFalse(readiness(e)[0])
 def test_pending_reference_binding_preserved(self):
  e=self.valid();e['blocking_reasons']=['reference_binding_pending'];self.assertFalse(readiness(e)[0])
 def test_uncertain_bin_not_counted(self):
  e=self.valid();e['theta']=.06;e['boundary'].pop('theta_star');e['boundary']['bracket']=[0,.02]
  self.assertFalse(readiness(e)[0])
if __name__=='__main__':unittest.main()
