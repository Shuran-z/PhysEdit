"""Register measured 4.1 s source windows without extending or retiming media."""
import hashlib
import json
from pathlib import Path


ROOT=Path(__file__).resolve().parents[1]
EVIDENCE=ROOT/'review/core100_resolution_20261027'


def main():
    verified_path=EVIDENCE/'physical_window15_verified.json'
    verified=json.loads(verified_path.read_bytes())
    truth_path=EVIDENCE/'physical_window15_event_truth.json'
    truth={r['clip_id']:r for r in json.loads(truth_path.read_bytes())}
    assert len(verified)==15 and all(r['verified'] and r['state_dynamic_specs_exact'] for r in verified)
    assert len(truth)==15
    cases={}
    for row in verified:
        cid=row['clip_id']; event=truth[cid]
        assert row['required_horizon_s']==4.1 and event['state_sha256']==row['state_sha256']
        assert event['source_config_sha256']==row['config_sha256']
        ref=row['reference']
        assert ref['frames']==210 and ref['physical_dt_s']==.02
        assert ref['decoded_frames_identical'] is True and ref['media_fps']==50.
        cases[cid]=dict(clip_id=cid,required_horizon_s=4.1,condition_frame_index=4,reference_end_frame=209,
                        physical_frame_period_s=.02,reference_media_fps=50.,reference_video_sha256=ref['sha256'],
                        reference=ref,source_config_sha256=row['config_sha256'],state_sha256=row['state_sha256'],
                        source_state_origin=row['state_origin'],window_status='registered_source_end_window',
                        boundary_window_status='must_match_source_end_209_or_be_recomputed',
                        terminal_rule='Evaluate the last generated native frame at or before 4.1 s; retain its exact timestamp and discretization error.',
                        generated_endpoint_rule='floor(4.1 * fps + 1e-9)',
                        shorter_native_outputs='coverage_gap_not_zero',
                        old_five_second_labels='no_automatic_transfer_of_positives_terminal_labels_order_or_quality_failures',
                        source_event=event,reference_rgb_admitted=False,formal_boundary_admitted=False)
    catalog=dict(schema='core100-source-physical-window-repair-v1',cases=cases,
                 decision='Use the complete available original physical trajectory; no extrapolation to 5 s. Selection uses source clocks only, independent of generated results.',
                 evidence_sha256={p.name:hashlib.sha256(p.read_bytes()).hexdigest()for p in [verified_path,truth_path]})
    path=ROOT/'annotation_site/resources/core100_physical_windows_20261027.json'
    path.write_text(json.dumps(catalog,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    manifest_path=EVIDENCE/'formal_seed0_v6_manifest.json';manifest=json.loads(manifest_path.read_bytes())
    for task in manifest['tasks']:
        if task['clip_id'] not in cases:continue
        rule=cases[task['clip_id']];task['required_horizon_s']=4.1
        task['window_registration_sha256']=hashlib.sha256(path.read_bytes()).hexdigest()
        frames,fps=task['native_frames'],task['native_fps']
        covers=frames is not None and fps and (frames-1)/fps+1e-6>=4.1
        task['native_covers_registered_window']=bool(covers)
        task['evaluation_end_native_frame']=min(frames-1,int(4.1*fps+1e-9))if frames is not None and fps else None
        task['existing_longer_window_annotations_require_recheck']=True
    manifest_path.write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({'registered_windows':len(cases),'resource':str(path)}))


if __name__=='__main__':main()
