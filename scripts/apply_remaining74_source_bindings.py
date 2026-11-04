"""Fill missing original state identities; never edit numerical intervals or labels."""
import hashlib
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
WORK=ROOT/'review/core100_remaining74_admission_20261101'


def apply_source_bindings(cases,rows,evidence,path):
    for row in rows:
        if row['status']!='verified_original_published_interval':continue
        r=cases[row['clip_id']]
        assert r['reference_video_sha256']==row['reference_video_sha256']
        assert all(r[k]==row[k]for k in ('condition_frame_index','end_frame_index','horizon_s'))
        assert any(b['event']==row['target_event']and b['bracket']==row['original_boundary_interval']and b['endpoint_labels']==row['original_labels']for b in r['boundary_records'])
        source=row['source']
        assert r['source_state_sha256']in(None,source['state_sha256'])
        if r['source_state_sha256']is None:
            r['source_state_sha256']=source['state_sha256']
            assert r.get('fixed_context_sha256')in(None,source['fixed_context_sha256'])
            r['fixed_context_sha256']=source['fixed_context_sha256']
            r['original_source_state_registration']=dict(file=path,source_state_sha256=source['state_sha256'],
                scope='Exact active original sidecar identity recovered; intervals, normalizations, labels and scores unchanged')
    evidence[path]=hashlib.sha256((ROOT/path).read_bytes()).hexdigest()


if __name__=='__main__':
    p=ROOT/'annotation_site/resources/core100_distance_bindings.json'
    before=p.read_bytes();(WORK/'NUMERICAL_BEFORE_SOURCE_BINDING.json').write_bytes(before)
    registry=json.loads(before);proof=WORK/'PUBLISHED_INTERVAL_READBACK.json';digest=hashlib.sha256(proof.read_bytes()).hexdigest()
    sealed=WORK/'sealed_intervals'/(digest+'.json');sealed.parent.mkdir(exist_ok=True)
    if not sealed.exists():sealed.write_bytes(proof.read_bytes())
    cases={r['clip_id']:r for r in registry['cases']}
    apply_source_bindings(cases,json.loads(sealed.read_text()),registry['evidence_sha256'],sealed.relative_to(ROOT).as_posix())
    p.write_text(json.dumps(registry,ensure_ascii=False,indent=2),encoding='utf8')
    print(json.dumps(dict(recovered_cases=[r['clip_id']for r in registry['cases']if r.get('original_source_state_registration')],summary=registry['summary'])))
