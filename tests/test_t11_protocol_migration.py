import copy
import json

import pytest

from physedit.core100_critical import load, primary
from scripts import migrate_core100_t11_observable_protocol as migration


def sources():
    base, _ = load(migration.PARENT, migration.PARENT_SHA)
    refs, _ = migration.checked('CURRENT.json')
    contexts, _ = migration.checked('PUBLISHED_SPEED_CONTEXTS.json')
    endpoints, _ = migration.checked('EXISTING_G_PATH_ENDPOINT_REREAD.json')
    reviews = json.loads((migration.CANDIDATE / 'RGB_REVIEW.json').read_text(encoding='utf8'))
    published, _ = migration.checked('PUBLISHED_G_CONTRAST.json')
    return base, refs, contexts, reviews, endpoints, published


def test_versioned_event_migration_preserves_old_inputs_and_original_parameter_domains():
    values = sources(); old = copy.deepcopy(values[0])
    result = migration.migrate(*values)
    assert values[0] == old
    assert result['input_bindings'] == old['input_bindings']
    assert result['pairs'] == old['pairs']
    before = {c['clip_id']: c for c in old['cases']}
    for row in result['cases']:
        cid = row['clip_id']
        if row['scene_id'] != 'T11':
            assert row == before[cid]
            continue
        assert row['theta'] == before[cid]['theta']
        assert row['normalization_domain'] == before[cid]['normalization_domain']
        assert row['reference_video_sha256'] == before[cid]['reference_video_sha256']
        assert row['observable_event_revision']['prior']['reference_events'] == before[cid]['reference_events']
        assert set(row['reference_events']) == set(row['judge_protocol']['events']) == {migration.EVENT}
        assert not row['observable_event_revision']['cpu64_intervals_used']
        assert row['conditional_solver_evidence']['source']=='original_published_native_trajectories'
        if cid in migration.SPEED_CASES:
            assert primary(row)['intervals'] == [[2.3, 2.5]]
            assert primary(row)['rgb_distance_admitted']
            if cid in ['T11_C01', 'T11_C02']:
                assert primary(row)['bin'] is None  # Broad interval crosses buckets.
        else:
            assert primary(row)['rgb_distance_admitted']
            assert primary(row)['intervals'] == [[.3393210590231814, .4868816575079043]]
            assert row['observable_event_revision']['fine_replay_not_used_for_distance']
    assert result['summary']['critical_rgb_distance_cases'] == 92
    assert result['summary']['admitted_near_cases'] == 13
    assert result['summary']['independent_admitted_pairs'] == 4


@pytest.mark.parametrize('defect', ['reference', 'window', 'context', 'axis', 'unknown', 'unreviewed', 'control', 'event', 'global_source', 'global_physics', 'global_no_flip'])
def test_migration_rejects_cross_version_or_unattested_evidence(defect):
    base, refs, contexts, reviews, endpoints, published = sources()
    target = next(r for r in refs['references'] if r['clip_id'] == 'T11_C04')
    context = next(r for r in contexts['rows'] if r['clip_id'] == 'T11_C04')
    if defect == 'reference': target['reference_video_sha256'] = 'wrong-video'
    if defect == 'window': target['measurement']['window_frames'] = [4, 209]
    if defect == 'context': contexts['comparisons_to_C01'][-1]['same_condition_poses'] = False
    if defect == 'axis': context['projection']['experiment_parameter']['case_mass_kg'] += .1
    if defect == 'unknown': target['measurement']['events'][migration.EVENT]['label'] = None
    if defect == 'unreviewed': reviews['negative_reference_full_window_review_pending'] = ['T11_C01']
    if defect == 'control': context['projection']['original_runtime_forces'][0]['frame_end'] += 1
    if defect == 'event': refs['new_event_original_published_contrast']['event'] = 'old-terminal-z'
    if defect == 'global_source': published['rows'][5]['vector']['driver_initial_speed_mps'] += .1
    if defect == 'global_physics': published['rows'][2]['physical_object_mismatches'] = ['table']
    if defect == 'global_no_flip':
        for r in published['rows']: r['measurement']['events'][migration.EVENT]['label'] = 1
    with pytest.raises(ValueError):
        migration.migrate(base, refs, contexts, reviews, endpoints, published)


def test_finished_same_side_t18_probes_remain_pending_without_deleting_reference():
    base=sources()[0]
    pointer=json.loads((migration.ROOT/'review/core100_v2_resolution_20261102/T18_GPU_ENDPOINTS_RESULT.json').read_text())
    report=json.loads((migration.ROOT/pointer['path']).read_text())
    migration.attach_verified_t18_probes(base,report)
    for cid in ['T18_C01','T18_C02']:
        row=next(c for c in base['cases']if c['clip_id']==cid)
        assert row['completed_original_axis_probes']['completed']==7
        assert row['normalization_domain']==[.08,.8]
        assert not row['completed_original_axis_probes']['not_applicable_claimed']
        assert not primary(row)['rgb_distance_admitted']
    altered=copy.deepcopy(report)
    next(p for p in altered['points']if p['clip_id']=='T18_C01')['status']='running'
    with pytest.raises(ValueError,match='unverified'):
        migration.attach_verified_t18_probes(base,altered)
