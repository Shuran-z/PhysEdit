"""Recover unchanged original T14S matrix input records, never synthesize configs."""
import collections,concurrent.futures,gzip,hashlib,json
from pathlib import Path
R=Path('/data_cached/wangzijun_p25/config_bindings_20261031');O=R/'remaining6767';BASE=R/'followup/stage/releases/physedit';ROOT=Path('/home/wangzijun_p25/liyuhan/isaac_sim_everyday_bifurcation/t14s_prep_20261014')
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def load(p):return list(map(json.loads,gzip.open(p,'rt')))
manifest=Path('/data2/wangzijun_p25/isaac_out/t14s_delivery_v1/DELIVERY_MANIFEST.jsonl');mh=sha(manifest);assert mh=='7cac0def3905e76fdeeaf21f429218c3c7611b883f0c6de7dce1f80f015a35c6'
registered={x['sample_id']:x for x in json.loads(Path('/data_cached/wangzijun_p25/author_release_20261029/metadata/t14s_source_inputs.json').read_bytes())};delivery={json.loads(l)['sample_id']:json.loads(l) for l in manifest.read_bytes().splitlines()}
matrixfile=ROOT/'t14s_isaac_matrix_v1.jsonl';matrixhash=sha(matrixfile);matrix={}
for lineno,raw in enumerate(matrixfile.read_bytes().splitlines(keepends=True),1):
 x=json.loads(raw);native=x['sample_id'];assert x==delivery[native]['matrix']==registered[native]['matrix'];assert registered[native]['source_delivery_manifest_sha256']==mh;matrix[native]=(lineno,raw,x)
remaining=load(O/'REMAINING.jsonl.gz');ids={x['canonical_video_id'] for x in remaining if x['scene']=='T14'};catalog=[x for x in load(BASE/'catalog/videos.jsonl.gz') if x['canonical_video_id'] in ids];assert len(catalog)==960
out=O/'matrix_originals';out.mkdir(exist_ok=True)
for line,raw,x in matrix.values():(out/(hashlib.sha256(raw).hexdigest()+'.json')).write_bytes(raw)
tasks={x['canonical_video_id']:x for x in load(R/'TASKS.jsonl.gz')}
def recover(v):
 if v['native_sample_id'].startswith('T14SRS26'):
  cid=v['canonical_video_id'];t=tasks[cid];p=Path(v['local_source']);job=p.parent.parent/'job.json';h=sha(job);assert h==t['expected_sha256'];assert sha(p)==v['sha256'];j=json.loads(job.read_bytes());assert j['sample_id']==v['native_sample_id'];request=p.parent.parent/'request.json';cmd=json.loads(request.read_bytes())['command'];assert float(cmd[cmd.index('--gravity')+1])==j['inputs']['gravity'];assert float(cmd[cmd.index('--spring-force')+1])==j['inputs']['spring_force'];assert cmd[cmd.index('--sample-id')+1]==v['native_sample_id'];renderer=Path('/data2/wangzijun_p25/resample_training_duplicates_20261030/isaac_code/runtime/render_t14s_physics.py');assert sha(renderer)==v['source_input_evidence']['renderer_source_sha256'];ann=t['current_render']['actual_annotations'][0];trajectory=Path(ann['path']);assert sha(trajectory)==ann['gzip_sha256'];assert hashlib.sha256(gzip.decompress(trajectory.read_bytes())).hexdigest()==ann['raw_sha256']
  return dict(canonical_video_id=cid,status='RECOVERED',local_path=str(job),sha256=h,config_document_type='original_render_job_record',method='registered_original_job_sha256_video_and_execution_request',evidence=dict(video_sha256=v['sha256'],config_byte_sha256=h,previously_registered_config_sha256=t['expected_sha256'],execution_request_sha256=sha(request),renderer_source_sha256=sha(renderer),trajectory_raw_sha256=ann['raw_sha256'],source_bundle=t['current_render']['source_bundle'],source_bundle_config_member=t['current_render']['config_member']))
 cid=v['canonical_video_id'];native=v['native_sample_id'];line,raw,m=matrix[native];s=delivery[native];p=Path(v['local_source']);selected=Path(s['selected_dir']);assert p.parent in [selected,selected/'videos'];assert sha(p)==v['sha256'];e=v['source_input_evidence'];renderer=Path(e['renderer_source_path']);assert sha(renderer)==e['renderer_source_sha256'];traj=selected/'trajectory.json';assert sha(traj)==e['trajectory_sha256'];tr=json.loads(traj.read_bytes())['summary'];assert tr['gravity_mps2']==m['gravity_mps2'] and tr['spring_force_n']==m['spring_force_n'];h=hashlib.sha256(raw).hexdigest();dest=out/(h+'.json')
 # Shared views contain exactly the same original input record bytes.
 assert sha(dest)==h
 return dict(canonical_video_id=cid,status='RECOVERED',local_path=str(dest),sha256=h,config_document_type='original_generation_matrix_record',method='original_matrix_delivery_renderer_trajectory_and_video_hash_binding',evidence=dict(video_sha256=v['sha256'],config_byte_sha256=h,matrix_source_path=str(matrixfile),matrix_source_sha256=matrixhash,matrix_line_number=line,delivery_manifest_sha256=mh,renderer_source_path=str(renderer),renderer_source_sha256=e['renderer_source_sha256'],trajectory_sha256=e['trajectory_sha256'],source_document_is_standalone_config=False))
with concurrent.futures.ThreadPoolExecutor(12) as pool:new=list(pool.map(recover,catalog))
prior=load(O/'NEW_RECOVERIES.jsonl.gz');assert not ids&{x['canonical_video_id'] for x in prior}
for name,rows in [('NEW_RECOVERIES.jsonl.gz',prior+new),('REMAINING.jsonl.gz',[x for x in remaining if x['canonical_video_id'] not in ids])]:
 with gzip.open(O/name,'wt') as f:
  for x in rows:f.write(json.dumps(x)+'\n')
sourceout=O/'extra_metadata/provenance/t14s_original_inputs';sourceout.mkdir(parents=True,exist_ok=True)
for p in [matrixfile,ROOT/'runtime/render_t14s_physics.py',ROOT/'runtime/isaac_event_common.py',ROOT/'runtime/run_in_container_t14s.sh']:(sourceout/p.name).write_bytes(p.read_bytes())
receipt=dict(recovered=len(new),unique_original_matrix_records=len({x['sha256'] for x in new if x['config_document_type']=='original_generation_matrix_record'}),by_document_type=dict(collections.Counter(x['config_document_type'] for x in new)),source_matrix_sha256=matrixhash,original_delivery_manifest_sha256=mh,all_video_and_trajectory_hashes_match=True,total_new_recoveries=len(prior+new));(O/'T14_MATRIX_RECEIPT.json').write_text(json.dumps(receipt,indent=2));print(json.dumps(receipt),flush=True)
