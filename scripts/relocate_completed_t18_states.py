"""Move immutable owned state blobs without changing receipts or logical paths."""
import fcntl
import gzip
import hashlib
import json
import os
from pathlib import Path
import shutil


def relocate(source,target,receipt):
    source=Path(source);target=Path(target)
    if source.is_symlink():return False
    before=source.stat()
    target.parent.mkdir(parents=True,exist_ok=True)
    temp=target.with_name(target.name+'.copying')
    shutil.copyfile(source,temp)
    raw=temp.read_bytes()
    if hashlib.sha256(raw).hexdigest()!=receipt['stored_state_sha256'] or hashlib.sha256(gzip.decompress(raw)).hexdigest()!=receipt['state_sha256']:
        raise ValueError('relocation changed stored or uncompressed state')
    after=source.stat()
    if (before.st_ino,before.st_size,before.st_mtime_ns)!=(after.st_ino,after.st_size,after.st_mtime_ns):
        raise ValueError('source changed during relocation')
    temp.replace(target)
    link=source.with_name(source.name+'.relocating')
    link.symlink_to(target)
    os.replace(link,source)
    return True


def main():
    source=Path('/data_cached/wangzijun_p25/liyuhan/t18_table_contact_search_20261020').resolve()
    dest=Path('/data2/liyuhan_boundary_state_storage_20261023').resolve();dest.mkdir(exist_ok=True)
    lock=(dest/'relocation.lock').open('w');fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
    moved=0;count=0;journal=dest/'receipt.jsonl'
    for final in sorted(source.glob('*/*/result.json')):
        result=json.loads(final.read_text())
        if result.get('status')!='conditional_event_search_completed':continue
        for path in sorted(final.parent.glob('*/receipt.json')):
            receipt=json.loads(path.read_text());blob=Path(receipt['state_path'])
            if blob.is_symlink():continue
            if not blob.is_relative_to(source) or blob.resolve().parent!=path.parent.resolve():raise ValueError('blob outside owned job')
            if shutil.disk_usage(dest).free<26*1024**3:break
            target=dest/blob.relative_to(source)
            size=blob.stat().st_size
            if relocate(blob,target,receipt):
                moved+=size;count+=1
                with journal.open('a') as out:out.write(json.dumps(dict(source=str(blob),target=str(target),stored_state_sha256=receipt['stored_state_sha256'],state_sha256=receipt['state_sha256']))+'\n')
            if moved>=15*1024**3:break
        if moved>=15*1024**3:break
    summary=dict(files=count,moved_bytes=moved,source_free_GiB=shutil.disk_usage(source).free/1024**3,
                 target_free_GiB=shutil.disk_usage(dest).free/1024**3,logical_paths_and_receipts_unchanged=True)
    (dest/'summary.json').write_text(json.dumps(summary,indent=2));print(json.dumps(summary))


if __name__=='__main__':main()
