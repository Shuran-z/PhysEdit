"""Fresh colleague-style metadata and sample-video download audit."""
import collections
import csv
import gzip
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import zipfile
from huggingface_hub import HfApi, hf_hub_download

ROOT=Path('/data_cached/wangzijun_p25/colleague_download_check_20261031')
REPO='phy2/phydataset'

def digest(p):
    h=hashlib.sha256()
    with p.open('rb') as f:
        for b in iter(lambda:f.read(1024*1024),b''):h.update(b)
    return h.hexdigest()

def rows(p):
    with gzip.open(p,'rt',encoding='utf8') as f:
        yield from map(json.loads,f)

def main():
    ROOT.mkdir(exist_ok=True)
    revision=HfApi().repo_info(REPO,repo_type='dataset').sha
    path=hf_hub_download(REPO,'releases/physedit/downloads/physedit_metadata.zip',repo_type='dataset',revision=revision,local_dir=ROOT/'metadata_download')
    subprocess.run([sys.executable,'-m','zipfile','-e',path,str(ROOT)],check=True)
    d=ROOT/'physedit'
    checks=json.loads((d/'checks/FILES_SHA256.json').read_text())
    for check in checks['files']:
        assert digest(d/check['path'])==check['sha256'],check['path']
    criteria=[('genesis','T01','train_final'),('isaac','T01','train_final'),
        ('genesis','T03','ood_holdout'),('isaac','T11','ood_holdout'),
        ('genesis','T19','ood_holdout'),('isaac','T19','ood_holdout'),
        ('genesis','T12','protected_core100_reserve80_lineage'),('isaac','T20','ood_holdout')]
    selected={}
    for row in rows(d/'catalog/videos.jsonl.gz'):
        key=row['engine'],row['quota_scene'],row['split']
        if key in criteria and key not in selected:selected[key]=row
    assert len(selected)==len(criteria),(len(selected),criteria)
    split={r['canonical_video_id']:r for r in csv.DictReader((d/'catalog/split_assignments.csv').open(encoding='utf-8-sig'))}
    texts={r['sha256']:r['prompt'] for r in rows(d/'prompts/prompt_texts.jsonl.gz')}
    result=[]
    for key in criteria:
        r=selected[key]
        path=hf_hub_download(REPO,r['canonical_path'],repo_type='dataset',revision=revision,local_dir=ROOT/'dataset')
        assert digest(Path(path))==r['sha256']
        assert Path(path).stem==r['canonical_video_id']
        s=split[r['canonical_video_id']]
        assert all(s[k]==r[k] for k in ['split','source_group_id','sha256'])
        assert len(r['prompt_variants_en'])==3 and r['prompt_en']==r['prompt_variants_en'][0]
        for text,h in zip(r['prompt_variants_en'],r['prompt_variant_sha256']):
            assert hashlib.sha256(text.encode()).hexdigest()==h and texts[h]==text
        probe=subprocess.run(['ffprobe','-v','error','-show_entries','stream=codec_name,width,height,nb_frames','-show_entries','format=duration','-of','json',path],check=True,capture_output=True,text=True)
        subprocess.run(['ffmpeg','-v','error','-i',path,'-f','null','-'],check=True,capture_output=True)
        result.append(dict(engine=r['engine'],scene=r['quota_scene'],canonical_video_id=r['canonical_video_id'],
            split=r['split'],source_group_id=r['source_group_id'],sha256=r['sha256'],video_download_and_full_decode=True,
            prompts_and_split_match=True,media=json.loads(probe.stdout),
            configuration_fields={k:v for k,v in r.items() if any(w in k for w in ['config','physical','source','parameter','archive','binding'])}))
    (ROOT/'SAMPLE_ROWS.json').write_text(json.dumps([selected[k] for k in criteria],ensure_ascii=False,indent=2))
    (ROOT/'DOWNLOAD_CHECK.json').write_text(json.dumps(dict(revision=revision,metadata_files_verified=len(checks['files']),samples=result),ensure_ascii=False,indent=2))
    print(json.dumps(dict(revision=revision,samples=len(result),metadata_files_verified=len(checks['files']),status='VIDEO_PROMPT_SPLIT_PASS_CONFIG_PENDING')),flush=True)

if __name__=='__main__':main()
