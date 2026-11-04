"""Independent tiny CUDA + vendored-Pyrender context; no physics or source config."""
import json
import logging
import os
from pathlib import Path
import subprocess
import sys
import xml.etree.ElementTree as ET

from egl_uuid_identity import matching_egl_index


def main():
    physical = sys.argv[1]
    rows = subprocess.check_output(['nvidia-smi', '--query-gpu=index,uuid',
                                    '--format=csv,noheader']).decode().splitlines()
    identity = dict(tuple(x.strip() for x in row.split(',')) for row in rows)[physical]
    assert physical in ('0', '1')
    index = matching_egl_index(identity)
    os.environ.update(CUDA_VISIBLE_DEVICES=identity, EGL_DEVICE_ID=str(index),
                      CUDA_DEVICE_ORDER='PCI_BUS_ID', PYOPENGL_PLATFORM='egl')
    import torch
    allocation = torch.ones(64, device='cuda')
    torch.cuda.synchronize()
    from egl_renderer_bootstrap import install_gl_dispatch
    install_gl_dispatch()
    import genesis as gs
    gs.logger = logging.getLogger('device_identity_probe')
    from genesis.ext.pyrender.platforms.egl import EGLPlatform
    platform = EGLPlatform(16, 16, device_id=index)
    platform.init_context()
    from OpenGL import GL
    texture = GL.glGenTextures(1)
    GL.glBindTexture(GL.GL_TEXTURE_2D, texture)
    GL.glTexImage2D(GL.GL_TEXTURE_2D, 0, GL.GL_RGBA8, 16, 16, 0,
                    GL.GL_RGBA, GL.GL_UNSIGNED_BYTE, None)
    GL.glFinish()
    raw = subprocess.check_output(['nvidia-smi', '-q', '-x'])
    Path(sys.argv[2] + '.nvml.xml').write_bytes(raw)
    actual = []
    for gpu in ET.fromstring(raw).findall('gpu'):
        for process in gpu.findall('./processes/process_info'):
            if process.findtext('pid') == str(os.getpid()):
                actual.append(dict(uuid=gpu.findtext('uuid'), type=process.findtext('type'),
                                   used_memory=process.findtext('used_memory')))
    result = dict(pid=os.getpid(), physical_index=int(physical), expected_uuid=identity,
                  egl_index=index, actual_nvml_processes=actual,
                  renderer=GL.glGetString(GL.GL_RENDERER).decode(),
                  no_simulation_or_frozen_config_loaded=True)
    Path(sys.argv[2]).write_text(json.dumps(result, indent=2))
    assert actual and all(row['uuid'] == identity for row in actual), result
    assert any('C' in row['type'] for row in actual), result
    assert any('G' in row['type'] for row in actual), result
    GL.glDeleteTextures([texture])
    platform.delete_context()
    del allocation
    print(json.dumps(result))


if __name__ == '__main__':
    main()
