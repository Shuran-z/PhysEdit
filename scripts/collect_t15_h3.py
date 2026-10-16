"""Import all four registered H3 attempts; export a neutral Qwen manifest."""
import argparse
import json
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from physedit.boundary import digest, media, read_rows, write_json, write_rows

EVENTS = ['book_contacts_laptop','laptop_crosses_support_boundary',
          'laptop_falls_to_floor','laptop_contacts_phone','phone_slides']

def collect(manifest, generated, out):
    rows = read_rows(manifest)
    expected = {f't15_h3_case{c:02d}_s{s}' for c in (1,2) for s in (41000,41001)}
    if {r['sample_id'] for r in rows} != expected:
        raise ValueError('expected the complete four-attempt roster')
    assets=Path(__file__).resolve().parents[1]/'examples/t15_h3'
    refs=json.loads((assets/'reference_provenance.json').read_text())
    out=Path(out).resolve();out.mkdir(parents=True,exist_ok=False)
    inputs=[];keys=[];obs=[];qwen=[];templates=[]
    for row in rows:
        sid=row['sample_id'];case=1 if '_case01_' in sid else 2;ref=refs[case-1]
        events={e:int(ref['event_frames'][e] is not None and
                      29 <= ref['event_frames'][e] <= 29+5.125*30) for e in EVENTS}
        assert list(events.values()) == ref['events']
        inputs.append(dict(sample_id=sid,seed=row['seed'],evaluation_duration_s=5.125))
        keys.append(dict(sample_id=sid,scene_id='T15',source_group_id=ref['speed_context_hash'],
            family_id='basic_velocity_probe',point_id=f'case{case:02d}',theta=ref['speed'],
            target_event=EVENTS[2],events=events,required_order=list(zip(EVENTS,EVENTS[1:])),
            pair_ids=['basic_two_sides'],pairing_mode='coupled_seed',gravity=9.81,
            inversion=dict(status='not_applicable' if case==1 else 'pending_reference_validation',
                           reason='reference_no_fall' if case==1 else 'no_frozen_T15_inversion_registration'),
            boundary=dict(status='unavailable'),reference_sample_id=ref['sample_id'],
            reference_state_sha256=ref['state_sha256']))
        path=Path(generated).resolve()/'full/generated'/sid/row['prompt_granularity']/'generated_video_resized_to_source.mp4'
        try:
            observed=dict(sample_id=sid,**media(path,dict(row,output_fps=24)))
            qwen.append(dict(sample_id=sid,video=str(path),sha256=observed['video_sha256'],start_frame=0,duration_s=5.125))
        except (OSError,ValueError,ImportError) as exc:
            observed=dict(sample_id=sid,status='generation_failure',reason=str(exc))
        obs.append(observed)
        templates.append(dict(sample_id=sid,video_sha256=observed.get('video_sha256'),method='unannotated',
                              events={e:None for e in EVENTS},event_times_s={},evidence=''))
    write_rows(out/'inputs.jsonl',inputs);write_rows(out/'answers.jsonl',keys)
    write_rows(out/'observed_rows.jsonl',obs);write_rows(out/'event_annotation_template.jsonl',templates)
    write_json(out/'registered.json',dict(model='minimax_h3_fl2va',source_manifest_sha256=digest(manifest),
               reference_provenance_sha256=digest(assets/'reference_provenance.json'),
               importer_sha256=digest(__file__),scope='basic development probe, not NearAcc'))
    write_json(out/'snapshot_hashes.json',{n:digest(out/n) for n in ('inputs.jsonl','answers.jsonl','registered.json')})
    (out/'qwen').mkdir();write_rows(out/'qwen/inputs.jsonl',qwen)
    print(json.dumps(dict(registered=4,media_ok=len(qwen),failed=4-len(qwen))))

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--manifest',required=True)
    p.add_argument('--generated',required=True);p.add_argument('--out',required=True)
    a=p.parse_args();collect(a.manifest,a.generated,a.out)
