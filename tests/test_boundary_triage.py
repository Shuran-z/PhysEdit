import unittest
from physedit.boundary_triage import route,parse_with_closing_brace_repair

class TriageTests(unittest.TestCase):
    def test_only_missing_final_brace_repaired(self):
        result,fix=parse_with_closing_brace_repair('{"events":{"label":"yes"}')
        self.assertEqual(result,{'events':{'label':'yes'}});self.assertIsNotNone(fix)
        with self.assertRaises(ValueError):parse_with_closing_brace_repair('{"label":"ye')
    def data(self):
        r={'confidence':.95,'evidence':[0,1],'reason':'pixels'}
        return {'quality':dict(r,status='measurable'), 'events':{k:dict(r,label='yes',relation='detached') for k in ('departure','descent','landing')}}
    def test_unseen_landing_not_manual_binary(self):
        d=self.data();d['events']['landing'].update(label='not_observed',relation='unobservable')
        r=route(d,[0,10],{0:[0,0,10,10],10:[0,30,10,40]})
        self.assertEqual(r['events']['descent']['route'],'preannotated')
        self.assertEqual(r['events']['landing']['route'],'observation_only')
        self.assertIsNone(r['events']['landing']['accepted_label'])
    def test_corruption_two_times(self):
        d=self.data();d['quality'].update(status='unmeasurable',failure='fusion')
        self.assertEqual(route(d,[0,0],{})['quality']['route'],'review')
        self.assertEqual(route(d,[0,10],{})['quality']['route'],'reject_measurement')
    def test_confident_edge_contact_not_fall(self):
        d=self.data();d['events']['descent']['relation']='uncertain'
        self.assertEqual(route(d,[0,10],{0:[0,0,10,10],10:[0,30,10,40]})['events']['descent']['route'],'review')
    def test_motion_never_proves_detachment(self):
        d=self.data();d['events']['departure']['label']='uncertain'
        self.assertEqual(route(d,[0,10],{})['events']['departure']['route'],'review')
    def test_low_confidence_local_only(self):
        d=self.data();d['events']['landing'].update(label='uncertain',confidence=.4)
        r=route(d,[0,10],{0:[0,0,10,10],10:[0,30,10,40]})
        self.assertEqual(r['events']['descent']['route'],'preannotated')
        self.assertEqual(r['events']['landing']['route'],'review')

if __name__=='__main__':unittest.main()
