"""Install the hash-checked numerical supplement in an isolated p25 runtime."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import zipfile

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
from boundary_ssh import remote_text, transport_options


def main():
    folder=ROOT/'review/core100_binding_20261028/runtime_delivery'
    folder.mkdir(exist_ok=True)
    # A follower and a manual retry must not write the same archive together.
    guard=(folder/'delivery.lock').open('a+b');guard.seek(0)
    if os.name=='nt':
        import msvcrt
        if guard.read(1)==b'':guard.write(b'0');guard.flush()
        guard.seek(0);msvcrt.locking(guard.fileno(),msvcrt.LK_NBLCK,1)
    else:
        import fcntl
        fcntl.flock(guard,fcntl.LOCK_EX|fcntl.LOCK_NB)
    registry=ROOT/'annotation_site/resources/core100_distance_bindings.json'
    data=json.loads(registry.read_text(encoding='utf8'))
    names=set(data['evidence_sha256'])|{'annotation_site/resources/core100_distance_bindings.json',
        'physedit/core100_bindings.py','physedit/boundary_recovery.py',
        'physedit/original_joint_path.py',
        'physedit/runtime_snapshot.py',
        'docs/critical_boundary/CORE100_DISTANCE_BINDINGS.md',
        'docs/critical_boundary/CORE100_CONDITIONAL_AXES.md'}
    review_doc='docs/critical_boundary/CORE100_ORIGINAL_REFERENCE_REAUDIT.md'
    if(ROOT/review_doc).exists():names.add(review_doc)
    files={name:hashlib.sha256((ROOT/name).read_bytes()).hexdigest()for name in sorted(names)}
    archive=folder/'distance_runtime.zip'
    manifest=dict(schema='core100-distance-runtime-supplement-v1',files=files,summary=data['summary'],
        base_runtime='/data2/liyuhan/core100_t19_replacement_20261031/project',
        no_reference_prompt_or_generated_annotation_modified=True)
    parent='/data2/liyuhan/core100_distance_bindings_20261031'
    storage='/home/wangzijun_p25/core100_distance_bindings_storage_v2_20261101'
    # Seed the content store from hash-verified prior deliveries. Only bytes
    # absent on the server need to cross the network again.
    seed_code='''import hashlib,json,os,shutil,uuid
from pathlib import Path
files=FILES;cache=Path(STORAGE)/'shared/objects';sources={}
for manifest_file in Path(PARENT).glob('snapshots/*/project/DISTANCE_SUPPLEMENT_MANIFEST.json'):
 old=json.loads(manifest_file.read_text())
 for name,digest in old['files'].items():
  if files.get(name)==digest:sources.setdefault(digest,manifest_file.parent/name)
missing=[]
for name,digest in files.items():
 obj=cache/digest[:2]/digest
 if obj.exists():
  assert hashlib.sha256(obj.read_bytes()).hexdigest()==digest
  continue
 src=sources.get(digest)
 if src is None:missing.append(name);continue
 raw=src.read_bytes();assert hashlib.sha256(raw).hexdigest()==digest
 obj.parent.mkdir(parents=True,exist_ok=True)
 temp=obj.with_name(obj.name+'.seed-'+uuid.uuid4().hex);temp.write_bytes(raw);temp.chmod(0o444);os.replace(temp,obj)
print(json.dumps(missing))
'''.replace('FILES',repr(files)).replace('STORAGE',repr(storage)).replace('PARENT',repr(parent))
    missing=json.loads(remote_text('p25',seed_code,timeout=120))
    with zipfile.ZipFile(archive,'w',compression=zipfile.ZIP_DEFLATED)as z:
        for name in sorted(missing):z.write(ROOT/name,name)
        z.writestr('DISTANCE_SUPPLEMENT_MANIFEST.json',json.dumps(manifest,indent=2))
    package_id=hashlib.sha256(json.dumps(manifest,sort_keys=True).encode()).hexdigest()[:12]
    remote=storage+'/snapshots/'+package_id
    remote_text('p25',"from pathlib import Path\nPath(%r).mkdir(parents=True,exist_ok=True)"%remote)
    # Close inherited output pipes and bound the transfer: killing an outer
    # Python timeout must not leave an orphan holding the follower's pipes.
    with (folder/'transfer.log').open('ab')as transfer_log:
        subprocess.run(['scp',*transport_options('p25'),'-o','BatchMode=yes',
            '-o','ConnectTimeout=10','-o','ServerAliveInterval=15','-o','ServerAliveCountMax=2',
            '-q',str(archive),'p25:'+remote+'/distance_runtime.zip'],check=True,
            stdout=transfer_log,stderr=transfer_log,timeout=900)
    installer=(ROOT/'physedit/runtime_snapshot.py').read_text(encoding='utf8')
    pointer=dict(package_id=package_id,receipt=remote+'/DELIVERED.json',project=remote+'/project')
    code='''import json,hashlib,subprocess,fcntl
from pathlib import Path
root=Path(REMOTE_ROOT);cache=Path(STORAGE_ROOT)/'shared';cache.mkdir(parents=True,exist_ok=True)
lock=(cache/'install.lock').open('a');fcntl.flock(lock,fcntl.LOCK_EX)
namespace={};exec(INSTALLER_SOURCE,namespace)
installed=namespace['install_snapshot'](root/'distance_runtime.zip',root,
 Path('/data2/liyuhan/core100_t19_replacement_20261031/project'),cache)
project=Path(installed['project']);manifest=installed.pop('manifest')
check=subprocess.run(['/home/wangzijun_p25/miniconda3/envs/genesis/bin/python','-m','physedit.core100_bindings','status','--verify-evidence'],cwd=project,capture_output=True,text=True)
assert check.returncode==0,check.stderr
status=json.loads(check.stdout)
receipt=dict(project=str(project),files=len(manifest['files']),summary=status['summary'],verified_evidence=True,original_runtime_not_modified=True,
 registry_sha256=manifest['files']['annotation_site/resources/core100_distance_bindings.json'],
 content_addressed_storage=True,storage_statistics=installed,
 package_zip_sha256=hashlib.sha256((root/'distance_runtime.zip').read_bytes()).hexdigest())
pointer=ACTIVE_POINTER
for folder in [Path(STORAGE_ROOT),Path(PUBLIC_ROOT)]:
 temp=folder/'ACTIVE.next.json';temp.write_text(json.dumps(pointer));temp.replace(folder/'ACTIVE.json')
(root/'DELIVERED.json').write_text(json.dumps(receipt,indent=2));print(json.dumps(receipt))
(root/'distance_runtime.zip').unlink()
'''
    for marker,value in [('REMOTE_ROOT',remote),('STORAGE_ROOT',storage),('INSTALLER_SOURCE',installer),
                         ('ACTIVE_POINTER',pointer),('PUBLIC_ROOT',parent)]:
        code=code.replace(marker,repr(value))
    text=remote_text('p25',code,timeout=120)
    (folder/'DELIVERED.json').write_text(text,encoding='utf8')
    print(text)


if __name__=='__main__':main()
