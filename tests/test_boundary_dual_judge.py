import unittest
from physedit.boundary_dual_judge import route_dual

class DualTests(unittest.TestCase):
    def fixture(self):
        rec={'confidence':.95,'evidence':[0,1],'reason':'visible evidence'}
        return {'quality':dict(rec,status='measurable',failure='none'),
                'frames':[{'index':i,'identity':'same','location':'tabletop'} for i in range(2)],
                'events':{k:dict(rec,label='no') for k in ('departure','descent','landing')}}
    def test_prelabel_not_ground_truth(self):
        r=route_dual(self.fixture(),[0,10],{0:[0,0,10,10],10:[0,0,10,10]})
        self.assertEqual(r['events']['descent']['route'],'preannotated')
        self.assertEqual(r['events']['landing']['route'],'review')
    def test_high_confidence_conflict(self):
        r=route_dual(self.fixture(),[0,10],{0:[0,0,10,10],10:[0,80,10,90]})
        self.assertEqual(r['events']['descent']['route'],'review')
    def test_low_confidence_per_event(self):
        d=self.fixture();d['events']['descent']['confidence']=.5
        r=route_dual(d,[0,10],{0:[0,0,10,10],10:[0,0,10,10]})
        self.assertEqual(r['events']['departure']['route'],'preannotated')
        self.assertEqual(r['events']['descent']['route'],'review')
    def test_reject_retains_denominator(self):
        d=self.fixture();d['quality'].update(status='unmeasurable',failure='fusion')
        r=route_dual(d,[0,10],{})
        self.assertTrue(r['retain_in_denominator']);self.assertEqual(r['events']['descent']['route'],'blocked_quality')
    def test_malformed_evidence_review(self):
        d=self.fixture();d['events']['departure']['evidence']=[{}]
        self.assertEqual(route_dual(d,[0,10],{})['events']['departure']['route'],'review')
    def test_explicit_frame_text_preserved(self):
        d=self.fixture();d['quality']['evidence']=['Frame 0: visible','Frame 1: visible']
        r=route_dual(d,[0,10],{0:[0,0,10,10],10:[0,0,10,10]})
        self.assertEqual(r['quality']['evidence'],[0,1]);self.assertIn('raw_evidence',r['quality'])

if __name__=='__main__':unittest.main()
