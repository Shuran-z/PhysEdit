"""Small, auditable SQLite store for the PHY2 annotation site (stdlib only)."""
import hashlib
import hmac
import json
import secrets
import sqlite3
import time
from contextlib import contextmanager
from pathlib import Path

ASSIGNMENTS = {
    'r01': ['Wan-2.2-5B', 'VideoGPA'],
    'r02': ['Wan-2.2-A14B', 'PhysAlign'],
    'r03': ['CogVideoX-1.5', 'HunyuanVideo-1.5'],
    'r04': ['Cosmos-Predict2', 'Cosmos3-Nano'],
    'r05': ['LTX-Video-2B', 'PhysRVG'],
    'r06': ['DynamiCrafter'],
    'r07': ['MiniMax-H3'],
}
MODEL_OWNER = {m: u for u, models in ASSIGNMENTS.items() for m in models}
# Default model ownership; pilot overrides are explicit and formal assignments use quotas.
ASSIGNMENT_QUOTAS = {f'r{i:02d}':520 if i<=5 else 500 for i in range(1,8)}


def assign_formal_slots(slots):
    """Freeze mixed-model assignments independently of the seed/prompt selection."""
    import random
    if len(slots)!=3600:raise ValueError('正式分工必须包含3600个任务槽位')
    roster=[uid for uid,n in ASSIGNMENT_QUOTAS.items() for _ in range(n)]
    indices=list(range(len(slots)))
    random.Random(20261022).shuffle(indices)
    for i,index in enumerate(indices):
        slots[index]['primary_id']=roster[i]
        slots[index]['reviewer_id']=''
        slots[index]['review_policy']='vlm_human_dispute_only_v2'


def digest(value):
    return hashlib.sha256(value.encode()).hexdigest()


def password_hash(password, salt=None):
    salt = salt or secrets.token_hex(16)
    value = hashlib.scrypt(password.encode(), salt=bytes.fromhex(salt), n=16384, r=8, p=1).hex()
    return salt + ':' + value


def check_password(password, saved):
    return bool(saved) and hmac.compare_digest(password_hash(password, saved.split(':')[0]), saved)


