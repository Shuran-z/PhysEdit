"""Copy only requested config files after validating their registered raw hashes."""
import hashlib,json,tarfile,io,os
from pathlib import Path
R=Path(os.environ.get('CONFIG_RECOVERY_DIR','/tmp/physedit_config_recovery_20261031'))
R.mkdir(exist_ok=True)
requests=json.loads((R/'REQUESTS.json').read_text())
result=[];done=set()
with tarfile.open(R/'configs.tar','w') as tar:
    for r in requests:
        expected=r['expected_sha256'];paths=r['local_paths'];found=None
        for path in paths:
            p=Path(path)
            if not p.is_file():continue
            raw=p.read_bytes();h=hashlib.sha256(raw).hexdigest()
            if h!=expected:continue
            json.loads(raw);found=dict(canonical_video_id=r['canonical_video_id'],sha256=h,path=path)
            if h not in done:
                item=tarfile.TarInfo(h+'.json');item.size=len(raw);tar.addfile(item,io.BytesIO(raw));done.add(h)
            break
        result.append(found or dict(canonical_video_id=r['canonical_video_id'],status='MISSING_OR_HASH_MISMATCH'))
(R/'RESULT.json').write_text(json.dumps(result,indent=2))
print(json.dumps(dict(requests=len(requests),recovered=sum('sha256' in r for r in result),unique_files=len(done))))
