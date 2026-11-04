import copy
import json
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import pytest
from physedit.isolated_annotation_io import annotation_path, validate_output, write_state


def setup(tmp_path, camera='cam01'):
    video=tmp_path/'sample'/'videos'/('sample__'+camera+'.mp4')
    video.parent.mkdir(parents=True,exist_ok=True);video.write_bytes(b'native-test-video')
    config={'render':{'save_video':str(video)},'annotations':{}}
    config['annotations']['save_path']=str(annotation_path(config))
    return config


def test_camera_paths_are_distinct_and_shared_path_rejected(tmp_path):
    a,b=setup(tmp_path),setup(tmp_path,'cam02')
    assert validate_output(a)!=validate_output(b)
    b['annotations']['save_path']=a['annotations']['save_path']
    with pytest.raises(ValueError):validate_output(b)


def test_concurrent_publication_never_clobbers_original(tmp_path):
    c=setup(tmp_path);original=copy.deepcopy(c);p=annotation_path(c)
    def publish(i):
        try:write_state(p,{'render':c['render'],'frames':[i]},c);return True
        except FileExistsError:return False
    with ThreadPoolExecutor(4)as pool:results=list(pool.map(publish,range(4)))
    assert sum(results)==1
    before=p.read_bytes()
    with pytest.raises(FileExistsError):write_state(p,{'render':c['render'],'frames':[99]},c)
    assert p.read_bytes()==before and c==original
    assert len(json.loads(before)['native_media_binding']['video_sha256'])==64
    assert not list(p.parent.glob('*.tmp'))


def test_reject_mismatched_state_header(tmp_path):
    c=setup(tmp_path)
    with pytest.raises(ValueError):write_state(annotation_path(c),{'render':{'save_video':'other.mp4'}},c)
    assert not annotation_path(c).exists()
