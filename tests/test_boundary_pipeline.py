import json
from unittest.mock import patch
from tests.test_boundary import BoundaryTests
from physedit.boundary import write_rows
from physedit.boundary_pipeline import run_pipeline

class PipelineTests(BoundaryTests):
    def setup_pipeline(self):
        root=self.prepared();p=self.root/'protocol.json'
        protocol={'samples':{sid:{'target':'test object','events':{'fall':{'definition':'visible departure and descent','minimum_evidence_times':2}}} for sid in ('p0','p1')},
                  'quality_command':['quality','{manifest}','{output}'],'event_command':['events','{manifest}','{output}']}
        p.write_text(json.dumps(protocol));return root,p

    def test_sequential_gates_and_human_only_scores(self):
        root,p=self.setup_pipeline();calls=[]
        def provider(command,manifest,output,log,timeout):
            jobs=[json.loads(x) for x in manifest.read_text().splitlines()];calls.append(command[0]);records=[]
            for j in jobs:
                self.assertFalse(set(j)&{'answers','theta','gravity','reference_event','boundary'})
                r={'sample_id':j['sample_id'],'video_sha256':j['video_sha256'],'status':'ok'}
                evidence={'confidence':.95,'evidence_times_s':[0,1],'reason':'synthetic test only'}
                if command[0]=='quality':
                    self.assertNotIn('events',j)
                    r['quality']=dict(evidence,status='measurable' if j['sample_id']=='p0' else 'unmeasurable',failure='none' if j['sample_id']=='p0' else 'fusion',target_integrity='intact',support_integrity='intact')
                else:
                    self.assertEqual(j['sample_id'],'p0')
                    r['events']={'fall':dict(evidence,label='no',contradictions=[])}
                records.append(r)
            write_rows(output,records);return {'returncode':0}
        out=self.root/'judged'
        with patch('physedit.boundary_pipeline.invoke',side_effect=provider):receipt=run_pipeline(root,p,out,execute=True)
        self.assertEqual(calls,['quality','events']);self.assertEqual(receipt['registered'],2)
        self.assertEqual(receipt['events_scheduled'],1);self.assertEqual(receipt['preannotated_event_count'],1)
        score=json.loads((out/'scores.json').read_text());self.assertEqual(score['registered'],2);self.assertEqual(score['balanced_accuracy'],0)
        observed=[json.loads(l) for l in (root/'observed_rows.jsonl').read_text().splitlines()]
        reviews=self.root/'reviews.jsonl'
        write_rows(reviews,[dict(sample_id=o['sample_id'],video_sha256=o['video_sha256'],reviewer='tester',evidence='fixture adjudication',quality_status='pass' if o['sample_id']=='p0' else 'confirmed_failure',events={'fall':{'label':0,'evidence':'visible throughout'}} if o['sample_id']=='p0' else {}) for o in observed])
        run_pipeline(root,p,self.root/'reviewed',out/'quality_predictions.jsonl',out/'event_predictions.jsonl',reviews)
        score=json.loads((self.root/'reviewed/scores.json').read_text());self.assertEqual(score['registered'],2);self.assertEqual(score['screening']['confirmed_failure_count'],1)

    def test_missing_judges_preserve_roster(self):
        root,p=self.setup_pipeline();receipt=run_pipeline(root,p,self.root/'pending')
        self.assertEqual(receipt['registered'],2);self.assertEqual(receipt['events_scheduled'],0)

    def test_hash_mismatch_aborts(self):
        root,p=self.setup_pipeline();q=self.root/'q.jsonl';write_rows(q,[{'sample_id':'p0','video_sha256':'wrong'}])
        with self.assertRaises(ValueError):run_pipeline(root,p,self.root/'wrong',q)
