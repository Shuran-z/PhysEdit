"""Recover source-bound media for four existing published replacement points."""
import base64
import gzip
import hashlib
import json
from pathlib import Path, PurePosixPath
import subprocess
import zipfile
import zlib

from scripts.boundary_ssh import remote_text, transport_options

ROOT=Path(__file__).resolve().parents[1]
WORK=ROOT/'review/core100_six_replacements_20261103'
REMOTE=r'''
import gzip,hashlib,json,os,pathlib,subprocess,zipfile
from huggingface_hub import hf_hub_download
if PROXY:os.environ['HTTP_PROXY']=PROXY;os.environ['HTTPS_PROXY']=PROXY
os.environ['HF_HUB_DOWNLOAD_TIMEOUT']='30';os.environ['HF_HUB_ETAG_TIMEOUT']='15'
root=pathlib.Path('/data_cached/wangzijun_p25/liyuhan/core100_six_replacement_sources_20261103');root.mkdir(exist_ok=True)
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
proofs=[]
for row in ROWS:
 cid=row['replacement_clip_id'];sid=row['native_sample_id'];out=root/cid;out.mkdir(exist_ok=True)
 video=pathlib.Path(row['local_source']);assert sha(video)==row['sha256'],'catalog_video_bytes_changed:'+cid
 sp=pathlib.Path(row['state_path']);published_identity=False
 if not sp.exists()and row.get('source_metadata_download'):
  m=row['source_metadata_download'];sp=pathlib.Path(hf_hub_download(repo_id=m['repo_id'],repo_type='dataset',revision=m['revision'],filename=m['path'],local_files_only=not bool(PROXY)))
 packed=sp.read_bytes();raw=gzip.decompress(packed)if packed[:2]==bytes([31,139])else packed;s=json.loads(raw)
 assert len(s['frames'])==210 and s['scene_overrides'].get('record_contacts')
 assert hashlib.sha256(raw).hexdigest()==row['expected_state_sha256']
 candidates=[pathlib.Path(s['render']['save_video'].replace('__cam03','__cam01').replace('__cam02','__cam01')),sp.parent.parent/'videos'/(sid+'__cam01.mp4')]
 native=[dict(path=str(p),sha256=sha(p))for p in candidates if p.is_file()]
 identity=any(p['sha256']==row['sha256']for p in native)
 if not identity and row.get('source_metadata_download'):
  m=row['source_metadata_download'];sd=row['source_download']
  # Require the state and source video in the same immutable release; do
  # not transfer an event from a later video with only a matching ID.
  assert m['repo_id']==sd['repo_id']and m['revision']==sd['revision']
  published=pathlib.Path(hf_hub_download(repo_id=sd['repo_id'],repo_type='dataset',revision=sd['revision'],filename=sd['path'],local_files_only=not bool(PROXY)))
  assert sha(published)==row['sha256'];published_identity=True;identity=True
 assert identity,'published_video_native_state_identity_missing:'+cid
 state=out/'source_state.json.gz';state.write_bytes(gzip.compress(raw,mtime=0))
 dest=out/'reference.mp4'
 if dest.exists():assert sha(dest)==row['sha256']
 else:dest.write_bytes(video.read_bytes())
 probe=json.loads(subprocess.check_output(['ffprobe','-v','error','-select_streams','v:0','-show_entries','stream=width,height,nb_frames,r_frame_rate','-of','json',str(dest)],text=True))['streams'][0]
 assert int(probe['nb_frames'])==210
 subprocess.run(['ffmpeg','-v','error','-nostdin','-y','-i',str(dest),'-vf',r'select=eq(n\,4)','-frames:v','1',str(out/'condition.png')],check=True)
 subprocess.run(['ffmpeg','-v','error','-nostdin','-y','-i',str(dest),'-vf',r'select=eq(n\,4)+eq(n\,35)+eq(n\,65)+eq(n\,95)+eq(n\,125)+eq(n\,154)+eq(n\,180)+eq(n\,209),scale=480:-1,tile=4x2','-frames:v','1',str(out/'contact_sheet.jpg')],check=True)
 proof=dict(clip_id=cid,native_sample_id=sid,reference_video_sha256=sha(dest),source_state_decoded_sha256=hashlib.sha256(raw).hexdigest(),
  source_state_path=str(sp),native_video_candidates=native,state_video_identity_verified=identity,
  same_immutable_release_identity_verified=published_identity,media=probe,files={p.name:sha(p)for p in out.iterdir()if p.is_file()and p.name!='SOURCE_PROOF.json'})
 (out/'SOURCE_PROOF.json').write_text(json.dumps(proof,indent=2));proofs.append(proof)
archive=root/'published_four.zip'
with zipfile.ZipFile(archive,'w',compression=zipfile.ZIP_STORED)as z:
 for p in sorted(root.glob('T*_C*/*')):
  if p.is_file():z.write(p,p.relative_to(root).as_posix())
print(json.dumps(dict(sources=proofs,archive=str(archive),archive_sha256=sha(archive))))
'''


