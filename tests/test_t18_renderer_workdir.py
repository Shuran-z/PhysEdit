import json
from pathlib import Path
import pytest
from scripts.t18_table_contact_boundary_worker import renderer_working_directory

def fixture(tmp_path):
    project=tmp_path/'project';project.mkdir()
    mesh=tmp_path/'assets'/'decor.obj';mesh.parent.mkdir();mesh.write_text('v 0 0 0')
    manifest=tmp_path/'manifest.json'
    manifest.write_text(json.dumps({'objects':[{'mesh_path':'assets/decor.obj','decor_collision_policy':'visual_only','bbox':{'extent':[4,3,3]}}]}))
    return project,mesh,{'manifest':str(manifest)}

def test_relative_decor_resolves_from_importer_not_project(tmp_path,monkeypatch):
    project,mesh,config=fixture(tmp_path);monkeypatch.chdir(project)
    assert not Path('assets/decor.obj').exists()
    root=renderer_working_directory(project,config)
    assert (root/'assets/decor.obj').is_file()

def test_missing_decor_does_not_silently_admit_bbox_fallback(tmp_path):
    project,mesh,config=fixture(tmp_path);mesh.unlink()
    with pytest.raises(FileNotFoundError,match='bbox fallback prohibited'):
        renderer_working_directory(project,config)


def test_legacy_completed_result_cannot_hide_a_corrected_failure():
    from scripts.register_t18_table_contact_distances import select_repaired_results
    legacy=dict(job_id='a',status='conditional_event_search_completed',source_root='/old/run')
    repaired=dict(job_id='a',status='failed',source_root='/new/run_0_cwd_fix')
    assert select_repaired_results([legacy,repaired])=={'a':repaired}
    assert select_repaired_results([legacy])=={}

def test_corrected_complete_result_survives_another_failed_attempt():
    from scripts.register_t18_table_contact_distances import select_repaired_results
    good=dict(job_id='a',status='conditional_event_search_completed',source_root='/new/run_0_cwd_fix')
    failed=dict(job_id='a',status='failed',source_root='/new/run_1_cwd_fix')
    assert select_repaired_results([good,failed])=={'a':good}
