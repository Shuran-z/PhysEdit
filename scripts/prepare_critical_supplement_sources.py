"""Recover eight published references for the separately authorized supplement."""
import gzip
import hashlib
import json
from pathlib import Path,PurePosixPath
import subprocess
import zipfile

from scripts.boundary_ssh import remote_text,transport_options

ROOT=Path(__file__).resolve().parents[1]
WORK=ROOT/'review/critical_supplement_20261101'
SELECTIONS=[
 ('T04_S01','T04F880V1__bg01_home_ase__g03_earth__cf_stack_sliding_minus__rep02'),
 ('T04_S02','T04F880V1__bg01_home_ase__g03_earth__cf_stack_sliding_star__rep02'),
 ('T05_S01','T05F880V1__bg01_home_ase__g03_earth__cf_gate_passage_star__rep02'),
 ('T05_S02','T05F880V1__bg01_home_ase__g03_earth__cf_gate_passage_plus__rep02'),
 ('T10_S01','PROD_T10_bg01_home_ase_g03_earth_supx_p19'),
 ('T10_S02','PROD_T10_bg01_home_ase_g03_earth_supx_p20'),
 ('T11_S01','T11R011__bg01_home_ase__g03_earth__A_speed_theta_minus_03'),
 ('T11_S02','T11R011__bg01_home_ase__g03_earth__A_speed_theta_minus_04')]
REMOTE=r'''
import gzip,hashlib,json,subprocess,zipfile
import os
from pathlib import Path
from huggingface_hub import hf_hub_download
os.environ['HTTP_PROXY']=PROXY_URL;os.environ['HTTPS_PROXY']=PROXY_URL
os.environ['HF_HUB_DOWNLOAD_TIMEOUT']='30';os.environ['HF_HUB_ETAG_TIMEOUT']='15'
root=Path('/home/wangzijun_p25/critical_supplement_sources_20261101');root.mkdir(exist_ok=True)
proof=[]
for row in ROWS:
 cid=row['supplement_id'];out=root/cid;out.mkdir(exist_ok=True)
 video=Path(row['local_source']);assert hashlib.sha256(video.read_bytes()).hexdigest()==row['sha256'],str(video)
 sp=Path(row['state_path']);source_release_identity=False
 if not sp.exists()and row.get('source_metadata_download'):
  meta=row['source_metadata_download'];sp=Path(hf_hub_download(repo_id=meta['repo_id'],revision=meta['revision'],filename=meta['path'],repo_type='dataset'))
  source= row['source_download']
  published_video=Path(hf_hub_download(repo_id=source['repo_id'],revision=source['revision'],filename=source['path'],repo_type='dataset'))
  assert hashlib.sha256(published_video.read_bytes()).hexdigest()==row['sha256']
  source_release_identity=True
 packed=sp.read_bytes();raw=gzip.decompress(packed)if sp.suffix=='.gz'else packed
 state=json.loads(raw);assert len(state['frames'])==210
 if row.get('expected_state_sha256'):
  assert row['expected_state_sha256']in[hashlib.sha256(raw).hexdigest(),hashlib.sha256(packed).hexdigest()]
 source_video=Path(state['render']['save_video']);old_video_hash=hashlib.sha256(source_video.read_bytes()).hexdigest()if source_video.is_file()else None
 if cid.startswith('T10'):
  source_video=sp.parent.parent/'videos'/(row['native_sample_id']+'__cam01.mp4')
  old_video_hash=hashlib.sha256(source_video.read_bytes()).hexdigest()
 # Missing originals remain explicit; a native ID alone cannot certify a
 # replacement video as belonging to this state.
 native_video_matches=old_video_hash==row['sha256']or source_release_identity
 (out/'source_state.json.gz').write_bytes(gzip.compress(raw,mtime=0))
 if not(out/'reference.mp4').exists():(out/'reference.mp4').write_bytes(video.read_bytes())
 assert hashlib.sha256((out/'reference.mp4').read_bytes()).hexdigest()==row['sha256']
 probe=subprocess.run(['ffprobe','-v','error','-select_streams','v:0','-show_entries','stream=width,height,nb_frames,r_frame_rate','-of','json',str(video)],capture_output=True,text=True,check=True)
 media=json.loads(probe.stdout)['streams'][0]
 for name,filter_text in [('condition.png',r'select=eq(n\,4)'),('contact_sheet.jpg',r'select=eq(n\,4)+eq(n\,30)+eq(n\,60)+eq(n\,90)+eq(n\,120)+eq(n\,154)+eq(n\,180)+eq(n\,209),scale=480:-1,tile=4x2')]:
  subprocess.run(['ffmpeg','-v','error','-nostdin','-y','-i',str(video),'-vf',filter_text,'-frames:v','1',str(out/name)],check=True)
 result=dict(supplement_id=cid,native_sample_id=row['native_sample_id'],video_sha256=row['sha256'],
  original_video_path=str(source_video),original_video_sha256=old_video_hash,state_video_byte_identity_verified=native_video_matches,
  same_immutable_release_source_video_and_metadata_verified=source_release_identity,
  source_state_path=str(sp),source_state_raw_sha256=hashlib.sha256(raw).hexdigest(),
  source_state_stored_sha256=hashlib.sha256(packed).hexdigest(),media=media,
  physics_dt_s=state['scene_overrides']['dt'],physics_steps_per_frame=state['render'].get('physics_steps_per_render_frame'),
  condition_frame_index=4,contact_sheet_frames=[4,30,60,90,120,154,180,209],files={})
 for p in out.iterdir():
  if p.is_file()and p.name!='SOURCE_PROOF.json':result['files'][p.name]=hashlib.sha256(p.read_bytes()).hexdigest()
 (out/'SOURCE_PROOF.json').write_text(json.dumps(result,indent=2));proof.append(result)
archive=root/'references.zip'
with zipfile.ZipFile(archive,'w',compression=zipfile.ZIP_STORED)as z:
 for result in proof:
  for p in sorted((root/result['supplement_id']).iterdir()):
   if p.is_file():z.write(p,p.relative_to(root).as_posix())
print(json.dumps(dict(remote_archive=str(archive),archive_sha256=hashlib.sha256(archive.read_bytes()).hexdigest(),sources=proof)))
'''


