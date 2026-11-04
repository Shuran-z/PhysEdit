"""Install immutable scoring snapshots without duplicating their evidence bytes."""
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import shutil
import uuid
import zipfile


def _digest(path):
    value=hashlib.sha256()
    with Path(path).open('rb') as handle:
        for block in iter(lambda:handle.read(1024*1024),b''):value.update(block)
    return value.hexdigest()


def _target(root, name):
    part=PurePosixPath(name)
    if part.is_absolute() or '..' in part.parts or '\\' in name:
        raise ValueError('snapshot_path_escape:'+name)
    target=(root/Path(*part.parts)).resolve()
    if not target.is_relative_to(root.resolve()):raise ValueError('snapshot_path_escape:'+name)
    return target


def _atomic_link(source, target):
    target.parent.mkdir(parents=True,exist_ok=True)
    temporary=target.with_name(target.name+'.link-'+uuid.uuid4().hex)
    os.link(source,temporary)
    try:os.replace(temporary,target)
    finally:
        if temporary.exists():temporary.unlink()


def _base_files(base):
    return [p for p in sorted(base.rglob('*'))if p.is_file() and
        not any(x in p.parts for x in ['__pycache__','.pytest_cache','.git'])and p.suffix!='.pyc']


def install_snapshot(archive, snapshot, base, cache):
    """Preserve the base and previous snapshots; replace overlay links atomically.

    Publishing ACTIVE and running the evidence reader are the caller's final
    steps. A failed installation never publishes an active pointer.
    """
    archive=Path(archive);snapshot=Path(snapshot);base=Path(base);cache=Path(cache)
    snapshot.mkdir(parents=True,exist_ok=True);cache.mkdir(parents=True,exist_ok=True)
    entries={p.relative_to(base).as_posix():_digest(p)for p in _base_files(base)}
    fingerprint=hashlib.sha256(json.dumps(entries,sort_keys=True).encode()).hexdigest()
    cached_base=cache/'base_trees'/fingerprint
    if not cached_base.exists():
        cached_base.parent.mkdir(parents=True,exist_ok=True)
        temporary=cached_base.with_name(fingerprint+'.build-'+uuid.uuid4().hex)
        temporary.mkdir()
        for name,digest in entries.items():
            target=_target(temporary,name);target.parent.mkdir(parents=True,exist_ok=True)
            shutil.copy2(base/name,target)
            if _digest(target)!=digest:raise ValueError('snapshot_base_changed:'+name)
            if os.name!='nt':target.chmod(0o444)
        temporary.rename(cached_base)
    for name,digest in entries.items():
        target=_target(cached_base,name)
        if not target.is_file()or _digest(target)!=digest:
            raise ValueError('snapshot_cached_base_changed:'+name)
        # POSIX can atomically replace a read-only link. Windows applies its
        # read-only attribute to the shared file and refuses that replacement.
        if os.name!='nt':target.chmod(0o444)
    project=snapshot/'project'
    if not project.exists():shutil.copytree(cached_base,project,copy_function=os.link)
    installed=project/'DISTANCE_SUPPLEMENT_MANIFEST.json'
    stats=dict(new_objects=0,reused_objects=0,new_object_bytes=0)
    with zipfile.ZipFile(archive) as package:
        manifest=json.loads(package.read('DISTANCE_SUPPLEMENT_MANIFEST.json'))
        if installed.exists() and json.loads(installed.read_text())!=manifest:
            raise ValueError('immutable_snapshot_manifest_changed')
        # Validate all bytes before linking any overlay into this snapshot.
        for name,digest in manifest['files'].items():
            _target(project,name)
            obj=cache/'objects'/digest[:2]/digest
            if name in package.namelist():
                raw=package.read(name)
                if hashlib.sha256(raw).hexdigest()!=digest:raise ValueError('snapshot_archive_hash_mismatch:'+name)
            elif not obj.exists():
                raise ValueError('snapshot_missing_archive_and_cache:'+name)
            if obj.exists():
                if _digest(obj)!=digest:raise ValueError('snapshot_cache_hash_mismatch:'+name)
                stats['reused_objects']+=1
            else:
                obj.parent.mkdir(parents=True,exist_ok=True)
                temporary=obj.with_name(obj.name+'.build-'+uuid.uuid4().hex)
                temporary.write_bytes(raw);temporary.chmod(0o444);os.replace(temporary,obj)
                stats['new_objects']+=1;stats['new_object_bytes']+=len(raw)
        for name,digest in manifest['files'].items():
            target=_target(project,name);obj=cache/'objects'/digest[:2]/digest
            if not target.exists()or _digest(target)!=digest:_atomic_link(obj,target)
        raw=json.dumps(manifest,indent=2).encode()
        temporary=installed.with_name(installed.name+'.build-'+uuid.uuid4().hex)
        temporary.write_bytes(raw);os.replace(temporary,installed)
    return dict(project=str(project),manifest=manifest,base_fingerprint=fingerprint,**stats)
