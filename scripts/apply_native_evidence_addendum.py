"""Apply hash-bound independent observations to a local frozen formal snapshot.

This preserves all human task objects, old results and existing denominators.
Only previously pending original-task rows may acquire evidence in this entrypoint.
"""
from pathlib import Path
import argparse,json,copy,hashlib,sys
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'annotation_site'));sys.path.insert(0,str(ROOT))
from scoped_native_completion import apply,registered_pair_results
def digest(v):return hashlib.sha256(json.dumps(v,sort_keys=True).encode()).hexdigest()
def calculate(snapshot,registry,artifact_root):
 tasks=snapshot['tasks'];assert digest(tasks)==registry['source_task_snapshot_sha256'],'Task snapshot changed'
 before=snapshot['result'];result=copy.deepcopy(before);old=result['formal_critical_cohorts'];by={x['task_id']:x for x in old['outputs']};ids=[x['id']for x in registry['reviews']]
 assert len(ids)==len(set(ids))and all(x in by and by[x]['final_correct']is None for x in ids),'Addendum must bind unique previously pending outputs'
 assert all(x['kind']!='supplemental_generation'for x in registry['reviews']),'No new generation admission in this entrypoint'
 for r in registry['reviews']:
  task=next(t for t in tasks if t['id']==r['id']);assert digest(task['annotations'])==r['original_human_annotations_sha256'],'Original label identity changed'
 previous_completion=copy.deepcopy(old.get('scoped_native_completion'));apply(result,tasks,registry,artifact_root);formal=result['formal_critical_cohorts'];batch=formal.pop('scoped_native_completion');formal['scoped_native_completion']=previous_completion;formal['native_evidence_completion_867']=batch;formal['registered_pair_results']=registered_pair_results(formal)
 after={x['task_id']:x for x in formal['outputs']};assert set(after)==set(by)
 for tid,row in by.items():
  if tid not in ids:assert after[tid]==row,'Unrelated output changed: '+tid
 assert formal['references']==before['formal_critical_cohorts']['references']and formal['summary']==before['formal_critical_cohorts']['summary']
 for key in ['per_model','admitted_cohort','contact_amendment','completed_scoped_window_scores']:
  assert result[key]==before[key],'Historical score changed: '+key
 if 'formal_boundary_evaluation'in result:
  b=result['formal_boundary_evaluation'];b['explicit_formal_cohorts']=formal;b['current_per_scene_model']=formal['per_scene_model']
 assert digest(tasks)==registry['source_task_snapshot_sha256']
 return result
def main():
 p=argparse.ArgumentParser();p.add_argument('--snapshot',type=Path,required=True);p.add_argument('--reviews',type=Path,required=True);p.add_argument('--out',type=Path,required=True);a=p.parse_args()
 snapshot=json.loads(a.snapshot.read_text(encoding='utf8'));registry=json.loads(a.reviews.read_text(encoding='utf8'));result=calculate(snapshot,registry,ROOT/'annotation_site');a.out.mkdir(exist_ok=True)
 for name,v in [('FORMAL_RESULTS_CURRENT.json',result['formal_critical_cohorts']),('FORMAL_BOUNDARY_CURRENT.json',result['formal_boundary_evaluation'])]:(a.out/name).write_text(json.dumps(v,ensure_ascii=False),encoding='utf8')
 f=result['formal_critical_cohorts'];known=sum(x['final_correct']is not None for x in f['outputs']);receipt=dict(source_snapshot_sha256=hashlib.sha256(a.snapshot.read_bytes()).hexdigest(),reviews_sha256=hashlib.sha256(a.reviews.read_bytes()).hexdigest(),formal_results_sha256=hashlib.sha256((a.out/'FORMAL_RESULTS_CURRENT.json').read_bytes()).hexdigest(),previous_known=sum(x['final_correct']is not None for x in snapshot['result']['formal_critical_cohorts']['outputs']),current_known=known,added=known-sum(x['final_correct']is not None for x in snapshot['result']['formal_critical_cohorts']['outputs']),original_tasks_and_labels_unchanged=True,historical_results_unchanged=True,reference_membership_unchanged=True,output_membership_unchanged=True,website_updates=0,hf_uploads=0)
 (a.out/'INTEGRATION_RECEIPT.json').write_text(json.dumps(receipt,indent=2));print(json.dumps(receipt))
if __name__=='__main__':main()
