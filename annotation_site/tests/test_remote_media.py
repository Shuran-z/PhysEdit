import io
import sys
import tempfile
import unittest
import urllib.error
from pathlib import Path
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from remote_media import Resolver, MediaUnavailable, REPOSITORY


class RemoteMediaTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        Path(self.tmp.name, 'hf_read_token').write_text('test-only-token')
        self.resolver = Resolver(self.tmp.name)
        self.task = dict(seed=1, prompt_variant=1, model='test', clip_id='T15_C01',
                         video_sha256='a'*64, remote_media=dict(repository=REPOSITORY,
                         revision='b'*40, path='videos/seed1/annotation1/test/T15_C01.mp4',
                         lfs_sha256='a'*64, size=100, verification='pinned_hf_lfs_metadata'))

    def tearDown(self):
        self.tmp.cleanup()

    def redirect(self, sha='a'*64):
        return urllib.error.HTTPError('https://huggingface.co/test', 302, 'redirect',
            {'Location':'https://cdn-lfs.hf.co/test', 'X-Linked-Etag':sha,
             'X-Linked-Size':'100'}, io.BytesIO())

    @patch('remote_media.time.sleep')
    @patch('remote_media.urllib.request.build_opener')
    def test_transient_tls_retry_then_verified_cache(self, build, sleep):
        opener = build.return_value
        opener.open.side_effect = [urllib.error.URLError('TLS EOF'), self.redirect()]
        self.assertEqual(self.resolver.url(self.task), 'https://cdn-lfs.hf.co/test')
        self.assertEqual(self.resolver.url(self.task), 'https://cdn-lfs.hf.co/test')
        self.assertEqual(opener.open.call_count, 2)

    @patch('remote_media.time.sleep')
    @patch('remote_media.urllib.request.build_opener')
    def test_exhaustion_is_unavailable_not_quality_failure(self, build, sleep):
        build.return_value.open.side_effect = urllib.error.URLError('TLS EOF')
        with self.assertRaises(MediaUnavailable):self.resolver.url(self.task)
        self.assertEqual(build.return_value.open.call_count, 3)
        self.assertEqual(self.resolver.cache, {})

    @patch('remote_media.urllib.request.build_opener')
    def test_identity_mismatch_never_retried_or_cached(self, build):
        build.return_value.open.side_effect = self.redirect('c'*64)
        with self.assertRaises(ValueError):self.resolver.url(self.task)
        self.assertEqual(build.return_value.open.call_count, 1)
        self.assertEqual(self.resolver.cache, {})


if __name__ == '__main__':unittest.main()
