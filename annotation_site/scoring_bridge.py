"""Hash-bound website adapter for the repository's unmodified boundary scorer."""
import argparse
import base64
import hashlib
import json
import re
import tempfile
import threading
import time
from pathlib import Path
from workflow import final_annotation
from input_contract import matches_frozen_input
from window_contract import window_binding

FILES=('inputs.jsonl','answers.jsonl','registered.json','snapshot_hashes.json','observed_rows.jsonl')
NAMES={'BalancedTargetAccuracy':'balanced_accuracy','NearAcc':'near_accuracy','IndependentPairAcc':'independent_pair_accuracy','EventExact':'event_exact'}


def digest(value):return hashlib.sha256(value).hexdigest()
def rows(value):return [json.loads(l) for l in value.splitlines() if l.strip()]
def protocol_hash(task):return digest(json.dumps(task['protocol'],ensure_ascii=False,sort_keys=True).encode())
def fingerprint(tasks):return digest(json.dumps([(t['id'],t['version'],t['state']) for t in tasks],sort_keys=True).encode())
def empty_scores():return {name:None for name in NAMES}
def dump(path,value):
    tmp=path.with_suffix('.tmp');tmp.write_text(json.dumps(value,ensure_ascii=False,indent=2,allow_nan=False),encoding='utf-8');tmp.replace(path)


