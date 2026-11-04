"""Verify each transferred source and every retimed frame, without image thresholds."""
import hashlib,json,subprocess
from pathlib import Path
ROOT=Path('/data_cached/wangzijun_p25/core100_remaining20_20261101')
jobs=json.loads((ROOT/'ORIGINAL_SOURCE_JOBS.json').read_text())
states={r['clip_id']:r for r in json.loads((ROOT/'ARCHIVED_STATE_TRACE.json').read_text())}
def frames(path):
    output=subprocess.check_output(['/usr/bin/ffmpeg','-v','error','-threads','1','-hwaccel','none','-i',str(path),'-vsync','0','-f','framemd5','-'])
    return [line.rsplit(b',',1)[-1].strip().decode()for line in output.splitlines()if line and not line.startswith(b'#')]
out=[]
for j in jobs:
    record=dict(clip_id=j['clip_id'])
    try:
        config_record=next(x for x in j['transfer_records']if x['destination'].endswith('.json'))
        video_record=next(x for x in j['transfer_records']if x['destination'].endswith('.mp4'))
        config_path=Path(config_record['source']);video_path=Path(video_record['source'])
        assert hashlib.sha256(config_path.read_bytes()).hexdigest()==config_record['sha256']
        assert hashlib.sha256(video_path.read_bytes()).hexdigest()==j['parent_video_sha256']==video_record['sha256']
        identity=json.loads(Path(j['active_video_identity']).read_text());active=Path(identity['video_path'])
        assert hashlib.sha256(active.read_bytes()).hexdigest()==j['video_sha256']
        source_frames=frames(video_path);active_frames=frames(active)
        assert len(source_frames)==len(active_frames)==210 and source_frames==active_frames
        state=states[j['clip_id']]['states'][0];cfg=json.loads(config_path.read_text())
        record.update(status='original_config_parent_and_all210_active_frames_verified',original_config_sha256=config_record['sha256'],
            original_config_path=str(config_path),original_parent_video_sha256=video_record['sha256'],active_reference_video_sha256=j['video_sha256'],
            all210_decoded_frames_identical=True,frame_hash_sequence_sha256=hashlib.sha256(json.dumps(source_frames).encode()).hexdigest(),
            config_annotation_save_path=cfg.get('annotations',{}).get('save_path'),located_state_sha256=state['sha256'],
            located_state_declared_video=state['declared_video'],state_camera_matches_current_reference='__cam01/'in state['declared_video'],
            original_state_binding_admitted=False,reason='State declares another camera; parent/retime identity alone does not prove shared physics trajectory')
    except Exception as error:record.update(status='pending',error=str(error),error_type=type(error).__name__)
    out.append(record)
(ROOT/'ORIGINAL_TRANSFER_FRAME_PROOF.json').write_text(json.dumps(out,indent=2))
print(json.dumps([dict(clip_id=r['clip_id'],status=r['status'],error=r.get('error'))for r in out]))
