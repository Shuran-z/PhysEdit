"""Use existing state-audited T15 outcomes; no new rendering or VLM labeling."""
import json
from pathlib import Path
from collections import defaultdict
from physedit.boundary import digest,read_rows
from physedit.boundary_recovery import recover,observed_distances

def main():
 source=Path('review/t15_boundary_pilot_20261014/reference_audit.json')
 groups=defaultdict(list)
 for r in json.loads(source.read_text(encoding='utf-8'))['rows']:
  groups[r['speed_context_hash']].append(dict(sample_id=r['sample_id'],theta=r['speed'],
       label=r['raw_fall'],valid=r['audit_valid'] and r['cached_fall_agrees']))
 records={k:recover(v) for k,v in groups.items()}
 out=Path('review/release_boundary_binding_20261018')
 (out/'t15_observed_intervals.json').write_text(json.dumps(dict(source=str(source),source_sha256=digest(source),target='reference raw_fall under archived audit definition',groups=records),indent=2),encoding='utf-8')
 keys=read_rows('review/h3_delivery_audit_20261016/recomputed_with_cv2/evaluation/answers.jsonl')
 rows=[dict(sample_id=k['sample_id'],theta=k['theta'],context=k['source_group_id'],evidence_kind='observed_sample_transitions',distance_to_observed_intervals=observed_distances(k['theta'],records[k['source_group_id']]),certified_distance=None,near_bin=None) for k in keys]
 (out/'h3_observed_distances.json').write_text(json.dumps(rows,indent=2),encoding='utf-8')
 answers=Path('review/h3_delivery_audit_20261016/recomputed_with_cv2/evaluation/answers.jsonl')
 audit_rows={r['sample_id']:r for r in json.loads(source.read_text(encoding='utf-8'))['rows']}
 bindings=[]
 for k in keys:
  reference=audit_rows[k['reference_sample_id']]
  assert reference['state_sha256']==k['reference_state_sha256'] and reference['speed_context_hash']==k['source_group_id'] and reference['speed']==k['theta']
  row={f:k[f] for f in ('sample_id','reference_sample_id','reference_state_sha256','source_group_id','target_event','theta')}
  row.update(source_file='../t15_boundary_pilot_20261014/reference_audit.json',source_sha256=digest(source),mapping_status='matched',mapping_evidence='reference state hash, speed, fixed physics context matched to archived state audit; labels are reference raw_fall',parameter_name='initial_book_speed',parameter_unit='m/s',boundary={'status':'observed','intervals':records[k['source_group_id']]['intervals']})
  bindings.append(row)
 (out/'h3_observed_bindings.json').write_text(json.dumps(dict(answers_sha256=digest(answers),bindings=bindings),indent=2),encoding='utf-8')
 print(json.dumps(dict(groups=len(records),with_intervals=sum(bool(r['intervals']) for r in records.values()),h3=rows)))

if __name__=='__main__':main()
