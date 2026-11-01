"""Independent qualitative observation; never changes the frozen event scorer."""
import collections,hashlib,json
from workflow import final_annotation

KEY='tissue_box_translation_independent_v1'
CONTACT='can_tissue_box_contact'
DEFINITION={'id':KEY,'version':'box-translation-independent-v1','name':'纸巾盒是否发生平移',
 'definition':'在观察窗内，原纸巾盒相对稳定场景位置发生可辨认的平移；对照至少两个时刻。无需罐子先接触。排除镜头运动、仅旋转、物体替换。看不清或出画无法确认时选不可判。此项没有2厘米阈值，不等同于末态位移。',
 'requires_prior_can_contact':False,'unit':'qualitative_visual_translation','scope':'supplemental_observation_only_not_original_score'}
DEFINITION_SHA=hashlib.sha256(json.dumps(DEFINITION,ensure_ascii=False,sort_keys=True).encode()).hexdigest()

def eligible(p):return p.get('clip_id','').startswith('T17_') and CONTACT in p.get('protocol',{}).get('events',{})

def view(task,user):
 if not eligible(task['payload']):return None
 record=task.get('independent_observations',{}).get(KEY)
 primary=task['annotations'].get('primary',{}).get('payload',{})
 return {'definition':DEFINITION,'definition_sha256':DEFINITION_SHA,'record':record,
  'can_edit':user['id']==task['primary_id'] and not task['payload'].get('annotation_hold',{}).get('active'),
  'saved_quality_is_measurable':primary.get('quality',{}).get('status')=='pass'}

def cross_statistics(tasks,preliminary=False):
 bins=collections.defaultdict(collections.Counter)
 for task in tasks:
  p=task['payload']
  if not eligible(p):continue
  c=bins[p['model']];c['registered']+=1
  if p.get('annotation_hold',{}).get('active'):c['held']+=1;continue
  c['active']+=1;human=final_annotation(task)
  if preliminary and not human:
   a=task['annotations'].get('primary',{})
   if a.get('submitted'):human=a['payload']
  if not human:c['human_pending']+=1;continue
  if human.get('quality',{}).get('status')!='pass':c['quality_blocked']+=1;continue
  c['measurable_human']+=1
  record=task.get('independent_observations',{}).get(KEY)
  if not record:c['motion_missing']+=1;continue
  if record.get('video_sha256')!=p['video_sha256'] or record.get('definition_sha256')!=DEFINITION_SHA:
   c['motion_binding_invalid']+=1;continue
  contact=human.get('events',{}).get(CONTACT,{}).get('label');motion=record.get('label')
  if contact not in ('yes','no')or motion not in ('yes','no'):c['pair_unknown']+=1;continue
  c['paired_binary']+=1;c['contact_'+contact+'_motion_'+motion]+=1
 def finish(c):
  out={k:c[k]for k in ['registered','active','held','human_pending','quality_blocked','measurable_human','motion_missing','motion_binding_invalid','pair_unknown','paired_binary','contact_yes_motion_yes','contact_yes_motion_no','contact_no_motion_yes','contact_no_motion_no']}
  den=c['contact_no_motion_yes']+c['contact_no_motion_no'];out['no_contact_binary_denominator']=den
  out['motion_rate_when_no_contact']=c['contact_no_motion_yes']/den if den else None
  out['paired_coverage']=c['paired_binary']/c['active']if c['active']else None
  return out
 total=collections.Counter()
 for c in bins.values():total.update(c)
 return {'total':finish(total),'per_model':{m:finish(c)for m,c in sorted(bins.items())}}

def report(tasks):
 return {'definition':DEFINITION,'definition_sha256':DEFINITION_SHA,'contact_event_id':CONTACT,
  'final':cross_statistics(tasks),'preliminary':cross_statistics(tasks,True),
  'note':'仅独立补充观察，与原评分分开。未填不视为未发生；不从接触后平移、原命中分支或VLM反推新标签。无罐子接触时盒子平移不自动证明无其他作用或物理违背。正式汇总仅使用已解决且可测的人类记录；初步表另含仍争议的已提交判断。'}
