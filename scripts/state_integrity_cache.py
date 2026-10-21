"""Cache identity for immutable generated states after an initial full digest check."""


def state_identity(path, receipt):
    stat=path.stat()
    return [stat.st_dev,stat.st_ino,stat.st_size,stat.st_mtime_ns,stat.st_ctime_ns,
            receipt['stored_state_sha256'],receipt['state_sha256'],receipt.get('source_config_sha256')]
