"""Explain failed T13 endpoint replays without changing labels or intervals."""
import collections
import json
from pathlib import Path
import subprocess
from scripts.export_original_boundary_distances import ROOT

REMOTE=r'''
import collections,hashlib,json,math,pathlib
base=pathlib.Path('/data_cached/wangzijun_p25/liyuhan');actors=['t13_driver_book','t13_falling_book','t13_drink_box'];rows=[]
for name in ['t13_current_boundary_context_bound_20261019','t13_original_full_retry_20261020']:
 root=base/name
 statuses=json.loads((root/'status.json').read_text())
 for failed in statuses:
  if failed['status']!='failed':continue
  job=PLANS[failed['job_id']]
  for endpoint in job['endpoints']:
   folder=root/job['job_id']/format(endpoint['theta'],'.12g')
   # Older plans use bracket coordinates on endpoints rather than a theta field.
   state_path=folder/'physics.json'
   if not state_path.exists():continue
   raw=state_path.read_bytes();s=json.loads(raw);frames=s['frames']
   if len(frames)!=168:continue
   track={n:[next(o['position'] for o in f['objects'] if o['name']==n) for f in frames] for n in actors}
   first=min([f['frame_index'] for f in frames if any(c.get('entity_a') in actors and c.get('entity_b') in actors and c.get('entity_a')!=c.get('entity_b') for c in f.get('contacts',[]))],default=18)
   deltas=[max(math.dist(endpoint['tracks'][n][i]['position'],track[n][i]) for n in actors) for i in range(168)]
   drink=track['t13_drink_box'];motion=max(math.dist(drink[18],p) for p in drink[18:]);drop=drink[18][2]-min(p[2] for p in drink[18:])
   actual=int(motion>=.01) if job['target_event']=='t13_drink_box_motion_ge_1cm' else int(drop>=.05)
   pre=max(deltas[:first],default=0);label_match=actual==endpoint['label']
   cfg=json.loads((folder/'config.json').read_text());expected={o['name']:o for o in endpoint['config']['dynamic_objects']};got={o['name']:o for o in cfg['dynamic_objects']}
   rows.append(dict(root=name,job_id=job['job_id'],sample_id=endpoint['sample_id'],theta=endpoint['theta'],event=job['target_event'],expected_label=endpoint['label'],actual_label=actual,
    precontact_error_m=pre,first_dynamic_contact_frame=first,first_over_5mm_frame=next((i for i,v in enumerate(deltas) if v>.005),None),
    motion_m=motion,drop_m=drop,source_objects_match=got==expected,scene_physics_match=cfg['scene_overrides']==endpoint['config']['scene_overrides'],
    classification='matches_under_corrected_window' if pre<=.005 and label_match else 'event_mismatch_after_matching_precontact' if pre<=.005 else 'precontact_mismatch',
    state_sha256=hashlib.sha256(raw).hexdigest(),source_state_sha256=endpoint['state_sha256']))
print(json.dumps(rows))
'''


def main():
    plans=json.loads((ROOT/'t13_current_search_plan_20261019.json').read_text())
    for j in plans:
        for e,t in zip(j['endpoints'],j['bracket']):e['theta']=t
    p=subprocess.run(['ssh','-o','BatchMode=yes','p25','python3 -'],input=REMOTE.replace('PLANS',repr({j['job_id']:j for j in plans})).encode(),capture_output=True,timeout=240)
    if p.returncode:raise RuntimeError(p.stderr.decode(errors='replace'))
    rows=json.loads(p.stdout);dest=ROOT/'t13_all_failed_endpoint_diagnostics_20261020.json';dest.write_text(json.dumps(rows,indent=2))
    summary=dict(examined_endpoint_states=len(rows),unique_jobs=len({r['job_id'] for r in rows}),classifications=dict(collections.Counter(r['classification'] for r in rows)),
        physical_config_mismatches=sum(not r['source_objects_match'] or not r['scene_physics_match'] for r in rows),
        root_cause_claim='Observed replay differences only; no proof of a unique internal solver cause. Original v6 initializes without explicit seed.',original_reference_labels_unchanged=True)
    (ROOT/'t13_failed_endpoint_diagnostic_summary_20261020.json').write_text(json.dumps(summary,indent=2));print(json.dumps(summary))


if __name__=='__main__':main()
