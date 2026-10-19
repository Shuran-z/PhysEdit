import copy
import json
import tempfile
import sys
import unittest
from pathlib import Path
from unittest.mock import patch
from scripts.reference_visual_admission import apply_review, load_reviews
from physedit.boundary import digest, plan, run, score, write_rows

OUT = Path('review/scene_family_completion_20261018')

class VisualAdmissionTests(unittest.TestCase):
    def test_identity_and_evidence_guards(self):
        r=json.loads((OUT/'near375_visual/frozen_candidates.json').read_text())[0]
        v=load_reviews()[(r['engine'],r['sample_id'])]
        self.assertEqual(apply_review(r,v)['blocking_reasons'],[])
        bad=copy.deepcopy(v);bad['video_sha256']='changed'
        with self.assertRaises(ValueError):apply_review(r,bad)
        bad=copy.deepcopy(v);bad['reference_state_sha256']='changed'
        with self.assertRaises(ValueError):apply_review(r,bad)
        bad=copy.deepcopy(v);bad['evidence_sha256']='changed'
        with self.assertRaises(ValueError):apply_review(r,bad)
        r['blocking_reasons'].append('other_pending')
        self.assertIn('other_pending',apply_review(r,v)['blocking_reasons'])

    def test_admitted_roster_through_real_scorer_synthetic_predictions(self):
        # Real reference bindings; synthetic media/predictions strictly for plumbing.
        keys=[json.loads(x) for x in (OUT/'admitted_near_reference_answers.jsonl').read_text(encoding='utf-8').splitlines()]
        self.assertEqual(len(keys),72)
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);image=root/'fixture.png';image.write_bytes(b'fixture only')
            inputs=[dict(sample_id=k['sample_id'],condition_image=str(image),condition_sha256=digest(image),prompt='synthetic plumbing fixture',seed=0,num_frames=210,fps=30,evaluation_duration_s=209/30,source_width=16,source_height=16) for k in keys]
            write_rows(root/'inputs.jsonl',inputs);write_rows(root/'answers.jsonl',keys)
            spec=dict(model='SYNTHETIC_TEST_ONLY',inputs=str(root/'inputs.jsonl'),answers=str(root/'answers.jsonl'),generation_command=[sys.executable,'-c','pass'])
            self.assertEqual(plan(spec)['generation_candidates'],72)
            def fake_media(path,row):
                path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(b'fixture')
                return dict(status='ok',video=str(path),video_sha256=digest(path))
            with patch('physedit.boundary.media',side_effect=fake_media):run(spec,root/'run')
            observations=[json.loads(x) for x in (root/'run/observed_rows.jsonl').read_text().splitlines()]
            for name,value,expected in [('oracle',None,1),('constant',1,.5)]:
                ann=[dict(sample_id=k['sample_id'],video_sha256=o['video_sha256'],method='synthetic_test',evidence='not a model result',events=k['events'] if value is None else {k['target_event']:value}) for k,o in zip(keys,observations)]
                write_rows(root/(name+'.jsonl'),ann)
                result=score(root/'run',root/(name+'.jsonl'))
                self.assertEqual(result['near_accuracy'],expected)
                self.assertEqual(result['registered'],72)
            result=score(root/'run')
            self.assertEqual(result['registered'],72)
            self.assertEqual(result['near_accuracy'],0)

if __name__=='__main__':unittest.main()
