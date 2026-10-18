import unittest
from physedit.boundary_window import select_frames,route_observations

class WindowTests(unittest.TestCase):
    def test_no_future_frames(self):
        tracks=[{'frame':i,'bbox_xyxy':[0,i,10,i+10]} for i in range(100)]
        a,_=select_frames(tracks,40);b,_=select_frames(tracks[:41],40)
        self.assertEqual(a,b);self.assertLessEqual(max(a),40)
    def test_fall_without_landing(self):
        d={'frames':[{'index':i,'location':s,'identity':'same'} for i,s in enumerate(['tabletop','airborne','airborne'])]}
        r=route_observations(d,[0,10,20],{0:[0,0,10,10],10:[0,20,10,30],20:[0,40,10,50]})
        self.assertEqual(r['descent'],1);self.assertIsNone(r['landing'])
        self.assertEqual(r['landing_observation'],'not_observed')
    def test_confident_wrong_support_review(self):
        d={'frames':[{'index':i,'location':'tabletop','identity':'same'} for i in range(3)]}
        r=route_observations(d,[0,10,20],{0:[0,0,10,10],10:[0,20,10,30],20:[0,40,10,50]})
        self.assertEqual(r['route'],'review');self.assertIsNone(r['descent'])
    def test_unknown_not_negative(self):
        d={'frames':[{'index':0,'location':'uncertain','identity':'uncertain'}]}
        self.assertIsNone(route_observations(d,[0],{})['descent'])
    def test_disputed_landing_keeps_upstream(self):
        d={'frames':[{'index':i,'location':s,'identity':'same'} for i,s in enumerate(['tabletop','airborne','airborne','ground','ground'])]}
        r=route_observations(d,list(range(5)),{i:[0,i*20,10,i*20+10] for i in range(5)})
        self.assertEqual(r['descent'],1);self.assertIsNone(r['landing'])
        self.assertEqual(r['route'],'review');self.assertEqual(r['event_routes']['descent'],'candidate_usable')

if __name__=='__main__':unittest.main()
