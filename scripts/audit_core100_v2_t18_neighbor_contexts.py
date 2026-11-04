"""Record why neighboring T18 parameter IDs cannot share a fixed context."""
import hashlib
import json
from pathlib import Path
from review.cvpr_experiments_20261031.archive_hunyuan_checkpoint_sftp import rpc,P21_OPTIONS

ROOT=Path(__file__).resolve().parents[1];WORK=ROOT/'review/core100_v2_resolution_20261102'
REMOTE=r'''
import gzip,hashlib,json
from pathlib import Path
root=Path('/home/wangzijun_p25/liyuhan/phydataset/ase_asset_importer/everyday_bifurcation_72k_T16_T20_v1/production')
rows=[]
for index in [18,19,20]:
 sid='T18__bg01_home_ase__g01_moon__contact_friction__p'+str(index).zfill(3)
 path=root/sid/'metadata'/(sid+'__cam01.json.gz');raw=path.read_bytes();state=json.loads(gzip.decompress(raw))
 specs={o['name']:o.get('spec',o)for o in state['dynamic_objects']};books={n:o for n,o in specs.items()if n.startswith('t18_book_')}
 rows.append(dict(sample_id=sid,state_path=str(path),stored_state_sha256=hashlib.sha256(raw).hexdigest(),
  theta=state['experiment']['parameter']['parameter_value'],variant_id=state['experiment'].get('event_variant_id'),
  book_count=len(books),supported=state['experiment'].get('supported_book_names'),
  moving_books={n:o.get('motion',{})for n,o in books.items()if any(o.get('motion',{}).get('initial_velocity',[0,0,0]))},
  physical_specs={n:{k:o.get(k)for k in['size','collision_proxy_size','mass','pose','motion','friction']}for n,o in books.items()}))
print(json.dumps(dict(cases=rows,simulations_started=0,original_files_modified=False,
 conclusion='Neighboring friction IDs also change physical topology, placement and/or extraction. They are not a fixed-context friction contrast.')))
'''


def main():
    result=rpc(P21_OPTIONS,'p25',REMOTE);raw=json.dumps(result,indent=2).encode();digest=hashlib.sha256(raw).hexdigest()
    path=WORK/('t18_context_audit_'+digest[:12]+'.json')
    if not path.exists():path.write_bytes(raw)
    else:assert path.read_bytes()==raw
    (WORK/'T18_CONTEXT_AUDIT.json').write_text(json.dumps(dict(path=path.relative_to(ROOT).as_posix(),sha256=digest),indent=2),encoding='utf8')
    print(json.dumps([dict(sample_id=r['sample_id'],theta=r['theta'],books=r['book_count'],variant=r['variant_id'],moving=r['moving_books'])for r in result['cases']]))


if __name__=='__main__':main()
