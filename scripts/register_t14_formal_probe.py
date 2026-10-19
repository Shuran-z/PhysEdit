"""Register measured same-profile A endpoints for distance diagnostics, not full-scene certification."""
import json
from pathlib import Path
from physedit.boundary import digest,distance
OUT=Path('review/scene_family_completion_20261018')
def main():
 source=OUT/'t14_formal_backend_probe.json';runs=json.loads(source.read_text(encoding='utf-8'))
 identities={r['sample_id']:r for r in json.loads(Path('review/original_search_tasks_20261018/t14_source_identity.json').read_text(encoding='utf-8'))}
 rows=[]
 for run in runs:
  assert run['returncode']==0 and run['analyzer_returncode']==0
  outcome=run['outcome'];sid=outcome['sample_id'];ref=identities[sid]
  assert ref['config_sha256']==run['original_sha256']
  theta=ref['manifest_row']['channel_gap_m']
  rows.append(dict(reference_sample_id=sid,reference_config_sha256=run['original_sha256'],theta=theta,
   scene_id='T14',engine='genesis',family_id='A',target_event='passed_channel',reference_label=int(outcome['passed_channel']),
   source_file=source.name,source_sha256=digest(source),parameter_unit='m',
   boundary={'status':'observed','source':str(source.resolve()),'source_sha256':digest(source),'intervals':[{'bracket':[.018,.019]}]},
   eligibility='observed_interval_diagnostic_only',remaining='repeat/context transfer and answer-state binding pending; no model output scored',
   normalization_span=None))
 assert sorted((r['theta'],r['reference_label']) for r in rows)==[(.018,0),(.019,1)]
 for row in rows:row['pipeline_distance']=distance(row)
 (OUT/'t14_formal_probe_distance_registry.json').write_text(json.dumps(rows,indent=2),encoding='utf-8')
 print(json.dumps(rows))
if __name__=='__main__':main()
