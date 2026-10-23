"""Move owned T12 queues while preserving plans, caches and runtime environments."""
import argparse
import json
from scripts.boundary_ssh import remote_text
from scripts.export_original_boundary_distances import ROOT


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--move', nargs=2, type=int, action='append', metavar=('QUEUE', 'GPU'))
    parser.add_argument('--receipt', default='t12_gpu_redistribution_20261022.json')
    args = parser.parse_args()
    if '/' in args.receipt or '\\' in args.receipt:
        parser.error('receipt must be a filename')
    marker = ROOT / args.receipt
    previous = json.loads(marker.read_text()) if marker.exists() else []
    primary = ROOT / 't12_remaining_grid_launch_20261022.json'
    launches = json.loads(primary.read_text())
    requested = args.move or [(0, 0), (5, 5)]
    if any(not 0 <= i < len(launches) or not -1 <= gpu < 6 for i, gpu in requested):
        parser.error('invalid queue or GPU index')
    moves = [(i, gpu, f't12_remaining_grid_{i}_launch_20261022.json' if i < 2
              else f't12_remaining_grid_p26_{i-2}_launch_20261022.json') for i, gpu in requested]
    records = list(previous)
    for index, gpu, name in moves:
        old = launches[index]
        if any(r['root'] == old['root'] for r in records):
            continue
        code = r'''
import pathlib,json,os,signal,subprocess,time,hashlib
l=LAUNCH;gpu=GPU;root=pathlib.Path(l['root']);proc=pathlib.Path('/proc')/str(l['pid'])
if gpu == -1:
 cards=[tuple(map(int,line.split(','))) for line in subprocess.check_output(['nvidia-smi','--query-gpu=index,memory.free','--format=csv,noheader,nounits']).decode().splitlines()]
 gpu=max((row for row in cards if row[0]!=l['gpu']),key=lambda row:row[1])[0]
argv=[v.decode() for v in (proc/'cmdline').read_bytes().split(b'\0') if v]
if l['root'] not in argv or l['active_plan'] not in argv or os.getpgid(l['pid'])!=l['pid']:
 raise ValueError('owned worker identity changed')
worker=pathlib.Path(argv[1]);plan=pathlib.Path(l['active_plan'])
if hashlib.sha256(worker.read_bytes()).hexdigest()!=l['worker_sha256'] or hashlib.sha256(plan.read_bytes()).hexdigest()!=l['active_plan_sha256']:
 raise ValueError('worker or plan provenance changed')
if float(subprocess.check_output(['nvidia-smi','-i',str(gpu),'--query-gpu=memory.free','--format=csv,noheader,nounits']).decode())<8192:
 raise ValueError('destination GPU no longer available')
env=dict(v.decode().split('=',1) for v in (proc/'environ').read_bytes().split(b'\0') if v)
cwd=os.readlink(proc/'cwd')
status=root/'status.json'
if status.exists():(root/'status_before_gpu_redistribution_20261022.json').write_bytes(status.read_bytes())
os.killpg(l['pid'],signal.SIGTERM)
for _ in range(150):
 if not subprocess.run(['pgrep','-g',str(l['pid'])],capture_output=True).stdout:break
 time.sleep(.1)
else:raise RuntimeError('owned worker group did not stop')
argv[argv.index('--gpu')+1]=str(gpu)
with (root/'redistributed_worker_20261022.log').open('w') as log:
 p=subprocess.Popen(argv,cwd=cwd,env=env,stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
time.sleep(2)
if p.poll() is not None:raise RuntimeError('replacement worker exited; inspect preserved log')
out=dict(l,previous_pid=l['pid'],previous_gpu=l['gpu'],pid=p.pid,gpu=gpu,
 relocation='same host, plan, source, runtime environment and cached completed probes')
(root/'gpu_redistribution_receipt_20261022.json').write_text(json.dumps(out,indent=2))
print(json.dumps(out))
'''.replace('LAUNCH', repr(old)).replace('GPU', repr(gpu))
        python = '/home/wangzijun_p25/miniconda3/envs/genesis/bin/python' if old['host'] == 'p26' else 'python3'
        result = json.loads(remote_text(old['host'], code, timeout=60, attempts=1, python=python))
        launches[index] = result
        (ROOT / name).write_text(json.dumps(result, indent=2))
        primary.write_text(json.dumps(launches, indent=2))
        records.append(result)
        marker.write_text(json.dumps(records, indent=2))
        print(json.dumps(dict(host=result['host'], gpu=result['gpu'], pid=result['pid'])))


if __name__ == '__main__':
    main()
