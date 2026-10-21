"""Reuse complete digest verification only for unchanged files and expectations."""


def verify_probe_files(probe, folder, cache):
    import gzip
    import hashlib
    from pathlib import Path
    def identity(path):
        s=path.stat()
        return [str(path),s.st_dev,s.st_ino,s.st_size,s.st_mtime_ns,s.st_ctime_ns]
    path=Path(probe.get('state_path',str(folder/'physics.json')))
    if not path.exists() and path.suffix=='.json' and path.with_suffix('.json.gz').exists():path=path.with_suffix('.json.gz')
    config=folder/'config.json'
    key=[identity(path),identity(config),probe['state_sha256'],probe.get('stored_state_sha256'),probe['config_sha256']]
    name=str(folder)
    if cache.get(name)==key:return str(path)
    raw=path.read_bytes()
    if probe.get('stored_state_sha256') and hashlib.sha256(raw).hexdigest()!=probe['stored_state_sha256']:raise ValueError('stored state changed')
    plain=gzip.decompress(raw) if path.suffix=='.gz' else raw
    if hashlib.sha256(plain).hexdigest()!=probe['state_sha256']:raise ValueError('numeric state changed')
    if hashlib.sha256(config.read_bytes()).hexdigest()!=probe['config_sha256']:raise ValueError('probe config changed')
    if key[:2]!=[identity(path),identity(config)]:raise ValueError('state or config changed during verification')
    cache[name]=key
    return str(path)
