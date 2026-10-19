"""Compare completed original-backend probes against immutable published states."""
import gzip,hashlib,json,math
from pathlib import Path
from scripts.audit_t04_completion_states import measure

ROOT=Path('review/scene_family_completion_20261018')

def main():
    rows=[]
    for theta,branch,filename in [(.105,'star','t04_probe_0105_state.json'),(.14,'plus','t04_probe_014_state.json')]:
        replay_path=ROOT/(filename+'.gz')
        if not replay_path.exists():continue
        sid=f'T04F880V1__bg01_home_ase__g01_moon__cf_stack_sliding_{branch}__rep01'
        reference_path=ROOT/'completion_states/T04'/(sid+'.json.gz')
        actual=json.loads(gzip.decompress(replay_path.read_bytes()));reference=json.loads(gzip.decompress(reference_path.read_bytes()))
        if len(actual['frames'])!=len(reference['frames']):raise ValueError('incomplete replay')
        errors=[];by_object={}
        for a,b in zip(actual['frames'],reference['frames']):
            aa={o['name']:o for o in a['objects']};bb={o['name']:o for o in b['objects']}
            if aa.keys()!=bb.keys():raise ValueError('object identities differ')
            for n in aa:
                error=math.dist(aa[n]['position'],bb[n]['position']);errors.append(error)
                by_object[n]=max(by_object.get(n,0),error)
        measured=measure(actual);truth=measure(reference)
        rows.append(dict(theta=theta,reference_id=sid,frames=len(actual['frames']),reference_sha256=hashlib.sha256(reference_path.read_bytes()).hexdigest(),probe_sha256=hashlib.sha256(replay_path.read_bytes()).hexdigest(),reference_events=truth['events'],probe_events=measured['events'],reference_metrics=truth['metrics'],probe_metrics=measured['metrics'],event_labels_match=truth['events']==measured['events'],max_position_error_m=max(errors),mean_position_error_m=sum(errors)/len(errors),max_position_error_by_object_m=by_object,status='replay_comparison_not_visual_admission'))
    (ROOT/'t04_backend_release_comparison.json').write_text(json.dumps(rows,indent=2),encoding='utf-8')
    print(json.dumps(rows))

if __name__=='__main__':main()
