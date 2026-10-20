import copy
import gzip
import hashlib
import json
from scripts.collect_t16_t20_published_events import extract
from scripts.register_t09_table_contact_events import final_event, TABLE
from scripts.register_t16_t20_contact_distances import context


def test_t09_settling_without_upper_book_table_contact_is_not_positive():
    c={'experiment':{'supported_book_names':['t09_book_04','t09_book_05']}}
    pairs=[['t09_book_03','t09_book_04'],['t09_book_04','t09_book_05']]
    assert final_event(c,pairs,pairs)['reference_label']==0
    result=final_event(c,pairs,pairs+[[TABLE,'t09_book_05']])
    assert result=={'reference_label':1,'upper_books_on_table':['t09_book_05']}


def test_contact_context_masks_only_intervention_and_keeps_mass_and_revision():
    a={'scene_id':'T20','revision':'release-a','experiment':{'parameter':{'parameter_name':'book_drive_speed'},'book_drive_speed':1.0},
       'actors':[{'name':'t20_book','spec':{'motion':{'initial_velocity':[1.,0.,0.]},'mass':.4}}],
       'scene_overrides':{'gravity':[0.,0.,-9.81]},'render':{'fps':30,'frames':210}}
    b=copy.deepcopy(a);b['actors'][0]['spec']['motion']['initial_velocity'][0]=2.;b['experiment']['book_drive_speed']=2.
    assert context(a)==context(b)
    b['actors'][0]['spec']['mass']=.5
    assert context(a)!=context(b)
    b=copy.deepcopy(a);b['revision']='release-b'
    assert context(a)!=context(b)


def test_original_64_character_filename_is_not_a_hf_blob_hash(tmp_path):
    sid='s'*49
    filename=sid+'__cam01.json.gz'
    assert len(filename)==64
    p=tmp_path/'production'/sid/'metadata'/filename;p.parent.mkdir(parents=True)
    state={'experiment':{'trajectory_id':sid},'frames':[{'frame_index':0,'contacts':[],'objects':[]}],
           'dynamic_objects':[],'render':{},'scene_overrides':{}}
    raw=gzip.compress(json.dumps(state).encode());p.write_bytes(raw)
    row={'sample_id':sid,'repo_id':'a/b','revision':'rev','sidecar_paths':['released.gz'],'event_id':'T17','videos':{}}
    expected={'released.gz':{'sha256':hashlib.sha256(raw).hexdigest()}}
    result=extract(row,tmp_path/'cache',release_hashes=expected,production=tmp_path/'production')
    assert result['hash_verified']
    assert all(c['occurred'] is None for c in result['contacts'])
