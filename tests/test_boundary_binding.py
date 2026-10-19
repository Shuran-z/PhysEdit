import copy
import json
from pathlib import Path
import tempfile
import unittest
from physedit.boundary import digest, distance
from physedit.boundary_binding import bind


class BindingTests(unittest.TestCase):
    def test_snapshot_source_and_context(self):
        with tempfile.TemporaryDirectory() as directory:
            p=Path(directory);src=p/'search.json';src.write_text('{}')
            key=dict(sample_id='a',reference_sample_id='ref',reference_state_sha256='state',source_group_id='context',target_event='fall',theta=1.9,boundary={'status':'unavailable'})
            answers=p/'answers.jsonl';answers.write_text(json.dumps(key)+'\n')
            row={k:v for k,v in key.items() if k!='boundary'}
            row.update(source_file='search.json',source_sha256=digest(src),mapping_status='matched',mapping_evidence='same version/state/control',parameter_name='speed',parameter_unit='m/s',normalization_basis='frozen range',boundary={'status':'verified','theta_star':2.,'normalization_span':10.})
            data=dict(answers_sha256=digest(answers),bindings=[row]);f=p/'bindings.json'
            f.write_text(json.dumps(data));bound,receipt=bind([key],f,answers)
            self.assertEqual(distance(bound[0])['bin'],'near')
            self.assertEqual(receipt['registered'],1)
            self.assertEqual(key['boundary']['status'],'unavailable')
            for field in ('reference_sample_id','reference_state_sha256','source_group_id','target_event','theta'):
                wrong=copy.deepcopy(data);wrong['bindings'][0][field]='wrong';f.write_text(json.dumps(wrong))
                with self.assertRaises(ValueError):bind([key],f,answers)
            f.write_text(json.dumps(data));src.write_text('{"changed":true}')
            with self.assertRaises(ValueError):bind([key],f,answers)

    def test_unmatched_stays_unavailable(self):
        with tempfile.TemporaryDirectory() as directory:
            p=Path(directory);src=p/'search.json';src.write_text('{}')
            key=dict(sample_id='a',reference_sample_id='ref',reference_state_sha256='state',source_group_id='context',target_event='fall',theta=1.9)
            a=p/'answers.jsonl';a.write_text(json.dumps(key)+'\n')
            row=dict(key,source_file='search.json',source_sha256=digest(src),mapping_status='version_mismatch',boundary={'status':'unavailable'},reason='duration is not speed')
            f=p/'binding.json';f.write_text(json.dumps(dict(answers_sha256=digest(a),bindings=[row])))
            bound,receipt=bind([key],f,a)
            self.assertEqual(receipt['bound'],0)
            self.assertIsNone(distance(bound[0])['bin'])

if __name__=='__main__':unittest.main()
