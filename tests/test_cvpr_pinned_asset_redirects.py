"""Pinned downloads must support HF metadata without leaking hub credentials."""
import ast
import hashlib
from pathlib import Path
from types import SimpleNamespace
from urllib.parse import urljoin, urlsplit

import pytest


SOURCE = Path(__file__).resolve().parents[1]/'review/cvpr_experiments_20261031/cog_matched/stage_assets.py'


def downloader(tmp_path, requests):
    tree = ast.parse(SOURCE.read_text(encoding='utf8'))
    fn = next(x for x in tree.body if isinstance(x, ast.FunctionDef) and x.name == 'download')
    ns = dict(R=tmp_path, source=dict(repo='org/model', revision='frozen'),
              headers={'Authorization': 'Bearer TEST_ONLY'}, requests=requests,
              urljoin=urljoin, urlsplit=urlsplit, digest=lambda p: hashlib.sha256(p.read_bytes()).hexdigest(),
              update=lambda *a: None, time=SimpleNamespace(sleep=lambda n: None),
              shutil=SimpleNamespace(disk_usage=lambda p: SimpleNamespace(free=100*1024**3)))
    exec(compile(ast.Module(body=[fn], type_ignores=[]), str(SOURCE), 'exec'), ns)
    return ns['download']


def response(payload=b'', redirect=None):
    return SimpleNamespace(is_redirect=bool(redirect), headers={'Location': redirect}, status_code=302 if redirect else 200,
                           raise_for_status=lambda: None, close=lambda: None, iter_content=lambda n: iter([payload]))


def record(payload):
    return dict(path='transformer/config.json', size=len(payload), sha256=hashlib.sha256(payload).hexdigest())


def test_relative_hf_redirect_retains_credentials_only_on_hf(tmp_path):
    payload=b'{"pinned":true}';calls=[]
    def get(url, **kw):
        calls.append((url, kw))
        return response(redirect='/api/resolve-cache/models/org/model/frozen/config') if len(calls)==1 else response(payload)
    download=downloader(tmp_path,SimpleNamespace(get=get))
    download(record(payload))
    assert calls[1][0]=='https://huggingface.co/api/resolve-cache/models/org/model/frozen/config'
    assert calls[1][1]['headers']['Authorization']=='Bearer TEST_ONLY'
    assert (tmp_path/'models/base/transformer/config.json').read_bytes()==payload


def test_signed_cdn_request_never_receives_hf_token(tmp_path):
    payload=b'pinned weights';calls=[]
    class Direct:
        trust_env=True
        def get(self,url,**kw):
            calls.append((url,kw,self.trust_env));return response(payload)
    requests=SimpleNamespace(get=lambda *a,**k:response(redirect='https://cdn.aws.cdn.hf.co/model?SIGNED_TEST_ONLY'), Session=Direct)
    downloader(tmp_path,requests)(record(payload))
    assert calls[0][2] is False
    assert 'Authorization' not in calls[0][1]['headers']


def test_foreign_redirect_is_rejected_before_following(tmp_path):
    requests=SimpleNamespace(get=lambda *a,**k:response(redirect='https://foreign.invalid/model'))
    with pytest.raises(AssertionError, match='Unexpected weight CDN'):
        downloader(tmp_path,requests)(record(b'unused'))
    assert not (tmp_path/'models/base/transformer/config.json').exists()
