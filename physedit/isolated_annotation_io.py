"""Camera-specific annotation paths and immutable, video-bound state writes."""
import hashlib
import json
import os
from pathlib import Path
import tempfile


def annotation_path(config):
    video = Path(config['render']['save_video']).resolve()
    return video.parent.parent / 'annotations' / (video.stem + '.json')


def validate_output(config):
    path = Path(config['annotations']['save_path']).resolve()
    if path != annotation_path(config):
        raise ValueError('Shared/incorrect camera annotation path: ' + str(path))
    camera = config.get('camera_id')
    if camera and not Path(config['render']['save_video']).stem.endswith('__' + camera):
        raise ValueError('Declared camera does not match native video filename')
    return path


def sha256_file(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as f:
        for b in iter(lambda: f.read(1024 * 1024), b''):
            h.update(b)
    return h.hexdigest()


def write_state(path, data, config):
    """Publish complete state atomically; never overwrite a previous run."""
    path = Path(path).resolve()
    if path != validate_output(config):
        raise ValueError('State destination differs from checked camera path')
    video = Path(config['render']['save_video']).resolve()
    if Path(data.get('render', {}).get('save_video', '')).resolve() != video:
        raise ValueError('State header belongs to another video')
    record = dict(data)
    record['native_media_binding'] = dict(video_path=str(video),
        video_sha256=sha256_file(video), camera_id=config.get('camera_id') or video.stem.rsplit('__', 1)[-1],
        config_sha256=hashlib.sha256(json.dumps(config, sort_keys=True).encode()).hexdigest())
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(prefix='.' + path.name + '.', suffix='.tmp', dir=path.parent)
    try:
        with os.fdopen(fd, 'w', encoding='utf8') as f:
            json.dump(record, f, ensure_ascii=False, indent=2)
            f.flush()
            os.fsync(f.fileno())
        # Hard-link publication is atomic and fails if the destination exists.
        os.link(name, path)
    finally:
        Path(name).unlink(missing_ok=True)


def install_writer(base, config):
    target = validate_output(config)
    original = base.save_json
    def guarded(path, data):
        if Path(path).resolve() == target:
            return write_state(path, data, config)
        return original(path, data)
    base.save_json = guarded
