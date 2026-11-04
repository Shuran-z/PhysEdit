"""Build a separate T11 visual-event candidate from existing reference states."""
import base64
import gzip
import hashlib
import json
from pathlib import Path
import zlib
from physedit import t11_visual_events as events
from physedit.core100_critical import load
from review.cvpr_experiments_20261031.archive_hunyuan_checkpoint_sftp import rpc,P21_OPTIONS

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'benchmarks/t11_observable_events_candidate_v1_20261103'
POINTER=ROOT/'catalog/active_core100_critical_protocol.json'
REMOTE=r'''
import gzip,hashlib,json
from pathlib import Path
rows=[]
for t in TARGETS:
 p=Path(t['native']['state_path']);raw=p.read_bytes();decoded=gzip.decompress(raw)if raw[:2]==bytes([31,139])else raw
 assert hashlib.sha256(raw).hexdigest()==t['native']['stored_state_sha256']
 assert hashlib.sha256(decoded).hexdigest()==t['native']['decoded_state_sha256']
 s=json.loads(decoded);assert len(s['frames'])==210
 rows.append(dict(clip_id=t['clip_id'],reference_video_sha256=t['reference_video_sha256'],
  native_stored_state_sha256=hashlib.sha256(raw).hexdigest(),native_decoded_state_sha256=hashlib.sha256(decoded).hexdigest(),
  measurement=reference_events(s,condition_frame=t['condition_frame'],end_frame=t['end_frame'])))
print(json.dumps(rows))
'''


def main():
    before=hashlib.sha256(POINTER.read_bytes()).hexdigest();data,registry=load();rows=[];targets=[]
    module=ROOT/'physedit/t11_visual_events.py'
    for c in data['cases']:
        if c['scene_id']!='T11':continue
        if c['clip_id']in['T11_C01','T11_C02']:
            source=ROOT/'benchmarks/critical_supplement_v1_20261101/evidence'/('T11_S01.json.gz'if c['clip_id']=='T11_C01'else'T11_S02.json.gz')
            raw=source.read_bytes();decoded=gzip.decompress(raw)
            # The frozen supplement alias was named "decoded" but contains
            # its stored gzip-file digest. Verify the manifest too, then emit
            # both correctly typed hashes without rewriting that old alias.
            manifest=json.loads((source.parents[1]/'MANIFEST.json').read_text())
            stored=hashlib.sha256(raw).hexdigest()
            assert stored==c['reference_native_state_binding']['decoded_state_sha256']
            assert stored==manifest['files'][source.relative_to(source.parents[1]).as_posix()]
            rows.append(dict(clip_id=c['clip_id'],reference_video_sha256=c['reference_video_sha256'],
                native_stored_state_sha256=hashlib.sha256(raw).hexdigest(),native_decoded_state_sha256=hashlib.sha256(decoded).hexdigest(),
                original_binding_hash_semantics='Legacy decoded_state_sha256 alias refers to the manifest-bound stored gzip digest; original alias preserved.',
                measurement=events.reference_events(json.loads(decoded),condition_frame=c['condition_frame_index'],end_frame=c['end_frame_index'])))
        else:
            targets.append(dict(clip_id=c['clip_id'],reference_video_sha256=c['reference_video_sha256'],
                native=c['reference_native_state_binding'],condition_frame=c['condition_frame_index'],end_frame=c['end_frame_index']))
    payload=module.read_text(encoding='utf8')+'\nTARGETS='+repr(targets)+'\n'+REMOTE
    encoded=base64.b64encode(zlib.compress(payload.encode())).decode()
    rows+=rpc(P21_OPTIONS,'p25','import base64,zlib;exec(zlib.decompress(base64.b64decode('+repr(encoded)+')))')
    rows.sort(key=lambda r:r['clip_id'])
    assert len(rows)==5 and hashlib.sha256(POINTER.read_bytes()).hexdigest()==before
    result=dict(version=events.VERSION,status='candidate_not_active',registered_original_reference_count=5,
        source_critical_registry_sha256=hashlib.sha256(registry.read_bytes()).hexdigest(),
        event_definition_sha256=hashlib.sha256(module.read_bytes()).hexdigest(),references=rows,
        new_simulations=0,active_critical_registry_modified=False,old_labels_modified=False,
        existing_boundary_labels_transferred=False,formal_reference_count_increment=0,
        scope='Reference state readback only; image observability, event-matched boundary readback and new generated-video annotations remain separately required.')
    by_id={r['clip_id']:r for r in rows};c1,c2=[next(c for c in data['cases']if c['clip_id']==cid)for cid in['T11_C01','T11_C02']]
    assert c1['fixed_context_sha256']==c2['fixed_context_sha256']and c1['normalization_domain']==c2['normalization_domain']
    event=events.ACTORS[0]+'_edge_fall_begins';labels=[by_id[c['clip_id']]['measurement']['events'][event]['label']for c in[c1,c2]]
    assert labels==[0,1]
    result['new_event_original_published_contrast']=dict(event=event,clips=[c1['clip_id'],c2['clip_id']],
        parameter=c1['parameter'],bracket=[c1['theta'],c2['theta']],endpoint_labels=labels,
        normalization_domain=c1['normalization_domain'],source='New predicate evaluated independently on both original published states; no old height-rule labels copied.',
        exact_root_claimed=False,formal_rgb_distance_admitted=False,
        limitation='Stage the contrast only. Fresh image-event review and versioned scoring migration are required; fine intervals from the old predicate are not transferred.')
    OUT.mkdir(exist_ok=True)
    raw=json.dumps(result,ensure_ascii=False,indent=2).encode();digest=hashlib.sha256(raw).hexdigest();path=OUT/('reference_labels_'+digest[:12]+'.json')
    if path.exists():assert path.read_bytes()==raw
    else:path.write_bytes(raw)
    (OUT/'contract.json').write_text(json.dumps(events.contract(),ensure_ascii=False,indent=2),encoding='utf8')
    (OUT/'CURRENT.json').write_text(json.dumps(dict(path=path.name,sha256=digest,status='candidate_not_active'),indent=2))
    for r in rows:
        print(json.dumps(dict(clip_id=r['clip_id'],falls={a:r['measurement']['events'][a+'_edge_fall_begins']for a in events.ACTORS}),ensure_ascii=False))


if __name__=='__main__':main()
