import copy
import hashlib
import json
import sys
import tempfile
import threading
import unittest
import urllib.error
import urllib.request
from pathlib import Path

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from store import Store, ASSIGNMENTS, MODEL_OWNER, assign_formal_slots
from server import App
from workflow import annotations_agree, export_files, metrics, validate_annotation


class WorkflowTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name);self.store=Store(self.root/'annotations.sqlite3')
        self.invites=self.store.provision(include_qa=True);(self.root/'media').mkdir();f=self.root/'media/test.mp4';f.write_bytes(b'qa-unit-fixture-not-real-video')
        self.task={'id':'t01','model':'HunyuanVideo-1.5','clip_id':'T15_C03','primary_id':'r03','reviewer_id':'r01',
                   'seed':1,'prompt_variant':3,'media_file':'test.mp4','video_sha256':hashlib.sha256(f.read_bytes()).hexdigest(),
                   'fps':24,'duration_s':5,'window_s':5,'protocol':{'version':'test-v1','status':'diagnostic','target':'test target',
                   'events':{'departure':{'definition':'complete loss of support','minimum_evidence_times':1}}},
                   'machine':{'quality_route':'pass','quality_prediction':{'secret_machine':'must stay hidden'}},
                   'reference':{'admission':'pending','target_event':'departure','events':{'departure':1}}}
        self.package={'batch':{'id':'test','name':'unit fixture','mode':'pilot'},'tasks':[self.task]};self.store.import_batch(self.package,self.root/'media')
        self.primary={'id':'r03','role':'annotator'};self.reviewer={'id':'r01','role':'annotator'};self.admin={'id':'admin','role':'admin'}

    def tearDown(self):self.tmp.cleanup()

    def test_import_registered_label_only_protocol_without_requiring_timestamps(self):
        task=copy.deepcopy(self.task)
        task['id']='registered_label_only'
        catalog=Path(__file__).resolve().parents[1]/'resources/event_contracts.json'
        task['protocol']=json.loads(catalog.read_text(encoding='utf8'))['clips']['T03_C01']
        self.assertTrue(any(e['minimum_evidence_times']==0 for e in task['protocol']['events'].values()))
        package={'batch':{'id':'registered_label_only','name':'registered contract schema test','mode':'pilot'},'tasks':[task]}
        self.store.import_batch(package,self.root/'media')
        self.assertEqual(self.store.get_task(task['id'])['payload']['protocol'],task['protocol'])

    def test_import_rejects_invalid_timestamp_counts(self):
        for value in (-1, True, 0.5, None):
            with self.subTest(value=value):
                package=copy.deepcopy(self.package)
                package['batch']['id']='invalid_evidence'
                package['tasks'][0]['id']='invalid_evidence'
                package['tasks'][0]['protocol']['events']['departure']['minimum_evidence_times']=value
                with self.assertRaisesRegex(ValueError,'事件定义/证据要求缺失'):
                    self.store.import_batch(package,self.root/'media')

    def annotation(self,label='no'):
        return {'video_sha256':self.task['video_sha256'],'protocol_version':'test-v1',
                'quality':{'status':'pass','failure':'none','evidence_times_s':[0,5],'reason':'目标身份连续且整个观察窗桌面支撑清楚'},
                'events':{'departure':{'label':label,'time_s':1 if label=='yes' else None,'evidence_times_s':[0,5],'reason':'完整观察窗内目标没有完全离开支撑面'}}}

    def test_legacy_tasks_allow_human_before_vlm_and_preserve_labels(self):
        from server import Handler
        for flag in (None, False, True):
            for status in ('pending', 'running', 'network_failure', 'media_clock_failure'):
                with self.subTest(flag=flag, status=status):
                    p=copy.deepcopy(self.task)
                    p.update(vlm_required=True, frames=120, protocol_sha256='protocol', remote_media={'size':24})
                    p['machine']={'pipeline_status':status}
                    if flag is not None:p['human_annotation_without_vlm']=flag
                    with self.store.connect() as db:
                        db.execute('DELETE FROM annotations WHERE task_id=?',('t01',))
                        db.execute("UPDATE tasks SET payload=?,version=0,state='pending',batch_id='formal3600_v1' WHERE id='t01'",(json.dumps(p),))
                    view=Handler.task_view(None,self.store.get_task('t01'),self.primary)
                    self.assertTrue(view['can_work']);self.assertFalse(view['vlm_pending'])
                    annotation={**self.annotation(),'protocol_sha256':'protocol'}
                    self.store.save(self.primary,'t01','primary',copy.deepcopy(annotation),0,False)
                    saved=self.store.save(self.primary,'t01','primary',copy.deepcopy(annotation),1,True)
                    self.assertEqual(saved['annotations']['primary']['payload']['annotation_workflow'],'human_first_vlm_optional')
                    machine={'pipeline_status':'complete','media_verified':{'sha256':p['video_sha256'],'frames':120,'fps':24,'size':24},'quality_prediction':{'video_sha256':p['video_sha256']}}
                    if status != 'media_clock_failure':
                        self.store.install_machine_result({'task_id':'t01','video_sha256':p['video_sha256'],'protocol_sha256':'protocol','machine':machine})
                        after=self.store.get_task('t01')
                        self.assertEqual(after['annotations'],saved['annotations']);self.assertEqual(after['state'],saved['state'])
                    with self.assertRaises(ValueError):
                        self.store.save(self.primary,'t01','primary',self.annotation(),self.store.get_task('t01')['version'],True)

    def test_evidence_and_missing_are_not_zero(self):
        p=self.annotation();p['events']['departure']['evidence_times_s']=[]
        validate_annotation(p,self.task)  # Current human form does not require timestamps.
        p['events']={}
        with self.assertRaises(ValueError):validate_annotation(p,self.task)
        p=self.annotation('not_observed');validate_annotation(p,self.task)
        p['events']['departure']['time_s']=0
        validate_annotation(p,self.task)
        self.assertEqual(p['events']['departure']['label'],'not_observed')
        p=self.annotation();short={**self.task,'duration_s':2};p['quality']['evidence_times_s']=[0,1]
        with self.assertRaises(ValueError):validate_annotation(p,short)

    def test_formal_3600_balanced_unique_and_independent(self):
        tasks=[]
        for i,(model,owner) in enumerate(MODEL_OWNER.items()):
            for clip in range(100):
                for variant in (1,2,3):
                    tasks.append({**copy.deepcopy(self.task),'id':f'f_{i}_{clip}_{variant}',
                                  'model':model,'primary_id':owner,'clip_id':f'C{clip}',
                                  'seed':0,'prompt_variant':variant})
        assign_formal_slots(tasks)
        package={'batch':{'id':'formal_good','name':'balanced fixture','mode':'formal'},'tasks':tasks}
        self.store.import_batch(package,self.root/'media')
        self.assertEqual(len(self.store.all_tasks('formal_good')),3600)
        bad=copy.deepcopy(package);bad['batch']['id']='bad_duplicate'
        bad['tasks'][1]['prompt_variant']=1
        with self.assertRaises(ValueError):self.store.import_batch(bad,self.root/'media')
        bad=copy.deepcopy(package);bad['batch']['id']='bad_review_load'
        bad['tasks'][0]['reviewer_id']='r07' if bad['tasks'][0]['reviewer_id']!='r07' else 'r06'
        with self.assertRaises(ValueError):self.store.import_batch(bad,self.root/'media')

    def test_auth_assignment_versions_and_double_review(self):
        with self.assertRaises(PermissionError):self.store.save({'id':'r02','role':'annotator'},'t01','primary',self.annotation(),0,True)
        with self.assertRaises(PermissionError):self.store.save(self.primary,'t01','review',self.annotation(),0,True)
        with self.assertRaises(ValueError):self.store.save(self.reviewer,'t01','review',self.annotation(),0,True)
        t=self.store.save(self.primary,'t01','primary',self.annotation(),0,True);self.assertEqual(t['state'],'review_pending')
        with self.assertRaises(RuntimeError):self.store.save(self.reviewer,'t01','review',self.annotation(),0,True)
        t=self.store.save(self.reviewer,'t01','review',self.annotation(),1,True);self.assertEqual(t['state'],'resolved')
        m=metrics([t],'pilot');self.assertEqual(m['pipeline']['true_pass'],1);self.assertIsNone(m['formal_scores']['NearAcc'])
        files=export_files([t],{'mode':'pilot'},[]);self.assertEqual(json.loads(files['annotations.jsonl'])['events']['departure'],0)

    def test_label_disagreement_needs_adjudication_optional_times_do_not(self):
        self.store.save(self.primary,'t01','primary',self.annotation(),0,True)
        t=self.store.save(self.reviewer,'t01','review',self.annotation('yes'),1,True);self.assertEqual(t['state'],'disputed')
        p=self.annotation();p['adjudication_reason']='逐帧检查0至5秒，原目标始终仍在桌面支撑范围内。'
        t=self.store.save(self.admin,'t01','adjudication',p,2,True);self.assertEqual(t['state'],'resolved')
        a=self.annotation('yes');b=copy.deepcopy(a);b['events']['departure']['time_s']=1.5
        self.assertTrue(annotations_agree(a,b,self.task))  # Consensus is on event labels.

    def test_quality_failure_blocks_events_and_false_pass_is_counted(self):
        p=self.annotation();p['quality'].update(status='failure',failure='identity_loss');p['events']={}
        self.store.save(self.primary,'t01','primary',p,0,True);t=self.store.save(self.reviewer,'t01','review',p,1,True)
        m=metrics([t],'pilot');self.assertEqual(m['pipeline']['false_pass'],1)
        records=export_files([t],{'mode':'pilot'},[]);self.assertEqual(json.loads(records['screening.jsonl'])['status'],'confirmed_failure')
        self.assertEqual(json.loads(records['annotations.jsonl'])['events'],{})
        p['quality']['evidence_times_s']=[1,1]
        validate_annotation(p,self.task)  # Optional legacy evidence is not a required field.
        p['events']={'departure':{'label':'yes'}}
        with self.assertRaises(ValueError):validate_annotation(p,self.task)

    def test_invite_single_use_and_import_tampering(self):
        token=next(i['token'] for i in self.invites if i['user_id']=='r03')
        self.assertEqual(self.store.activate(token,'a-long-password-2026'),'r03')
        with self.assertRaises(ValueError):self.store.activate(token,'a-long-password-2026')
        self.assertEqual(self.store.login('r03','a-long-password-2026'),'r03')
        p=copy.deepcopy(self.package);p['batch']['id']='evil';p['tasks'][0]['media_file']='../annotations.sqlite3'
        with self.assertRaises(ValueError):self.store.import_batch(p,self.root/'media')

    def test_http_blinding_csrf_range_and_export_permissions(self):
        app=App(('127.0.0.1',0),self.root,prefix='/',secure=False)
        thread=threading.Thread(target=app.serve_forever,daemon=True);thread.start();base=f'http://127.0.0.1:{app.server_port}'
        token=app.store.session('r01');user=app.store.authenticate(token)
        def get(p,headers=None):return urllib.request.urlopen(urllib.request.Request(base+p,headers={'Cookie':'phylabel_session='+token,**(headers or {})}),timeout=5)
        try:
            detail=json.load(get('/api/tasks/t01'));self.assertNotIn('machine',detail);self.assertNotIn('reference',detail);self.assertFalse(detail['can_work'])
            self.store.save(self.primary,'t01','primary',self.annotation(),0,True)
            detail=json.load(get('/api/tasks/t01'));self.assertTrue(detail['can_work']);self.assertNotIn('comparison',detail)
            with self.assertRaises(urllib.error.HTTPError) as err:get('/api/export?batch=test')
            self.assertEqual(err.exception.code,403)
            response=get('/media/t01',{'Range':'bytes=2-7'});self.assertEqual(response.status,206);self.assertEqual(len(response.read()),6)
            bad=urllib.request.Request(base+'/api/tasks/t01/annotation',data=json.dumps({'stage':'review','version':1,'submit':True,'annotation':self.annotation()}).encode(),headers={'Cookie':'phylabel_session='+token,'Content-Type':'application/json','Origin':base},method='POST')
            with self.assertRaises(urllib.error.HTTPError) as err:urllib.request.urlopen(bad)
            self.assertEqual(err.exception.code,403)
        finally:app.shutdown();app.server_close()


if __name__=='__main__':unittest.main()
