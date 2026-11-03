"""Verify named terminal witnesses for C05 without equating trajectories."""
import base64
import hashlib
import inspect
import json
from pathlib import Path
import zlib
from scripts.t18_table_contact_boundary_worker import table_event
from physedit.core100_critical import load
from review.cvpr_experiments_20261031.archive_hunyuan_checkpoint_sftp import rpc,P21_OPTIONS

ROOT=Path(__file__).resolve().parents[1];WORK=ROOT/'review/core100_v2_resolution_20261102'
REMOTE=r'''
import gzip,hashlib,json
from pathlib import Path
path=Path(TARGET['state_path']);raw=path.read_bytes();decoded=gzip.decompress(raw)if raw[:2]==bytes([31,139])else raw
assert hashlib.sha256(decoded).hexdigest()==TARGET['decoded_state_sha256']
s=json.loads(decoded);assert len(s['frames'])==210
history=[f['frame_index']for f in s['frames'][4:155]if table_event(s,f)['label']]
terminal=[]
for f in s['frames'][145:155]:
 m=table_event(s,f);terminal.append(dict(frame=f['frame_index'],label=m['label'],upper_books_on_table=m['upper_books_on_table']))
print(json.dumps(dict(original_state_path=str(path),original_stored_state_sha256=hashlib.sha256(raw).hexdigest(),
 original_decoded_state_sha256=hashlib.sha256(decoded).hexdigest(),reference_video_sha256=VIDEO_SHA,
 original_contact_history=history,original_terminal_frames=terminal,original_state_modified=False)))
'''


def main():
    data,_=load();row=next(r for r in data['cases']if r['clip_id']=='T18_C05')
    pointer=json.loads((WORK/'T18_C05_REPEAT_COLLECT.json').read_text());path=ROOT/pointer['path'];assert hashlib.sha256(path.read_bytes()).hexdigest()==pointer['sha256']
    repeats=json.loads(path.read_text());assert all(p['status']in['completed','failed']for p in repeats['points']),'Do not turn running repeats into observations'
    target=row['reference_native_state_binding'];payload='TARGET='+repr(target)+'\nVIDEO_SHA='+repr(row['reference_video_sha256'])+'\n'+inspect.getsource(table_event)+'\n'+REMOTE
    encoded=base64.b64encode(zlib.compress(payload.encode())).decode()
    original=rpc(P21_OPTIONS,'p25','import base64,zlib;exec(zlib.decompress(base64.b64decode('+repr(encoded)+')))')
    image=ROOT/'review/core100_remaining74_admission_20261101/reference_review/T18_C05/original_sheet.jpg'
    result=dict(clip_id='T18_C05',original=original,repeats=repeats,
        additional_repeats_successful=repeats['status']=='completed',
        additional_repeat_limitation='Failed CUDA attempts provide no event observations and no repeatability evidence; use only the separately hash-bound original and completed initial source replay.',
        source_trajectory_equivalence_claimed=False,original_numeric_profile_preserved=True,
        source_video_visual_review=dict(image_path=image.relative_to(ROOT).as_posix(),image_sha256=hashlib.sha256(image.read_bytes()).hexdigest(),
            reviewer='assistant_visual_review_not_independent_human_gold',notes='The five non-extracted upper books visibly lean onto the tabletop; the travelling blue extracted book is not the target.'),
        scope='Named terminal event and fixed-profile observed interval only; source arrangement drift is retained and not called exact trajectory reproduction.',
        source_hashes={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest()for p in[path,Path(__file__),ROOT/'scripts/repeat_core100_v2_t18_c05.py',image]})
    raw=json.dumps(result,indent=2).encode();digest=hashlib.sha256(raw).hexdigest();path=WORK/('t18_c05_event_equivalence_'+digest[:12]+'.json');path.write_bytes(raw)
    (WORK/'T18_C05_EVENT_EQUIVALENCE.json').write_text(json.dumps(dict(path=path.relative_to(ROOT).as_posix(),sha256=digest),indent=2))
    print(json.dumps(dict(clip_id='T18_C05',repeat_terminal_labels={p['kind']:[f['label']for f in p.get('terminal_frames',[])]for p in repeats['points']},original_terminal_labels=[f['label']for f in original['original_terminal_frames']])))


if __name__=='__main__':main()
