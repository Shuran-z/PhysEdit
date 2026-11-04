"""Attach new source/repeat evidence without turning failed repeats into roots."""
import argparse
import copy
import hashlib
import json
from pathlib import Path

from physedit.core100_bindings import interval_distance
from physedit.core100_critical import load,primary,sha

ROOT=Path(__file__).resolve().parents[1]
WORK=ROOT/'review/core100_v2_resolution_20261102'


def read(p):return json.loads(Path(p).read_text(encoding='utf8'))


def proof(name):
    pointer=read(WORK/name);path=ROOT/pointer['path']
    if sha(path)!=pointer['sha256']:raise ValueError('resolution_source_changed:'+name)
    return read(path),path


def apply_t04_repeat_evidence(data,source,repeats):
    result=copy.deepcopy(data);row=next(c for c in result['cases']if c['clip_id']=='T04_C02')
    if (source['native_stored_sha256']!=row['reference_native_state_binding']['stored_state_sha256']
            or source['native_decoded_sha256']!=row['reference_native_state_binding']['decoded_state_sha256']
            or not source['source_physical_contract_attested']
            or source['saved_source_seed']!=source['base_config_seed']):
        raise ValueError('t04_source_physical_identity_unattested')
    rows=repeats['rows']
    if len(rows)!=2 or any(p.get('status')!='completed' or not p.get('physical_input_seed_solver_and_clock_verified')
                           or p['theta']!=.125 or p['original_seed']!=source['saved_source_seed'] for p in rows):
        raise ValueError('t04_repeat_evidence_incomplete')
    # This application is deliberately restricted to the observed failed
    # endpoint. Opposite, unknown or heterogeneous new evidence needs a fresh
    # admission decision, not a canned success/failure response.
    labels=[p['measurement']['label']for p in rows]
    if labels!=[0,0]:raise ValueError('t04_repeat_pattern_requires_new_decision')
    prior=copy.deepcopy(row['critical_units'])
    for b in row['boundary_records']:
        if any(abs(theta-.125)<1e-12 for theta in b['bracket']):
            b['endpoint_repeatability']=dict(status='not_reproduced',theta=.125,observed_labels=[1]+labels,
                original_expected_label=1,new_original_GPU_repeats=len(rows),
                wrong_parameter_or_seed_not_inferred=True)
    allowed=[b['bracket']for b in row['boundary_records']if b.get('endpoint_repeatability',{}).get('status')!='not_reproduced']
    if not allowed:raise ValueError('t04_requires_explicit_unresolved_unit_migration')
    for unit in row['critical_units']:
        distances=[interval_distance(unit['theta'],b,unit['normalization_span'])for b in allowed]
        low,high=[min(d['normalized_absolute_interval'][i]for d in distances)for i in [0,1]]
        unit.update(intervals=allowed,normalized_absolute_interval=[low,high],
                    bin='near'if high<=.05 else'mid'if low>.05 and high<=.15 else'far'if low>.15 else None,
                    rgb_distance_admitted=False,rgb_blockers=['original_GPU_endpoint_instability'],
                    numerical_evidence_status='remaining_unrepeated_candidates_after_failed_endpoint_repeats')
    row['source_physical_contract_binding']=source
    row['original_endpoint_instability']=dict(theta=.125,labels=[1]+labels,repeats=rows,
        previous_numerical_units=prior,reference_video_and_label_preserved=True,
        no_full_trajectory_equivalence_claim=True,deterministic_boundary_admitted=False)
    row['distance_admission_pending_reason']='原物理输入和seed=1212927170已核对。0.125原正端两次新复跑均为负，同参数三次结果为1/0/0；相关候选区间已拦截，剩余候选未当作稳定边界。'
    result['summary']['numerical_near_cases']=sum(primary(c)['bin']=='near'for c in result['cases'])
    return result


def main():
    p=argparse.ArgumentParser();p.add_argument('--expected-active-sha256',required=True);args=p.parse_args()
    data,path=load();assert sha(path)==args.expected_active_sha256
    source,source_path=proof('T04_SOURCE_CONTRACT.json');repeats,repeat_path=proof('T04_RECHECK_COLLECT.json')
    updated=apply_t04_repeat_evidence(data,source,repeats)
    source_files=[source_path,repeat_path,Path(__file__),ROOT/'scripts/audit_core100_v2_t04_source_contract.py',ROOT/'scripts/recheck_core100_v2_t04_original_gpu.py']
    t10_path=ROOT/'review/core100_v3_remaining8_20261103/T10_C05_PHYSICAL_CONFIG_SEARCH.json'
    t10=read(t10_path);row=next(c for c in updated['cases']if c['clip_id']=='T10_C05')
    row['additional_physical_config_search']=dict(configs_read=t10['configs_read'],exact_matches=len(t10['exact_physical_object_matches']),
        scope='Bounded p25 current and production_OLD_bak T10 Earth configuration search; no proof all archives were exhausted.')
    source_files.append(t10_path)
    out=path.parent
    for source_file in source_files:
        digest=sha(source_file);target=out/'sources'/(digest+source_file.suffix)
        if target.exists():assert sha(target)==digest
        else:target.write_bytes(source_file.read_bytes())
        updated['source_hashes'][target.relative_to(ROOT).as_posix()]=digest
    updated['resolution_previous_registry']=dict(path=path.relative_to(ROOT).as_posix(),sha256=sha(path))
    assert updated['input_bindings']==data['input_bindings']and updated['pairs']==data['pairs']
    raw=json.dumps(updated,ensure_ascii=False,indent=2).encode();digest=hashlib.sha256(raw).hexdigest();new_path=out/('registry_'+digest[:12]+'.json');new_path.write_bytes(raw)
    load(new_path,digest)
    pointer=ROOT/'catalog/active_core100_critical_protocol.json';current=read(pointer)
    if current['registry_sha256']!=args.expected_active_sha256:raise ValueError('critical_pointer_changed_concurrently')
    previous=out/'previous_pointers';previous.mkdir(exist_ok=True)
    (previous/(current['registry_sha256']+'.json')).write_bytes(pointer.read_bytes())
    current.update(registry='../'+new_path.relative_to(ROOT).as_posix(),registry_sha256=digest)
    pointer.write_text(json.dumps(current,indent=2),encoding='utf8')
    lines=['# Core100临界点评测当前接入','',f"已接入 {updated['summary']['critical_rgb_distance_cases']}/100；Near参考 {updated['summary']['admitted_near_cases']} 条。",'',
           '|场景|已接入|待完成|','|---|---:|---:|']
    for i in range(1,21):
        n=sum(primary(c)['rgb_distance_admitted']for c in updated['cases']if c['scene_id']==f'T{i:02}')
        lines.append(f'|T{i:02}|{n}|{5-n}|')
    lines+=['','## 未完成项','']
    for c in updated['cases']:
        if not primary(c)['rgb_distance_admitted']:
            lines.append('- '+c['clip_id']+'：'+str(c.get('distance_admission_pending_reason')or c.get('rgb_pending_reason')or primary(c)['rgb_blockers']))
    (out/'STATUS.md').write_text('\n'.join(lines)+'\n',encoding='utf8')
    print(json.dumps(dict(registry=new_path.as_posix(),sha256=digest,formal=updated['summary']['critical_rgb_distance_cases'],
        T04_seed_recovered=True,T04_failed_repeats_retained=[1,0,0],frozen_inputs_changed=False)))


if __name__=='__main__':main()
