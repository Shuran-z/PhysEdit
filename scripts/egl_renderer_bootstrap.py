"""Bind native GL/EGL entry points and error queries; run the unchanged renderer."""
import ctypes
import json
import os
from pathlib import Path
import runpy
import sys


def install_gl_dispatch():
    from OpenGL.platform import baseplatform
    native=ctypes.CDLL('libGL.so.1')
    egl_native=ctypes.CDLL('libEGL.so.1')
    original=baseplatform.BasePlatform.constructFunction
    def bind(platform,name,dll,*args,**kwargs):
        symbol=name.decode() if isinstance(name,bytes) else name
        library=egl_native if symbol.startswith('egl') else native if symbol.startswith('gl') else None
        if library is not None and hasattr(library,symbol):
            dll=library;kwargs['force_extension']=False
        return original(platform,name,dll,*args,**kwargs)
    baseplatform.BasePlatform.constructFunction=bind
    from OpenGL.raw.GL import _errors
    get_error=native.glGetError;get_error.argtypes=[];get_error.restype=ctypes.c_uint
    _errors._error_checker._registeredChecker=get_error
    _errors._error_checker._currentChecker=get_error
    from OpenGL import EGL  # noqa: F401
    from OpenGL.raw.EGL import _errors as egl_errors
    egl_error=egl_native.eglGetError;egl_error.argtypes=[];egl_error.restype=ctypes.c_uint
    egl_errors._error_checker._registeredChecker=egl_error
    egl_errors._error_checker._currentChecker=egl_error


def main():
    if len(sys.argv)<2:raise SystemExit('usage: egl_renderer_bootstrap.py ORIGINAL_RENDERER [ARGS]')
    if '--config' not in sys.argv:raise SystemExit('numeric bootstrap requires an explicit config')
    config_path=Path(sys.argv[sys.argv.index('--config')+1])
    if json.loads(config_path.read_text())['render'].get('write_video') is not False:
        raise ValueError('numeric bootstrap requires write_video=False; video generation must use its configured writer')
    # p29's optional OpenCV wheel requires a newer GLIBC. Its failed import can
    # leave incompatible shared libraries loaded. No video writer is needed here.
    sys.modules['cv2']=None
    os.environ.setdefault('PYOPENGL_PLATFORM','egl')
    device=os.environ.get('CUDA_VISIBLE_DEVICES','').split(',')[0]
    if device.isdecimal():os.environ.setdefault('EGL_DEVICE_ID',device)
    install_gl_dispatch()
    print('[numeric_bootstrap] GL/EGL errors checked; optional video writer disabled; original CUDA physics retained',flush=True)
    renderer=Path(sys.argv[1]).resolve()
    sys.path.insert(0,str(renderer.parent))
    sys.argv=sys.argv[1:]
    runpy.run_path(str(renderer),run_name='__main__')


if __name__=='__main__':main()
