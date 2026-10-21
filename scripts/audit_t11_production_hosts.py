"""Recover production workers from completion receipts, not archive locations."""
import collections
import json
import subprocess
from scripts.export_original_boundary_distances import ROOT


def main():
    plans=[j for j in json.loads((ROOT/'five_scene_prepared_plan_20261020.json').read_text()) if j['scene_id']=='T11']
    plans+=json.loads((ROOT/'t11_original_p29_boundary_plan_20261020.json').read_text())
    endpoints={e['sample_id']:e for j in plans for e in j['endpoints']}
    sources={r['sample_id']:r for r in json.loads((ROOT/'t11_published_final_states.json').read_text()) if r['sample_id'] in endpoints}
    rows=[]
    for host in sorted({e['source_host'] for e in endpoints.values()}):
        selected={sid:s for sid,s in sources.items() if endpoints[sid]['source_host']==host}
        code=r'''
import pathlib,json,hashlib,re
rows=[]
for sid,source in SOURCES.items():
 parent=pathlib.Path(source['source_state']).parent.parent;p=parent/'FORMAL_COMPLETED.json'
 if not p.exists():rows.append(dict(sample_id=sid,production_host=None,reason='completion receipt missing',source_state=source['source_state']));continue
 raw=p.read_bytes();receipt=json.loads(raw);worker=receipt.get('worker','');match=re.match(r'(p[0-9]+)(?:_|$)',worker)
 if receipt.get('sample_id')!=sid:raise ValueError('completion receipt sample mismatch')
 rows.append(dict(sample_id=sid,production_host=match.group(1) if match else None,worker=worker,reason=None if match else 'completion_worker_host_unrecorded',completion_status=receipt.get('status','valid_true' if receipt.get('valid') else None),completion_receipt=str(p),completion_sha256=hashlib.sha256(raw).hexdigest(),source_state=source['source_state']))
print(json.dumps(rows))
'''.replace('SOURCES',repr(selected))
        result=subprocess.run(['ssh','-o','BatchMode=yes',host,'python3 -'],input=code.encode(),capture_output=True,timeout=60)
        if result.returncode:raise RuntimeError(result.stderr.decode(errors='replace'))
        rows.extend(dict(archive_host=host,**r) for r in json.loads(result.stdout))
    (ROOT/'t11_production_host_audit_20261020.json').write_text(json.dumps(rows,indent=2))
    summary=dict(endpoints=len(rows),production_hosts=dict(collections.Counter(r['production_host'] for r in rows)),
        archive_not_production_host=sum(r['production_host'] is not None and r['production_host']!=r['archive_host'] for r in rows),
        scope='Completion worker provenance. Archive host must not be described as the original production host without this evidence.')
    (ROOT/'t11_production_host_audit_summary_20261020.json').write_text(json.dumps(summary,indent=2));print(json.dumps(summary))


if __name__=='__main__':main()
