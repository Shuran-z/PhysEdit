"""Losslessly archive only completed generated search states, never source media.

Required for long searches on a finite cache disk. Raw SHA256 stays unchanged;
the compressed SHA256 is separate. Active job folders are left untouched.
"""
import argparse
import gzip
import hashlib
import json
from pathlib import Path
import time


def atomic(path,value):
    temp=path.with_suffix('.compress.tmp');temp.write_text(json.dumps(value,indent=2));temp.replace(path)


def compress_job(folder,root):
    result=folder/'result.json'
    if not result.exists():return (0,0,0)
    row=json.loads(result.read_text());receipts={};removed=stored=files=0
    for path in folder.glob('*/receipt.json'):
        receipt=json.loads(path.read_text());source=path.parent/'physics.json'
        if source.exists():
            if root.resolve() not in source.resolve().parents:raise ValueError('generated state outside task root')
            raw=source.read_bytes()
            if hashlib.sha256(raw).hexdigest()!=receipt['state_sha256']:raise ValueError('state checksum changed')
            compressed=gzip.compress(raw,compresslevel=3,mtime=0);dest=source.with_suffix('.json.gz');dest.write_bytes(compressed)
            if hashlib.sha256(gzip.decompress(dest.read_bytes())).hexdigest()!=receipt['state_sha256']:raise ValueError('compression was not lossless')
            receipt.update(state_path=str(dest),stored_state_sha256=hashlib.sha256(compressed).hexdigest());atomic(path,receipt)
            removed+=len(raw);stored+=len(compressed);files+=1;source.unlink()
        receipts[receipt['theta']]=receipt
    updated=[receipts[p['theta']] for p in row['probes']]
    if files or row['probes']!=updated:
        row['probes']=updated
        row['storage_format']='lossless_gzip_generated_numeric_states';atomic(result,row)
    return files,removed,stored


def main():
    p=argparse.ArgumentParser();p.add_argument('--roots',nargs='+',required=True);p.add_argument('--wait-pids',nargs='*',type=int,default=[]);p.add_argument('--status',required=True);args=p.parse_args()
    roots=[Path(p) for p in args.roots];counts=[0,0,0]
    while True:
        for root in roots:
            for folder in root.iterdir():
                if not folder.is_dir():continue
                added=compress_job(folder,root);counts=[a+b for a,b in zip(counts,added)]
        atomic(Path(args.status),dict(compressed_files=counts[0],raw_bytes=counts[1],stored_bytes=counts[2],
                                      original_source_media_untouched=True))
        if not any(Path('/proc').joinpath(str(pid),'cmdline').exists() for pid in args.wait_pids):break
        time.sleep(30)


if __name__=='__main__':main()
