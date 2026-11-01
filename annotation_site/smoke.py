"""Explicit six-video QA workflow. Synthetic labels NEVER enter the human pilot."""
import argparse
import copy
import hashlib
import http.cookiejar
import io
import json
import secrets
import urllib.error
import urllib.parse
import urllib.request
import zipfile
from pathlib import Path


class Client:
    def __init__(self, base):
        self.base=base.rstrip('/')+'/'
        self.origin=urllib.parse.urlsplit(base)
        self.origin=self.origin.scheme+'://'+self.origin.netloc
        self.cookies=http.cookiejar.CookieJar()
        self.opener=urllib.request.build_opener(urllib.request.HTTPCookieProcessor(self.cookies))
        self.csrf=''

    def request(self, path, data=None, raw=False, headers=None, expected=200):
        h={'Origin':self.origin,'Content-Type':'application/json','X-CSRF-Token':self.csrf,**(headers or {})}
        r=urllib.request.Request(self.base+path,data=json.dumps(data).encode() if data is not None else None,headers=h)
        try:
            with self.opener.open(r,timeout=45) as response:
                assert response.status==expected,(path,response.status,expected)
                body=response.read()
                return body if raw else json.loads(body)
        except urllib.error.HTTPError as e:
            body=e.read()
            if e.code!=expected:raise AssertionError((path,e.code,body.decode()))
            return json.loads(body)


def annotation(t, quality, label='no'):
    p={'video_sha256':t['video_sha256'],'protocol_version':t['protocol']['version'],
       'quality':{'status':quality,'failure':'identity_loss' if quality=='failure' else 'none',
                  'evidence_times_s':[0,1],'reason':'QA模拟操作标签，仅验收流程，不代表视频真实内容。'},'events':{}}
    if quality=='pass':
        for k in t['protocol']['events']:
            p['events'][k]={'label':label,'time_s':1 if label=='yes' else None,'evidence_times_s':[0,1,2],
                            'reason':'QA模拟事件标签，仅验收记录与导出，不代表真实事件。'}
    return p


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--base',required=True)
    parser.add_argument('--invitations',required=True);parser.add_argument('--output',required=True)
    a=parser.parse_args();out=Path(a.output);out.mkdir(parents=True,exist_ok=True)
    invitations={i['user_id']:i for i in json.loads(Path(a.invitations).read_text(encoding='utf-8'))}
    clients={};access={}
    for uid in ['qa_primary','qa_review','admin']:
        c=Client(a.base);password=secrets.token_urlsafe(24)
        result=c.request('api/auth/activate',{'token':invitations[uid]['token'],'password':password})
        c.csrf=result['user']['csrf'];clients[uid]=c;access[uid]={'password':password}
    (out/'qa_access.private.json').write_text(json.dumps(access),encoding='utf-8')
    (out/'qa_access.private.json').chmod(0o600)
    p,r,admin=[clients[k] for k in ['qa_primary','qa_review','admin']]
    before=admin.request('api/tasks?batch=pilot6')['tasks']
    assert len(before)==6 and all(t['state']=='unstarted' for t in before)
    tasks=p.request('api/tasks?batch=qa6')['tasks'];assert len(tasks)==6
    checks=[]
    for i,row in enumerate(tasks):
        tid=row['id'];endpoint='api/tasks/'+tid
        t=p.request(endpoint);blind=r.request(endpoint)
        assert not blind['can_work'] and 'machine' not in blind and 'comparison' not in blind and 'reference' not in blind
        assert t['model']=='匿名模型'
        if i==0:
            media=p.request('media/'+tid,raw=True,headers={'Range':'bytes=0-31'},expected=206)
            assert len(media)==32
            p.request('api/export?batch=qa6',expected=403)
            p.request('api/tasks/pilot_h03',expected=403)
            original_csrf=p.csrf;p.csrf='wrong'
            p.request(endpoint+'/annotation',{'stage':'primary','version':t['version'],'annotation':{},'submit':False},expected=403)
            p.csrf=original_csrf
            draft=p.request(endpoint+'/annotation',{'stage':'primary','version':t['version'],'annotation':{'qa_draft':True},'submit':False})
            assert draft['own']['payload']['qa_draft']
            p.request(endpoint+'/annotation',{'stage':'primary','version':t['version'],'annotation':{},'submit':False},expected=409)
            t=draft
        q=['pass','pass','pass','failure','failure','uncertain'][i]
        label='not_observed' if i==2 else 'no'
        payload=annotation(t,q,label)
        t=p.request(endpoint+'/annotation',{'stage':'primary','version':t['version'],'annotation':payload,'submit':True})
        assert t['state']=='review_pending'
        blind=r.request(endpoint);assert blind['can_work'] and 'comparison' not in blind and 'machine' not in blind
        review=copy.deepcopy(payload)
        if i==0:
            first=next(iter(review['events']));review['events'][first].update(label='yes',time_s=1)
        t=r.request(endpoint+'/annotation',{'stage':'review','version':blind['version'],'annotation':review,'submit':True})
        if i==0:
            assert t['state']=='disputed'
            t=admin.request(endpoint);payload['adjudication_reason']='QA模拟分歧仲裁流程，采用初审模拟标签进行导出验收。'
            t=admin.request(endpoint+'/annotation',{'stage':'adjudication','version':t['version'],'annotation':payload,'submit':True})
        assert t['state']=='resolved'
        checks.append({'task_id':tid,'workflow':'resolved','synthetic':True})
    blob=admin.request('api/export?batch=qa6',raw=True)
    (out/'qa6-export.zip').write_bytes(blob)
    with zipfile.ZipFile(io.BytesIO(blob)) as z:
        sums=json.loads(z.read('checksums.json'))
        assert all(hashlib.sha256(z.read(k)).hexdigest()==v for k,v in sums.items())
        metrics=json.loads(z.read('metrics.json'));assert metrics['resolved']==6
        assert metrics['human_pass']==3 and metrics['human_failure']==2 and metrics['human_uncertain']==1
        assert all(v is None for v in metrics['formal_scores'].values())
        labels=[json.loads(line) for line in z.read('annotations.jsonl').splitlines()]
        assert len(labels)==6
        assert next(x for x in labels if x['sample_id']==tasks[2]['id'])['events']=={}
    after=admin.request('api/tasks?batch=pilot6')['tasks']
    assert all(t['state']=='unstarted' for t in after)
    report={'base':a.base,'synthetic_qa_only':True,'checks':checks,'pilot_real_human_records':0,
            'verified':['activation','permissions','CSRF','optimistic_versions','authenticated_video_range',
                        'draft','independent_blind_review','disagreement','adjudication','ZIP_checksums',
                        'unknown_not_zero','quality_block','QA_isolation'],
            'metrics':metrics}
    (out/'qa_report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({'qa_resolved':6,'pilot_unstarted':6,'checks':len(report['verified'])}))


if __name__=='__main__':main()
