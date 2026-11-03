"""Observation-only event contracts, independent of reference answers."""
import copy
import hashlib
import json
import math

VERSION='registered-observations-v2'


def observation_definitions(events):
    out={}
    for name,d in events.items():
        value={k:copy.deepcopy(d[k])for k in ['definition','minimum_evidence_times']if k in d}
        value.setdefault('minimum_evidence_times',1)
        if 'time_semantics'in d:
            if not isinstance(d['time_semantics'],str)or not d['time_semantics']:raise ValueError('invalid_event_time_semantics')
            value['time_semantics']=d['time_semantics']
        for field in ['actors','affected_actor_options']:
            if field in d:
                a=d[field]
                if not isinstance(a,list)or any(not isinstance(x,str)or not x for x in a):raise ValueError('invalid_event_actor_list')
                value[field]=list(a)
        if 'required_contact_pairs'in d:
            pairs=d['required_contact_pairs']
            if not isinstance(pairs,list)or any(not isinstance(p,list)or len(p)!=2 or any(not isinstance(x,str)or not x for x in p)for p in pairs):raise ValueError('invalid_event_contact_pairs')
            value['required_contact_pairs']=copy.deepcopy(pairs)
        out[name]=value
    return out


def contract_hash(job):
    fields=['event_job_schema','target','window_s','events','uncertainty_policy','generated_fps',
            'last_observed_time_s','roi','generated_track_sha256']
    data={k:job[k]for k in fields if k in job}
    return hashlib.sha256(json.dumps(data,sort_keys=True,ensure_ascii=False,allow_nan=False,separators=(',',':')).encode()).hexdigest()


def sampling_valid(prediction,job):
    times=prediction.get('times_s');fps=job['generated_fps'];end=job['last_observed_time_s']
    return (isinstance(times,list)and len(times)>=2
        and all(type(t)in(int,float)and math.isfinite(t)and 0<=t<=end+1e-6
            and abs(t*fps-round(t*fps))<1e-4 for t in times)
        and times==sorted(set(times))
        and abs(times[0])<1e-6 and abs(times[-1]-end)<1e-5)


def temporal_evidence_supported(prediction,definition,job):
    """Route an ungrounded prelabel to review; never invent an event value."""
    if job.get('event_job_schema')!=VERSION:return True
    cited=prediction.get('evidence_times_s',[]);end=job['last_observed_time_s']
    final=any(type(t)in(int,float)and abs(t-end)<1e-5 for t in cited)
    if definition.get('time_semantics')=='window_end_state':return final
    if prediction.get('label')=='no':return final and any(type(t)in(int,float)and abs(t)<1e-6 for t in cited)
    return True


def instruction_text(prompt,job,stage):
    text=prompt+'\nTarget: '+job['target']
    if stage=='events':
        text+='\nRegistered definitions: '+json.dumps(job['events'],ensure_ascii=False)
        if job.get('uncertainty_policy'):text+='\nObservation limits: '+job['uncertainty_policy']
        if job.get('event_job_schema')==VERSION:
            text+='\nEnd-state events require evidence at the last supplied sample. For a negative ever-event, cite both initial and final samples after checking the whole observed window. If physical units cannot be measured or calibrated, use uncertain; never substitute pixels for metres.'
    return text
