import ctypes
import sys
import types
import pytest
from scripts import egl_renderer_bootstrap as bootstrap


def test_adapter_preserves_original_renderer_arguments_and_source(tmp_path,monkeypatch):
    events=[];renderer=tmp_path/'original_renderer.py';renderer.write_text('original source')
    config=tmp_path/'unchanged.json';config.write_text('{"render":{"write_video":false}}')
    args=[str(renderer),'--strict-live-physics','--config',str(config)]
    monkeypatch.setattr(sys,'argv',['bootstrap']+args);monkeypatch.setattr(sys,'path',list(sys.path))
    monkeypatch.setattr(bootstrap,'install_gl_dispatch',lambda:events.append('dispatch installed'))
    monkeypatch.setattr(bootstrap.runpy,'run_path',lambda path,run_name:events.append((path,run_name,list(sys.argv))))
    monkeypatch.setitem(sys.modules,'cv2',None)
    bootstrap.main()
    assert events==['dispatch installed',(str(renderer),'__main__',args)]
    assert renderer.read_text()=='original source'
    assert config.read_text()=='{"render":{"write_video":false}}'


def test_numeric_adapter_cannot_silently_disable_a_requested_video_writer(tmp_path,monkeypatch):
    config=tmp_path/'video.json';config.write_text('{"render":{"write_video":true}}')
    monkeypatch.setattr(sys,'argv',['bootstrap','renderer.py','--config',str(config)])
    with pytest.raises(ValueError,match='write_video=False'):bootstrap.main()


def test_native_graphics_binding_retains_error_checks_and_unrelated_calls(monkeypatch):
    calls=[]
    class Base:
        def constructFunction(self,name,dll,*args,**kwargs):calls.append((name,dll,kwargs))
    native=types.SimpleNamespace(glClear=object(),glGetError=types.SimpleNamespace())
    egl_native=types.SimpleNamespace(eglInitialize=object(),eglGetError=types.SimpleNamespace())
    checker=types.SimpleNamespace(_registeredChecker='old',_currentChecker='old')
    egl_checker=types.SimpleNamespace(_registeredChecker='old',_currentChecker='old')
    modules={name:types.ModuleType(name) for name in ['OpenGL','OpenGL.platform','OpenGL.raw','OpenGL.raw.GL','OpenGL.raw.EGL','OpenGL.EGL']}
    for name,module in modules.items():
        module.__path__=[];monkeypatch.setitem(sys.modules,name,module)
    modules['OpenGL.platform'].baseplatform=types.SimpleNamespace(BasePlatform=Base)
    modules['OpenGL.raw.GL']._errors=types.SimpleNamespace(_error_checker=checker)
    modules['OpenGL.raw.EGL']._errors=types.SimpleNamespace(_error_checker=egl_checker)
    modules['OpenGL'].EGL=modules['OpenGL.EGL']
    monkeypatch.setattr(bootstrap.ctypes,'CDLL',lambda name:egl_native if name=='libEGL.so.1' else native)
    bootstrap.install_gl_dispatch()
    Base().constructFunction('glClear','old',error_checker=checker)
    Base().constructFunction('eglInitialize','egl',error_checker='unchanged')
    Base().constructFunction('unrelated','other',error_checker='unchanged')
    assert calls[0][1] is native and calls[0][2]['error_checker'] is checker
    assert calls[1][1] is egl_native and calls[1][2]['error_checker']=='unchanged'
    assert calls[2][1:] == ('other',{'error_checker':'unchanged'})
    assert checker._registeredChecker is native.glGetError
    assert checker._currentChecker is native.glGetError
    assert native.glGetError.restype is ctypes.c_uint
    assert egl_checker._registeredChecker is egl_native.eglGetError
    assert egl_checker._currentChecker is egl_native.eglGetError
