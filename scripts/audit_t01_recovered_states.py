"""Run the unmodified original T01 auditor on hash-bound published states."""
import collections
import gzip
import hashlib
import importlib.util
import json
from pathlib import Path

ROOT=Path('review/scene_family_completion_20261018')


def main():
    source=ROOT/'t01_current_sources/audit_t01_v2.py';rule_hash=hashlib.sha256(source.read_bytes()).hexdigest()
    spec=importlib.util.spec_from_file_location('original_t01_auditor',source)
    auditor=importlib.util.module_from_spec(spec);spec.loader.exec_module(auditor)
    bindings={r['sample_id']:r for r in json.loads(Path('review/original_search_tasks_20261018/t01_original_family_bindings.json').read_text(encoding='utf-8'))}
    target=ROOT/'t01_measured_published_events_20261019.json'
    cached={r['sample_id']:r for r in json.loads(target.read_text())} if target.exists() else {}
    rows=[]
    for receipt in sorted((ROOT/'completion_states').glob('T01_*.json')):
        for record in json.loads(receipt.read_text(encoding='utf-8')):
            path=Path(record['local_path'])
            if hashlib.sha256(path.read_bytes()).hexdigest()!=record['sha256']:raise ValueError('published T01 state changed')
            old=cached.get(record['sample_id'])
            if old and old['sha256']==record['sha256'] and old['auditor_sha256']==rule_hash:rows.append(old);continue
            result=auditor.analyze(path)
            row=dict(**record,auditor_sha256=rule_hash,audit=result,original_family=bindings[record['sample_id']],status='original_auditor_run_boundary_mapping_pending')
            rows.append(row)
        target.write_text(json.dumps(rows,indent=2),encoding='utf-8')
    summary=dict(states=len(rows),outcomes=dict(collections.Counter(r['audit'].get('outcome_label','unknown') for r in rows)),families=dict(collections.Counter(str(r['original_family']['family']) for r in rows)))
    (ROOT/'t01_measured_summary_20261019.json').write_text(json.dumps(summary,indent=2),encoding='utf-8');print(json.dumps(summary))


if __name__=='__main__':main()
