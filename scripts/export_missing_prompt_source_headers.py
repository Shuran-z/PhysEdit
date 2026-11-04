"""Recover compact, hash-checked original metadata headers for all 2640 fallback rows."""
from pathlib import Path
import base64,gzip,json,sys
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from scripts.boundary_ssh import remote_text
OUT=ROOT/'review/full_prompt_audit_20261102'
rows=[json.loads(l) for l in gzip.open(ROOT/'review/scene_videos_20261031/MISSING_CONFIG_ALIGNMENT.jsonl.gz','rt',encoding='utf8')]
inputs=[{k:r[k] for k in ['canonical_video_id','video_sha256','metadata_source_key','metadata_source_sha256','metadata_artifact_sha256']} for r in rows]
code='''from pathlib import Path
import json,gzip,hashlib,base64,concurrent.futures
inputs=INPUTS
base=Path('/data2/wangzijun_p25/phy2_standardization_20261027')
keys={r['metadata_source_key'] for r in inputs};records={}
for line in (base/'processed.jsonl').open():
 r=json.loads(line)
 if r['source_key'] in keys:records[r['source_key']]=r
def one(r):
 a=records[r['metadata_source_key']];p=base/'phy2_release_v1.0.0_rc1'/a['path'];b=p.read_bytes()
 assert hashlib.sha256(b).hexdigest()==a['sha256']==r['metadata_artifact_sha256']
 raw=gzip.decompress(b) if b[:2]==b'\\x1f\\x8b' else b
 source_bytes=raw if a.get('storage_transform')=='gzip_lossless' else b
 assert hashlib.sha256(source_bytes).hexdigest()==r['metadata_source_sha256']
 prefix=raw[:131072].decode(errors='replace');suffix=raw[-262144:].decode(errors='replace');decoder=json.JSONDecoder();header={}
 for k in ['sample_id','experiment','render','scene_overrides','dynamic_objects','runtime_forces']:
  needle='\\n  '+json.dumps(k)+':';text=suffix if needle in suffix else prefix;at=text.rfind(needle)
  if at>=0:header[k]=decoder.raw_decode(text[at+len(needle):].lstrip())[0]
 assert header.get('experiment') and header.get('dynamic_objects')
 return {**r,'header':header,'artifact_path':str(p)}
with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:out=list(pool.map(one,inputs))
print(base64.b64encode(gzip.compress(json.dumps(out).encode(),compresslevel=1)).decode())
'''.replace('INPUTS',repr(inputs))
if '--background' in sys.argv:
    job=code.split('with concurrent.futures.ThreadPoolExecutor')[0]+'''
root=Path('/tmp/phy_full_prompt_metadata_audit_20261102');root.mkdir(exist_ok=True)
partial=root/'headers.jsonl';done={}
if partial.exists():
 for line in partial.read_text().splitlines():
  r=json.loads(line);done[r['canonical_video_id']]=r
todo=[r for r in inputs if r['canonical_video_id'] not in done]
with partial.open('a') as dest, concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:
 for r in pool.map(one,todo):
  done[r['canonical_video_id']]=r;dest.write(json.dumps(r)+'\\n');dest.flush()
  if len(done)%10==0:(root/'PROGRESS.json').write_text(json.dumps({'completed':len(done),'total':len(inputs)}))
assert len(done)==2640
(root/'headers.json.gz').write_bytes(gzip.compress(json.dumps(list(done.values())).encode(),compresslevel=1))
(root/'PROGRESS.json').write_text(json.dumps({'completed':len(done),'total':len(inputs),'status':'complete'}))
'''
    launcher='''from pathlib import Path
import subprocess,sys,json
root=Path('/tmp/phy_full_prompt_metadata_audit_20261102');root.mkdir(exist_ok=True)
p=root/'collector.py';p.write_text(JOB)
with (root/'collector.log').open('a') as log:
 process=subprocess.Popen([sys.executable,'-u',str(p)],stdin=subprocess.DEVNULL,stdout=log,stderr=log,start_new_session=True)
(root/'PID').write_text(str(process.pid));print(json.dumps({'pid':process.pid,'directory':str(root)}))
'''.replace('JOB',repr(job))
    print(remote_text('p25',launcher,timeout=30));sys.exit(0)
if '--fetch' in sys.argv:
    encoded=remote_text('p25',"from pathlib import Path;import base64;print(base64.b64encode(Path('/tmp/phy_full_prompt_metadata_audit_20261102/headers.json.gz').read_bytes()).decode())",timeout=90)
else:encoded=remote_text('p25',code,timeout=300,attempts=1)
b=base64.b64decode(encoded);out=json.loads(gzip.decompress(b));assert len(out)==2640
(OUT/'ORIGINAL_METADATA_HEADERS.json.gz').write_bytes(b)
print(json.dumps({'recovered_headers':len(out),'videos_bound':len({r['canonical_video_id'] for r in out})}))
