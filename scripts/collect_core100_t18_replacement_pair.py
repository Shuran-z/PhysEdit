"""Validate completed pose-replay videos before preparing replacement inputs."""
import hashlib
import json
from pathlib import Path
import subprocess
import zipfile

from review.cvpr_experiments_20261031.archive_hunyuan_checkpoint_sftp import rpc, P21_OPTIONS

ROOT=Path(__file__).resolve().parents[1]
WORK=ROOT/'review/core100_six_replacements_20261103'
REMOTE=r'''
import copy,gzip,hashlib,json,math,pathlib,subprocess,zipfile
root=pathlib.Path('/data_cached/wangzijun_p25/liyuhan/core100_t18_replacement_rgb_replay_v2_20261103');results=[]
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
for cid in ['T18_C01','T18_C02']:
 dest=root/cid;r=json.loads((dest/'DISPATCH.json').read_text());proc=pathlib.Path('/proc',str(r['pid']),'cmdline')
 if proc.exists()and str(dest/'config.json').encode()in proc.read_bytes():
  print(json.dumps({'status':'running','clip_id':cid}));raise SystemExit
 assert sha(dest/'config.json')==r['config_sha256']
 cfg=json.loads((dest/'config.json').read_text());original_cfg=json.loads((pathlib.Path(r['source_state_path']).parent/'config.json').read_text())
 assert cfg['trajectory_replay_path']==str(dest/'trajectory_replay.json')and cfg['trajectory_replay_sha256']==r['replay_sha256']
 assert json.loads((dest/'runtime_backend.json').read_text())['simulation_steps_forbidden']and r['simulation_steps_forbidden']
 assert 'trajectory replay loaded:'in(dest/'run.log').read_text(errors='replace')
 assert cfg['dynamic_objects']==original_cfg['dynamic_objects']and cfg['scene_overrides']==original_cfg['scene_overrides']
 for k in ['seed','runtime_forces']:assert cfg.get(k)==original_cfg.get(k)
 source=pathlib.Path(r['source_state_path']);assert sha(source)==r['source_state_sha256'];s=json.loads(source.read_text())
 replay=dest/'trajectory_replay.json';assert sha(replay)==r['replay_sha256']
 rendered=dest/'rendered_state.json';v=json.loads(rendered.read_text());assert len(v['frames'])==len(s['frames'])==210
 max_delta=0.;max_qdelta=0.;actors=set()
 for a,b in zip(s['frames'],v['frames']):
  assert a['frame_index']==b['frame_index']
  actual={o['name']:o for o in b['objects']}
  for o in a['objects']:
   other=actual[o['name']];actors.add(o['name']);max_delta=max(max_delta,math.dist(o['position'],other['position']))
   q=o['quaternion_xyzw'];w=other['quaternion_xyzw'];max_qdelta=max(max_qdelta,min(math.dist(q,w),math.dist(q,[-x for x in w])))
 assert max_delta<1e-5 and max_qdelta<1e-5
 video=dest/'reference.mp4';media=json.loads(subprocess.check_output(['ffprobe','-v','error','-select_streams','v:0','-show_entries','stream=width,height,nb_frames,r_frame_rate','-of','json',str(video)],text=True))['streams'][0]
 assert int(media['nb_frames'])==210 and media['width']==1280 and media['height']==720
 subprocess.run(['ffmpeg','-v','error','-nostdin','-i',str(video),'-f','null','-'],check=True)
 subprocess.run(['ffmpeg','-v','error','-nostdin','-y','-i',str(video),'-vf',r'select=eq(n\,4)','-frames:v','1',str(dest/'condition.png')],check=True)
 # The immutable numerical file remains on the server. Keep a compressed
 # readable copy with its original all-substep contact evidence separately.
 state=dest/'source_state.json.gz';state.write_bytes(gzip.compress(source.read_bytes(),mtime=0))
 out=dict(r,status='completed_integrity_and_replay_pose_verified',video_sha256=sha(video),media=media,
  rendered_state_sha256=sha(rendered),maximum_exported_position_difference_m=max_delta,
  maximum_exported_quaternion_difference=max_qdelta,compared_actors=sorted(actors),
  verification_limit='Exported pose equality and source hashes; independent visual event review required.',
  files={n:sha(dest/n)for n in ['reference.mp4','condition.png','config.json','source_state.json.gz','DISPATCH.json']})
 (dest/'SOURCE_PROOF.json').write_text(json.dumps(out,indent=2));results.append(out)
archive=root/'validated_pair.zip'
with zipfile.ZipFile(archive,'w',compression=zipfile.ZIP_STORED)as z:
 for r in results:
  for n in list(r['files'])+['SOURCE_PROOF.json']:z.write(root/r['clip_id']/n,r['clip_id']+'/'+n)
print(json.dumps({'status':'collected','sources':results,'archive':str(archive),'archive_sha256':sha(archive)}))
'''


def main():
    result=rpc(P21_OPTIONS,'p25',REMOTE)
    if result['status']!='collected':print(json.dumps(result));return
    archive=WORK/'validated_t18_pair.zip'
    subprocess.run(['scp',*P21_OPTIONS,'-q','p25:'+result['archive'],str(archive)],check=True,timeout=180)
    assert hashlib.sha256(archive.read_bytes()).hexdigest()==result['archive_sha256']
    with zipfile.ZipFile(archive)as z:
        for name in z.namelist():assert(WORK/'sources'/name).resolve().is_relative_to((WORK/'sources').resolve())
        z.extractall(WORK/'sources')
    for r in result['sources']:
        for n,h in r['files'].items():assert hashlib.sha256((WORK/'sources'/r['clip_id']/n).read_bytes()).hexdigest()==h
    (WORK/'T18_SOURCE_RECOVERY.json').write_text(json.dumps(result,indent=2),encoding='utf8')
    print(json.dumps(dict(status='collected',videos=2,exported_pose_equality=True,visual_review_pending=True)))


if __name__=='__main__':main()
