import json
from pathlib import Path

from physedit import core100_tasks as task_export
from physedit.boundary import read_rows


def test_tasks_bind_exactly_the_15_changed_inputs_and_preserve_old_results(tmp_path):
    out=tmp_path/'tasks';result=task_export.export(out)
    rows=read_rows(out/'tasks.jsonl')
    assert result['required_new_inputs']==15 and result['generation_positions_per_model']==45
    assert {r['clip_id']for r in rows}=={'T03_C02','T04_C01','T04_C02','T04_C03','T05_C01','T05_C03',
        'T06_C02','T06_C03','T10_C01','T10_C02','T10_C05','T11_C01','T11_C02','T18_C01','T18_C02'}
    assert all(r['roster_release']=='core100-critical-pairs-v4-20261103'for r in rows)
    assert all(r['status']=='generation_and_annotation_required'for r in rows)
    assert next(r for r in rows if r['clip_id']=='T03_C02')['reason']=='camera_cam03_to_cam02'


def test_generation_and_blind_review_exports_do_not_contain_answers(tmp_path):
    out=tmp_path/'tasks';task_export.export(out)
    gen=read_rows(out/'generation_tasks.jsonl');reviews=read_rows(out/'annotation_tasks.jsonl')
    forbidden={'reference_events','theta','boundary','distance','label','gravity_truth'}
    assert all(not forbidden.intersection(r)for r in gen+reviews)
    assert all('events'not in r and not r['reuse_legacy_generated_output']for r in gen)
    assert all(r['generated_video_sha256']is None and r['event_labels']is None and not r['reuse_legacy_annotations_or_scores']for r in reviews)
    assert all(len(r['prompt_variants_en'])==3 and not Path(r['condition_image']).is_absolute()for r in gen)


def test_task_bundle_never_overwrites_existing_work(tmp_path):
    import pytest
    out=tmp_path/'tasks';task_export.export(out)
    before=(out/'MANIFEST.json').read_bytes()
    with pytest.raises(FileExistsError):task_export.export(out)
    assert (out/'MANIFEST.json').read_bytes()==before
