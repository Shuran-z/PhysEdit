"""Resolve private pinned HF objects to short-lived CDN URLs; never store video bytes."""
import hashlib
import re
import threading
import time
import urllib.error
import urllib.request
import ssl
from pathlib import Path
from urllib.parse import quote, urlparse

REPOSITORY='phy2/phy2-benchmark-generations'


class MediaUnavailable(Exception):
    """Temporary transport failure; never a video quality judgment."""


def validate_remote(t):
    r=t.get('remote_media',{})
    if r.get('repository')!=REPOSITORY or not re.fullmatch(r'[0-9a-f]{40}',r.get('revision','')):
        raise ValueError('远程媒体须绑定指定HF仓库和固定提交')
    if r.get('path')!=f"videos/seed{t['seed']}/annotation{t['prompt_variant']}/{t['model']}/{t['clip_id']}.mp4":
        raise ValueError('远程媒体路径与任务身份不一致')
    if not re.fullmatch(r'[0-9a-f]{64}',t.get('video_sha256','')) or r.get('lfs_sha256')!=t['video_sha256']:
        raise ValueError('HF LFS媒体哈希未绑定')
    if type(r.get('size')) is not int or r['size']<=0:raise ValueError('HF媒体大小未登记')
    if r.get('verification')!='pinned_hf_lfs_metadata':raise ValueError('远程媒体核验来源缺失')


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self,*args):return None


class Resolver:
    def __init__(self,data_dir):
        self.token_file=Path(data_dir)/'hf_read_token'
        self.proxy_file=Path(data_dir)/'hf_proxy_url'
        self.cache={};self.lock=threading.Lock()

    def url(self,task):
        validate_remote(task);r=task['remote_media'];key=(r['revision'],r['path'],task['video_sha256'])
        with self.lock:
            old=self.cache.get(key)
            if old and old[0]>time.time():return old[1]
        token=self.token_file.read_text().strip()
        u=f"https://huggingface.co/datasets/{REPOSITORY}/resolve/{r['revision']}/{quote(r['path'],safe='/')}"
        handlers=[NoRedirect()]
        if self.proxy_file.is_file():
            proxy=self.proxy_file.read_text().strip()
            if not proxy.startswith(('http://','https://')):raise ValueError('HF代理配置格式无效')
            handlers.append(urllib.request.ProxyHandler({'https':proxy}))
        opener=urllib.request.build_opener(*handlers)
        for attempt in range(3):
            try:
                response=opener.open(urllib.request.Request(u,method='HEAD',headers={'Authorization':'Bearer '+token,'Cache-Control':'no-cache'}),timeout=7)
                response.close();raise ValueError('HF未提供直接播放地址')
            except urllib.error.HTTPError as e:
                if e.code in (429,500,502,503,504):
                    e.close()
                    if attempt==2:raise MediaUnavailable('视频源连接暂时失败，请重试播放；标注记录已保留') from None
                    time.sleep(.5*(attempt+1));continue
                if e.code not in (302,303,307):
                    e.close();raise ValueError('HF播放地址暂不可用：'+str(e.code)) from None
                location=e.headers.get('Location','');etag=e.headers.get('X-Linked-Etag','').strip('"')
                size=e.headers.get('X-Linked-Size','0');e.close()
                if etag!=task['video_sha256'] or int(size)!=r['size']:
                    raise ValueError('HF固定版本媒体身份已改变')
                break
            except (urllib.error.URLError,TimeoutError,ConnectionError,ssl.SSLError):
                if attempt==2:raise MediaUnavailable('视频源连接暂时失败，请重试播放；标注记录已保留') from None
                time.sleep(.5*(attempt+1))
        parsed=urlparse(location)
        if parsed.scheme!='https' or not parsed.hostname or not (parsed.hostname.endswith('.hf.co') or parsed.hostname.endswith('.xethub.hf.co')):
            raise ValueError('HF播放重定向域名不在允许范围')
        with self.lock:self.cache[key]=(time.time()+300,location)
        return location
