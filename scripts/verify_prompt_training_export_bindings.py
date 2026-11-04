"""Check that the training consumer view contains the exact audited records."""
from pathlib import Path
import gzip,hashlib,json,sys
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from physedit.prompt_contract import parameter_facts_sha
OUT=ROOT/'review/full_prompt_audit_20261102/audited_release'

def fingerprint(r):
    actual=[hashlib.sha256(t.encode()).hexdigest() for t in r['prompt_variants_en']]
    assert actual==r['prompt_variant_sha256']
    facts=parameter_facts_sha(r['parameter_facts']);assert facts==r['parameter_facts_sha256']
    return {'prompts':actual,'facts':facts,'video_sha256':r['sha256'],'download':r['download'],'source_group_id':r['source_group_id']}

def main():
    expected={};count=0
    for line in gzip.open(OUT/'videos.jsonl.gz','rt',encoding='utf8'):
        r=json.loads(line);count+=1
        if r['split']=='train_final':expected[r['canonical_video_id']]=fingerprint(r)
    observed=set()
    for line in gzip.open(OUT/'train_final_candidates.jsonl.gz','rt',encoding='utf8'):
        r=json.loads(line);vid=r['canonical_video_id'];assert vid not in observed and r['split']=='train_final';observed.add(vid)
        assert expected[vid]==fingerprint(r),(vid,'stale_training_export')
    assert observed==set(expected) and len(observed)==45357 and count==72000
    result={'status':'passed','catalog_rows':count,'training_rows_verified':len(observed),'prompt_fact_media_group_bindings_match':True,
            'training_manifest_sha256':hashlib.sha256((OUT/'train_final_candidates.jsonl.gz').read_bytes()).hexdigest()}
    (OUT/'TRAIN_BINDING_VERIFICATION.json').write_text(json.dumps(result,indent=2),encoding='utf8');print(json.dumps(result))

if __name__=='__main__':main()
