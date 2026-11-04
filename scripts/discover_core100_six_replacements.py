"""Read published T18 native states for source-only replacement selection.

No simulator is launched, and missing extraction/contact contracts are kept
separate rather than inferred from filename order or a height threshold.
"""
import hashlib
import json
from pathlib import Path

from review.cvpr_experiments_20261031.archive_hunyuan_checkpoint_sftp import rpc, P21_OPTIONS

ROOT = Path(__file__).resolve().parents[1]
WORK = ROOT / 'review/core100_v3_remaining8_20261103'
REMOTE = r'''
import gzip,json,pathlib,copy,hashlib,collections
root=pathlib.Path('/home/wangzijun_p25/liyuhan/phydataset/ase_asset_importer/everyday_bifurcation_72k_T16_T20_v1/production')
rows=[];excluded=[]
def norm(x):
 if isinstance(x,float):return round(x,8)
 if isinstance(x,dict):return{k:norm(v)for k,v in x.items()}
 if isinstance(x,list):return[norm(v)for v in x]
 return x
for p in sorted(root.glob('T18__bg01_home_ase__g03_earth__*/metadata/*__cam01.json.gz')):
 raw=p.read_bytes();decoded=gzip.decompress(raw);s=json.loads(decoded);e=s['experiment']
 if 'supported_book_names'not in e or len(s.get('frames',[]))!=210 or not s['scene_overrides'].get('record_contacts'):
  excluded.append(dict(path=str(p),reason='supported_set_or_complete_contact_contract_missing'));continue
 axis=e['parameter']['parameter_name'];theta=e['parameter']['parameter_value'];names=set(e['supported_book_names'])
 specs={o['name']:copy.deepcopy(o.get('spec',o))for o in s['dynamic_objects']}
 for n,o in specs.items():
  if axis=='contact_friction'and n.startswith('t18_book_'):o['friction']=0.
  if axis=='overlap_length'and n in names:o['pose']['position'][0]+=theta
 phy={k:v for k,v in s['scene_overrides'].items()if not k.startswith('raytracing')}
 ctx=hashlib.sha256(json.dumps(norm({'specs':specs,'physics':phy,'pre_static_frames':s['render']['pre_static_frames'],'steps':s['render']['physics_steps_per_render_frame']}),sort_keys=True).encode()).hexdigest()
 table='frozen_tabletop_collision_slab'
 hits=[c for c in s['frames'][154].get('contacts',[])if any({c.get('entity_a'),c.get('entity_b')}=={n,table}for n in names)]
 rows.append(dict(sample_id=e['trajectory_id'],axis=axis,theta=theta,context_sha256=ctx,label=int(bool(hits)),state_path=str(p),state_stored_sha256=hashlib.sha256(raw).hexdigest(),state_decoded_sha256=hashlib.sha256(decoded).hexdigest(),supported=sorted(names),native_video=s['render']['save_video'],variant=e.get('event_variant_id'),seed=e.get('seed'),frame_count=len(s['frames'])))
groups=collections.defaultdict(list)
for r in rows:groups[(r['axis'],r['context_sha256'])].append(r)
contrasts=[v for v in groups.values()if{r['label']for r in v}=={0,1}]
print(json.dumps({'rows':rows,'contrasts':contrasts,'groups':len(groups),'excluded':excluded,'new_simulations':0}))
'''


def main():
    data = rpc(P21_OPTIONS, 'p25', REMOTE)
    raw = json.dumps(data, indent=2).encode()
    digest = hashlib.sha256(raw).hexdigest()
    WORK.mkdir(exist_ok=True)
    path = WORK / ('t18_published_contrasts_' + digest[:12] + '.json')
    if path.exists():
        assert path.read_bytes() == raw
    else:
        path.write_bytes(raw)
    (WORK / 'T18_PUBLISHED_CONTRASTS.json').write_text(json.dumps(dict(
        path=path.relative_to(ROOT).as_posix(), sha256=digest), indent=2))
    print(json.dumps(dict(rows=len(data['rows']), groups=data['groups'],
        excluded=len(data['excluded']), contrasts=[[
            [r['sample_id'], r['theta'], r['label']] for r in group
        ] for group in data['contrasts']])))


if __name__ == '__main__':
    main()
