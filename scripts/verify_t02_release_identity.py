"""Verify all three released camera files against original T02 production output."""
import json,subprocess
from pathlib import Path
from bind_t14_original_contract import REMOTE,OUT

code=REMOTE.replace('everyday_bifurcation_T14_v2_pose_gate','everyday_bifurcation_T02_v2_causal_gate').replace('formal_r006','formal_52800_r006_p26_480p')
code=code.replace("video=root/'formal_52800_r006_p26_480p'/r['sample_id']/'videos'/(r['sample_id']+'__'+cam+'.mp4')", "cc=json.loads((p.parent/(cam+'.json')).read_text());video=pathlib.Path(cc['render']['save_video'])")
p=subprocess.run(['ssh','-o','BatchMode=yes','p26','python3 -'],input=code.encode(),capture_output=True,timeout=300)
(OUT/'t02_remote_stderr.txt').write_bytes(p.stderr);p.check_returncode()
rows=json.loads(p.stdout);(OUT/'t02_source_identity.json').write_bytes(p.stdout)
inventory={r['sample_id']:r for r in map(json.loads,Path('../dataset_splits_v2/all_selected_trajectories.jsonl').read_text().splitlines()) if r['event_id']=='T02' and r['engine']=='genesis'}
identities={r['sample_id']:r for r in rows}
bindings=json.loads((OUT/'t02_original_family_bindings.json').read_text())
for b in bindings:
 r=identities[b['sample_id']];pub=inventory.get(b['sample_id'])
 b['release_video_hashes_match']=bool(pub) and all(r.get('videos',{}).get(cam,{}).get('sha256')==v['sha256'] for cam,v in pub['videos'].items())
 expected=r['manifest_row']['config_sha256']['cam01']
 b['source_config_hash_matches_manifest']=r.get('config_sha256','').lower()==expected.lower()
 if b['release_video_hashes_match'] and b['source_config_hash_matches_manifest'] and b['fixed_manifest_values_match'] and b['calibration_report_hash_match']:
  b['status']='release_bytes_and_original_task_linked_pending_solver_contract_validation'
(OUT/'t02_original_family_bindings.json').write_text(json.dumps(bindings,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps({'total':len(bindings),'video_matches':sum(b['release_video_hashes_match'] for b in bindings),'config_matches':sum(b['source_config_hash_matches_manifest'] for b in bindings)}))
