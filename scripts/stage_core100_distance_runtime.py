"""Install the hash-checked numerical supplement in an isolated p25 runtime."""
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import zipfile

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
from boundary_ssh import remote_text


def main():
    registry=ROOT/'annotation_site/resources/core100_distance_bindings.json'
    data=json.loads(registry.read_text(encoding='utf8'))
    names=set(data['evidence_sha256'])|{'annotation_site/resources/core100_distance_bindings.json',
        'physedit/core100_bindings.py','physedit/boundary_recovery.py',
        'docs/critical_boundary/CORE100_DISTANCE_BINDINGS.md'}
    review_doc='docs/critical_boundary/CORE100_ORIGINAL_REFERENCE_REAUDIT.md'
    if(ROOT/review_doc).exists():names.add(review_doc)
    files={name:hashlib.sha256((ROOT/name).read_bytes()).hexdigest()for name in sorted(names)}
    folder=ROOT/'review/core100_binding_20261028/runtime_delivery'
    folder.mkdir(exist_ok=True)
    archive=folder/'distance_runtime.zip'
    manifest=dict(schema='core100-distance-runtime-supplement-v1',files=files,summary=data['summary'],
        base_runtime='/data2/liyuhan/core100_t19_replacement_20261031/project',
        no_reference_prompt_or_generated_annotation_modified=True)
    with zipfile.ZipFile(archive,'w',compression=zipfile.ZIP_DEFLATED)as z:
        for name in sorted(names):z.write(ROOT/name,name)
        z.writestr('DISTANCE_SUPPLEMENT_MANIFEST.json',json.dumps(manifest,indent=2))
    package_id=hashlib.sha256(json.dumps(manifest,sort_keys=True).encode()).hexdigest()[:12]
    parent='/data2/liyuhan/core100_distance_bindings_20261031'
    remote=parent+'/snapshots/'+package_id
    remote_text('p25',"from pathlib import Path\nPath(%r).mkdir(parents=True,exist_ok=True)"%remote)
    subprocess.run(['scp','-q',str(archive),'p25:'+remote+'/distance_runtime.zip'],check=True)
    code='''import json,hashlib,shutil,zipfile,subprocess
from pathlib import Path
root=Path(%r);project=root/'project'
if not project.exists():shutil.copytree(Path('/data2/liyuhan/core100_t19_replacement_20261031/project'),project)
with zipfile.ZipFile(root/'distance_runtime.zip')as z:
 manifest=json.loads(z.read('DISTANCE_SUPPLEMENT_MANIFEST.json'))
 for name,expected in manifest['files'].items():
  target=(project/name).resolve();assert target.is_relative_to(project.resolve())
  raw=z.read(name);assert hashlib.sha256(raw).hexdigest()==expected
  if target.exists()and hashlib.sha256(target.read_bytes()).hexdigest()!=expected:
   raise RuntimeError('Existing isolated runtime differs: '+name)
  target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(raw)
 (project/'DISTANCE_SUPPLEMENT_MANIFEST.json').write_text(json.dumps(manifest,indent=2))
check=subprocess.run(['/home/wangzijun_p25/miniconda3/envs/genesis/bin/python','-m','physedit.core100_bindings','status','--verify-evidence'],cwd=project,capture_output=True,text=True)
assert check.returncode==0,check.stderr
status=json.loads(check.stdout)
receipt=dict(project=str(project),files=len(manifest['files']),summary=status['summary'],verified_evidence=True,original_runtime_not_modified=True)
(root/'DELIVERED.json').write_text(json.dumps(receipt,indent=2));print(json.dumps(receipt))
'''%remote
    text=remote_text('p25',code,timeout=120)
    (folder/'DELIVERED.json').write_text(text,encoding='utf8')
    pointer=dict(package_id=package_id,receipt=remote+'/DELIVERED.json',project=remote+'/project')
    remote_text('p25',"import json\nfrom pathlib import Path\nPath(%r).write_text(%r)"%(parent+'/ACTIVE.json',json.dumps(pointer)))
    print(text)


if __name__=='__main__':main()
