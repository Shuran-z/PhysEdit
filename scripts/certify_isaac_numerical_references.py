"""Certify original Isaac numerical registrations; keep RGB observability separate."""
import collections,json
from pathlib import Path
from physedit.boundary import digest,distance
OUT=Path('review/scene_family_completion_20261018')
def main():
 source=OUT/'isaac_original_scoring_provenance.json';proof={r['sample_id']:r for r in json.loads(source.read_text())}
 old=json.loads((OUT/'isaac_original_distance_registry.json').read_text());rows=[]
 for r in old:
  p=proof[r['sample_id']];q=p['metadata']['qa.json'];e=p['metadata']['event_graph.json'];b=r['boundary']['intervals'][0]['bracket'];span=p['range']['normalization_span']
  checks=dict(source_and_video_hashes_match=p['all_hashes_match'],frozen_domain_hashes_match=p['range']['all_frozen_input_hashes_match'],physics_pass=q['status']=='PASS',events_match_qa=e['depth']==q['depth']==r['reference_depth'],repeat_both_outcomes=r['same_repeat_both_outcomes'],media_decode_pass=p['metadata']['media_qa.json']['status']=='PASS',camera_projection_pass=p['metadata']['camera_visibility.json']['status']=='PASS',within_original_domain=p['range']['domain'][0]<=r['theta']<=p['range']['domain'][1],positive_normalization=span>0)
  x={**r,'numerical_checks':checks,'numerical_reference_verified':all(checks.values()),'reference_event_vector':{'depth_ge_'+str(d):int(e['depth']>=d) for d in [1,2,3]},'reference_event_nodes':e['nodes'],'reference_state_sha256':p['complete']['files'].get('state.json.gz',p['complete']['files'].get('state.json')),'reference_video_hashes':p['video_hashes'],'runtime_signature':p['complete']['signature'],'normalization_basis':p['range'],'mapping_status':'matched','mapping_evidence':dict(source_file=str(source.resolve()),source_sha256=digest(source)),'rgb_observability_status':'pending_static_occlusion_review','boundary':dict(status='verified' if all(checks.values()) else 'unavailable',source=str(source.resolve()),source_sha256=digest(source),normalization_span=span,bracket=b),'blocking_reasons':['reference_rgb_observability_pending'],'formal_near_eligible':False}
  x['distance']=distance(x);x['near_numerical_eligible']=x['numerical_reference_verified'] and x['distance']['bin']=='near';rows.append(x)
 (OUT/'isaac_verified_numerical_registry.json').write_text(json.dumps(rows,indent=2),encoding='utf-8')
 summary=dict(total=len(rows),numerically_verified=sum(r['numerical_reference_verified'] for r in rows),near_numerical=sum(r['near_numerical_eligible'] for r in rows),rgb_formally_ready=0,bins=dict(collections.Counter(str(r['distance']['bin']) for r in rows)))
 (OUT/'isaac_verified_numerical_summary.json').write_text(json.dumps(summary,indent=2));print(json.dumps(summary))
if __name__=='__main__':main()
