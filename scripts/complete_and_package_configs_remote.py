"""Finish source recovery and package exact config bytes plus per-video bindings."""
import collections,gzip,hashlib,json,tarfile,zipfile
from pathlib import Path
from huggingface_hub import hf_hub_download

R=Path('/data_cached/wangzijun_p25/config_bindings_20261031')
B=Path('/data2/wangzijun_p25/phy2_standardization_20261027/phy2_release_v1.0.0_rc1')
def sha(raw):return hashlib.sha256(raw).hexdigest()
def load(p):
    with gzip.open(p,'rt') as f:return list(map(json.loads,f))
def main():
    tasks=load(R/'TASKS.jsonl.gz');rec={r['canonical_video_id']:r for r in load(R/'RECOVERED_LOCAL.jsonl.gz')}
    blobs=R/'raw';blobs.mkdir(exist_ok=True)
    def save(raw,expected=None):
        h=sha(raw)
        if expected:assert h==expected
        json.loads(raw)
        p=blobs/(h+'.json')
        if not p.exists():p.write_bytes(raw)
        else:assert sha(p.read_bytes())==h
        return h
    if (R/'RESULT.json').exists():
        with tarfile.open(R/'configs.tar') as tar:
            for item in tar:
                if item.isfile():save(tar.extractfile(item).read(),Path(item.name).stem)
        for item in json.loads((R/'RESULT.json').read_text()):
            if item.get('sha256'):
                rec[item['canonical_video_id']]=dict(canonical_video_id=item['canonical_video_id'],status='RECOVERED',sha256=item['sha256'],local_path=str(blobs/(item['sha256']+'.json')),method='registered_config_sha256_recovered_on_p29')
    # Restore Isaac T19 via the independently audited media-replacement registry.
    verified=json.loads(Path('/data_cached/wangzijun_p25/t19_existing_replacement_20261030/VERIFIED_REPLACEMENTS.json').read_text())
    byid={v['canonical_video_id']:v for v in verified}
    supplement=Path('/data_cached/wangzijun_p25/author_release_20261029/metadata/supplement_prompt_input_bindings.jsonl.gz')
    with gzip.open(supplement,'rt') as f:
        input_bindings={x['video_sha256']:x for x in map(json.loads,f)}
    for t in tasks:
        if rec[t['canonical_video_id']]['status']=='RECOVERED':continue
        original=input_bindings.get(t['video_sha256'])
        if not original or original.get('sample_id')!=t['native_sample_id'] or original.get('camera')!=t['camera']:continue
        declared=[x for x in original.get('runtime_config_binding',[]) if x.get('camera')==t['camera']]
        for source in declared:
            p=Path(source['source'])
            if not p.is_file():continue
            h=save(p.read_bytes(),source['source_sha256'])
            if t['expected_sha256'] and h!=t['expected_sha256']:continue
            rec[t['canonical_video_id']]=dict(canonical_video_id=t['canonical_video_id'],status='RECOVERED',sha256=h,local_path=str(p),method='frozen_supplement_video_hash_and_source_config_sha256')
            break
    for t in tasks:
        old=rec[t['canonical_video_id']]
        if old['status']=='RECOVERED':continue
        current=t['current_render']
        if current:
            job=current['config_member'].split('/')[0]
            p=Path('/data2/wangzijun_p25/resample_training_duplicates_20261030/normalized_configs')/job/Path(current['config_member']).name
            if p.is_file():
                raw=p.read_bytes();h=save(raw,t['expected_sha256'])
                rec[t['canonical_video_id']]=dict(canonical_video_id=t['canonical_video_id'],status='RECOVERED',sha256=h,local_path=str(p),method='registered_current_bundle_config_raw_sha256')
                continue
        v=byid.get(t['canonical_video_id'])
        if v and v['sha256']==t['video_sha256']:
            raw=Path(v['config_source']).read_bytes();h=save(raw,v['config_sha256'])
            if t['expected_sha256']:assert h==t['expected_sha256']
            rec[t['canonical_video_id']]=dict(canonical_video_id=t['canonical_video_id'],status='RECOVERED',sha256=h,local_path=v['config_source'],method='same_config_bytes_verified_by_current_media_replacement')
    # The original 44-point Isaac delivery records bind config and video hashes independently.
    legacy=Path('/data2/wangzijun_p25/phy2_standardization_20261027/isaac_960_resolved_v2')
    samples={}
    for line in (legacy/'all_3520_mappings.jsonl').open():
        x=json.loads(line);samples[x['scene'],x['sample_id']]=x
    video_sources={}
    for scene in ['T16','T17','T18','T19']:
        for line in (legacy/(scene.lower()+'_960_videos.jsonl')).open():
            x=json.loads(line);video_sources[scene,x['sample_id'],x['camera']]=x
    for t in tasks:
        if rec[t['canonical_video_id']]['status']=='RECOVERED' or t['engine']!='isaac':continue
        x=samples.get((t['scene'],t['native_sample_id']));v=video_sources.get((t['scene'],t['native_sample_id'],t['camera']))
        if not x or not v or v['expected_sha256']!=t['video_sha256']:continue
        if not x.get('config_hash_match') or not x.get('metadata_hash_match'):continue
        p=Path(x['local_sample_path'])/'config.json'
        if p.is_file():
            h=save(p.read_bytes(),x['config_sha256'])
            rec[t['canonical_video_id']]=dict(canonical_video_id=t['canonical_video_id'],status='RECOVERED',sha256=h,local_path=str(p),method='original_isaac_delivery_video_hash_and_registered_config_hash')
    # Recover T13 original config members at their registered immutable revisions.
    inline=Path('/data_cached/wangzijun_p25/colleague_download_check_20261031/physedit/provenance/t13_backgroundfix_20261030/source_configs.jsonl.gz')
    reconstructed={}
    with gzip.open(inline,'rt') as f:
        for x in map(json.loads,f):
            expected=x['source_config_sha256']
            for indent in [2,4,None]:
                for ascii_only in [False,True]:
                    for ending in ['', '\n']:
                        raw=(json.dumps(x['config'],ensure_ascii=ascii_only,indent=indent)+ending).encode()
                        if sha(raw)==expected:
                            h=save(raw,expected);reconstructed[h]=str(blobs/(h+'.json'))
    for t in tasks:
        h=t['expected_sha256']
        if rec[t['canonical_video_id']]['status']!='RECOVERED' and h in reconstructed:
            rec[t['canonical_video_id']]=dict(canonical_video_id=t['canonical_video_id'],status='RECOVERED',sha256=h,local_path=reconstructed[h],method='lossless_inline_config_original_raw_sha256_match')
    archives=collections.defaultdict(list)
    for t in tasks:
        if rec[t['canonical_video_id']]['status']=='RECOVERED':continue
        e=t['evidence'].get('config_evidence') or {}
        if e.get('archive_path') and e.get('member'):
            archives[e.get('repo_id','phy2/phydataset'),e['revision'],e['archive_path']].append((t,e))
    for (repo,rev,path),items in archives.items():
        local=Path(hf_hub_download(repo,path,repo_type='dataset',revision=rev))
        members=collections.defaultdict(list)
        for t,e in items:members[e['member']].append(t)
        with tarfile.open(local,'r|gz') as tar:
            for member in tar:
                if member.name not in members:continue
                assert member.isfile();raw=tar.extractfile(member).read()
                for t in members.pop(member.name):
                    h=save(raw,t['expected_sha256'])
                    rec[t['canonical_video_id']]=dict(canonical_video_id=t['canonical_video_id'],status='RECOVERED',sha256=h,local_path=str(blobs/(h+'.json')),method='registered_archive_member_and_raw_sha256')
                if not members:break
        assert not members,list(members)[:3]
        print(json.dumps({'recovered_archive':path,'video_bindings':len(items)}),flush=True)
    # Materialize only verified original bytes. Do not serialize parameter tables as configs.
    counts=collections.Counter();missing=[];bindings=[];stored=set()
    previous_missing={x['canonical_video_id']:x for x in json.loads((R/'LOCAL_UNRESOLVED.json').read_text())}
    archive=R/'configs.zip'
    with zipfile.ZipFile(archive,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=6) as z:
        for t in tasks:
            x=rec[t['canonical_video_id']]
            if x['status']=='RECOVERED':
                if x.get('artifact'):
                    a=x['artifact'];packed=(B/a['path']).read_bytes();assert sha(packed)==a['sha256']
                    raw=gzip.decompress(packed) if a['storage_transform']=='gzip_lossless' else packed
                else:
                    raw=Path(x['local_path']).read_bytes()
                    if x['local_path'].endswith('.gz'):raw=gzip.decompress(raw)
                h=sha(raw);assert h==x['sha256'],(t['canonical_video_id'],h,x['sha256']);json.loads(raw)
                member='configs/'+h+'.json'
                if h not in stored:z.writestr(member,raw);stored.add(h)
                binding=dict(canonical_video_id=t['canonical_video_id'],video_sha256=t['video_sha256'],
                    engine=t['engine'],scene=t['scene'],status='VERIFIED',config_sha256=h,
                    archive_member=member,method=x['method'])
            else:
                detail=previous_missing.get(t['canonical_video_id'],{})
                if detail.get('matching_hashes',0)>1:reason='Multiple compatible source config files; original byte version is ambiguous'
                elif t['expected_sha256']:reason='Registered original config bytes not recovered'
                elif detail.get('config_candidates',0)>0:reason='Candidate files exist but exact source input linkage is not verified'
                else:reason='Original config file source not located'
                binding=dict(canonical_video_id=t['canonical_video_id'],video_sha256=t['video_sha256'],engine=t['engine'],
                    scene=t['scene'],status='UNRESOLVED',expected_sha256=t['expected_sha256'],reason=reason)
                missing.append(dict(binding,declared_config=t['declared_config'],evidence=t['evidence'],candidate_summary=detail))
            counts[binding['status']]+=1;bindings.append(binding)
    with zipfile.ZipFile(archive) as z:
        assert z.testzip() is None
        for h in stored:assert sha(z.read('configs/'+h+'.json'))==h
    with gzip.open(R/'config_bindings.jsonl.gz','wt') as f:
        for b in bindings:f.write(json.dumps(b)+'\n')
    with gzip.open(R/'unresolved_configs.jsonl.gz','wt') as f:
        for m in missing:f.write(json.dumps(m)+'\n')
    with gzip.open(R/'FINAL_RECOVERIES.jsonl.gz','wt') as f:
        for t in tasks:f.write(json.dumps(rec[t['canonical_video_id']])+'\n')
    sample_ids=['physedit_genesis_t03_7b11b86fe8ac0134__cam01','physedit_isaac_t11_a4ea4e89bd9981be__cam01','physedit_isaac_t19_0987dd87acd0c6d0__cam01','physedit_isaac_t20_48df634f70618cca__cam01']
    assert all(rec[cid]['status']=='RECOVERED' for cid in sample_ids)
    summary=dict(total=len(tasks),counts=dict(counts),unique_configs=len(stored),zip_sha256=sha(archive.read_bytes()),zip_bytes=archive.stat().st_size,
        all_four_sample_gaps_recovered=True,by_scene=[dict(engine=e,scene=s,status=k,videos=n) for (e,s,k),n in sorted(collections.Counter((b['engine'],b['scene'],b['status']) for b in bindings).items())])
    (R/'PACKAGE.json').write_text(json.dumps(summary,indent=2));print(json.dumps(summary),flush=True)

if __name__=='__main__':main()
