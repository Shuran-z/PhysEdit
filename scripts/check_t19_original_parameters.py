"""Compare published T19 parameter facts with the original saved render metadata."""
import concurrent.futures
import gzip
import json
import math
from pathlib import Path

ROOT=Path('/data_cached/wangzijun_p25/t19_review_20261029')


def check(row):
    sid=row['native_sample_id'];target=ROOT/'parameter_checks'/f'{sid}.json'
    if target.exists():return json.loads(target.read_text())
    meta=Path(row['local_source']).parent.parent/'metadata'/(sid+'__cam01.json.gz')
    d=json.load(gzip.open(meta,'rt'));spec={o['name']:o['spec'] for o in d['dynamic_objects']};errors=[]
    for key,value,unit in row['parameter_facts']:
        if key=='gravity':actual=math.sqrt(sum(x*x for x in d['experiment']['gravity_vector']))
        elif '.' in key:
            name,attr=key.split('.',1)
            if name not in spec:actual=None
            elif attr=='initial_speed':actual=math.sqrt(sum(v*v for v in spec[name].get('motion',{}).get('initial_velocity',[0,0,0])))
            else:actual=spec[name].get(attr)
        else:actual=d['experiment'].get(key)
        if actual is None or not math.isclose(float(actual),float(value),rel_tol=1e-7,abs_tol=1e-8):errors.append({'key':key,'catalog':value,'original':actual})
    finite=True;identities=True
    for f in d['frames']:
        identities &= set(o['name'] for o in f['objects'])==set(spec)
        for o in f['objects']:
            for key in ['position','velocity','quaternion_xyzw','angular_velocity']:finite &= all(math.isfinite(x) for x in o.get(key,[]))
    result={'sample':sid,'facts_checked':len(row['parameter_facts']),'mismatches':errors,'all_pose_motion_finite':finite,'actor_identity_stable_in_state':identities}
    target.write_text(json.dumps(result));return result


def main():
    import fcntl
    lock=open(ROOT/'parameter_check.lock','w');fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
    (ROOT/'parameter_checks').mkdir(exist_ok=True)
    rows={r['native_sample_id']:r for r in map(json.loads,(ROOT/'genesis1830.jsonl').read_text().splitlines())}
    results=[]
    with concurrent.futures.ProcessPoolExecutor(max_workers=12) as pool:
        for result in pool.map(check,rows.values()):
            results.append(result);(ROOT/'parameter_progress.json').write_text(json.dumps({'completed':len(results),'total':len(rows)}))
    (ROOT/'original_parameter_checks.json').write_text(json.dumps(results))
    summary={'groups':len(results),'facts_checked':sum(x['facts_checked'] for x in results),'groups_with_parameter_mismatch':sum(bool(x['mismatches']) for x in results),'nonfinite_groups':sum(not x['all_pose_motion_finite'] for x in results),'actor_identity_change_groups':sum(not x['actor_identity_stable_in_state'] for x in results),'first_mismatches':[x for x in results if x['mismatches']][:3]}
    (ROOT/'parameter_check_summary.json').write_text(json.dumps(summary,indent=2));print(json.dumps(summary))


if __name__=='__main__':main()
