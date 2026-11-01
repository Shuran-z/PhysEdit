"""Apply immutable source/event/window-matched follow-up evidence, never labels."""
import copy,hashlib

def apply_updates(cases,supplement,root,evidence):
    for rel,h in supplement['evidence_sha256'].items():
        path=(root/rel).resolve()
        assert path.is_relative_to(root.resolve()) and hashlib.sha256(path.read_bytes()).hexdigest()==h
        evidence[rel]=h
    for update in supplement['updates']:
        old=cases[update['clip_id']]
        assert old['sample_id']==update['sample_id']
        assert old['reference_video_sha256']==update['reference_video_sha256']
        assert old['reference_release_version']==update['reference_release_version']
        old.update(copy.deepcopy(update))
