"""Read existing T04 candidates; do not infer visible penetration from telemetry."""
import base64
import hashlib
import json
from pathlib import Path
import zlib
from physedit.core100_critical import load
from scripts.audit_core100_v2_t03_contact_geometry import REMOTE as GEOMETRY
from review.cvpr_experiments_20261031.archive_hunyuan_checkpoint_sftp import rpc,P21_OPTIONS

ROOT=Path(__file__).resolve().parents[1];WORK=ROOT/'review/core100_v2_resolution_20261102'
REMOTE=r'''
rows=[]
for p in POINTS:
 path=Path(p['state_path']);raw=path.read_bytes();decoded=gzip.decompress(raw)
 assert p['state_sha256']in[hashlib.sha256(raw).hexdigest(),hashlib.sha256(decoded).hexdigest()]
 s=json.loads(decoded);assert len(s['frames'])==210
 specs={o['name']:o.get('spec',o)for o in s['dynamic_objects']};book='t04v3_stack_book_bottom';ramp='t04v3_folder_ramp_pbr';can='t04v3_chain_can_2';mug='t04v3_chain_mug'
 peak=0.;frame_at_peak=None;hits=[];frames=s['frames'][4:155]
 track=[next(o for o in f['objects']if o['name']==mug)for f in frames];q=track[0]['quaternion_xyzw']
 disp=max(math.dist(track[0]['position'],o['position'])for o in track)
 angle=max(math.degrees(2*math.acos(min(1.,abs(sum(x*y for x,y in zip(q,o['quaternion_xyzw'])))/math.sqrt(sum(x*x for x in q)*sum(x*x for x in o['quaternion_xyzw'])))))for o in track)
 for f in frames:
  obs={o['name']:o for o in f['objects']}
  d=box_depth(obs[book],specs[book].get('collision_proxy_size',specs[book]['size']),obs[ramp],specs[ramp].get('collision_proxy_size',specs[ramp]['size']))
  if d>peak:peak=d;frame_at_peak=f['frame_index']
  contacts=f.get('original_exterior_contacts',[])if f['frame_index']>=s['render']['pre_static_frames']else f.get('contacts',[])
  if any({a['entity_a'],a['entity_b']}=={can,mug}for a in contacts):hits.append(f['frame_index'])
 rows.append(dict(theta=p['theta'],stored_state_sha256=hashlib.sha256(raw).hexdigest(),decoded_state_sha256=hashlib.sha256(decoded).hexdigest(),
  label=int(bool(hits)and(angle>=18 or disp>=.04)),can_mug_contact_frames=hits,mug_maximum_displacement_m=disp,mug_maximum_angle_deg=angle,
  maximum_saved_book_ramp_overlap_m=peak,frame_at_peak=frame_at_peak,native_peak_m=p['native_peak_m'],config_seed=json.loads((path.parent/'config.json').read_text()).get('seed')))
path=Path(TARGET['state_path']);raw=path.read_bytes();s=json.loads(gzip.decompress(raw))
root=Path('/home/wangzijun_p25/liyuhan/phydataset/ase_asset_importer');name='T04F880V1__bg01_home_ase__g02_mars__global_03__rep01';found=[]
for project in root.glob('*T04*'):
 for pattern in ['configs/*/'+name+'/cam01.json','configs/*/'+name+'__cam01/*.json','configs/*/*/'+name+'/cam01.json']:
  found.extend(str(p)for p in project.glob(pattern))
print(json.dumps(dict(points=rows,native_top_level_keys=list(s),original_experiment_seed=s['experiment'].get('random_seed'),matching_config_paths=found,
 candidate_projects=[str(p)for p in root.glob('*T04*')],formal_admission=False,source_modified=False)))
'''


def main():
    data,_=load();row=next(r for r in data['cases']if r['clip_id']=='T04_C02')
    receipts=json.loads((WORK/'t04_original_receipts.json').read_text())['receipts']
    points=[p for p in receipts if p['theta']in[.1,.125]or(p['theta']==.15 and'source_repeat'in p['state_path'])]
    payload='POINTS='+repr(points)+'\nTARGET='+repr(row['reference_native_state_binding'])+'\n'+GEOMETRY.split('rows=[]')[0]+'\n'+REMOTE
    encoded=base64.b64encode(zlib.compress(payload.encode())).decode()
    result=rpc(P21_OPTIONS,'p25','import base64,zlib;exec(zlib.decompress(base64.b64decode('+repr(encoded)+')))')
    raw=json.dumps(result,indent=2).encode();digest=hashlib.sha256(raw).hexdigest();path=WORK/('t04_saved_geometry_'+digest[:12]+'.json');path.write_bytes(raw)
    (WORK/'T04_SAVED_GEOMETRY.json').write_text(json.dumps(dict(path=path.relative_to(ROOT).as_posix(),sha256=digest),indent=2))
    print(json.dumps(result))


if __name__=='__main__':main()
