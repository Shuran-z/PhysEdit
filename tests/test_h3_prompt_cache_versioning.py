import hashlib,json,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
from scripts import h3_new_prompt_common as c

def test_same_id_with_changed_bytes_uses_current_execution_clock(tmp_path):
    if hasattr(c.clock,'current'):delattr(c.clock,'current')
    (tmp_path/'CURRENT_CLOCKS.json').write_text(json.dumps({'v':{'physical_fps':24,'config_sha256':'newconfig'}}))
    row={'canonical_video_id':'v','sha256':'newvideo','config_download':{'sha256':'newconfig'},'external_control_inputs':{}}
    fps,proof=c.clock(row,{'v':{'sha256':'oldvideo'}},{'v':{'physical_frame_period_s':1/30}})
    assert fps==24 and proof['kind']=='hash_bound_current_executed_render_config'
    delattr(c.clock,'current')

def test_encoding_only_lineage_preserves_original_physical_seconds():
    row={'canonical_video_id':'v','sha256':'reencoded','current_render':{'encoding_compatibility':{'source_sha256':'original'}}}
    fps,proof=c.clock(row,{'v':{'sha256':'original'}},{'v':{'physical_frame_period_s':1/30}})
    assert fps==30 and proof['encoding_lineage_used']

def test_current_caption_is_hash_bound_and_source_clock_is_disclosed():
    texts=['Apply force during frames 0-47.']*3
    row={'canonical_video_id':'v','prompt_variants_en':texts,'prompt_variant_sha256':[hashlib.sha256(t.encode()).hexdigest() for t in texts]}
    _,text=c.caption(row,30)
    assert text.endswith('Frame indices use a 30 fps reference clock.')
    row['prompt_variant_sha256']=['stale']*3
    try:c.caption(row,30)
    except AssertionError:pass
    else:raise AssertionError('Stale text binding was accepted')

class CacheVersioningTests(unittest.TestCase):
    def test_changed_bytes(self):
        with tempfile.TemporaryDirectory() as folder, patch.object(c,'R',Path(folder)):
            test_same_id_with_changed_bytes_uses_current_execution_clock(Path(folder))
    def test_encoding_clock(self):
        test_encoding_only_lineage_preserves_original_physical_seconds()
    def test_caption_binding(self):
        test_current_caption_is_hash_bound_and_source_clock_is_disclosed()
if __name__=='__main__':unittest.main()
