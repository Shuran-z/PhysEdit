"""Refresh the active inventory while remote rendering/audits progress."""
import datetime
import json
import subprocess
import sys
import time
from pathlib import Path

repo=Path(__file__).resolve().parents[1]
out=repo.parent/'release_72000_active'
out.mkdir(exist_ok=True)
# Hold an OS lock for the process lifetime; stale files do not block recovery.
lock = (out/'watcher.lock').open('a+b')
if sys.platform == 'win32':
    import msvcrt
    lock.seek(0)
    if not lock.read(1):
        lock.write(b'0'); lock.flush()
    lock.seek(0)
    msvcrt.locking(lock.fileno(), msvcrt.LK_NBLCK, 1)
else:
    import fcntl
    fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
while True:
    try:
        p=subprocess.run([sys.executable,str(repo/'scripts/refresh_72000_inventory.py')],
                         capture_output=True,timeout=600)
    except (subprocess.TimeoutExpired, OSError) as exc:
        with (out/'refresh_log.jsonl').open('a',encoding='utf8') as f:
            f.write(json.dumps(dict(utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),
                returncode=None,error=str(exc),retry_after_seconds=300))+'\n')
        time.sleep(300)
        continue
    with (out/'refresh_log.jsonl').open('a',encoding='utf8') as f:
        f.write(json.dumps(dict(utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),
            returncode=p.returncode,output=p.stdout.decode(errors='replace')[-4000:],
            error=p.stderr.decode(errors='replace')[-2000:]))+'\n')
    if p.returncode==0:
        ptr=json.loads((out/'ACTIVE.json').read_text(encoding='utf8'))
        summary=json.loads(Path(ptr['summary']).read_text(encoding='utf8'))
        audited=sum(summary['supplementary_integrity_counts'].values())
        if summary['media_inventory_complete'] and audited==651:
            (out/'RENDER_AND_INTEGRITY_COMPLETE_REVIEW_PENDING.json').write_text(json.dumps(dict(
                summary=ptr['summary'],physical_visual_acceptance=False,
                next_step='Review sheets, resolve quality failures and retired T19; bind new prompts.'),indent=2))
            break
    time.sleep(300)
