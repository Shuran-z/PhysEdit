"""Read surviving original annotations at paths declared in published configs.

Only compact parameters, exact physical-config correspondence and kinematics are
returned. No new event threshold is invented by this recovery command.
"""
import argparse
import json
import subprocess

from scripts.export_original_boundary_distances import ROOT

REMOTE=r'''
import concurrent.futures,gzip,hashlib,json,math,pathlib,re
cache=pathlib.Path('/tmp/physedit_t06_t09_original_states_20261019');cache.mkdir(exist_ok=True)
def correspondence(out,c,raw):
 text=(gzip.decompress(raw) if raw[:2]==b'\x1f\x8b' else raw).decode();decoder=json.JSONDecoder()
 def field(name):
  match=re.search(r'(?m)^  "'+re.escape(name)+r'"\s*:',text)
  if match is None:raise ValueError('missing top-level '+name)
  start=match.end()
  while text[start].isspace():start+=1
  return decoder.raw_decode(text,start)[0]
 def core(rows):return [{k:r.get(k) for k in ['name','target','force_world','frame_start','frame_end']} for r in rows]
 scene=field('scene_overrides');forces=field('runtime_forces')
 out['runtime_force_core_matches']=core(forces)==core(c.get('runtime_forces',[]))
 out['scene_consumed_physics_matches']=all(scene.get(k)==v for k,v in c['scene_overrides'].items() if not k.startswith('raytracing'))
 out['comparison_note']='Compare applied force and timing fields; runtime annotations omit descriptive profile. Retain all configured non-raytracing scene fields.'
 return out
def read(r):
 c=r['config'];p=pathlib.Path(c['annotations']['save_path']);p=p if p.exists() else p.with_suffix(p.suffix+'.gz')
 if not p.exists():return dict(sample_id=r['sample_id'],scene_id=r['scene_id'],status='original_annotation_path_missing')
 receipt=cache/(r['sample_id']+'.json')
 if receipt.exists():
  old=json.loads(receipt.read_text(encoding='utf-8'))
  if 'runtime_force_core_matches' not in old:
   raw=p.read_bytes()
   if hashlib.sha256(raw).hexdigest()!=old['source_sha256']:raise ValueError('cached source annotation changed')
   old=correspondence(old,c,raw);receipt.write_text(json.dumps(old))
  return old
 try:
  raw=p.read_bytes();text=(gzip.decompress(raw) if raw[:2]==b'\x1f\x8b' else raw).decode()
  d,end=json.JSONDecoder().raw_decode(text);trailing=text[end:]
  if len(d.get('frames',[]))!=210:raise ValueError('incomplete original trajectory')
  specs={o['name']:o['spec'] for o in d['dynamic_objects']};expected={o['name']:o for o in c['dynamic_objects']}
  different=[name for name in set(specs)|set(expected) if specs.get(name)!=expected.get(name)]
  names=c['experiment']['tracked_objects'];frames=d['frames'];metrics={}
  for name in names:
   track=[next(o for o in f['objects'] if o['name']==name) for f in frames];initial=track[0]
   q=initial['quaternion_xyzw']
   def rotation(o):
    other=o['quaternion_xyzw'];den=math.sqrt(sum(x*x for x in q)*sum(x*x for x in other))
    return math.degrees(2*math.acos(min(1,abs(sum(a*b for a,b in zip(q,other)))/den)))
   metrics[name]=dict(initial_position=initial['position'],final_position=track[-1]['position'],max_displacement_m=max(math.dist(initial['position'],o['position']) for o in track),max_rotation_deg=max(rotation(o) for o in track))
  contacts=sorted({tuple(sorted([v['entity_a'],v['entity_b']])) for f in frames for v in f.get('contacts',[])})
  out=dict(sample_id=r['sample_id'],scene_id=r['scene_id'],source_path=str(p),source_sha256=hashlib.sha256(raw).hexdigest(),status='original_annotation_recovered',
   published_config_sha256=r['sha256'],revision=r['revision'],original_parameter=c['experiment']['parameter'],
   metadata_parameter=d['experiment']['parameter'],dynamic_spec_mismatches=different,
   runtime_forces_match=d.get('runtime_forces',[])==c.get('runtime_forces',[]),scene_overrides_match=d.get('scene_overrides')==c.get('scene_overrides'),
   metrics=metrics,observed_contact_pairs=contacts,frame_count=len(frames),
   trailing_nonwhitespace_bytes=len(trailing.encode()) if trailing.strip() else 0,
   parse_note='Read first complete 210-frame root document; preserve source checksum and report any stale trailing bytes; never modify original file.')
  out=correspondence(out,c,raw);receipt.write_text(json.dumps(out));return out
 except Exception as e:return dict(sample_id=r['sample_id'],scene_id=r['scene_id'],status='read_failed',error=str(e))
with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:rows=list(pool.map(read,INPUT))
print(json.dumps(rows))
'''


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--scenes',nargs='+',choices=['T06','T09','T10'],default=['T06','T09']);parser.add_argument('--out',default='t06_t09_surviving_original_state_evidence.json');args=parser.parse_args()
    rows=[r for f in ROOT.glob('published_batch_*.json') for r in json.loads(f.read_text(encoding='utf-8')) if r['scene_id'] in args.scenes]
    p=subprocess.run(['ssh','-o','BatchMode=yes','p25','python3 -'],input=REMOTE.replace('INPUT',repr(rows)).encode(),capture_output=True,timeout=1800)
    p.check_returncode();data=json.loads(p.stdout)
    (ROOT/args.out).write_text(json.dumps(data),encoding='utf-8')
    import collections
    print(json.dumps(dict(counts={str(k):v for k,v in collections.Counter((r['scene_id'],r['status']) for r in data).items()})))


if __name__=='__main__':main()
