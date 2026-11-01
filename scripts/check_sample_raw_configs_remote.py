"""Check raw config retrieval without treating server paths as public downloads."""
import hashlib
import io
import json
from pathlib import Path
import tarfile
import zipfile
import httpx2 as httpx
from huggingface_hub import HfApi, hf_hub_download, hf_hub_url, get_token

R=Path('/data_cached/wangzijun_p25/colleague_download_check_20261031')
S=json.loads((R/'SAMPLE_ROWS.json').read_text())
API=HfApi()
REV=json.loads((R/'DOWNLOAD_CHECK.json').read_text())['revision']
OUT=R/'configs'
OUT.mkdir(exist_ok=True)
results=[]

def record(r,raw,location,expected):
    h=hashlib.sha256(raw).hexdigest()
    assert h==expected,(r['canonical_video_id'],h,expected)
    json.loads(raw)
    target=OUT/(r['canonical_video_id']+'.json')
    target.write_bytes(raw)
    return dict(canonical_video_id=r['canonical_video_id'],status='RAW_CONFIG_DOWNLOADED_HASH_MATCH',sha256=h,location=location)

class Stream(io.RawIOBase):
    def __init__(self,response):self.it=response.iter_bytes();self.buf=b'';self.total=0
    def readable(self):return True
    def readinto(self,b):
        while len(self.buf)<len(b):
            try:chunk=next(self.it)
            except StopIteration:break
            self.total+=len(chunk)
            if self.total>150*1024*1024:raise ValueError('Bounded sample stream limit reached')
            self.buf+=chunk
        n=min(len(b),len(self.buf));b[:n]=self.buf[:n];self.buf=self.buf[n:];return n

for r in S:
    try:
        cid=r['canonical_video_id']
        if r.get('current_render'):
            c=r['current_render'];b=c['source_bundle'];member=c['config_member']
            with httpx.stream('GET',hf_hub_url(b['repo_id'],b['path'],repo_type='dataset',revision=b['revision']),headers={'Authorization':'Bearer '+get_token()},follow_redirects=True,timeout=60) as response:
                response.raise_for_status()
                with tarfile.open(fileobj=io.BufferedReader(Stream(response)),mode='r|gz') as tar:
                    for item in tar:
                        if item.name==member:
                            raw=tar.extractfile(item).read();break
                    else:raise ValueError('Config member missing')
            result=record(r,raw,{**b,'member':member},c['source_config_sha256'])
            # Check actual numeric intervention retained in full input triples.
            cfg=json.loads(raw)
            facts=dict((k,v) for k,v,u in r['parameter_facts'])
            for k,v in c['changed_inputs'].items():assert facts[k]==v,(k,v,facts.get(k))
            result['changed_inputs_match_parameter_facts']=True
        elif r['engine']=='genesis' and r['quota_scene']=='T19':
            d=R/'physedit/provenance/t19_gen_new_20261030'
            binding=next(b for b in map(json.loads,(d/'SOURCE_BINDINGS.jsonl').read_text().splitlines()) if any(v['sha256']==r['sha256'] for v in b['videos']))
            member='physics/'+binding['group']+'/'+binding['sample_id']+'/config.json'
            with zipfile.ZipFile(d/'source_metadata.zip') as z:raw=z.read(member)
            result=record(r,raw,{'path':'physedit/provenance/t19_gen_new_20261030/source_metadata.zip','member':member},binding['source_config_sha256'])
            assert json.loads(raw)==r['physical_inputs']['config']==binding['physical_inputs']
            result['full_physical_inputs_match']=True
        else:
            candidates=[]
            conf=r.get('prompt_source_config')
            if conf and conf.startswith('data/'):
                candidates.append(conf)
            if r.get('source_path') and '/videos/' in r['source_path']:
                root=r['source_path'].split('/videos/')[0]
                candidates.extend([root+'/configs/'+r['native_sample_id']+'.json',root+'/configs/'+r['native_sample_id']+'/cam01.json'])
            info=API.get_paths_info(r.get('source_repo') or 'phy2/phydataset',list(dict.fromkeys(candidates)),revision=r.get('source_revision') or REV,repo_type='dataset') if candidates else []
            expected=r.get('prompt_source_config_sha256') or r['prompt_binding_evidence'].get('source_config_sha256') or r['prompt_binding_evidence'].get('config_evidence',{}).get('expected_sha256')
            if info:
                p=Path(hf_hub_download(r['source_repo'],info[0].path,repo_type='dataset',revision=r['source_revision']))
                result=record(r,p.read_bytes(),{'repo_id':r['source_repo'],'revision':r['source_revision'],'path':info[0].path},expected)
            else:
                result=dict(canonical_video_id=cid,status='RAW_CONFIG_DOWNLOAD_BINDING_NOT_ESTABLISHED',expected_sha256=expected,
                    declared_config=conf,server_path_is_not_public_download=bool(conf and conf.startswith('/')),
                    attempted_paths=candidates,parameter_facts_present=bool(r['parameter_facts']))
    except Exception as e:
        result=dict(canonical_video_id=r['canonical_video_id'],status='UNVERIFIED',error_type=type(e).__name__,error=str(e)[:200])
    results.append(result)
    (R/'CONFIG_CHECK.json').write_text(json.dumps(results,ensure_ascii=False,indent=2))
    print(json.dumps(result,ensure_ascii=False),flush=True)