class ScoringService:
    def __init__(self,data_dir,store):
        self.root=Path(data_dir)/'scoring';self.root.mkdir(parents=True,exist_ok=True)
        self.media=(Path(data_dir)/'media').resolve();self.store=store;self.lock=threading.Lock();self.job_lock=threading.Lock();self.jobs={}

    def directory(self,batch_id):
        if not re.fullmatch(r'[A-Za-z0-9_-]{1,100}',batch_id):raise ValueError('批次ID格式错误')
        p=self.root/batch_id;p.mkdir(exist_ok=True);return p

    def validate(self,config,tasks):
        if config.get('schema')!='phy2-boundary-site-v1' or not config.get('scope_note'):raise ValueError('评分包需指定schema与评分范围scope_note')
        by={t['id']:t['payload'] for t in tasks};seen=set();models=set()
        input_contract_path=Path(__file__).parent/'resources/core100_final_input_policy.json'
        input_contract=json.loads(input_contract_path.read_text(encoding='utf-8')) if input_contract_path.exists() else None
        windows_path=Path(__file__).parent/'resources/core100_physical_windows_20261027.json'
        window_cases=json.loads(windows_path.read_text(encoding='utf-8'))['cases'] if windows_path.exists() else {}
        if not isinstance(config.get('runs'),list) or not config['runs']:raise ValueError('评分包没有冻结run')
        for run in config['runs']:
            files=run['files']
            if set(files)!=set(FILES) or any(not isinstance(v,str) for v in files.values()):raise ValueError('需提供原冻结run的五个完整文件，不能只传参考标签')
            frozen=json.loads(files['snapshot_hashes.json'])
            if set(frozen)!={'inputs.jsonl','answers.jsonl','registered.json'}:raise ValueError('冻结快照字段不完整或含未知路径')
            if any(digest(files[n].encode())!=h for n,h in frozen.items()):raise ValueError('冻结run哈希不符')
            keys=rows(files['answers.jsonl']);inputs=rows(files['inputs.jsonl']);obs=rows(files['observed_rows.jsonl'])
            ki={r['sample_id']:r for r in keys};ii={r['sample_id']:r for r in inputs};oi={r['sample_id']:r for r in obs}
            bindings=run['task_bindings'];bi={r['sample_id']:r for r in bindings}
            if not keys or len(ki)!=len(keys) or len(ii)!=len(inputs) or len(oi)!=len(obs) or len(bi)!=len(bindings) or set(ki)!=set(ii) or set(bi)!=set(ki) or set(oi)!=set(ki):raise ValueError('评分映射必须覆盖整个冻结run，不能筛掉失败或待审样本')
            receipt=json.loads(files['registered.json']);model=receipt['model']
            if model in models:raise ValueError('每模型仅接一个完整冻结run，避免错误合并分数')
            models.add(model)
            for sid,key in ki.items():
                mapping=bi[sid];tid=mapping['task_id']
                if tid in seen or tid not in by:raise ValueError('重复或不存在的网站任务映射')
                seen.add(tid);task=by[tid]
                if tid.startswith('f3600_') or task.get('clip_id') in (input_contract or {}).get('tasks',{}):
                    if not input_contract or input_contract.get('schema')!='author-core100-final-input-policy-v3':raise ValueError('缺少作者冻结的Core100 v6、seed 0输入合同')
                    if not matches_frozen_input(task,input_contract):raise ValueError('该视频的版本、文本、seed或条件图身份不匹配：'+tid)
                    window=window_binding(task,window_cases)
                    if window:
                        if not window['native_covers'] or not window['annotation_window_matches']:
                            raise ValueError('原生时长或人工观察窗尚未匹配登记的物理时域：'+tid)
                        horizon=key.get('evaluation_horizon_s',key.get('horizon_s'))
                        if horizon!=window['required_horizon_s']:
                            raise ValueError('参考答案尚未绑定登记的观察窗：'+tid)
                if key.get('reference_admission',{}).get('status')!='admitted':raise ValueError('参考未正式准入：'+sid)
                for name in ('source_group_id','scene_id','family_id','point_id','theta','target_event','events','inversion'):
                    if name not in key:raise ValueError('参考缺登记：'+name)
                if key['target_event'] not in key['events'] or not key['events'] or any(type(v) is not int or v not in (0,1) for v in key['events'].values()):raise ValueError('参考事件合同无效')
                if task['model']!=model or task.get('registration_sample_id',task['id'])!=sid:raise ValueError('模型或原登记ID不匹配')
                if task['protocol']['status']!='frozen' or mapping.get('protocol_sha256')!=protocol_hash(task):raise ValueError('网站事件协议未冻结或合同哈希不匹配')
                if task.get('source',{}).get('generation_metadata',{}).get('native_prompt_truncation') and task.get('generation_required_parameters_verified') is not True:raise ValueError('原生文本截断后的关键参数保留尚未核验：'+sid)
                if not set(key['events'])<=set(task['protocol'].get('formal_score_event_ids',[])):raise ValueError('评分包含辅助项、待登记事件或被撤下的阈值')
                if mapping.get('video_sha256')!=task['video_sha256'] or oi.get(sid,{}).get('video_sha256')!=task['video_sha256'] or oi[sid].get('status')!='ok':raise ValueError('原run观测与网站媒体身份不符')
                if ii[sid]['seed']!=task['seed'] or abs(ii[sid]['evaluation_duration_s']-task['window_s'])>1e-6 or abs(ii[sid]['fps']-task['fps'])>.02:raise ValueError('seed或原生观察时钟不匹配')
                if task.get('remote_media'):
                    from remote_media import validate_remote
                    validate_remote(task)
                else:
                    media=(self.media/task['media_file']).resolve()
                    if self.media not in media.parents or not media.is_file() or digest(media.read_bytes())!=task['video_sha256']:raise ValueError('网站实际媒体缺失或哈希变化')
            if run.get('boundary_bindings'):
                b=run['boundary_bindings']
                if b.get('answers_sha256')!=frozen['answers.jsonl']:raise ValueError('边界绑定不属于冻结答案')
                for binding in b.get('bindings',[]):
                    value=run.get('evidence_files',{}).get(binding['source_sha256'])
                    if not isinstance(value,str) or digest(base64.b64decode(value,validate=True))!=binding['source_sha256']:raise ValueError('边界原始证据缺失或哈希不符')
        return True

    def install(self,batch_id,config,actor):
        with self.lock:
            tasks=self.store.all_tasks(batch_id)
            if not tasks:raise ValueError('批次没有任务')
            self.validate(config,tasks)
            folder=self.directory(batch_id);h=digest(json.dumps(config,sort_keys=True,ensure_ascii=False).encode())
            dump(folder/('config-'+h+'.json'),config);dump(folder/'config.json',{'sha256':h,'file':'config-'+h+'.json'})
            with self.job_lock:self.jobs.pop(batch_id,None)
            with self.store.connect() as db:self.store.log(db,actor,'scoring_config_installed',detail={'batch_id':batch_id,'sha256':h,'scope':config['scope_note']})
            return {'ok':True,'config_sha256':h,'runs':len(config['runs'])}

    def source(self):
        p=Path(__file__).parent/'scorer_runtime';source=json.loads((p/'SOURCE.json').read_text(encoding='utf-8'))
        if any(digest((p/name).read_bytes())!=h for name,h in source['files'].items()):raise ValueError('仓库评分器快照被改动')
        return source

    def media_signature(self,tasks):
        result=[]
        for t in tasks:
            remote=t['payload'].get('remote_media')
            if remote:
                from remote_media import validate_remote
                validate_remote(t['payload'])
                result.append([t['id'],remote['repository'],remote['revision'],remote['path'],remote['lfs_sha256'],remote['size']])
                continue
            p=self.media/t['payload']['media_file']
            try:
                stat=p.stat();result.append([t['id'],stat.st_size,stat.st_mtime_ns])
            except OSError:result.append([t['id'],None,None])
        return result

    def latest(self,batch_id,tasks):
        folder=self.directory(batch_id);config_path=folder/'config.json';path=folder/'latest.json'
        base={'status':'not_configured','formal_scores':empty_scores(),'per_model':[],
              'note':'尚未绑定已准入的冻结run。请查看固定100条资格清单；不自动将人工标签或参考候选转换为正式成绩。'}
        with self.job_lock:job=dict(self.jobs.get(batch_id,{}))
        if job.get('status')=='running':return {**base,'status':'running','job':job,'note':'仓库评分器正在后台计算，页面会自动更新；不占用标注操作。'}
        if job.get('status')=='failed':return {**base,'status':'failed','job':job,'note':job['error']}
        if not config_path.exists():return base
        if not path.exists():return {**base,'status':'needs_computation','note':'评分包已绑定，等待点击计算。'}
        result=json.loads(path.read_text(encoding='utf-8'));pointer=json.loads(config_path.read_text())
        if result.get('site_scoring_policy')!='source-label-review-v4:event-vector-exact-v1' or result['task_fingerprint']!=fingerprint(tasks) or result['config_sha256']!=pointer['sha256'] or result.get('scorer_source')!=self.source() or result.get('media_signature')!=self.media_signature(tasks):
            return {**base,'status':'stale','note':'标签、抽样、评分包或评分器已更新；旧分数失效，需重新计算。'}
        return result

    def start(self,batch_id,actor):
        if not (self.directory(batch_id)/'config.json').exists():return self.latest(batch_id,self.store.all_tasks(batch_id))
        with self.job_lock:
            if self.jobs.get(batch_id,{}).get('status')=='running':return {'status':'running','note':'已有计算任务，无需重复启动。'}
            self.jobs[batch_id]={'status':'running','started_at':time.time()}
        def worker():
            try:
                self.compute(batch_id,actor)
                with self.job_lock:self.jobs[batch_id]={'status':'done','finished_at':time.time()}
            except Exception as exc:
                with self.job_lock:self.jobs[batch_id]={'status':'failed','error':str(exc),'finished_at':time.time()}
        threading.Thread(target=worker,daemon=True,name='boundary-score-'+batch_id).start()
        return {'status':'running','note':'已启动后台评分，页面将自动更新。'}

    def compute(self,batch_id,actor):
        from scorer_runtime.boundary import score
        with self.lock:
            tasks=self.store.all_tasks(batch_id);by={t['id']:t for t in tasks};folder=self.directory(batch_id)
            if not (folder/'config.json').exists():return self.latest(batch_id,tasks)
            pointer=json.loads((folder/'config.json').read_text());config=json.loads((folder/pointer['file']).read_text(encoding='utf-8'))
            if digest(json.dumps(config,sort_keys=True,ensure_ascii=False).encode())!=pointer['sha256']:raise ValueError('评分包被改动')
            self.validate(config,tasks);source=self.source();results=[]
            for run in config['runs']:
                keys=rows(run['files']['answers.jsonl']);bindings={b['sample_id']:b for b in run['task_bindings']}
                observations=rows(run['files']['observed_rows.jsonl']);annotations=[];screens=[];pending=[]
                for key in keys:
                    sid=key['sample_id'];task=by[bindings[sid]['task_id']];t=task['payload'];human=final_annotation(task)
                    if not human or human['quality']['status']=='uncertain':pending.append(task['id'])
                    q=human['quality']['status'] if human else 'uncertain';ev={};times={}
                    if human and q=='pass':
                        for name in key['events']:
                            item=human['events'].get(name,{})
                            from protocol_rules import observation_evidence_problem
                            issue=observation_evidence_problem(item,t['protocol']['events'][name],t,require_actor_ids=False)
                            if item.get('label') in ('yes','no') and not issue:
                                ev[name]=int(item['label']=='yes')
                                if item.get('time_s') is not None:times[name]=item['time_s']
                            elif task['id'] not in pending:pending.append(task['id'])
                    evidence=(human['quality'].get('reason') or 'human_review_record:'+task['id']) if human else 'human_review_pending'
                    screens.append({'sample_id':sid,'video_sha256':t['video_sha256'],'status':'confirmed_failure' if q=='failure' else 'pass' if q=='pass' else 'suspect',
                                    'method':'website_human_review','reviewer':task['annotations'].get('adjudication',task['annotations'].get('primary',{})).get('user_id'),
                                    'evidence':evidence,'evidence_kind':'human_review_record','blocked_events':list(key['events']) if q=='failure' else [],'block_inversion':q=='failure'})
                    if human:annotations.append({'sample_id':sid,'video_sha256':t['video_sha256'],'events':ev,'event_times_s':times,'method':'website_human_review','evidence':evidence,'evidence_kind':'human_review_record','annotation_schema':human.get('annotation_schema','legacy')})
                for obs in observations:
                    sid=obs['sample_id']
                    if sid in bindings:obs['video']=str(self.media/by[bindings[sid]['task_id']]['payload']['media_file'])
                with tempfile.TemporaryDirectory(dir=folder,prefix='score-') as temp:
                    work=Path(temp)
                    for name,value in run['files'].items():(work/name).write_bytes(value.encode('utf-8'))
                    for name,values in [('observed_rows.jsonl',observations),('human.jsonl',annotations),('screening.jsonl',screens)]:
                        (work/name).write_text(''.join(json.dumps(v,ensure_ascii=False)+'\n' for v in values),encoding='utf-8')
                    bindings_path=None
                    if run.get('boundary_bindings'):
                        b=json.loads(json.dumps(run['boundary_bindings']));(work/'evidence').mkdir()
                        for item in b['bindings']:
                            h=item['source_sha256'];(work/'evidence'/h).write_bytes(base64.b64decode(run['evidence_files'][h]));item['source_file']='evidence/'+h
                        dump(work/'bindings.json',b);bindings_path=work/'bindings.json'
                    raw=score(work,work/'human.jsonl',screening=work/'screening.jsonl',boundary_bindings=bindings_path)
                formal={name:raw[field] if not pending else None for name,field in NAMES.items()}
                chain=all(len(k['events'])>=2 for k in keys)
                matches=0
                for key in keys:
                    human=final_annotation(by[bindings[key['sample_id']]['task_id']]) if 'sample_id' in key else None
                    if human and human['quality']['status']=='pass' and all(human.get('events',{}).get(e,{}).get('label')==('yes' if v else 'no') for e,v in key['events'].items()):matches+=1
                formal['EventExact']=matches/len(keys) if chain and not pending and keys else None
                model_tasks=sum(t['payload']['model']==raw['model'] for t in tasks)
                results.append({'model':raw['model'],'registered':len(keys),'model_batch_tasks':model_tasks,'pending':len(pending),'pending_task_ids':pending,
                    'status':'provisional' if pending else 'complete','formal_scores':formal,'chain_contract_complete':chain,'event_exact_policy':'event-vector-exact-v1; order is separate; no fabricated timestamps',
                    'scope_note':config['scope_note'],'note':'未完成人工判读时，正式分数保持N/A。EventExact按完整事件标签向量比较，不要求时间；旧评分器的有序链结果仅保留为历史诊断。分母仅为该冻结run，未绑定任务另列。',
                    'raw_scorer_result':raw})
            result={'site_scoring_policy':'source-label-review-v4:event-vector-exact-v1','status':'provisional' if any(r['pending'] for r in results) else 'complete','at':time.time(),
                    'task_fingerprint':fingerprint(tasks),'config_sha256':pointer['sha256'],'scorer_source':source,'per_model':results,
                    'media_signature':self.media_signature(tasks),
                    'formal_scores':results[0]['formal_scores'] if len(results)==1 else empty_scores(),
                    'note':'多模型按模型分表，不平均成一个成绩。raw_scorer_result保留全登记分母诊断，存在pending时不能当最终模型成绩。'}
            dump(folder/'latest.json',result)
            with self.store.connect() as db:self.store.log(db,actor,'boundary_scores_computed',detail={'batch_id':batch_id,'config_sha256':pointer['sha256'],'task_fingerprint':result['task_fingerprint'],'status':result['status']})
            return result


def pack(run_dir,mapping,output,scope,bindings=None):
    root=Path(run_dir);run={'files':{name:(root/name).read_bytes().decode('utf-8') for name in FILES},
                           'task_bindings':json.loads(Path(mapping).read_text(encoding='utf-8'))}
    if bindings:
        path=Path(bindings);b=json.loads(path.read_text(encoding='utf-8'));run['boundary_bindings']=b;run['evidence_files']={}
        for item in b['bindings']:
            data=(path.parent/item['source_file']).read_bytes()
            if digest(data)!=item['source_sha256']:raise ValueError('边界证据哈希变化')
            run['evidence_files'][item['source_sha256']]=base64.b64encode(data).decode()
    dump(Path(output),{'schema':'phy2-boundary-site-v1','scope_note':scope,'runs':[run]})


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--run-dir',required=True);p.add_argument('--task-mapping',required=True);p.add_argument('--output',required=True);p.add_argument('--scope',required=True);p.add_argument('--boundary-bindings');a=p.parse_args()
    pack(a.run_dir,a.task_mapping,a.output,a.scope,a.boundary_bindings)