def main():
    WORK.mkdir(exist_ok=True)
    rows=json.loads((ROOT/'review/core100_v3_remaining8_20261103/FIRST_FOUR_SELECTIONS.json').read_text(encoding='utf8'))
    for row in rows:
        cid=row['replacement_clip_id'];sid=row['native_sample_id']
        if cid.startswith('T04'):
            path=ROOT/'review/scene_family_completion_20261018/completion_states/T04'/(sid+'.json.gz')
            raw=gzip.decompress(path.read_bytes());s=json.loads(raw)
            row['state_path']=str(PurePosixPath(s['render']['save_video']).parent.parent/'metadata'/(sid+'__cam01.json'))
            row['expected_state_sha256']=hashlib.sha256(raw).hexdigest()
            sd=row['source_download'];row['source_metadata_download']=dict(sd,path=str(PurePosixPath(sd['path']).parents[1]/'metadata'/(sid+'__cam01.json.gz')))
        else:
            ledger_id='T06_C05'if cid.startswith('T06')else'T10_C03'
            pointer=json.loads((ROOT/'review/core100_v2_resolution_20261102'/(ledger_id+'_RELEASED_AXIS.json')).read_text())
            source=ROOT/pointer['path'];assert hashlib.sha256(source.read_bytes()).hexdigest()==pointer['sha256']
            p=next(p for p in json.loads(source.read_text())['points']if p['sample_id']==sid)
            assert p['physics_settings_match_config']and p['executed_object_specs_match_config']and p['executed_force_commands_match_config']
            row.update(state_path=p['state_path'],expected_state_sha256=p['state_decoded_sha256'])
    (WORK/'FOUR_CATALOG_ROWS.json').write_text(json.dumps(rows,indent=2),encoding='utf8')
    payload='ROWS='+repr(rows)+'\nPROXY=None\n'+REMOTE
    packed=base64.b64encode(zlib.compress(payload.encode())).decode()
    result=json.loads(remote_text('p25','import base64,zlib;exec(zlib.decompress(base64.b64decode('+repr(packed)+')))',timeout=300,attempts=1,
        python='/home/wangzijun_p25/miniconda3/envs/genesis/bin/python'))
    archive=WORK/'published_four.zip'
    subprocess.run(['scp',*transport_options('p25'),'-q','p25:'+result['archive'],str(archive)],check=True,timeout=180)
    assert hashlib.sha256(archive.read_bytes()).hexdigest()==result['archive_sha256']
    with zipfile.ZipFile(archive)as z:
        for n in z.namelist():assert(WORK/'sources'/n).resolve().is_relative_to((WORK/'sources').resolve())
        z.extractall(WORK/'sources')
    for proof in result['sources']:
        for n,h in proof['files'].items():assert hashlib.sha256((WORK/'sources'/proof['clip_id']/n).read_bytes()).hexdigest()==h
    (WORK/'FOUR_SOURCE_RECOVERY.json').write_text(json.dumps(result,indent=2),encoding='utf8')
    print(json.dumps(dict(recovered=len(result['sources']),all_source_media_identities_verified=all(p['state_video_identity_verified']for p in result['sources']))))


if __name__=='__main__':main()
