import importlib.util
from pathlib import Path
import urllib.error
import urllib.request

import pytest


PATH=Path(__file__).resolve().parents[1]/'review/cvpr_experiments_20261031/h3_queue_recovery/feature_transport/transport_retry.py'
SPEC=importlib.util.spec_from_file_location('h3_transport_retry',PATH)
MODULE=importlib.util.module_from_spec(SPEC);SPEC.loader.exec_module(MODULE)


class Fake:
    def __init__(self,errors):self.errors=list(errors);self.requests=[]
    def open(self,request,**kwargs):
        self.requests.append(request)
        if self.errors:raise self.errors.pop(0)
        return 'ack'


def test_timed_out_cache_put_retries_identical_digest_bound_payload():
    req=urllib.request.Request('http://localhost/cache/h3/sample.pt',data=b'exact-cache',method='PUT',headers={'X-Content-SHA256':'digest'})
    inner=Fake([TimeoutError(),ConnectionResetError()]);wait=[]
    assert MODULE.ResilientOpener(inner,sleep=wait.append).open(req)=='ack'
    assert len(inner.requests)==3 and all(r is req and r.data==b'exact-cache'for r in inner.requests)
    assert wait==[1,2]


@pytest.mark.parametrize('status',[403,404,409])
def test_authorization_missing_or_conflicting_cache_is_not_retried(status):
    error=urllib.error.HTTPError('http://localhost/cache/h3/sample.pt',status,'stop',{},None)
    inner=Fake([error]);req=urllib.request.Request(error.url,method='HEAD')
    with pytest.raises(urllib.error.HTTPError):MODULE.ResilientOpener(inner,sleep=lambda _:None).open(req)
    assert len(inner.requests)==1


def test_mutable_frontier_put_is_not_retried():
    inner=Fake([TimeoutError()]);req=urllib.request.Request('http://localhost/frontier/h3',data=b'old-step',method='PUT')
    with pytest.raises(TimeoutError):MODULE.ResilientOpener(inner,sleep=lambda _:None).open(req)
    assert len(inner.requests)==1
