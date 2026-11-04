"""Read only: current device receipts and all NVML process types for owned launches."""
import json
from pathlib import Path
import subprocess
import xml.etree.ElementTree as ET

root = Path('/data2/liyuhan/core100_continue_20261031_device_policy')
roots = [Path(row['root']) for row in json.loads((root / 'HANDOFF_RECEIPT.json').read_text())['roots']]
records = []
for work in roots:
    for path in work.rglob('actual_gpu_selection.json'):
        row = json.loads(path.read_text())
        pid = row.get('pid')
        if pid and Path('/proc/%d' % pid).exists():
            records.append(dict(receipt=str(path), **row))
raw = subprocess.check_output(['nvidia-smi', '-q', '-x'])
by_pid = {}
for gpu in ET.fromstring(raw).findall('gpu'):
    for process in gpu.findall('./processes/process_info'):
        by_pid.setdefault(int(process.findtext('pid')), []).append(dict(uuid=gpu.findtext('uuid'),
                         type=process.findtext('type'), memory=process.findtext('used_memory')))
for row in records:
    row['actual_nvml_processes'] = by_pid.get(row['pid'], [])
result = dict(active_receipts=records, no_process_signals=True,
              note='Processes that already loaded the old module retain old code until natural exit.')
(root / 'egl_uuid_fix/ACTIVE_SNAPSHOT.json').write_text(json.dumps(result, indent=2))
print(json.dumps(result))
