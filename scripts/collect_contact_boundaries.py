"""Validate completed T12 probes and derive interval-valued distances.

Run beside the remote worker roots. Never promotes a numerical bracket to a
visually admitted reference or a cross-context pair.
"""
import argparse
import gzip
import hashlib
import json
from pathlib import Path


def collect(root):
    records = []
    for path in sorted(root.glob('worker*/T12_C*/result.json')):
        row = json.loads(path.read_text())
        if row['status'] != 'local_contact_bracket_completed':
            records.append(row)
            continue
        probes = row['probes']
        if not probes:
            raise ValueError('empty probe evidence: ' + str(path))
        for probe in probes:
            state = Path(probe['state_path'])
            raw = gzip.decompress(state.read_bytes())
            config = (state.parent/'config.json').read_bytes()
            if hashlib.sha256(raw).hexdigest() != probe['state_sha256'] or hashlib.sha256(config).hexdigest() != probe['config_sha256']:
                raise ValueError('probe evidence changed: ' + str(state))
            frames = json.loads(raw)['frames']
            if len(frames) != 210 or not all(f.get('contact_telemetry_complete') is True for f in frames):
                raise ValueError('incomplete contact telemetry')
            actual = int(any(f['contacts'] for f in frames if 4 <= f['frame_index'] <= 154))
            if actual != probe['label']:
                raise ValueError('probe label changed')
        lo, hi = row['bracket']; theta = row['source_theta']; span = row['normalization_span']
        by_theta = {p['theta']: p['label'] for p in probes}
        # An anchor may constitute an endpoint without a duplicated probe.
        if lo in by_theta and hi in by_theta and by_theta[lo] == by_theta[hi]:
            raise ValueError('boundary endpoints have identical labels')
        lower = max(lo-theta, theta-hi, 0)/span
        upper = max(abs(theta-lo), abs(theta-hi))/span
        bucket = 'near' if upper <= .05 else 'mid' if lower > .05 and upper <= .15 else 'far' if lower > .15 else 'bucket_uncertain'
        domain_lo, domain_hi = row['normalization_domain']
        in_domain = domain_lo <= lo <= hi <= domain_hi
        records.append(dict(**row, normalized_distance_interval=[lower, upper], distance_bin=bucket,
                            boundary_within_published_domain=in_domain,
                            distance_scope='published_domain' if in_domain else 'diagnostic_distance_to_out_of_domain_boundary',
                            probe_evidence_verified=True, reference_admitted=False, pair_admitted=False,
                            result_sha256=hashlib.sha256(path.read_bytes()).hexdigest()))
    return dict(schema='validated-contact-distance-ledger-v1', records=records,
                completed=sum(r.get('probe_evidence_verified') is True for r in records),
                expected=5, note='Numerical completion is separate from RGB reference and generated-video adjudication.')


if __name__ == '__main__':
    p = argparse.ArgumentParser();p.add_argument('--root', required=True);p.add_argument('--output', required=True)
    a = p.parse_args();result = collect(Path(a.root));out = Path(a.output)
    temp = out.with_suffix('.tmp');temp.write_text(json.dumps(result, ensure_ascii=False, indent=2));temp.replace(out)
    print(json.dumps({'completed': result['completed'], 'output': str(out)}))
