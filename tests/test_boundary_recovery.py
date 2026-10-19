import unittest
from physedit.boundary_recovery import recover,observed_distances
from physedit.boundary import distance
def point(t,label,valid=True):return dict(sample_id=str(t),theta=t,label=label,valid=valid)
class RecoveryTests(unittest.TestCase):
 def test_observed_interval_and_distance(self):
  r=recover([point(1,0),point(2,0),point(3,1)])
  self.assertEqual(r['intervals'][0]['bracket'],[2,3])
  self.assertEqual(observed_distances(1,r)[0]['absolute_distance_interval'],[1,2])
  self.assertIsNone(r['exact_threshold'])
 def test_conflict_blocks_adjacency(self):
  self.assertEqual(recover([point(1,0),point(2,0),point(2,1),point(3,1)])['intervals'],[])
 def test_invalid_blocks_adjacency(self):
  self.assertEqual(recover([point(1,0),point(2,None,False),point(3,1)])['intervals'],[])
 def test_nonmonotonic_keeps_all_transitions(self):
  r=recover([point(1,0),point(2,1),point(3,0)])
  self.assertTrue(r['multiple_transitions']);self.assertEqual(len(r['intervals']),2)
 def test_observed_distance_does_not_certify_near_bin(self):
  r=recover([point(2,0),point(3,1)])
  d=distance(dict(theta=1,boundary=dict(status='observed',source='audit',intervals=r['intervals'])))
  self.assertEqual(d['status'],'observed_transition_distance');self.assertIsNone(d['bin'])
  self.assertEqual(d['absolute_distance_intervals'][0]['absolute_distance_interval'],[1,2])
if __name__=='__main__':unittest.main()
