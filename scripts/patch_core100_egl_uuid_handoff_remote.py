"""Narrow future-start device fix; no process signals or simulation writes."""
import hashlib
import json
from pathlib import Path
import py_compile
import time

ROOT = Path('/data2/liyuhan/core100_continue_20261031_device_policy')
target = ROOT / 'device_handoff.py'
before = target.read_bytes()
old = "os.environ.update(CUDA_VISIBLE_DEVICES=uuid,EGL_DEVICE_ID=index,CUDA_DEVICE_ORDER='PCI_BUS_ID')"
new = """# CUDA physical ordinals and EGL enumeration have different orders on p25.
sys.path.insert(0,str(root))
from egl_uuid_identity import matching_egl_index
egl_index=matching_egl_index(uuid)  # fail closed, never fall back to EGL0
os.environ.update(CUDA_VISIBLE_DEVICES=uuid,EGL_DEVICE_ID=str(egl_index),CUDA_DEVICE_ORDER='PCI_BUS_ID')"""
source = before.decode()
assert source.count(old) == 1, 'Unexpected or already patched handoff'
source = source.replace(old, new)
source = source.replace('selected_gpu_uuid=uuid,allowed=', 'selected_gpu_uuid=uuid,selected_egl_index=egl_index,egl_identity_verified=True,allowed=')
compile(source, str(target), 'exec')
backup = ROOT / 'egl_uuid_fix'
backup.mkdir(exist_ok=False)
(backup / 'device_handoff.before.py').write_bytes(before)
original_receipt = json.loads((ROOT / 'HANDOFF_RECEIPT.json').read_text())
roots = [Path(row['root']) for row in original_receipt['roots']]
plans = []
for work in roots:
    deployment = work / 'deployment.json'
    raw = deployment.read_bytes()
    data = json.loads(raw)
    if str(target) not in data.get('sources', {}):
        continue
    assert data['sources'][str(target)] == hashlib.sha256(before).hexdigest(), str(work)
    plans.append((deployment, raw, data))
assert plans
temporary = target.with_suffix('.tmp')
temporary.write_text(source)
temporary.replace(target)
digest = hashlib.sha256(target.read_bytes()).hexdigest()
updates = []
for index, (deployment, raw, data) in enumerate(plans):
    (backup / ('deployment_%02d.before.json' % index)).write_bytes(raw)
    data['sources'][str(target)] = digest
    data['sources'][str(ROOT / 'egl_uuid_identity.py')] = hashlib.sha256((ROOT / 'egl_uuid_identity.py').read_bytes()).hexdigest()
    temporary = deployment.with_suffix('.tmp')
    temporary.write_text(json.dumps(data))
    temporary.replace(deployment)
    updates.append(str(deployment))
py_compile.compile(str(target), doraise=True)
receipt = dict(time=time.time(), old_handoff_sha256=hashlib.sha256(before).hexdigest(),
               new_handoff_sha256=digest, updated_future_deployment_hashes=updates,
               existing_processes_signalled=False, frozen_configs_or_solver_changed=False,
               existing_simulations_restarted=False,
               independent_probes=[json.loads((ROOT / ('PROBE_GPU%d_UUID.json' % i)).read_text()) for i in (0, 1)])
(backup / 'RECEIPT.json').write_text(json.dumps(receipt, indent=2))
print(json.dumps(receipt))