class Store:
    def __init__(self, path):
        self.path = str(path)
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        with self.connect() as db:
            db.executescript('''
            PRAGMA journal_mode=WAL;
            CREATE TABLE IF NOT EXISTS users (
              id TEXT PRIMARY KEY, name TEXT NOT NULL, role TEXT NOT NULL,
              password TEXT, invite_hash TEXT, enabled INTEGER NOT NULL DEFAULT 1);
            CREATE TABLE IF NOT EXISTS sessions (
              token_hash TEXT PRIMARY KEY, user_id TEXT NOT NULL, csrf TEXT NOT NULL, expires REAL NOT NULL);
            CREATE TABLE IF NOT EXISTS batches (
              id TEXT PRIMARY KEY, name TEXT NOT NULL, mode TEXT NOT NULL, metadata TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS tasks (
              id TEXT PRIMARY KEY, batch_id TEXT NOT NULL, primary_id TEXT NOT NULL,
              reviewer_id TEXT NOT NULL, payload TEXT NOT NULL, state TEXT NOT NULL DEFAULT 'unstarted',
              version INTEGER NOT NULL DEFAULT 0);
            CREATE INDEX IF NOT EXISTS task_assignment ON tasks(batch_id,primary_id,reviewer_id);
            CREATE TABLE IF NOT EXISTS annotations (
              task_id TEXT NOT NULL, stage TEXT NOT NULL, user_id TEXT NOT NULL,
              payload TEXT NOT NULL, submitted INTEGER NOT NULL, updated REAL NOT NULL,
              PRIMARY KEY(task_id,stage));
            CREATE TABLE IF NOT EXISTS audit (
              id INTEGER PRIMARY KEY AUTOINCREMENT, at REAL NOT NULL, actor TEXT NOT NULL,
              action TEXT NOT NULL, task_id TEXT, detail TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS dispute_samples (
              id TEXT PRIMARY KEY, batch_id TEXT NOT NULL, payload TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS independent_observations (
              task_id TEXT NOT NULL, observation_id TEXT NOT NULL, user_id TEXT NOT NULL,
              payload TEXT NOT NULL, version INTEGER NOT NULL, updated REAL NOT NULL,
              PRIMARY KEY(task_id,observation_id));
            ''')

    @contextmanager
    def connect(self):
        db = sqlite3.connect(self.path, timeout=20)
        db.row_factory = sqlite3.Row
        db.execute('PRAGMA busy_timeout=20000')
        try:
            yield db
            db.commit()
        except BaseException:
            db.rollback()
            raise
        finally:
            db.close()

    @staticmethod
    def log(db, actor, action, task_id=None, detail=None):
        db.execute('INSERT INTO audit(at,actor,action,task_id,detail) VALUES(?,?,?,?,?)',
                   (time.time(), actor, action, task_id, json.dumps(detail or {}, ensure_ascii=False)))

    def provision(self, include_qa=False):
        invitations = []
        people = [(k, '人员' + k[1:].lstrip('0'), 'annotator') for k in ASSIGNMENTS]
        people += [('admin', '项目管理员', 'admin')]
        if include_qa:
            people += [('qa_primary', '流程验收初审', 'qa'), ('qa_review', '流程验收复审', 'qa')]
        with self.connect() as db:
            for uid, name, role in people:
                if db.execute('SELECT 1 FROM users WHERE id=?', (uid,)).fetchone():
                    continue
                token = secrets.token_urlsafe(32)
                db.execute('INSERT INTO users(id,name,role,invite_hash) VALUES(?,?,?,?)',
                           (uid, name, role, digest(token)))
                invitations.append({'user_id': uid, 'name': name, 'role': role, 'token': token})
        return invitations

    def rotate_invite(self, uid):
        token = secrets.token_urlsafe(32)
        with self.connect() as db:
            db.execute('UPDATE users SET password=NULL,invite_hash=?,enabled=1 WHERE id=?', (digest(token), uid))
            db.execute('DELETE FROM sessions WHERE user_id=?', (uid,))
            self.log(db, 'system', 'invite_rotated', detail={'user_id': uid})
        return token

    def activate(self, token, password):
        if not isinstance(password, str) or len(password) < 10 or len(password) > 200:
            raise ValueError('密码需为10至200个字符')
        with self.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            row = db.execute('SELECT * FROM users WHERE invite_hash=? AND enabled=1', (digest(token),)).fetchone()
            if not row:
                raise ValueError('邀请链接无效或已使用')
            db.execute('UPDATE users SET password=?,invite_hash=NULL WHERE id=?', (password_hash(password), row['id']))
            self.log(db, row['id'], 'account_activated')
        return row['id']

    def login(self, uid, password):
        if not isinstance(uid,str) or not isinstance(password,str) or len(uid)>100 or not 1<=len(password)<=200:
            return None
        with self.connect() as db:
            row = db.execute('SELECT * FROM users WHERE id=? AND enabled=1', (uid,)).fetchone()
            if not row or not check_password(password, row['password']):
                return None
        return uid

    def session(self, uid):
        token, csrf = secrets.token_urlsafe(32), secrets.token_urlsafe(24)
        with self.connect() as db:
            db.execute('DELETE FROM sessions WHERE expires<?', (time.time(),))
            db.execute('INSERT INTO sessions VALUES(?,?,?,?)', (digest(token), uid, csrf, time.time()+14*86400))
        return token

    def authenticate(self, token):
        with self.connect() as db:
            r = db.execute('''SELECT u.id,u.name,u.role,s.csrf FROM users u JOIN sessions s ON u.id=s.user_id
                            WHERE s.token_hash=? AND s.expires>? AND u.enabled=1''', (digest(token), time.time())).fetchone()
        return dict(r) if r else None

    def logout(self, token):
        with self.connect() as db:
            db.execute('DELETE FROM sessions WHERE token_hash=?', (digest(token),))

    def import_batch(self, package, media_root, actor='system'):
        from workflow import validate_task
        bid = package['batch']['id']
        if not bid.replace('-', '').replace('_', '').isalnum():
            raise ValueError('批次ID格式错误')
        tasks = package['tasks']
        if len(tasks) > 3600 or len({t['id'] for t in tasks}) != len(tasks):
            raise ValueError('任务重复或超过3600条')
        mode = package['batch']['mode']
        if mode not in ('pilot', 'formal', 'qa'):
            raise ValueError('批次类型错误')
        for t in tasks:
            validate_task(t, media_root)
            if mode == 'pilot' and (t['primary_id'] not in ASSIGNMENT_QUOTAS or t['model'] not in MODEL_OWNER):
                raise ValueError('试跑任务须分配给七位成员之一，并使用已登记模型')
        model_counts = {}
        for t in tasks:
            model_counts[t['model']] = model_counts.get(t['model'], 0)+1
        if mode == 'formal' and (set(model_counts) != set(MODEL_OWNER) or any(v != 300 for v in model_counts.values())):
            raise ValueError('正式批次必须12模型各300条，总量3600')
        if mode == 'formal':
            combos={(t['model'],t['clip_id'],t['seed'],t['prompt_variant']) for t in tasks}
            if len(combos)!=len(tasks):raise ValueError('正式抽样存在重复的seed/prompt组合')
            source_counts={};primary_counts={uid:0 for uid in ASSIGNMENT_QUOTAS}
            for t in tasks:
                source_counts[t['model'],t['clip_id']]=source_counts.get((t['model'],t['clip_id']),0)+1
                if t['reviewer_id'] or t.get('review_policy')!='vlm_human_dispute_only_v2':
                    raise ValueError('正式任务只安排一次人工复核；不得预分配全量复审')
                if t['primary_id'] not in primary_counts:raise ValueError('正式任务初审者须为七位成员之一')
                primary_counts[t['primary_id']]+=1
            if len(source_counts)!=1200 or any(n!=3 for n in source_counts.values()):
                raise ValueError('每模型必须覆盖100个测试样本，每样本3个组合')
            sources=[{clip for model,clip in source_counts if model==m} for m in MODEL_OWNER]
            if any(s!=sources[0] for s in sources):raise ValueError('模型的测试样本集合必须相同')
            if primary_counts!=ASSIGNMENT_QUOTAS:
                raise ValueError('七人总配额须为前五人520条、后两人500条')
        with self.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            db.execute('INSERT INTO batches VALUES(?,?,?,?)', (bid, package['batch']['name'], mode,
                       json.dumps(package['batch'], ensure_ascii=False)))
            for t in tasks:
                if t['primary_id'] == t['reviewer_id']:
                    raise ValueError('初审与复审必须是不同人员')
                for uid in (t['primary_id'], t['reviewer_id']):
                    if not uid:continue
                    if not db.execute('SELECT 1 FROM users WHERE id=?', (uid,)).fetchone():
                        raise ValueError('任务人员不存在')
                db.execute('INSERT INTO tasks(id,batch_id,primary_id,reviewer_id,payload) VALUES(?,?,?,?,?)',
                           (t['id'], bid, t['primary_id'], t['reviewer_id'], json.dumps(t, ensure_ascii=False)))
            self.log(db, actor, 'batch_imported', detail={'batch_id': bid, 'count': len(tasks), 'model_counts': model_counts})

    def get_task(self, tid):
        with self.connect() as db:
            row = db.execute('SELECT * FROM tasks WHERE id=?', (tid,)).fetchone()
            notes = db.execute('SELECT * FROM annotations WHERE task_id=?', (tid,)).fetchall()
            independent={r['observation_id']:json.loads(r['payload'])for r in db.execute('SELECT * FROM independent_observations WHERE task_id=?',(tid,))}
        if not row:
            return None
        return {**dict(row), 'payload': json.loads(row['payload']),
                'annotations': {r['stage']: {**dict(r), 'payload': json.loads(r['payload'])} for r in notes},'independent_observations':independent}

    def all_tasks(self, batch_id):
        with self.connect() as db:
            tasks=[{**dict(r),'payload':json.loads(r['payload']),'annotations':{}} for r in db.execute('SELECT * FROM tasks WHERE batch_id=? ORDER BY id',(batch_id,))]
            by={t['id']:t for t in tasks}
            for r in db.execute('SELECT a.* FROM annotations a JOIN tasks t ON a.task_id=t.id WHERE t.batch_id=?',(batch_id,)):
                by[r['task_id']]['annotations'][r['stage']]={**dict(r),'payload':json.loads(r['payload'])}
            for r in db.execute('SELECT o.* FROM independent_observations o JOIN tasks t ON o.task_id=t.id WHERE t.batch_id=?',(batch_id,)):
                by[r['task_id']].setdefault('independent_observations',{})[r['observation_id']]=json.loads(r['payload'])
        return tasks

    def save_box_observation(self,user,tid,data):
        from box_motion import KEY,DEFINITION_SHA,eligible
        if data.get('label')not in ('yes','no','uncertain'):raise ValueError('请选择发生、未发生或不可判')
        with self.connect()as db:
            db.execute('BEGIN IMMEDIATE');r=db.execute('SELECT * FROM tasks WHERE id=?',(tid,)).fetchone()
            if not r:raise LookupError('任务不存在')
            p=json.loads(r['payload'])
            if user['id']!=r['primary_id']:raise PermissionError('只能补充自己负责的独立观察')
            if p.get('annotation_hold',{}).get('active'):raise ValueError('本任务暂缓标注')
            if not eligible(p):raise ValueError('本项仅适用于T17登记任务')
            if data.get('video_sha256')!=p['video_sha256']or data.get('definition_sha256')!=DEFINITION_SHA:raise ValueError('媒体或独立观察定义已变更，请刷新')
            a=db.execute("SELECT payload FROM annotations WHERE task_id=? AND stage='primary'",(tid,)).fetchone()
            if not a or json.loads(a['payload']).get('quality',{}).get('status')!='pass':raise ValueError('请先将可测性选为可测并保存草稿或提交')
            old=db.execute('SELECT * FROM independent_observations WHERE task_id=? AND observation_id=?',(tid,KEY)).fetchone()
            version=old['version']if old else 0
            if type(data.get('version'))is not int or data['version']!=version:raise RuntimeError('独立观察已更新，请刷新后重试')
            now=time.time();payload={'observation_id':KEY,'label':data['label'],'user_id':user['id'],'video_sha256':p['video_sha256'],'definition_sha256':DEFINITION_SHA,'version':version+1,'updated':now,'scope':'supplemental_not_scored'}
            db.execute('INSERT OR REPLACE INTO independent_observations VALUES(?,?,?,?,?,?)',(tid,KEY,user['id'],json.dumps(payload,ensure_ascii=False),version+1,now))
            self.log(db,user['id'],'independent_box_translation_saved',tid,{'previous':json.loads(old['payload'])if old else None,'current':payload,'original_annotation_unchanged':True})
        return self.get_task(tid)

    def save_process_observation(self,user,tid,data):
        from process_observations import definitions
        if data.get('label') not in ('yes','no','uncertain'):raise ValueError('请选择发生、未发生或不可判')
        with self.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            r=db.execute('SELECT * FROM tasks WHERE id=?',(tid,)).fetchone()
            if not r:raise LookupError('任务不存在')
            p=json.loads(r['payload'])
            if user['id']!=r['primary_id']:raise PermissionError('只能补充自己负责的独立观察')
            if p.get('annotation_hold',{}).get('active'):raise ValueError('本任务暂缓标注')
            item=next((x for x in definitions(p) if x['definition']['id']==data.get('observation_id')),None)
            if not item:raise ValueError('此任务没有登记该独立观察')
            key=item['definition']['id'];sha=item['definition_sha256']
            if data.get('video_sha256')!=p['video_sha256'] or data.get('definition_sha256')!=sha:raise ValueError('媒体或观察定义已变更，请刷新')
            a=db.execute("SELECT payload FROM annotations WHERE task_id=? AND stage='primary'",(tid,)).fetchone()
            if not a or json.loads(a['payload']).get('quality',{}).get('status')!='pass':raise ValueError('请先保存可测性为可测；物理错误本身不代表不可测')
            if data['label']=='no' and p['duration_s']+.001<p['window_s']:raise ValueError('视频未覆盖观察窗，请选不可判')
            old=db.execute('SELECT * FROM independent_observations WHERE task_id=? AND observation_id=?',(tid,key)).fetchone()
            version=old['version'] if old else 0
            if type(data.get('version')) is not int or data['version']!=version:raise RuntimeError('独立观察已更新，请刷新')
            now=time.time();payload=dict(observation_id=key,label=data['label'],user_id=user['id'],video_sha256=p['video_sha256'],definition_sha256=sha,version=version+1,updated=now,scope='supplemental_not_scored')
            db.execute('INSERT OR REPLACE INTO independent_observations VALUES(?,?,?,?,?,?)',(tid,key,user['id'],json.dumps(payload,ensure_ascii=False),version+1,now))
            self.log(db,user['id'],'independent_process_observation_saved',tid,{'previous':json.loads(old['payload']) if old else None,'current':payload,'original_annotation_unchanged':True})
        return self.get_task(tid)

    def save(self, user, tid, stage, payload, expected_version, submit):
        from workflow import can_access, validate_annotation, annotations_agree, dispute_reasons, SINGLE_REVIEW_POLICY
        with self.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            row = db.execute('SELECT * FROM tasks WHERE id=?', (tid,)).fetchone()
            if not row:
                raise LookupError('任务不存在')
            task = dict(row)
            task['payload'] = json.loads(task['payload'])
            if task['payload'].get('annotation_hold',{}).get('active'):
                raise ValueError('本任务暂缓标注：等待使用v6 prompt重新生成，已有记录保留')
            notes = {r['stage']: dict(r) for r in db.execute('SELECT * FROM annotations WHERE task_id=?', (tid,))}
            for r in notes.values():
                r['payload'] = json.loads(r['payload'])
            task['annotations'] = notes
            if not can_access(user, task):
                raise PermissionError('无此任务权限')
            if type(expected_version) is not int or task['version'] != expected_version:
                raise RuntimeError('记录已更新，请刷新后重试；草稿仍保留在本页')
            valid_stage = (stage=='primary' and user['id']==row['primary_id'] or
                           stage=='review' and user['id']==row['reviewer_id'] or
                           stage=='adjudication' and user['role']=='admin')
            if not valid_stage:
                raise PermissionError('不能代替其他人提交')
            if notes.get(stage, {}).get('submitted'):
                raise ValueError('已提交记录锁定；保留初审与复审记录，争议由管理员仲裁')
            if stage=='review' and not notes.get('primary', {}).get('submitted'):
                raise ValueError('等待初审提交后才能独立复审')
            if stage=='adjudication' and task['state']!='disputed':
                raise ValueError('仅对有争议的任务二审')
            single=task['payload'].get('review_policy')==SINGLE_REVIEW_POLICY
            if stage=='adjudication' and single and not task['payload'].get('second_review_sample',{}).get('selected'):
                raise ValueError('此争议尚未抽中二审；保留待定，不自动增加任务')
            if isinstance(payload,dict) and payload.get('annotation_schema') in ('source-label-review-v4','measurability-binary-v5'):
                from protocol_rules import has_numeric_rule
                payload['measurement_verification']={k:'not_verified' for k,d in task['payload']['protocol']['events'].items() if has_numeric_rule(d)}
            if submit:
                validate_annotation(payload, task['payload'])
            elif not isinstance(payload, dict):
                raise ValueError('草稿格式错误')
            now = time.time()
            payload['annotation_workflow']='human_first_vlm_optional'
            payload['machine_status_when_saved']=task['payload'].get('machine',{}).get('pipeline_status','pending')
            payload['machine_availability_note']='Availability at save time; not evidence that the annotator viewed the prediction. Do not claim independent blind labels.'
            db.execute('INSERT OR REPLACE INTO annotations VALUES(?,?,?,?,?,?)',
                       (tid, stage, user['id'], json.dumps(payload, ensure_ascii=False), int(submit), now))
            if submit:
                if stage=='primary':
                    reasons=dispute_reasons(payload,task['payload']) if single else []
                    state=('disputed' if reasons else 'resolved') if single else 'review_pending'
                    if reasons:self.log(db,user['id'],'dispute_flagged',tid,{'reasons':reasons})
                elif stage=='adjudication':
                    state='resolved'
                else:
                    state='resolved' if annotations_agree(notes['primary']['payload'],payload,task['payload']) else 'disputed'
            else:
                state=task['state'] if stage!='primary' else 'draft'
            db.execute('UPDATE tasks SET state=?,version=version+1 WHERE id=?', (state, tid))
            self.log(db, user['id'], stage+('_submitted' if submit else '_draft_saved'), tid,
                     {'version': expected_version+1, 'payload': payload})
        return self.get_task(tid)

    def install_machine_result(self,data):
        """Scoped worker may populate machine fields once, never write human labels."""
        tid=data['task_id'];machine=data['machine']
        if machine.get('pipeline_status') not in ('complete','evaluator_failure','blocked_quality','media_clock_failure'):raise ValueError('预评状态无效')
        if not machine.get('media_verified') or not machine.get('quality_prediction'):raise ValueError('媒体未核验或VLM尚未实际预评，不能接收机器结果')
        with self.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            row=db.execute('SELECT * FROM tasks WHERE id=?',(tid,)).fetchone()
            if not row:raise LookupError('任务不存在')
            p=json.loads(row['payload'])
            if row['batch_id']!='formal3600_v1' or not p.get('vlm_required'):raise ValueError('预评任务范围错误')
            if data.get('video_sha256')!=p['video_sha256'] or data.get('protocol_sha256')!=p['protocol_sha256']:raise ValueError('预评媒体/协议不匹配')
            verified=machine['media_verified']
            if (verified.get('sha256')!=p['video_sha256'] or verified.get('frames')!=p['frames']
                or type(verified.get('fps')) not in (float,int) or abs(verified['fps']-p['fps'])>.02
                or verified.get('size')!=p['remote_media']['size']):raise ValueError('预评实际媒体时钟/哈希未通过核验')
            for name in ('quality_prediction','event_prediction'):
                pred=machine.get(name)
                if pred and pred.get('video_sha256')!=p['video_sha256']:raise ValueError('预评结果哈希不匹配')
            if machine.get('event_prediction',{}).get('status')=='ok' and set(machine['event_prediction'].get('events',{}))!=set(p['protocol']['events']):raise ValueError('预评事件集合不完整')
            if p.get('machine',{}).get('pipeline_status') in ('complete','evaluator_failure','blocked_quality','media_clock_failure'):
                if p['machine']!=machine:raise ValueError('已回传预评记录锁定')
                return
            has_human=bool(db.execute('SELECT 1 FROM annotations WHERE task_id=?',(tid,)).fetchone())
            if has_human:
                p['late_machine_result']={'received_after_human_record':True,'at':time.time(),'human_labels_and_state_preserved':True}
            p['machine']=machine
            db.execute('UPDATE tasks SET payload=?,version=version+1 WHERE id=?',(json.dumps(p,ensure_ascii=False),tid))
            self.log(db,'vlm-worker','machine_preassessment_installed',tid,{'pipeline_status':machine['pipeline_status'],'video_sha256':p['video_sha256'],'protocol_sha256':p['protocol_sha256']})

    def sample_disputes(self, actor, batch_id, rate=.2, seed=20261022):
        import math,random
        from workflow import SINGLE_REVIEW_POLICY
        if type(rate) not in (float,int) or not 0<rate<=1 or type(seed) is not int:raise ValueError('抽样比例须在0至1之间，种子须为整数')
        with self.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            batch=db.execute('SELECT mode FROM batches WHERE id=?',(batch_id,)).fetchone()
            if not batch:raise LookupError('批次不存在')
            if batch['mode']=='qa':raise ValueError('历史QA批次不执行正式争议抽样')
            pool=[]
            for row in db.execute("SELECT * FROM tasks WHERE batch_id=? AND state='disputed' ORDER BY id",(batch_id,)):
                p=json.loads(row['payload'])
                if p.get('review_policy')==SINGLE_REVIEW_POLICY and not p.get('second_review_sample') and not p.get('annotation_hold',{}).get('active'):pool.append((dict(row),p))
            if not pool:return {'pool':0,'selected':0,'note':'没有尚未抽样的争议；旧抽样不重抽'}
            count=math.ceil(len(pool)*rate);chosen=set(random.Random(seed).sample([r['id'] for r,p in pool],count))
            sid='dispute_'+secrets.token_hex(8)
            report={'id':sid,'batch_id':batch_id,'rate':rate,'seed':seed,'pool':[{'task_id':r['id'],'video_sha256':p['video_sha256']} for r,p in pool],
                    'selected_ids':sorted(chosen),'sampling':'uniform_without_replacement_ceil','reviewer':'admin','at':time.time()}
            for r,p in pool:
                p['second_review_sample']={'id':sid,'selected':r['id'] in chosen,'rate':rate,'seed':seed,'reviewer':'admin'}
                db.execute('UPDATE tasks SET payload=?,version=version+1 WHERE id=?',(json.dumps(p,ensure_ascii=False),r['id']))
            db.execute('INSERT INTO dispute_samples VALUES(?,?,?)',(sid,batch_id,json.dumps(report,ensure_ascii=False)))
            self.log(db,actor,'dispute_sample_frozen',detail=report)
            return {'id':sid,'pool':len(pool),'selected':count,'reviewer':'admin'}
