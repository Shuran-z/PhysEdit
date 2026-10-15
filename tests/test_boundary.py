"""Regression: valid negative outcomes survive missing inversion and generation failures."""
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

from physedit.boundary import digest, distance, plan, run, score, write_rows


class BoundaryTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name)
        image=self.root/'image.png';image.write_bytes(b'test condition')
        inputs=[];keys=[]
        for i,y in enumerate((0,1)):
            sid=f'p{i}'
            inputs.append(dict(sample_id=sid,condition_image=str(image),condition_sha256=digest(image),
                prompt='Move at the requested velocity',seed=i,num_frames=3,fps=2,
                evaluation_duration_s=1,source_width=16,source_height=16))
            keys.append(dict(sample_id=sid,scene_id='T15',source_group_id='s',family_id='f',point_id=sid,
                theta=i,target_event='fall',events={'fall':y},gravity=9.81,pair_ids=['pair'],
                inversion={'status':'not_applicable' if i==0 else 'eligible','reason':'registered',
                           'reference_registration_sha256':'reference'}))
        write_rows(self.root/'inputs.jsonl',inputs);write_rows(self.root/'answers.jsonl',keys)
        self.spec=dict(model='test',inputs=str(self.root/'inputs.jsonl'),answers=str(self.root/'answers.jsonl'),
                       generation_command=[sys.executable,'-c','pass'])

    def tearDown(self):self.tmp.cleanup()

    def prepared(self):
        def fake_media(path,row):
            path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(b'cpu test media')
            return dict(status='ok',video=str(path),video_sha256=digest(path))
        with patch('physedit.boundary.media',side_effect=fake_media):run(self.spec,self.root/'run')
        return self.root/'run'

    def annotations(self,root,labels=(0,1)):
        observed=[json.loads(s) for s in (root/'observed_rows.jsonl').read_text().splitlines()]
        path=self.root/'events.jsonl'
        write_rows(path,[dict(sample_id=o['sample_id'],video_sha256=o['video_sha256'],
                 method='unit_test_fixture',events={'fall':y},evidence='synthetic regression fixture')
                 for o,y in zip(observed,labels)])
        return path

    def test_no_inversion_gate(self):
        self.assertEqual(plan(self.spec)['generation_candidates'],2)
        root=self.prepared()
        export=[json.loads(s) for s in (root/'generation_rows.jsonl').read_text().splitlines()]
        self.assertEqual(len(export),2)
        for r in export:
            self.assertFalse(set(r)&{'events','inversion','boundary','theta','reference_target'})
        result=score(root,self.annotations(root))
        self.assertEqual(result['registered'],2)
        self.assertEqual(result['balanced_accuracy'],1)
        self.assertEqual(result['independent_pair_accuracy'],1)
        self.assertIsNone(result['near_accuracy'])
        self.assertEqual(result['inversion']['statuses'],{'not_applicable':1,'missing':1})

    def test_missing_annotation_remains_failure(self):
        root=self.prepared();r=score(root)
        self.assertEqual(r['registered'],2);self.assertEqual(r['balanced_accuracy'],0)
        self.assertEqual(r['annotations_bound'],0)

    def test_constant_answer_does_not_pass_pair(self):
        root=self.prepared();r=score(root,self.annotations(root,(1,1)))
        self.assertEqual(r['balanced_accuracy'],.5);self.assertEqual(r['independent_pair_accuracy'],0)

    def test_at_bound_not_success(self):
        root=self.prepared();path=self.root/'gravity.jsonl'
        write_rows(path,[dict(sample_id='p1',status='at_bound',gravity=9.81)])
        result=score(root,gravity=path)
        self.assertEqual(result['inversion']['fitted'],0)
        self.assertEqual(result['inversion']['statuses']['at_bound'],1)

    def test_all_generation_failures_retained(self):
        root=self.root/'run';run(self.spec,root);r=score(root)
        self.assertEqual(r['registered'],2);self.assertEqual(r['scored_rows'],2)
        self.assertEqual(r['balanced_accuracy'],0)

    def test_unknown_prediction_rejected(self):
        root=self.prepared();p=self.root/'bad.jsonl'
        write_rows(p,[dict(sample_id='alien')])
        with self.assertRaises(ValueError):score(root,p)

    def test_changed_key_rejected(self):
        root=self.prepared()
        with (root/'answers.jsonl').open('a') as f:f.write('\n')
        with self.assertRaises(ValueError):score(root)

    def test_changed_video_invalidates_annotation(self):
        root=self.prepared();ann=self.annotations(root)
        (root/'generated'/'p1'/'resized.mp4').write_bytes(b'changed')
        self.assertEqual(score(root,ann)['balanced_accuracy'],.5)

    def test_distance_interval_ambiguity(self):
        k=dict(theta=.06,boundary=dict(status='verified',source='search',normalization_span=1,bracket=[0,.02]))
        self.assertIsNone(distance(k)['bin'])
        k['theta']=.03
        self.assertEqual(distance(k)['bin'],'near')

    def test_existing_output_not_overwritten(self):
        root=self.prepared()
        with self.assertRaises(FileExistsError):run(self.spec,root)

    def test_short_native_clock_rejected(self):
        p=self.root/'inputs.jsonl'
        rows=[json.loads(s) for s in p.read_text().splitlines()]
        rows[0]['evaluation_duration_s']=2
        p.write_text(''.join(json.dumps(r)+'\n' for r in rows))
        with self.assertRaises(ValueError):plan(self.spec)

    def test_pilot_posix_condition_path_and_both_sides(self):
        from scripts.build_t15_boundary_run import build
        audit=Path(__file__).resolve().parents[1]/'review/t15_boundary_pilot_20261014'
        if not (audit/'reference_audit.json').exists() or not (Path(__file__).resolve().parents[1]/'scripts/build_t15_boundary_run.py').exists():
            self.skipTest('local pilot evidence and builder are not distributed with the reusable core')
        rows,keys=build(audit,self.root/'pilot','/remote/conditions')
        self.assertEqual(rows[0]['condition_image'],'/remote/conditions/g03_earth.png')
        self.assertEqual([k['events']['laptop_falls_to_floor'] for k in keys],[0,1])
        self.assertNotEqual(rows[0]['seed'],rows[1]['seed'])

    def test_successful_gravity_reports_both_denominators(self):
        root=self.prepared();observed=[json.loads(s) for s in (root/'observed_rows.jsonl').read_text().splitlines()]
        path=self.root/'gravity.jsonl'
        write_rows(path,[dict(sample_id='p1',status='ok',gravity=9.81,
                             video_sha256=observed[1]['video_sha256'],reference_registration_sha256='reference')])
        g=score(root,gravity=path)['inversion']
        self.assertEqual(g['registered_coverage'],.5)
        self.assertEqual(g['eligible_fit_coverage'],1)
        self.assertEqual(g['relative_deviation_mean'],0)

    def test_input_hash_failure_preserves_other_point(self):
        path=self.root/'inputs.jsonl';rows=[json.loads(s) for s in path.read_text().splitlines()]
        rows[0]['condition_sha256']='wrong'
        path.write_text(''.join(json.dumps(r)+'\n' for r in rows))
        root=self.prepared()
        self.assertEqual(len((root/'generation_rows.jsonl').read_text().splitlines()),1)
        self.assertEqual(score(root)['registered'],2)

    def test_duplicate_registration_rejected(self):
        path=self.root/'inputs.jsonl';first=path.read_text().splitlines()[0]
        with path.open('a') as f:f.write(first+'\n')
        with self.assertRaises(ValueError):plan(self.spec)

    def test_shared_seeds_not_mislabelled_independent(self):
        path=self.root/'inputs.jsonl';rows=[json.loads(s) for s in path.read_text().splitlines()]
        rows[1]['seed']=rows[0]['seed']
        path.write_text(''.join(json.dumps(r)+'\n' for r in rows))
        with self.assertRaises(ValueError):plan(self.spec)

    def test_runner_checks_available_gpu_capacity(self):
        from physedit.runners.boundary_ltx import check_gpu
        with patch('subprocess.check_output',return_value='0, 20000, 2\n'):
            check_gpu(0)
        with patch('subprocess.check_output',return_value='0, 13000, 2\n'):
            with self.assertRaises(RuntimeError):check_gpu(0)
        with patch('subprocess.check_output',return_value='0, 20000, 50\n'):
            with self.assertRaises(RuntimeError):check_gpu(0)


if __name__=='__main__':unittest.main()
