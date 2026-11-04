"""Read a candidate T03 stage from saved states, without migrating scoring."""
import base64
import hashlib
import json
from pathlib import Path
import zlib

from physedit.core100_critical import load
from review.cvpr_experiments_20261031.archive_hunyuan_checkpoint_sftp import rpc,P21_OPTIONS

ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'benchmarks/t03_observable_stage_candidate_v1_20261103'
REMOTE=r'''
import gzip,hashlib,json
from pathlib import Path
rows=[]
for t in TARGETS:
 raw=Path(t['state_path']).read_bytes();decoded=gzip.decompress(raw)if raw[:2]==bytes([31,139])else raw
 stored_sha=hashlib.sha256(raw).hexdigest();decoded_sha=hashlib.sha256(decoded).hexdigest()
 assert t['expected_sha256']in[stored_sha,decoded_sha]
 state=json.loads(decoded)
 rows.append(dict(t,stored_state_sha256=stored_sha,decoded_state_sha256=decoded_sha,
  measurement=reference_events(state,condition_frame=4,end_frame=154),
  experimental_seed=state['experiment'].get('seed'),declared_random_seed=state['experiment'].get('random_seed')))
print(json.dumps(rows))
'''


def main():
    data,path=load();targets=[]
    for c in data['cases']:
        if c['clip_id']not in['T03_C01','T03_C02','T03_C03']:continue
        native=c['reference_native_state_binding']
        targets.append(dict(clip_id=c['clip_id'],kind='frozen_reference',theta=c['theta'],state_path=native['state_path'],expected_sha256=native['stored_state_sha256'],reference_video_sha256=c['reference_video_sha256']))
        if c['clip_id']=='T03_C01':continue
        for b in c['boundary_records']:
            for p in b['endpoints']:
                targets.append(dict(clip_id=c['clip_id'],kind='existing_endpoint',theta=p['theta'],state_path=p['state_path'],expected_sha256=p['state_sha256'],config_sha256=p['config_sha256']))
    module=ROOT/'physedit/t03_visual_events.py';payload=module.read_text(encoding='utf8')+'\nTARGETS='+repr(targets)+'\n'+REMOTE
    encoded=base64.b64encode(zlib.compress(payload.encode())).decode()
    rows=rpc(P21_OPTIONS,'p25','import base64,zlib;exec(zlib.decompress(base64.b64decode('+repr(encoded)+')))')
    result=dict(status='candidate_only_pending_author_event_choice',rows=rows,source_registry_sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
                module_sha256=hashlib.sha256(module.read_bytes()).hexdigest(),simulations_started=0,
                old_complete_C2_labels_transferred=False,active_scoring_modified=False)
    raw=json.dumps(result,indent=2).encode();digest=hashlib.sha256(raw).hexdigest();OUT.mkdir(exist_ok=True)
    target=OUT/('readback_'+digest[:12]+'.json');target.write_bytes(raw)
    (OUT/'CURRENT.json').write_text(json.dumps(dict(path=target.name,sha256=digest),indent=2))
    print(json.dumps([dict(clip_id=r['clip_id'],kind=r['kind'],theta=r['theta'],measurement=r['measurement'])for r in rows]))


if __name__=='__main__':main()
