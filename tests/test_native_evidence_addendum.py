import copy,json
from pathlib import Path
import pytest
from scripts.apply_native_evidence_addendum import calculate,digest,ROOT

W=ROOT/'review/all20_completion_20261101'
def inputs():
 return (json.loads((W/'existing_reuse_audit_20261102/snapshot.json').read_text(encoding='utf8')),json.loads((W/'evidence_completion_867_20261102/FIRST15_REVIEWS.json').read_text(encoding='utf8')))

def test_real_addendum_preserves_humans_denominators_and_every_old_score():
 snapshot,registry=inputs();before=digest(snapshot);out=calculate(snapshot,registry,ROOT/'annotation_site')
 old=snapshot['result']['formal_critical_cohorts'];new=out['formal_critical_cohorts'];assert digest(snapshot)==before
 assert len(new['outputs'])==len(old['outputs'])and new['references']==old['references']
 assert sum(r['final_correct']is not None for r in new['outputs'])==1029
 by={x['task_id']:x for x in new['outputs']}
 assert all(by[x['task_id']]==x for x in old['outputs']if x['final_correct']is not None)
 assert new['scoped_native_completion']==old['scoped_native_completion']
 assert new['native_evidence_completion_867']['reviewed']==15

def test_wrong_window_reference_artifact_and_original_label_identity_are_rejected():
 snapshot,registry=inputs();original=digest(snapshot)
 for key,value in [('horizon_s',.5),('reference_video_sha256','0'*64),('original_human_annotations_sha256','0'*64)]:
  bad=copy.deepcopy(registry);bad['reviews'][0][key]=value
  with pytest.raises((ValueError,AssertionError)):calculate(snapshot,bad,ROOT/'annotation_site')
 bad=copy.deepcopy(registry);bad['reviews'][0]['artifacts'][0]['sha256']='0'*64
 with pytest.raises(ValueError):calculate(snapshot,bad,ROOT/'annotation_site')
 assert digest(snapshot)==original

def test_cannot_overwrite_already_scored_output_or_add_a_new_generation():
 snapshot,registry=inputs();bad=copy.deepcopy(registry);bad['reviews'][0]['id']=next(x['task_id']for x in snapshot['result']['formal_critical_cohorts']['outputs']if x['final_correct']is not None)
 with pytest.raises(AssertionError):calculate(snapshot,bad,ROOT/'annotation_site')
 bad=copy.deepcopy(registry);bad['reviews'][0]['kind']='supplemental_generation'
 with pytest.raises(AssertionError):calculate(snapshot,bad,ROOT/'annotation_site')