def main():
    WORK.mkdir(parents=True,exist_ok=True)
    from physedit.core100_release import load
    old={r['sample_id']for r in load()[2]['tasks']}
    wanted=dict((sid,cid)for cid,sid in SELECTIONS);found={}
    with gzip.open(ROOT.parent/'prompts_72000_unified/videos.jsonl.gz','rt',encoding='utf8')as f:
        for line in f:
            row=json.loads(line);sid=row.get('native_sample_id')
            if sid in wanted and row.get('camera')=='cam01'and row.get('engine')=='genesis':
                assert sid not in found,'ambiguous_published_video_identity:'+sid
                found[sid]=row
    original={r['sample_id']:r for r in json.loads((ROOT/'review/scene_family_completion_20261018/t11_published_final_states.json').read_text())}
    rows=[]
    for cid,sid in SELECTIONS:
        assert sid not in old,'frozen_core100_reference_reused'
        row=dict(found[sid],supplement_id=cid)
        assert row['split']in ['protected_core100_reserve80_lineage','ood_holdout'],'training_source_selected:'+sid
        if cid.startswith(('T04','T05')):
            local=ROOT/'review/scene_family_completion_20261018/completion_states'/cid[:3]/(sid+'.json.gz')
            state=json.loads(gzip.decompress(local.read_bytes()));video=PurePosixPath(state['render']['save_video'])
            row.update(state_path=str(video.parent.parent/'metadata'/(sid+'__cam01.json')),
                expected_state_sha256=hashlib.sha256(gzip.decompress(local.read_bytes())).hexdigest())
            old=row['source_download'];row['source_metadata_download']=dict(old,
                path=str(PurePosixPath(old['path']).parents[1]/'metadata'/(sid+'__cam01.json.gz')))
        elif cid.startswith('T10'):
            row['state_path']='/data_cached/wangzijun_p25/hf_phyediting/data/T10/production_2640_480p_h264_20260906/metadata/'+sid+'__cam01.json'
        else:
            row.update(state_path=original[sid]['source_state'],expected_state_sha256=original[sid]['state_sha256'])
        rows.append(row)
    (WORK/'selected_catalog_rows.json').write_text(json.dumps(rows,indent=2),encoding='utf8')
    from scripts.supplement_hf_transport import hf_transport
    with hf_transport(WORK)as proxy:
        result=json.loads(remote_text('p25',REMOTE.replace('ROWS',repr(rows)).replace('PROXY_URL',repr(proxy)),timeout=300,attempts=1,
            python='/home/wangzijun_p25/miniconda3/envs/genesis/bin/python'))
    archive=WORK/'references.zip'
    subprocess.run(['scp',*transport_options('p25'),'-q','p25:'+result['remote_archive'],str(archive)],check=True,timeout=180)
    assert hashlib.sha256(archive.read_bytes()).hexdigest()==result['archive_sha256']
    with zipfile.ZipFile(archive)as z:
        for name in z.namelist():
            target=(WORK/'sources'/name).resolve();assert target.is_relative_to((WORK/'sources').resolve())
        z.extractall(WORK/'sources')
    for proof in result['sources']:
        for name,digest in proof['files'].items():assert hashlib.sha256((WORK/'sources'/proof['supplement_id']/name).read_bytes()).hexdigest()==digest
    (WORK/'SOURCE_RECOVERY.json').write_text(json.dumps(result,indent=2),encoding='utf8')
    print(json.dumps(dict(videos=len(rows),state_video_byte_identity_verified=sum(r['state_video_byte_identity_verified']for r in result['sources']),archive_bytes=archive.stat().st_size)))


if __name__=='__main__':main()
