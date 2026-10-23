"""Run one bounded command when a GPU has sufficient free memory."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import time


def choose_gpu(csv, minimum):
    cards = [tuple(map(int, row.split(','))) for row in csv.splitlines() if row.strip()]
    available = [(index, free) for index, free in cards if free >= minimum]
    return max(available, key=lambda row: row[1])[0] if available else None


def save(path, data):
    temp = path.with_suffix('.tmp')
    temp.write_text(json.dumps(data, indent=2))
    temp.replace(path)


def main():
    import fcntl
    parser = argparse.ArgumentParser()
    parser.add_argument('--manifest', required=True)
    args = parser.parse_args()
    manifest = json.loads(Path(args.manifest).read_text())
    root = Path(manifest['root'])
    root.mkdir(parents=True, exist_ok=True)
    lock = (root / 'gpu_wait_supervisor.lock').open('w')
    fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    argv = manifest['argv']
    if not isinstance(argv, list) or argv.count('{GPU}') != 1:
        raise ValueError('command needs exactly one GPU argument placeholder')
    deadline = time.monotonic() + manifest.get('hours', 336) * 3600
    while time.monotonic() < deadline:
        for name, digest in manifest['source_sha256'].items():
            if hashlib.sha256(Path(name).read_bytes()).hexdigest() != digest:
                raise ValueError('queued source/plan changed: ' + name)
        csv = subprocess.check_output(['nvidia-smi', '--query-gpu=index,memory.free',
                                       '--format=csv,noheader,nounits']).decode()
        gpu = choose_gpu(csv, manifest['minimum_free_memory_mib'])
        if gpu is None:
            save(root / 'resource_status.json', dict(status='waiting_for_memory', gpu='auto',
                 minimum_free_memory_mib=manifest['minimum_free_memory_mib'], checked_at=time.time()))
            time.sleep(20)
            continue
        command = [str(gpu) if value == '{GPU}' else value for value in argv]
        with (root / 'scheduled_worker.log').open('a') as log:
            child = subprocess.Popen(command, stdout=log, stderr=subprocess.STDOUT)
            save(root / 'gpu_wait_supervisor_status.json', dict(status='worker_started',
                 gpu=gpu, child_pid=child.pid, started_at=time.time()))
            code = child.wait()
        save(root / 'gpu_wait_supervisor_status.json', dict(status='worker_ended',
             gpu=gpu, child_pid=child.pid, returncode=code, ended_at=time.time()))
        raise SystemExit(code)
    save(root / 'gpu_wait_supervisor_status.json', dict(status='memory_wait_deadline_expired'))


if __name__ == '__main__':
    main()
