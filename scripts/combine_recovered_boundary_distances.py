"""Combine real recovered distances without conflating original and new references.

This numerical input catalog does not apply visual/inversion/near-bucket gates.
It does not itself certify event ground truth or promote rendering stars to
solved thresholds. Retired T19 records remain explicitly marked historical.
"""
import collections
import csv
import hashlib
import json
from pathlib import Path

from scripts.export_original_boundary_distances import ROOT, distances


def read(path):
    if not path.exists():return []
    if path.suffix=='.jsonl':return [json.loads(s) for s in path.read_text(encoding='utf-8').splitlines() if s.strip()]
    return json.loads(path.read_text(encoding='utf-8'))


def normalize(row,source,kind):
    row=dict(row)
    bracket=row.get('original_boundary_interval') or row.get('boundary',{}).get('bracket')
    if bracket is not None:row.update(original_boundary_interval=bracket,**distances(row['theta'],bracket=bracket))
    row['reference_category']=kind
    row['ledger_source']=str(source.resolve())
    row['publication_status']='retired_T19_render' if row['scene_id']=='T19' else row.get('publication_status','published_reference')
    row['extra_validation_blocks_distance']=False
    row['distance_record_id']=hashlib.sha256(json.dumps(dict(engine=row.get('engine'),revision=row.get('revision'),sample_id=row['sample_id'],family=row.get('family_id'),theta=row['theta'],parameter=row.get('parameter_name'),
        event=row.get('target_event'),kind=kind,bracket=bracket,point=row.get('original_critical_value',row.get('original_rendering_star'))),sort_keys=True).encode()).hexdigest()
    return row


def main():
    out=ROOT/'original_value_distance_ledger'
    sources=[(out/'sample_distances.jsonl','recovered_original'),(out/'recorded_rendering_star_distances.jsonl','rendering_star'),
        (out/'t03_recorded_rendering_star_distances.jsonl','rendering_star'),(out/'t11_recorded_rendering_star_distances.jsonl','rendering_star')]
    sources += [(out/name,'supplemental') for name in ['t03_supplemental_sample_distances.jsonl','t04_t05_supplemental_sample_distances.jsonl',
        't12_supplemental_sample_distances.jsonl','t15_supplemental_sample_distances.jsonl','t11_supplemental_sample_distances.jsonl','t08_supplemental_sample_distances.jsonl','t06_supplemental_sample_distances.jsonl']]
    sources += [(ROOT/'t07_original_search_distance_registry.json','supplemental')]
    rows=[];source_counts=[]
    for path,kind in sources:
        loaded=read(path);rows.extend(normalize(r,path,kind) for r in loaded);source_counts.append(dict(path=str(path),records=len(loaded)))
    for filename in ['t13_current_solver_distance_registry.json','t10_probe_distance_registry.json']:
      path=ROOT/filename
      for r in read(path):
        # One sample may have several local transition windows. Retain each.
          for interval in r['boundary'].get('intervals',[]):
            rows.append(normalize({**r,'original_boundary_interval':interval['bracket'],'refinement_job_id':interval.get('job_id')},path,'supplemental'))
    unique={}
    for row in rows:unique.setdefault(row['distance_record_id'],row)
    rows=list(unique.values())
    (out/'combined_distance_inputs.jsonl').write_text(''.join(json.dumps(r,ensure_ascii=False)+'\n' for r in rows),encoding='utf-8')
    fields=['distance_record_id','scene_id','engine','sample_id','revision','family_id','target_event','theta','reference_category','original_critical_value','original_rendering_star',
        'original_boundary_interval','signed_distance','absolute_distance','distance_lower','distance_upper','publication_status','ledger_source']
    with (out/'combined_distance_inputs.csv').open('w',encoding='utf-8-sig',newline='') as stream:
        writer=csv.DictWriter(stream,fieldnames=fields,extrasaction='ignore');writer.writeheader();writer.writerows(rows)
    summary=[]
    for scene in [f'T{i:02}' for i in range(1,21)]:
        selected=[r for r in rows if r['scene_id']==scene]
        counts={kind:len({(r['engine'],r.get('revision'),r['sample_id']) for r in selected if r['reference_category']==kind}) for kind in ['recovered_original','rendering_star','supplemental']}
        numerical=[r for r in selected if r['reference_category']!='rendering_star']
        summary.append(dict(scene_id=scene,**counts,unique_samples_with_numerical_reference=len({(r['engine'],r.get('revision'),r['sample_id']) for r in numerical}),
            completion='not_complete',retired=scene=='T19'))
    (out/'combined_all20_summary.json').write_text(json.dumps(dict(all20_completed=False,scenes=summary,source_counts=source_counts,
        records=len(rows),important='Per-category counts overlap. Rendering-star distances are separate from solved boundary distances. Every scene still requires its full family/context coverage check.'),ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(dict(records=len(rows),scenes=summary),ensure_ascii=False))


if __name__=='__main__':main()
