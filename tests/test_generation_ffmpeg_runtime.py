"""The prepared FFmpeg binary must also be used by the resize stage."""
import json
from pathlib import Path
import sys

from physedit.runners.diffusers_i2v import _resize_to_source
from physedit.runners.oneclick_registry import contract
from physedit.runners.registered_oneclick import _preflight


def executable(path):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text('#!' + sys.executable + '\n'
                    'import json, pathlib, sys\n'
                    'pathlib.Path(sys.argv[-1]).write_text(json.dumps(sys.argv))\n')
    path.chmod(0o755)
    return path


def test_registered_nonstandard_ffmpeg_name_reaches_actual_resize(tmp_path, monkeypatch):
    ffmpeg = executable(tmp_path / 'media runtime' / 'ffmpeg-linux-v7')
    model = tmp_path / 'model'
    model.mkdir()
    spec = dict(model='ltx_i2v', model_dir=str(model), generation_runtime=dict(
        python=sys.executable, ffmpeg=str(ffmpeg)))
    _, _, env = _preflight(spec, contract('ltx_i2v'))
    # The registered binary's directory has no executable named "ffmpeg".
    assert not (ffmpeg.parent / 'ffmpeg').exists()
    monkeypatch.setenv('PATH', env['PATH'])
    monkeypatch.setenv('IMAGEIO_FFMPEG_EXE', env['IMAGEIO_FFMPEG_EXE'])
    output = tmp_path / 'resized.mp4'
    _resize_to_source(tmp_path / 'raw.mp4', tmp_path / 'reference.avi', output,
                      fps=16., dims=(1280, 720))
    argv = json.loads(output.read_text())
    assert Path(argv[0]) == ffmpeg
    assert argv[argv.index('-vf') + 1] == 'scale=1280:720'
    assert argv[argv.index('-r') + 1] == '16.0'
    assert '-n' in argv


def test_standard_ffmpeg_path_still_works_without_explicit_binding(tmp_path, monkeypatch):
    ffmpeg = executable(tmp_path / 'bin' / 'ffmpeg')
    monkeypatch.delenv('IMAGEIO_FFMPEG_EXE', raising=False)
    monkeypatch.setenv('PATH', str(ffmpeg.parent))
    output = tmp_path / 'resized.mp4'
    _resize_to_source(tmp_path / 'raw.mp4', tmp_path / 'reference.avi', output,
                      fps=24., dims=(854, 480))
    argv = json.loads(output.read_text())
    assert Path(argv[0]) == ffmpeg
    assert argv[argv.index('-r') + 1] == '24.0'
