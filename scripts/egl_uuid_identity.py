"""Resolve EGL ordinals by NVIDIA persistent UUID without initializing CUDA."""
import ctypes
import uuid


def egl_uuid_devices():
    library = ctypes.CDLL('libEGL.so.1')
    library.eglGetProcAddress.argtypes = [ctypes.c_char_p]
    library.eglGetProcAddress.restype = ctypes.c_void_p

    def function(name, result, *arguments):
        address = library.eglGetProcAddress(name.encode())
        if not address:
            raise RuntimeError('Required EGL identity function missing: ' + name)
        return ctypes.CFUNCTYPE(result, *arguments)(address)

    query = function('eglQueryDevicesEXT', ctypes.c_uint, ctypes.c_int,
                     ctypes.POINTER(ctypes.c_void_p), ctypes.POINTER(ctypes.c_int))
    binary = function('eglQueryDeviceBinaryEXT', ctypes.c_uint, ctypes.c_void_p,
                      ctypes.c_int, ctypes.c_int, ctypes.c_void_p,
                      ctypes.POINTER(ctypes.c_int))
    devices = (ctypes.c_void_p * 64)()
    count = ctypes.c_int()
    if not query(64, devices, ctypes.byref(count)):
        raise RuntimeError('EGL enumeration failed')
    rows = []
    for index in range(count.value):
        value = (ctypes.c_ubyte * 16)()
        length = ctypes.c_int()
        # EGL_DEVICE_UUID_EXT from EGL_EXT_device_persistent_id.
        if binary(devices[index], 0x335C, 16, value, ctypes.byref(length)) and length.value == 16:
            rows.append(dict(egl_index=index, uuid='GPU-' + str(uuid.UUID(bytes=bytes(value)))))
    if not rows:
        raise RuntimeError('No persistent EGL device UUIDs available')
    return rows


def matching_egl_index(identity):
    matches = [row['egl_index'] for row in egl_uuid_devices() if row['uuid'] == identity]
    if len(matches) != 1:
        raise RuntimeError('EGL UUID must have exactly one match: ' + identity)
    return matches[0]


if __name__ == '__main__':
    import json
    print(json.dumps(egl_uuid_devices(), indent=2))
