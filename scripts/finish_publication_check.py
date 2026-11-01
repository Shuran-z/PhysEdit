"""Finish the authorized audit/card delivery once the verified media copy completes."""
import json
from pathlib import Path
import subprocess
import sys
import tarfile
import time

REPO=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(REPO/'scripts'))
from boundary_ssh import remote_text

ROOT=REPO.parent/'release_72000_active/publication_audit_20261029'
REMOTE='/data_cached/wangzijun_p25/publication_audit_20261029'


def run(args):subprocess.run(args,check=True,cwd=REPO)


def status(phase):
    (ROOT/'delivery_status.json').write_text(json.dumps({'phase':phase,'updated':time.time()},indent=2))
    print(json.dumps({'phase':phase}),flush=True)


def main():
    status('WAITING_FOR_MEDIA_CONSOLIDATION')
    deadline=time.time()+7200
    while True:
        text=remote_text('p25',f"from pathlib import Path;p=Path('{REMOTE}/MEDIA_CONSOLIDATED.json');print(p.read_text() if p.exists() else 'PENDING')",timeout=20,attempts=1)
        if text.strip()!='PENDING':
            receipt=json.loads(text);assert receipt['all_destination_lfs_hashes_verified']
            (ROOT/'MEDIA_CONSOLIDATED.json').write_text(json.dumps(receipt,indent=2));break
        if time.time()>deadline:raise TimeoutError('Media consolidation did not finish within this execution window')
        time.sleep(20)
    status('FINALIZING_CATALOG_AND_REPORT')
    run([sys.executable,str(REPO/'scripts/finalize_publication_audit.py')])
    stage=ROOT/'metadata';package=ROOT/'audited_metadata.tar.gz'
    with tarfile.open(package,'w:gz') as tar:tar.add(stage,arcname='metadata')
    status('TRANSFERRING_AUDITED_METADATA')
    run(['scp',str(package),'p25:'+REMOTE+'/audited_metadata.tar.gz'])
    run(['scp',str(REPO/'scripts/publish_audited_dataset_card_remote.py'),'p25:'+REMOTE+'/publish_audited_dataset_card_remote.py'])
    run(['ssh','p25','tar','-xzf',REMOTE+'/audited_metadata.tar.gz','-C',REMOTE])
    wrapper=(REPO/'scripts/publish_author_release_remote.py').read_text(encoding='utf-8')
    wrapper=wrapper.replace("out = Path(__file__).resolve().parents[2] / 'release_72000_active'",
        "out = Path(__file__).resolve().parent / 'release_72000_active' / 'publication_audit_20261029'")
    wrapper=wrapper.replace('/author_release_20261029/upload.py','/publication_audit_20261029/publish_audited_dataset_card_remote.py')
    path=REPO.parent/'run_audited_card_upload_20261029.py';path.write_text(wrapper,encoding='utf-8')
    status('PUBLISHING_AND_VERIFYING_CARD')
    run([sys.executable,str(path)])
    run(['scp','p25:'+REMOTE+'/PUBLISHED.json',str(ROOT/'PUBLISHED.json')])
    published=json.loads((ROOT/'PUBLISHED.json').read_text())
    assert published['all_metadata_hashes_verified']
    catalog=json.loads((ROOT/'final_catalog_audit.json').read_text())
    pointer={'repo':published['repo'],'revision':published['revision'],'prefix':published['prefix'],
        'manifest':str((ROOT/'metadata'/published['prefix']/'videos.jsonl.gz').resolve()),
        'manifest_sha256':catalog['manifest_sha256'],'video_entries':72000,'usable_entries':32868,
        'current_media_records':69210,'review_directory_removed':True,'license_changed':False,'visibility_changed':False}
    (ROOT.parent/'ACTIVE_CATALOG.json').write_text(json.dumps(pointer,ensure_ascii=True,indent=2),encoding='utf-8')
    status('COMPLETE')
    print(json.dumps({k:v for k,v in published.items() if k!='files'}),flush=True)


if __name__=='__main__':main()
