import hashlib
import json
import os
import zipfile

import pytest

from physedit.runtime_snapshot import install_snapshot


def package(path, files, *, wrong_hash=False):
    manifest=dict(schema='test',files={n:hashlib.sha256(raw).hexdigest()for n,raw in files.items()})
    if wrong_hash:manifest['files'][next(iter(files))]='0'*64
    with zipfile.ZipFile(path,'w')as z:
        z.writestr('DISTANCE_SUPPLEMENT_MANIFEST.json',json.dumps(manifest))
        for name,raw in files.items():z.writestr(name,raw)


def test_snapshots_share_unchanged_bytes_and_preserve_base_and_previous_snapshot(tmp_path):
    base=tmp_path/'base';base.mkdir();(base/'frozen.json').write_bytes(b'unchanged-input')
    (base/'module.py').write_bytes(b'original-code')
    z1=tmp_path/'one.zip';package(z1,{'module.py':b'first-code','evidence/a.json':b'proof','evidence/b.json':b'proof'})
    one=install_snapshot(z1,tmp_path/'one',base,tmp_path/'cache')
    assert one['new_objects']==2 and one['reused_objects']==1
    again=install_snapshot(z1,tmp_path/'one',base,tmp_path/'cache')
    assert again['new_objects']==again['new_object_bytes']==0
    z2=tmp_path/'two.zip';package(z2,{'module.py':b'second-code','evidence/a.json':b'proof'})
    two=install_snapshot(z2,tmp_path/'two',base,tmp_path/'cache')
    assert two['new_objects']==1 and two['reused_objects']==1
    first=tmp_path/'one/project';second=tmp_path/'two/project'
    assert (base/'module.py').read_bytes()==b'original-code'
    assert (first/'module.py').read_bytes()==b'first-code'
    assert (second/'module.py').read_bytes()==b'second-code'
    assert os.path.samefile(first/'evidence/a.json',second/'evidence/a.json')
    assert os.path.samefile(first/'frozen.json',second/'frozen.json')


@pytest.mark.parametrize('name,wrong_hash,error',[
    ('../escape.json',False,'path_escape'),('proof.json',True,'hash_mismatch')])
def test_invalid_package_never_publishes_a_snapshot_manifest(tmp_path,name,wrong_hash,error):
    base=tmp_path/'base';base.mkdir();(base/'input').write_bytes(b'frozen')
    archive=tmp_path/'bad.zip';package(archive,{name:b'evidence'},wrong_hash=wrong_hash)
    with pytest.raises(ValueError,match=error):
        install_snapshot(archive,tmp_path/'snapshot',base,tmp_path/'cache')
    assert not(tmp_path/'snapshot/project/DISTANCE_SUPPLEMENT_MANIFEST.json').exists()
    assert (base/'input').read_bytes()==b'frozen' and not(tmp_path/'escape.json').exists()


def test_delta_package_requires_verified_existing_bytes(tmp_path):
    base=tmp_path/'base';base.mkdir();(base/'input').write_bytes(b'frozen')
    archive=tmp_path/'full.zip';package(archive,{'proof.json':b'preserved'})
    install_snapshot(archive,tmp_path/'first',base,tmp_path/'cache')
    with zipfile.ZipFile(archive)as z:manifest=z.read('DISTANCE_SUPPLEMENT_MANIFEST.json')
    delta=tmp_path/'delta.zip'
    with zipfile.ZipFile(delta,'w')as z:z.writestr('DISTANCE_SUPPLEMENT_MANIFEST.json',manifest)
    result=install_snapshot(delta,tmp_path/'second',base,tmp_path/'cache')
    assert result['new_objects']==0 and result['reused_objects']==1
    assert (tmp_path/'second/project/proof.json').read_bytes()==b'preserved'
    with pytest.raises(ValueError,match='missing_archive_and_cache'):
        install_snapshot(delta,tmp_path/'missing',base,tmp_path/'empty-cache')
