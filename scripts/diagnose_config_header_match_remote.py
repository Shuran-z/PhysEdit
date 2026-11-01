import importlib.util,json
import gzip
from pathlib import Path
spec=importlib.util.spec_from_file_location('recovery','/data_cached/wangzijun_p25/scene_videos_20261031/recover_local_config_sources_remote.py');m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
root=Path('/home/wangzijun_p25/liyuhan/phydataset/ase_asset_importer/everyday_bifurcation_T01_v2_7s/configs/formal_52800_v2_full_chain/T01F52V2__bg01_home_ase__g01_moon__cfA_theta_minus_rep01__rmu230__g12250__g2m006__cmu340')
c=json.loads((root/'cam02.json').read_text())
p=Path('/data2/wangzijun_p25/phy2_standardization_20261027/phy2_release_v1.0.0_rc1/artifacts/ee/a_ee823505d7315f1ec23076cd8437291918651eba40e6e705920f653c89018594.json.gz')
d=m.input_prefix(p.read_bytes())
print(json.dumps({'keys':list(d),'equal':{k:c.get(k)==d.get(k) for k in d},'different_keys':{k:[key for key in set(c.get(k,{}))|set(d.get(k,{})) if c.get(k,{}).get(key)!=d.get(k,{}).get(key)] for k in ['experiment','scene_overrides']}}))
full=json.loads(gzip.decompress(p.read_bytes()))
print(json.dumps({'config_object':c['dynamic_objects'][0],'metadata_object':full['dynamic_objects'][0]},ensure_ascii=False)[:4500])
