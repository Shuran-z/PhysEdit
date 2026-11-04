"""Correct dimensionally invalid units on counts, frame indices and booleans."""
from pathlib import Path
import collections,copy,gzip,hashlib,json,re,sys
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from scripts import full_prompt_config_audit as audit
from scripts.repair_and_verify_all_prompts import pieces,fact_patterns,match_fact,texts_hash,numeric_value
from physedit.compact_prompt import sentence,counts,MODEL_BUDGETS
from physedit.prompt_contract import parameter_facts_sha
BASE=audit.OUT/'final';OUT=audit.OUT/'audited_release';OUT.mkdir(exist_ok=True)

def typed_unit(key,value,old):
    if isinstance(value,bool):return ''
    if key.endswith('_count'):return ''
    if key.endswith('_frame_range'):return 'frame index'
    if key.endswith('_frames'):return 'frames'
    return old

def main():
    stats=collections.Counter()
    with gzip.open(BASE/'videos.jsonl.gz','rt',encoding='utf8') as src,gzip.open(OUT/'videos.jsonl.gz','wt',encoding='utf8',compresslevel=1) as dst,gzip.open(OUT/'train_final_candidates.jsonl.gz','wt',encoding='utf8',compresslevel=1) as train,gzip.open(OUT/'UNIT_CHANGES.jsonl.gz','wt',encoding='utf8',compresslevel=1) as changes:
        for line in src:
            r=json.loads(line);original=copy.deepcopy(r);edits=[];before=[]
            for f in r['parameter_facts']:
                expected=typed_unit(f[0],f[-2],f[-1])
                if expected!=f[-1]:
                    before.append(copy.deepcopy(f));edits.append({'key':f[0],'old_unit':f[-1],'new_unit':expected,'reason':'boolean/count/frame type has no force or impulse dimension'});f[-1]=expected
            old_patterns=fact_patterns(before);bykey={f[0]:f for f in r['parameter_facts']};texts=[];shortened=False
            for text in r['prompt_variants_en']:
                    def compact(m):
                        nonlocal shortened
                        assert any(p['replacement']==m[0] for p in r['full_numeric_audit']['supplemental_clauses'])
                        shortened=True;return f'Book {m[1]} kinematic; {m[2]} books.'
                    text=re.sub(r'Book (\d+) stays kinematic; the stack has (\d+) books\.',compact,text)
                    clauses=[]
                    for cl in pieces(text):
                        match=match_fact(cl,old_patterns)
                        if match:
                            f=bykey[match[0]];assert audit.equal(match[1],match[2]);cl=sentence(f[0],f[-2],f[-1]);stats['text_unit_clauses_corrected']+=1
                        clauses.append(cl)
                    texts.append(' '.join(clauses))
            if any(any(counts(t)[m]>v for m,v in MODEL_BUDGETS.items()) for t in texts):
                proof=next(p for p in r['full_numeric_audit']['supplemental_clauses'] if p['kind']=='static_frames_and_media_rate')
                m=re.fullmatch(r'(\d+) static frames; ([\d.]+) fps\.',proof['replacement']);assert m
                hold=next(s for s in r['prompt_revision']['source_control_clauses'] if s.startswith('Hold initially for '))
                hm=re.fullmatch(r'Hold initially for (.+) s\.',hold);assert hm
                assert audit.equal(int(m[1])/float(m[2]),numeric_value(hm[1]))
                assert all(proof['replacement'] in text for text in texts)
                texts=[' '.join(pieces(t.replace(proof['replacement'],' '))) for t in texts]
                r['full_numeric_audit']['redundant_time_clause_moved_to_metadata']={'pre_static_frames':int(m[1]),'media_fps':float(m[2]),'equivalent_hold_clause':hold}
                stats['redundant_time_rows_compacted_without_input_loss']+=1
            if edits or texts!=r['prompt_variants_en']:
                r['prompt_variants_en']=texts;r['prompt_en']=texts[0];r['prompt_variant_sha256']=texts_hash(texts);r['prompt_sha256']=r['prompt_variant_sha256'][0]
                r['prompt_variant_token_counts']=[counts(t) for t in texts];r['prompt_token_counts']=counts(texts[0]);r['parameter_facts_sha256']=parameter_facts_sha(r['parameter_facts'])
                r['full_numeric_audit']['unit_corrections']=edits
                if shortened:
                    for proof in r['full_numeric_audit']['supplemental_clauses']:
                        proof['replacement']=re.sub(r'Book (\d+) stays kinematic; the stack has (\d+) books\.',lambda m:f'Book {m[1]} kinematic; {m[2]} books.',proof['replacement'])
                    stats['kinematic_rows_shortened_without_input_loss']+=1
                changes.write(json.dumps({'video_id':r['canonical_video_id'],'changes':edits,'kinematic_identity_shortened':shortened,'old_prompt_hashes':original['prompt_variant_sha256'],'new_prompt_hashes':r['prompt_variant_sha256']},ensure_ascii=False)+'\n')
                if edits:stats['unit_corrected_rows']+=1;stats['unit_fields_corrected']+=len(edits)
            for text in r['prompt_variants_en']:assert all(counts(text)[m]<=v for m,v in MODEL_BUDGETS.items()),(r['canonical_video_id'],counts(text))
            r['full_numeric_audit']['issues']=[i for i in r['full_numeric_audit']['issues'] if i['kind']!='over_token_budget']
            r['full_numeric_audit']['status']='needs_review' if r['full_numeric_audit']['issues'] else 'verified'
            r['prompt_revision']['issues']=[i for i in r['prompt_revision']['issues'] if i!='over_token_budget']
            r['prompt_revision']['status']='needs_review' if r['prompt_revision']['issues'] else 'revised'
            for k in ['sha256','download','split','source_group_id']:assert original.get(k)==r.get(k)
            encoded=json.dumps(r,ensure_ascii=False)+'\n';dst.write(encoded);stats['videos']+=1
            if r['split']=='train_final':train.write(encoded);stats['train_final_candidates']+=1
    assert stats['videos']==72000 and stats['train_final_candidates']==45357
    (OUT/'UNIT_REPORT.json').write_text(json.dumps(dict(stats),indent=2),encoding='utf8');print(json.dumps(dict(stats)))

if __name__=='__main__':main()
