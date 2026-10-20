"""Extract actual published parameters and native contacts, without old-config substitution.

No motion threshold is interpreted as collapse or fall. A contact label describes
native simulator contact, not visibility or a completed downstream response.
"""
import argparse
from concurrent.futures import ProcessPoolExecutor, as_completed
import gzip
import hashlib
import json
import math
from pathlib import Path

PAIRS = {
    'T16': [('t16_folder', 't16_support_book'), ('t16_folder', 't16_downstream_box')],
    'T17': [('t17_can', 't17_tissue_box')],
    'T18': [('t18_lower_book', 't18_upper_book')],
    'T20': [('t20_book', 't20_can'), ('t20_can', 't20_box'), ('t20_box', 't20_cup')],
}


def extract(row, cache, fetch_missing=False, release_hashes=None, production=None):
    path = cache / ('datasets--' + row['repo_id'].replace('/', '--')) / 'snapshots' / row['revision'] / row['sidecar_paths'][0]
    expected=(release_hashes or {}).get(row['sidecar_paths'][0],{})
    if not path.exists() and production and expected:
        original=Path(production)/row['sample_id']/'metadata'/(row['sample_id']+'__cam01.json.gz')
        if original.exists():path=original
    if not path.exists() and fetch_missing:
        from huggingface_hub import hf_hub_download
        path=Path(hf_hub_download(repo_id=row['repo_id'],repo_type='dataset',revision=row['revision'],
                                 filename=row['sidecar_paths'][0],cache_dir=str(cache)))
    raw = path.read_bytes()
    digest = hashlib.sha256(raw).hexdigest()
    blob = path.resolve().name
    is_hf_blob=path.resolve().parent.name=='blobs'
    if expected:
        if expected.get('sha256'):
            if digest!=expected['sha256']:
                if fetch_missing and production and Path(production) in path.parents:return extract(row,cache,True,release_hashes,None)
                raise ValueError('original metadata differs from published LFS bytes')
        elif hashlib.sha1(b'blob '+str(len(raw)).encode()+b'\0'+raw).hexdigest()!=expected['blob_id']:
            raise ValueError('original metadata differs from published Git blob')
    if is_hf_blob and len(blob) == 64 and blob != digest:
        raise ValueError('LFS hash mismatch')
    if is_hf_blob and len(blob) == 40 and hashlib.sha1(b'blob ' + str(len(raw)).encode() + b'\0' + raw).hexdigest() != blob:
        raise ValueError('Git blob hash mismatch')
    state = json.loads(gzip.decompress(raw) if path.suffix == '.gz' else raw)
    exp = state['experiment']
    if exp.get('trajectory_id') != row['sample_id']:
        raise ValueError('published trajectory identity mismatch')
    frames = state['frames']
    telemetry = any('contacts' in f for f in frames)
    actor_names={o['name'] for o in state['dynamic_objects']}
    contacts = []
    pairs={tuple(sorted(p)) for p in PAIRS[row['event_id']]+exp.get('required_contact_pairs',[])}
    for pair in sorted(pairs):
        applicable=set(pair)<=actor_names
        times = sorted({(f['frame_index'], c.get('physics_step_index', -1)) for f in frames for c in f.get('contacts', []) if {c.get('entity_a'), c.get('entity_b')} == set(pair)})
        last_pairs={frozenset([c.get('entity_a'),c.get('entity_b')]) for c in frames[-1].get('contacts',[])}
        contacts.append(dict(pair=list(pair), applicable=applicable, occurred=bool(times) if telemetry and applicable else None,
                             present_at_end=(frozenset(pair) in last_pairs) if 'contacts' in frames[-1] and applicable else None,
                             first=list(times[0]) if times else None, last=list(times[-1]) if times else None))
    actors = []
    for obj in state['dynamic_objects']:
        name = obj['name']
        track = [next(o for o in f['objects'] if o['name'] == name) for f in frames]
        positions = [o['position'] for o in track]
        if any(not math.isfinite(v) for p in positions for v in p):
            raise ValueError('nonfinite position')
        actors.append(dict(name=name, spec=obj['spec'], initial=track[0], final=track[-1],
                           maximum_displacement_m=max(math.dist(positions[0], p) for p in positions)))
    return dict(sample_id=row['sample_id'], scene_id=row['event_id'], engine='genesis',
                repo_id=row['repo_id'], revision=row['revision'], sidecar=row['sidecar_paths'][0],
                metadata_sha256=digest, hash_verified=bool(expected) or (is_hf_blob and len(blob) in (40, 64)), metadata_source_path=str(path), experiment=exp,
                render=state['render'], scene_overrides=state['scene_overrides'],
                actors=actors, contacts=contacts, contact_telemetry_present=telemetry,
                frames=len(frames), videos=row['videos'], status='published_metadata_extracted',schema_version=2,
                scope='native contact outcomes and continuous motion only; not visual QA or fall/collapse truth')


def set_options(options):
    global OPTIONS
    OPTIONS=options


def collect_one(row):
    root,cache,fetch_missing,hashes,production=OPTIONS
    dest=root/(row['sample_id']+'.json')
    if dest.exists():
        saved=json.loads(dest.read_text())
        if saved.get('revision')==row['revision'] and saved.get('status')=='published_metadata_extracted' and saved.get('schema_version')==2:
            return dict(scene_id=saved['scene_id'],status=saved['status'])
    try:value=extract(row,cache,fetch_missing,hashes,production)
    except Exception as exc:value=dict(sample_id=row['sample_id'],scene_id=row['event_id'],status='failed',error=str(exc))
    temp=dest.with_suffix('.tmp');temp.write_text(json.dumps(value));temp.replace(dest)
    return dict(scene_id=value['scene_id'],status=value['status'])


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--inventory', required=True)
    p.add_argument('--root', required=True)
    p.add_argument('--cache', default=str(Path.home()/'.cache/huggingface/hub'))
    p.add_argument('--workers', type=int, default=4)
    p.add_argument('--fetch-missing', action='store_true')
    p.add_argument('--release-hashes', help='Pinned HF file hashes; permits byte-identical original metadata')
    p.add_argument('--production', help='Original production root; never accepted without a release hash')
    args = p.parse_args()
    root = Path(args.root); root.mkdir(parents=True, exist_ok=True)
    rows = [r for r in map(json.loads, Path(args.inventory).read_text().splitlines())
            if r['engine']=='genesis' and r['event_id'] in PAIRS]
    manifest=json.loads(Path(args.release_hashes).read_text()) if args.release_hashes else {}
    if manifest and any(r['repo_id']!=manifest['repo_id'] or r['revision']!=manifest['revision'] for r in rows):
        raise ValueError('release hash index belongs to another revision')
    hashes=manifest.get('files',{})
    counts={}; done=0
    with ProcessPoolExecutor(max_workers=args.workers,initializer=set_options,
                             initargs=((root,Path(args.cache),args.fetch_missing,hashes,args.production),)) as pool:
        for future in as_completed([pool.submit(collect_one,r) for r in rows]):
            value=future.result();key=value['scene_id']+':'+value['status'];counts[key]=counts.get(key,0)+1;done+=1
            if done%20==0 or done==len(rows):
                tmp=root/'progress.tmp';tmp.write_text(json.dumps(dict(done=done,planned=len(rows),counts=counts)));tmp.replace(root/'progress.json')
                print(json.dumps(dict(done=done,planned=len(rows),counts=counts)),flush=True)


if __name__=='__main__': main()
