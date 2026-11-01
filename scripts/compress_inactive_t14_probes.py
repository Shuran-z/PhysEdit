"""Lossless storage recovery for completed generated probes, not source media."""
import concurrent.futures,fcntl,gzip,hashlib,json,os,shutil
from pathlib import Path

ROOT=Path('/data_cached/wangzijun_p25/liyuhan/t14_formal_all_contexts_20261019')
def main():
    assert ROOT.resolve()==ROOT and ROOT.is_dir()
    guard=(ROOT/'compression_20261030.lock').open('a');fcntl.flock(guard,fcntl.LOCK_EX|fcntl.LOCK_NB)
    worker=(ROOT/'worker.lock').open('a');fcntl.flock(worker,fcntl.LOCK_EX|fcntl.LOCK_NB)
    for p in Path('/proc').glob('[0-9]*/cmdline'):
        try:
            cmd=p.read_bytes()
            if b'--root' in cmd and (str(ROOT)+'\0').encode() in cmd:raise RuntimeError('T14 worker still active')
        except (OSError,ProcessLookupError):pass
    states=[]
    for folder in ROOT.iterdir():
        result=folder/'result.json'
        if not result.is_file() or json.loads(result.read_text()).get('status')!='scanned_original_triplet':continue
        states.extend(folder.glob('*/physics.json'))
    before=shutil.disk_usage(ROOT).free
    def compress(source):
        assert ROOT in source.resolve().parents and not source.is_symlink()
        receipt=json.loads(source.with_name('receipt.json').read_text());raw=source.read_bytes()
        digest=hashlib.sha256(raw).hexdigest();assert digest==receipt['state_sha256']
        dest=source.with_suffix('.json.gz');temp=dest.with_suffix('.gz.tmp')
        compressed=gzip.compress(raw,compresslevel=3,mtime=0)
        temp.write_bytes(compressed);assert hashlib.sha256(gzip.decompress(temp.read_bytes())).hexdigest()==digest
        temp.replace(dest)
        assert hashlib.sha256(source.read_bytes()).hexdigest()==digest
        record={'source':str(source),'raw_sha256':digest,'raw_bytes':len(raw),'stored_path':str(dest),'stored_sha256':hashlib.sha256(compressed).hexdigest(),'stored_bytes':len(compressed),'lossless_verified':True}
        source.with_suffix('.storage.json').write_text(json.dumps(record))
        source.unlink() # Verified identical bytes remain recoverable from the sibling gzip.
        return record
    records=[]
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
        for r in pool.map(compress,states):
            records.append(r)
            if len(records)%100==0:print(json.dumps({'compressed':len(records),'total':len(states),'free_GiB':shutil.disk_usage(ROOT).free/1024**3}),flush=True)
    report={'files':len(records),'free_before':before,'free_after':shutil.disk_usage(ROOT).free,'reclaimed_bytes':sum(r['raw_bytes']-r['stored_bytes'] for r in records),'source_media_changed':False,'records':records}
    (ROOT/'compression_20261030.json').write_text(json.dumps(report,indent=2))
    print(json.dumps({k:v for k,v in report.items() if k!='records'}),flush=True)
if __name__=='__main__':main()
