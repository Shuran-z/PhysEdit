"""Index the audited patch and diagnose only current-version configuration drift."""
from pathlib import Path
import collections,functools,gzip,hashlib,json,sqlite3,sys,zlib,zipfile
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from scripts import full_prompt_config_audit as audit
from scripts.repair_and_verify_all_prompts import source_controls
BASE=audit.OUT/'publish';CURRENT=BASE/'current';DB=BASE/'audited_patch.sqlite'
FIELDS=['parameter_facts','parameter_facts_sha256','prompt_en','prompt_variants_en','prompt_sha256','prompt_variant_sha256','prompt_variant_token_counts','prompt_token_counts','selected_parameter_keys','omitted_parameter_keys','external_control_inputs','external_control_disclosure','prompt_revision','full_numeric_audit']

def index():
    db=sqlite3.connect(DB)
    db.execute('CREATE TABLE IF NOT EXISTS patch(id TEXT PRIMARY KEY,sha TEXT,config_sha TEXT,payload BLOB)')
    if db.execute('SELECT COUNT(*) FROM patch').fetchone()[0]!=72000:
        db.execute('DELETE FROM patch')
        for line in gzip.open(audit.OUT/'audited_release/videos.jsonl.gz','rt',encoding='utf8'):
            r=json.loads(line);payload={k:r[k] for k in FIELDS if k in r}
            db.execute('INSERT INTO patch VALUES(?,?,?,?)',(r['canonical_video_id'],r['sha256'],(r.get('config_download') or {}).get('sha256'),zlib.compress(json.dumps(payload,ensure_ascii=False).encode(),1)))
        db.commit()
    return db

class Configs:
    def __init__(self):
        self.archives={'releases/physedit/provenance/configs.zip':zipfile.ZipFile(CURRENT/'configs.zip'),
                       'releases/t14_original_isaac_20261101/provenance.zip':zipfile.ZipFile(CURRENT/'t14_provenance.zip')}
    @functools.lru_cache(maxsize=512)
    def get(self,path,member,h):
        b=self.archives[path].read(member);assert hashlib.sha256(b).hexdigest()==h
        r=json.loads(b);return r,audit.context(r)

def main():
    db=index();cfg=Configs();stats=collections.Counter();pending=[];examples={}
    for line in gzip.open(CURRENT/'videos.jsonl.gz','rt',encoding='utf8'):
        r=json.loads(line);vid=r['canonical_video_id'];p=db.execute('SELECT sha,config_sha FROM patch WHERE id=?',(vid,)).fetchone();d=r.get('config_download') or {}
        if p and p[1]==d.get('sha256'):continue
        stats['new_or_changed_config_rows']+=1
        raw,ctx=cfg.get(d['path'],d['member'],d['sha256']);bad=[]
        for f in r['parameter_facts']:
            value,path=audit.resolve(f[0],f[-2],raw,ctx,r)
            if value is None:bad.append({'key':f[0],'kind':'unresolved','reason':path})
            elif not audit.equal(value,f[-2]):bad.append({'key':f[0],'kind':'mismatch','old':f[-2],'expected':value})
        try:
            n,c,clock=source_controls(r,raw,ctx);issues=n['issues']
        except Exception as exc:issues=['exception:'+repr(exc)]
        for issue in issues:stats['control_'+issue]+=1
        for issue in bad:stats[issue['kind']]+=1
        if bad or issues:
            pending.append({'video_id':vid,'scene':r['scene'],'engine':r['engine'],'fields':bad,'controller_issues':issues})
            tag=r['engine']+'/'+r['scene']
            examples.setdefault(tag,{'row':r,'config':raw})
    (BASE/'CURRENT_DRIFT_PREFLIGHT.json').write_text(json.dumps({'counts':dict(stats),'pending':pending},ensure_ascii=False,indent=2),encoding='utf8')
    (BASE/'CURRENT_DRIFT_EXAMPLES.json').write_text(json.dumps(examples,ensure_ascii=False,indent=2),encoding='utf8')
    print(json.dumps({'counts':dict(stats),'pending_rows':len(pending),'example_types':list(examples)},ensure_ascii=True))

if __name__=='__main__':main()
