"""PHY2 private labeling server. Python 3.10+, SQLite, no runtime dependencies."""
import argparse
import hashlib
import io
import json
import mimetypes
import os
import re
import secrets
import time
import zipfile
from http import cookies
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlparse

from store import ASSIGNMENT_QUOTAS, Store
from workflow import can_access, export_files, final_annotation, metrics, SINGLE_REVIEW_POLICY, dispute_reasons
from event_metrics import event_metrics, evidence_valid
from scoring_bridge import ScoringService
from remote_media import Resolver, MediaUnavailable
from critical_results import calculate as calculate_critical, csv_bytes as critical_csv

STATIC = Path(__file__).parent / 'static'
RESOURCES = Path(__file__).parent / 'resources'
PRIORITY_CLIPS = {'T06_C05','T09_C04','T16_C04','T16_C05','T17_C04','T17_C05'}


class App(ThreadingHTTPServer):
    daemon_threads = True

    def __init__(self, address, data_dir, prefix='/physics/', secure=True):
        super().__init__(address, Handler)
        self.data_dir=Path(data_dir);self.data_dir.mkdir(parents=True,exist_ok=True)
        self.media_root=self.data_dir/'media';self.media_root.mkdir(exist_ok=True)
        self.store=Store(self.data_dir/'annotations.sqlite3')
        self.scoring=ScoringService(self.data_dir,self.store)
        self.remote_media=Resolver(self.data_dir)
        self.prefix=prefix;self.secure=secure;self.failed_logins={}


class Handler(BaseHTTPRequestHandler):
    server_version='PHY2Label/1.0'

    def log_message(self, fmt, *args):
        # Avoid logging invitations, cookies, passwords or request bodies.
        print(json.dumps({'at':time.time(),'method':self.command,'path':urlparse(self.path).path,
                          'message':str(args[1]) if len(args)>1 else 'request'}),flush=True)

    def respond(self, data, status=200, ctype='application/json; charset=utf-8', headers=None):
        if not isinstance(data,bytes):data=json.dumps(data,ensure_ascii=False).encode()
        self.send_response(status)
        self.send_header('Content-Type',ctype);self.send_header('Content-Length',str(len(data)))
        self.send_header('Cache-Control','no-store');self.send_header('X-Content-Type-Options','nosniff')
        self.send_header('Referrer-Policy','no-referrer')
        self.send_header('Content-Security-Policy',"default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; media-src 'self' https://huggingface.co https://*.hf.co; connect-src 'self'; frame-ancestors 'none'; base-uri 'self'")
        for k,v in (headers or {}).items():self.send_header(k,v)
        self.end_headers()
        if self.command!='HEAD':self.wfile.write(data)

    def read_json(self):
        n=int(self.headers.get('Content-Length','0'))
        if not 0<n<=64*1024*1024:raise ValueError('请求体为空或超过64MB')
        if self.headers.get('Content-Type','').split(';')[0]!='application/json':raise ValueError('需要JSON请求')
        return json.loads(self.rfile.read(n))

    def token(self):
        c=cookies.SimpleCookie()
        try:c.load(self.headers.get('Cookie',''))
        except cookies.CookieError:return ''
        return c['phylabel_session'].value if 'phylabel_session' in c else ''

    def user(self, csrf=False):
        u=self.server.store.authenticate(self.token())
        if not u:raise PermissionError('请先登录')
        if csrf and not secrets.compare_digest(self.headers.get('X-CSRF-Token',''),u['csrf']):raise PermissionError('请求令牌失效，请刷新后重试')
        return u

    def origin_check(self):
        origin=self.headers.get('Origin')
        if not origin or urlparse(origin).netloc!=self.headers.get('Host'):
            raise PermissionError('请求来源不匹配')

    def admin(self, csrf=False):
        u=self.user(csrf)
        if u['role']!='admin':raise PermissionError('仅管理员可操作')
        return u

    def cookie_header(self, token, clear=False):
        return {'Set-Cookie':f'phylabel_session={token}; Path={self.server.prefix}; HttpOnly; SameSite=Strict; Max-Age={0 if clear else 1209600}'+('; Secure' if self.server.secure else '')}

    def do_HEAD(self):self.do_GET()

    def do_GET(self):
        try:self.get()
        except MediaUnavailable as e:self.respond({'error':str(e)},503,headers={'Retry-After':'3'})
        except PermissionError as e:self.respond({'error':str(e)},401 if not self.server.store.authenticate(self.token()) else 403)
        except LookupError as e:self.respond({'error':str(e)},404)
        except (ValueError,KeyError) as e:self.respond({'error':str(e)},400)
        except (BrokenPipeError,ConnectionResetError):pass
        except Exception as e:
            print(type(e).__name__,str(e),flush=True);self.respond({'error':'服务器处理失败，记录已保留'},500)

    def task_for_user(self, tid, user):
        t=self.server.store.get_task(tid)
        if not t:raise LookupError('任务不存在')
        if not can_access(user,t):raise PermissionError('无此任务权限')
        return t

    def task_view(self,t,u):
        p=t['payload'];notes=t['annotations'];single=p.get('review_policy')==SINGLE_REVIEW_POLICY
        selected=p.get('second_review_sample',{}).get('selected')
        stage='adjudication' if u['role']=='admin' and t['state']=='disputed' and (not single or selected) else 'primary' if u['id']==t['primary_id'] else 'review' if u['id']==t['reviewer_id'] else None
        view={k:p.get(k) for k in ['id','clip_id','prompt_variant','seed','fps','duration_s','window_s','video_sha256','protocol','protocol_sha256','evaluation_registration','supplemental_review_scope','source_annotation_task_id']}
        view['human_review_policy']='source-label-review-v4'
        from box_motion import view as box_view
        view['box_translation_observation']=box_view(t,u)
        from process_observations import view as process_view
        view['process_observations']=process_view(t,u)
        view['annotation_hold']=p.get('annotation_hold')
        view['human_annotation_without_vlm']=True
        view.update(batch_id=t['batch_id'],state=t['state'],version=t['version'],primary_id=t['primary_id'],reviewer_id=t['reviewer_id'],stage=stage)
        view.update(review_policy=p.get('review_policy','legacy_dual_review'),second_review_sample=p.get('second_review_sample'),
                    dispute_reasons=dispute_reasons(notes['primary']['payload'],p) if notes.get('primary',{}).get('submitted') and single else [])
        # Reference outcomes and requested parameters stay hidden; v2 exposes the VLM suggestions.
        view['model']=p['model'] if u['role']=='admin' else '匿名模型'
        view['own']=notes.get(stage) if stage else None
        view['can_work']=bool(stage) and not notes.get(stage,{}).get('submitted') and (stage!='review' or bool(notes.get('primary',{}).get('submitted')))
        if stage=='adjudication' or u['role']=='admin' or notes.get(stage,{}).get('submitted'):
            view['comparison']={k:v for k,v in notes.items() if v.get('submitted')}
            view['machine']=p.get('machine',{})
        if single:view['machine']=p.get('machine',{})
        if view.get('machine'):
            from protocol_rules import observation_evidence_problem
            prediction=view['machine'].get('event_prediction',{})
            view['machine_event_evidence']={}
            for key,definition in p['protocol']['events'].items():
                item=prediction.get('events',{}).get(key,{})
                valid=evidence_valid(prediction,item,definition,p)
                issue=observation_evidence_problem(item,definition,p,require_actor_ids=False)
                view['machine_event_evidence'][key]={'valid':valid,'note':'判定规则通过，仍须人工核对' if valid else issue or '预评身份、标签、矛盾记录或末帧采样未满足规则；无需补填时间和理由'}
        view['vlm_preassessment_pending']=p.get('vlm_required',False) and p.get('machine',{}).get('pipeline_status') not in ('complete','evaluator_failure','blocked_quality')
        view['vlm_pending']=False
        if p.get('annotation_hold',{}).get('active'):view['can_work']=False
        return view

    def get(self):
        parsed=urlparse(self.path);p=unquote(parsed.path);query=parse_qs(parsed.query)
        if p=='/health':return self.respond({'ok':True,'service':'phy2-label','version':1})
        if p in ('/','/index.html'):
            html=(STATIC/'index.html').read_text(encoding='utf-8').replace('__BASE__',self.server.prefix)
            return self.respond(html.encode(),ctype='text/html; charset=utf-8')
        if p.startswith('/assets/'):
            name=p[len('/assets/'):]
            if name not in ('app.js','style.css'):raise LookupError('资源不存在')
            return self.respond((STATIC/name).read_bytes(),ctype='application/javascript; charset=utf-8' if name.endswith('.js') else 'text/css; charset=utf-8')
        u=self.user()
        if p=='/api/me':return self.respond({'user':u})
        if p=='/api/dashboard':
            with self.server.store.connect() as db:
                batches=[dict(r) for r in db.execute('SELECT * FROM batches ORDER BY id') if u['role'] in ('admin','qa') or r['mode']!='qa']
            for b in batches:
                ts=self.server.store.all_tasks(b['id']);b['metadata']=json.loads(b['metadata'])
                visible=[t for t in ts if u['role']=='admin' or u['id']in(t['primary_id'],t['reviewer_id'])]
                own=[t for t in visible if not t['payload'].get('annotation_hold',{}).get('active')];b['available_to_you']=len(own)
                b['held_to_you']=len(visible)-len(own)
                b['counts']={state:sum(t['state']==state for t in own) for state in ['unstarted','draft','review_pending','disputed','resolved']}
                b['counts']['sampled_pending']=sum(t['state']=='disputed' and bool(t['payload'].get('second_review_sample',{}).get('selected')) for t in own)
                b['counts']['vlm_pending']=0
                b['counts']['vlm_ready']=len(own)-b['counts']['vlm_pending']
                b['counts']['event_contract_pending']=sum(t['payload']['protocol'].get('critical_contract_status') in ('pending_scene_specific_registration','original_critical_target_pending') for t in own)
                b['metrics']=metrics(ts,b['mode']) if u['role']=='admin' else None
                if b['metrics'] is not None:
                    b['metrics']['vlm_events']=event_metrics(ts)
                    from box_motion import report as box_report
                    b['metrics']['box_translation']=box_report(ts)
                    from process_observations import report as process_report
                    b['metrics']['process_observations']=process_report(ts)
                    scoring=self.server.scoring.latest(b['id'],ts)
                    b['metrics'].update(scoring=scoring,formal_scores=scoring['formal_scores'],formal_note=scoring['note'])
            formal=self.server.store.all_tasks('formal3600_v1')
            held_by_user={uid:sum(t['primary_id']==uid and bool(t['payload'].get('annotation_hold',{}).get('active')) for t in formal) for uid in ASSIGNMENT_QUOTAS}
            return self.respond({'batches':batches,'assignments':[{ 'id':uid,'name':'人员'+uid[1:].lstrip('0'),'models':['12个模型混合分配'],'planned_total':n-held_by_user[uid],'registered_total':n,'held':held_by_user[uid],'planned_primary':n-held_by_user[uid],'planned_review':0} for uid,n in [(uid,sum(t['primary_id']==uid for t in formal)) for uid in ASSIGNMENT_QUOTAS]],
                                 'review_policy':{'version':SINGLE_REVIEW_POLICY,'ordinary_reviews':1,'dispute_sampling_rate':.2,'second_reviewer':'admin','unselected_disputes':'pending_not_zero'},
                                 'sampling':{'total':3600,'per_model':300,'per_source':3,'seed_prompt':'random_without_replacement','note':'正式批次按每模型100个测试样本，每样本随机抽3个不同(seed,prompt)组合；抽样清单冻结后不按质量重抽。'}})
        if p in ('/api/original-contract-audit','/api/original-contract-audit.csv','/api/excluded-thresholds.csv'):
            self.admin()
            name={'/api/original-contract-audit':'original_contract_audit.json','/api/original-contract-audit.csv':'original_contract_audit.csv','/api/excluded-thresholds.csv':'excluded_thresholds.csv'}[p]
            return self.respond((RESOURCES/name).read_bytes(),ctype='application/json; charset=utf-8' if name.endswith('.json') else 'text/csv; charset=utf-8')
        if p in ('/api/remaining50-recovery','/api/remaining50-recovery.csv'):
            self.admin()
            name='remaining50_recovery.csv' if p.endswith('.csv') else 'remaining50_recovery.json'
            return self.respond((RESOURCES/name).read_bytes(),ctype='text/csv; charset=utf-8' if name.endswith('.csv') else 'application/json; charset=utf-8')
        if p=='/api/prompt-parameter-registration':
            self.admin()
            return self.respond((RESOURCES/'prompt_parameter_selection_registration.json').read_bytes(),ctype='application/json; charset=utf-8')
        if p=='/api/reference-window-admission':
            self.admin()
            return self.respond((RESOURCES/'reference_window_admission.json').read_bytes(),ctype='application/json; charset=utf-8')
        if p=='/api/active-core100-reference':
            self.admin()
            from physedit.core100_release import status as reference_release_status
            return self.respond(reference_release_status(pointer=RESOURCES/'active_reference_release.json'))
        if p in ('/api/reference-clocks100','/api/reference-clocks100.csv','/api/near6-windows','/api/near6-windows.csv','/api/t13-source-contacts'):
            self.admin()
            names={'/api/reference-clocks100':'reference_clocks100.json','/api/reference-clocks100.csv':'reference_clocks100.csv',
                   '/api/near6-windows':'near6_windows72.json','/api/near6-windows.csv':'near6_windows72.csv','/api/t13-source-contacts':'t13_F5_source_contacts.json'}
            name=names[p]
            return self.respond((RESOURCES/name).read_bytes(),ctype='text/csv; charset=utf-8' if name.endswith('.csv') else 'application/json; charset=utf-8')
        if p in ('/api/formal-boundary-results','/api/formal-boundary-models.csv','/api/formal-boundary-references.csv','/api/formal-boundary-outputs.csv'):
            self.admin()
            result=calculate_critical(self.server.store.all_tasks('formal3600_v1'))['formal_boundary_evaluation']
            if p.endswith('.csv'):
                key={'/api/formal-boundary-models.csv':'per_model','/api/formal-boundary-references.csv':'references','/api/formal-boundary-outputs.csv':'outputs'}[p]
                return self.respond(critical_csv({'outputs':result[key]}),ctype='text/csv; charset=utf-8')
            return self.respond(result)
        if p in ('/api/critical-results','/api/critical-results.csv','/api/critical-distances.csv','/api/critical-pairs.csv','/api/scoped-critical.csv','/api/critical-case-gaps.csv','/api/critical-window-gaps.csv','/api/core100-connections.csv','/api/core100-connected-outputs.csv','/api/core100-connected-boundaries.csv','/api/formal-critical-references.csv','/api/formal-critical-outputs.csv'):
            self.admin()
            result=calculate_critical(self.server.store.all_tasks('formal3600_v1'))
            if p.endswith('.csv'):
                if p in ('/api/core100-connections.csv','/api/core100-connected-outputs.csv','/api/core100-connected-boundaries.csv','/api/formal-critical-references.csv','/api/formal-critical-outputs.csv'):
                    if p in ('/api/formal-critical-references.csv','/api/formal-critical-outputs.csv'):
                        key='references' if p=='/api/formal-critical-references.csv' else 'outputs'
                        return self.respond(critical_csv({'outputs':result['formal_critical_cohorts'][key]}),ctype='text/csv; charset=utf-8')
                    key={'/api/core100-connections.csv':'cases','/api/core100-connected-outputs.csv':'outputs','/api/core100-connected-boundaries.csv':'boundaries'}[p]
                    return self.respond(critical_csv({'outputs':result['core100_connection'][key]}),ctype='text/csv; charset=utf-8')
                rows=result['execution_readiness']['cases'] if p=='/api/critical-case-gaps.csv' else result['execution_readiness']['physical_window_outputs'] if p=='/api/critical-window-gaps.csv' else result['admitted_cohort']['outputs'] if p=='/api/scoped-critical.csv' else result['distance_records'] if p=='/api/critical-distances.csv' else result['candidate_pairs'] if p=='/api/critical-pairs.csv' else result['outputs']
                return self.respond(critical_csv({'outputs':rows}),ctype='text/csv; charset=utf-8')
            return self.respond(result)
        if p in ('/api/core100-admission','/api/core100-admission.csv','/api/core100-admission.md','/api/v6-input-bindings.csv'):
            self.admin()
            name={'/api/core100-admission':'core100_admission.json','/api/core100-admission.csv':'core100_admission.csv','/api/core100-admission.md':'CORE100_ADMISSION.md','/api/v6-input-bindings.csv':'v6_input_bindings.csv'}[p]
            return self.respond((RESOURCES/name).read_bytes(),ctype='text/csv; charset=utf-8' if name.endswith('.csv') else 'text/markdown; charset=utf-8' if name.endswith('.md') else 'application/json; charset=utf-8')
        if p in ('/api/event-protocols','/api/event-protocols.csv'):
            name='event_contracts.json' if p=='/api/event-protocols' else 'event_annotation_template.csv'
            return self.respond((RESOURCES/name).read_bytes(),ctype='application/json; charset=utf-8' if name.endswith('.json') else 'text/csv; charset=utf-8')
        if p in ('/api/readiness','/api/readiness.csv','/api/readiness.md'):
            self.admin()
            name={'/api/readiness':'core100_readiness.json','/api/readiness.csv':'core100_readiness.csv','/api/readiness.md':'CORE100_READINESS.md'}[p]
            ctype='application/json; charset=utf-8' if p=='/api/readiness' else 'text/csv; charset=utf-8' if p.endswith('.csv') else 'text/markdown; charset=utf-8'
            headers={} if p=='/api/readiness' else {'Content-Disposition':f'attachment; filename="{name}"'}
            return self.respond((RESOURCES/name).read_bytes(),ctype=ctype,headers=headers)
        if p=='/api/process-observations':
            self.admin()
            from process_observations import report as process_report
            return self.respond(process_report(self.server.store.all_tasks(query.get('batch',['formal3600_v1'])[0])))
        if p=='/api/box-translation':
            self.admin()
            from box_motion import report as box_report
            return self.respond(box_report(self.server.store.all_tasks(query.get('batch',['formal3600_v1'])[0])))
        if p=='/api/scoring':
            self.admin();bid=query.get('batch',['pilot6'])[0]
            return self.respond(self.server.scoring.latest(bid,self.server.store.all_tasks(bid)))
        if p=='/api/tasks':
            bid=query.get('batch',['pilot6'])[0];ts=self.server.store.all_tasks(bid)
            rows=[]
            for t in ts:
                if not can_access(u,t):continue
                r=t['payload'];role='primary' if u['id']==t['primary_id'] else 'review' if u['id']==t['reviewer_id'] else 'admin'
                rows.append({'id':r['id'],'clip_id':r['clip_id'],'prompt_variant':r['prompt_variant'],'seed':r['seed'],
                             'model':r['model'] if u['role']=='admin' else '匿名模型','state':t['state'],'role':role,'version':t['version'],
                             'vlm_pending':False,
                             'annotation_hold':r.get('annotation_hold'),
                             'review_priority':100 if r['clip_id'] in PRIORITY_CLIPS else 0,
                             'second_review_selected':r.get('second_review_sample',{}).get('selected')})
            return self.respond({'tasks':rows})
        if p.startswith('/api/tasks/'):
            tid=p[len('/api/tasks/'):];return self.respond(self.task_view(self.task_for_user(tid,u),u))
        if p.startswith('/media/'):
            tid=p[len('/media/'):];task=self.task_for_user(tid,u)
            if task['payload'].get('remote_media'):
                return self.respond(b'',302,headers={'Location':self.server.remote_media.url(task['payload'])})
            f=(self.server.media_root/task['payload']['media_file']).resolve()
            if self.server.media_root.resolve() not in f.parents:raise LookupError('媒体不存在')
            return self.stream_media(f)
        if p=='/api/export':
            self.admin();bid=query.get('batch',['pilot6'])[0]
            with self.server.store.connect() as db:
                b=db.execute('SELECT * FROM batches WHERE id=?',(bid,)).fetchone()
                if not b:raise LookupError('批次不存在')
                audit=[dict(r) for r in db.execute('SELECT * FROM audit WHERE task_id IN (SELECT id FROM tasks WHERE batch_id=?) ORDER BY id',(bid,))]
                samples=[json.loads(r['payload']) for r in db.execute('SELECT payload FROM dispute_samples WHERE batch_id=? ORDER BY id',(bid,))]
                self.server.store.log(db,u['id'],'export_downloaded',detail={'batch':bid})
            files=export_files(self.server.store.all_tasks(bid),{**dict(b),'metadata':json.loads(b['metadata'])},audit)
            ts=self.server.store.all_tasks(bid);vlm=event_metrics(ts);scoring=self.server.scoring.latest(bid,ts)
            from box_motion import report as box_report,KEY as box_key
            box=box_report(ts)
            from process_observations import report as process_report, rows as process_rows
            files['process_observation_statistics.json']=json.dumps(process_report(ts),ensure_ascii=False,indent=2).encode()
            files['process_observations.jsonl']=''.join(json.dumps(r,ensure_ascii=False)+'\n' for r in process_rows(ts)).encode()
            files['box_translation_statistics.json']=json.dumps(box,ensure_ascii=False,indent=2).encode()
            files['box_translation_observations.jsonl']=''.join(json.dumps({'task_id':t['id'],'batch_id':t['batch_id'],'model':t['payload']['model'],'clip_id':t['payload']['clip_id'],**t['independent_observations'][box_key]},ensure_ascii=False)+'\n'for t in ts if box_key in t.get('independent_observations',{})).encode()
            from workflow import csv_bytes
            bx=box['final']['per_model']
            files['box_translation_by_model.csv']=csv_bytes(['model',*box['final']['total']],[[m,*r.values()]for m,r in bx.items()])
            files['vlm_event_metrics.json']=json.dumps(vlm,ensure_ascii=False,indent=2).encode()
            files['boundary_scoring.json']=json.dumps(scoring,ensure_ascii=False,indent=2).encode()
            if bid=='formal3600_v1':
                critical=calculate_critical(ts)
                files['critical_results.json']=json.dumps(critical,ensure_ascii=False,indent=2).encode()
                files['critical_outputs3600.csv']=critical_csv(critical)
                files['critical_distances.csv']=critical_csv({'outputs':critical['distance_records']})
                files['critical_candidate_pairs.csv']=critical_csv({'outputs':critical['candidate_pairs']})
                files['core100_final_input_policy.json']=(RESOURCES/'core100_final_input_policy.json').read_bytes()
                files['reference_window_admission.json']=(RESOURCES/'reference_window_admission.json').read_bytes()
                files['admitted_cohort_outputs.csv']=critical_csv({'outputs':critical['admitted_cohort']['outputs']})
                files['core100_case_gaps.csv']=critical_csv({'outputs':critical['execution_readiness']['cases']})
                files['physical_window_outputs540.csv']=critical_csv({'outputs':critical['execution_readiness']['physical_window_outputs']})
                for name in ('reference_clocks100.json','reference_clocks100.csv','near6_windows72.json','near6_windows72.csv','t13_F5_source_contacts.json'):
                    files[name]=(RESOURCES/name).read_bytes()
            combined=json.loads(files['metrics.json']);combined.update(vlm_events=vlm,scoring=scoring,formal_scores=scoring['formal_scores'],formal_note=scoring['note'])
            files['metrics.json']=json.dumps(combined,ensure_ascii=False,indent=2).encode()
            from workflow import csv_bytes
            files['vlm_event_metrics.csv']=csv_bytes(['event','registered','human_binary','raw_comparable','raw_accuracy','precision','recall','f1','contract_qualified','validated_comparable','validated_accuracy'],
                [[name,c['registered'],c['human_binary'],c['comparable'],c['raw']['accuracy'],c['raw']['precision'],c['raw']['recall'],c['raw']['f1'],c['machine_valid_evidence'],c['validated_comparable'],c['validated']['accuracy']] for name,c in vlm['final']['per_event'].items()])
            for name in ('core100_readiness.json','core100_readiness.csv','CORE100_READINESS.md','event_contracts.json','event_annotation_template.csv','event_registration_gaps.csv','EVENT_ANNOTATION_GUIDE.md','original_contract_audit.json','original_contract_audit.csv','excluded_thresholds.csv','ORIGINAL_CONTRACT_AUDIT.md','remaining50_recovery.json','remaining50_recovery.csv','core100_admission.json','core100_admission.csv','v6_input_bindings.csv'):files[name]=(RESOURCES/name).read_bytes()
            files['dispute_samples.jsonl']=''.join(json.dumps(s,ensure_ascii=False)+'\n' for s in samples).encode()
            data=io.BytesIO()
            with zipfile.ZipFile(data,'w',zipfile.ZIP_DEFLATED) as z:
                for name,value in files.items():z.writestr(name,value)
                z.writestr('checksums.json',json.dumps({k:hashlib.sha256(v).hexdigest() for k,v in files.items()},indent=2))
            return self.respond(data.getvalue(),ctype='application/zip',headers={'Content-Disposition':f'attachment; filename="phy2-{bid}-annotations.zip"'})
        raise LookupError('接口不存在')

    def stream_media(self,f):
        size=f.stat().st_size;start=0;end=size-1;r=self.headers.get('Range')
        if r:
            match=re.fullmatch(r'bytes=(\d*)-(\d*)',r)
            if not match or not any(match.groups()):return self.respond(b'',416,headers={'Content-Range':f'bytes */{size}'})
            a,b=match.groups()
            if a:start=int(a);end=min(int(b),end) if b else end
            else:start=max(0,size-int(b))
            if start>end or start>=size:return self.respond(b'',416,headers={'Content-Range':f'bytes */{size}'})
        self.send_response(206 if r else 200);self.send_header('Content-Type','video/mp4');self.send_header('Accept-Ranges','bytes')
        self.send_header('Content-Length',str(end-start+1));self.send_header('Cache-Control','private, no-store');self.send_header('X-Content-Type-Options','nosniff')
        if r:self.send_header('Content-Range',f'bytes {start}-{end}/{size}')
        self.end_headers()
        if self.command=='HEAD':return
        with f.open('rb') as stream:
            stream.seek(start);left=end-start+1
            while left:
                chunk=stream.read(min(left,256*1024))
                if not chunk:break
                self.wfile.write(chunk);left-=len(chunk)

    def do_POST(self):
        try:self.post()
        except PermissionError as e:self.respond({'error':str(e)},401 if not self.server.store.authenticate(self.token()) else 403)
        except RuntimeError as e:self.respond({'error':str(e)},409)
        except LookupError as e:self.respond({'error':str(e)},404)
        except (ValueError,KeyError,TypeError) as e:self.respond({'error':str(e)},400)
        except (BrokenPipeError,ConnectionResetError):pass
        except Exception as e:
            print(type(e).__name__,str(e),flush=True);self.respond({'error':'提交失败，已保存的记录不受影响'},500)

    def post(self):
        self.origin_check();p=urlparse(self.path).path
        data=self.read_json()
        if p in ('/api/worker/result','/api/worker/media-url'):
            import hmac
            secret=self.server.data_dir/'vlm_worker_key'
            supplied=self.headers.get('Authorization','').removeprefix('Bearer ')
            if not secret.is_file() or not supplied or not hmac.compare_digest(secret.read_text().strip(),supplied):
                raise PermissionError('预评回传认证失败')
            if p.endswith('/media-url'):
                task=self.server.store.get_task(data['task_id'])
                if not task or task['batch_id']!='formal3600_v1':raise PermissionError('预评任务范围错误')
                return self.respond({'url':self.server.remote_media.url(task['payload'])})
            self.server.store.install_machine_result(data)
            return self.respond({'ok':True})
        if p in ('/api/auth/login','/api/auth/activate'):
            ip=self.client_address[0] # nginx real client used only when trusted proxy connects
            if ip=='127.0.0.1':ip=self.headers.get('X-Real-IP',ip)
            now=time.time();key=(ip,p);recent=[t for t in self.server.failed_logins.get(key,[]) if now-t<600]
            if len(recent)>=20:return self.respond({'error':'尝试次数过多，请稍后重试'},429)
            try:
                uid=self.server.store.activate(data.get('token',''),data.get('password','')) if p.endswith('activate') else self.server.store.login(data.get('user_id',''),data.get('password',''))
            except ValueError:
                self.server.failed_logins[key]=recent+[now];raise
            if not uid:
                self.server.failed_logins[key]=recent+[now];return self.respond({'error':'账号或密码不正确'},401)
            token=self.server.store.session(uid);return self.respond({'user':self.server.store.authenticate(token)},headers=self.cookie_header(token))
        u=self.user(csrf=True)
        if p=='/api/auth/logout':
            self.server.store.logout(self.token());return self.respond({'ok':True},headers=self.cookie_header('',True))
        if p=='/api/admin/import':
            self.admin(csrf=True);self.server.store.import_batch(data,self.server.media_root,u['id']);return self.respond({'ok':True,'count':len(data['tasks'])})
        if p=='/api/admin/sample-disputes':
            self.admin(csrf=True)
            return self.respond(self.server.store.sample_disputes(u['id'],data['batch_id'],data.get('rate',.2),data.get('seed',20261022)))
        if p=='/api/admin/scoring-config':
            self.admin(csrf=True)
            return self.respond(self.server.scoring.install(data['batch_id'],data['config'],u['id']))
        if p=='/api/admin/score':
            self.admin(csrf=True)
            return self.respond(self.server.scoring.start(data['batch_id'],u['id']))
        if p.startswith('/api/tasks/') and p.endswith('/process-observation'):
            tid=p[len('/api/tasks/'):-len('/process-observation')]
            return self.respond(self.task_view(self.server.store.save_process_observation(u,tid,data),u))
        if p.startswith('/api/tasks/') and p.endswith('/box-translation'):
            tid=p[len('/api/tasks/'):-len('/box-translation')]
            return self.respond(self.task_view(self.server.store.save_box_observation(u,tid,data),u))
        if p.startswith('/api/tasks/') and p.endswith('/annotation'):
            tid=p[len('/api/tasks/'):-len('/annotation')]
            task=self.server.store.save(u,tid,data['stage'],data['annotation'],data['version'],bool(data.get('submit')))
            return self.respond(self.task_view(task,u))
        raise LookupError('接口不存在')


def main():
    p=argparse.ArgumentParser();p.add_argument('--host',default='127.0.0.1');p.add_argument('--port',type=int,default=13081)
    p.add_argument('--data-dir',required=True);p.add_argument('--prefix',default='/physics/');p.add_argument('--insecure-cookie',action='store_true')
    a=p.parse_args();app=App((a.host,a.port),a.data_dir,a.prefix,not a.insecure_cookie)
    print('PHY2 label server listening on',a.host,a.port,flush=True);app.serve_forever()


if __name__=='__main__':main()
