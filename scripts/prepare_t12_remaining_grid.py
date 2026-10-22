"""Expand T12 missing/no-flip slices on the actual released parameter grid."""
import collections
import gzip
import hashlib
import json
from scripts.export_original_boundary_distances import ROOT
from scripts.supplement_t12_published_boundaries import AXES,fixed_context,measure


def main():
    configs={};states={}
    with gzip.open(ROOT/'t12_latest_verified_records_20261019.jsonl.gz','rt',encoding='utf-8') as stream:
        for line in stream:
            r=json.loads(line)
            if '/configs/' in r['path']:configs[r['data']['sample_id']]=r
            elif '/metadata_shared/' in r['path']:
                sid=r['path'].rsplit('/',1)[-1].removesuffix('.gz').removesuffix('.json');states[sid]=dict(sha256=r['sha256'],label=int(measure(r['data']['frames'])>=.01))
    pending=json.loads((ROOT/'t12_conditional_slices_without_flip.json').read_text());groups=collections.defaultdict(list);domains=collections.defaultdict(set)
    revisions={m['sample_id']:m['revision'] for m in map(json.loads,(ROOT/'current_release_parameter_bindings_20261019.jsonl').read_text().splitlines()) if m['scene']=='T12'}
    for sid,r in configs.items():
        for axis,path in AXES.items():
            value={o['name']:o for o in r['data']['dynamic_objects']}
            for k in path:value=value[k]
            groups[(axis,fixed_context(r['data'],axis))].append(dict(sample_id=sid,theta=value,reference_label=states[sid]['label'],state_sha256=states[sid]['sha256'],config_sha256=r['sha256']))
            domains[axis].add(value)
    jobs=[]
    for p in pending:
        axis=p['axis'];members=sorted(groups[(axis,p['fixed_context_sha256'])],key=lambda x:(x['theta'],x['sample_id']))
        if sorted(p['samples'])!=sorted(m['sample_id'] for m in members):raise ValueError('pending slice membership changed')
        grid=sorted(domains[axis]);base=members[0]
        jobs.append(dict(job_id=hashlib.sha256(('t12_remaining_grid_v1:'+axis+':'+p['fixed_context_sha256']).encode()).hexdigest()[:24],
            axis=axis,fixed_context_sha256=p['fixed_context_sha256'],members=members,base_config=configs[base['sample_id']]['data'],
            grid=grid,normalization_domain=[grid[0],grid[-1]],target_event='tissue_box_max_displacement_ge_1cm',threshold_m=.01,
            revision=revisions[base['sample_id']],
            prior_reason=p['reason'],reference_kind='supplemental_original_backend_grid_not_recovered_original_search'))
    # Round-robin axes, then distribute to avoid starving mass/friction behind speed scans.
    queues=collections.defaultdict(list)
    for j in jobs:queues[j['axis']].append(j)
    ordered=[]
    while any(queues.values()):
        for axis in AXES:
            if queues[axis]:ordered.append(queues[axis].pop(0))
    (ROOT/'t12_remaining_grid_plan_20261022.json').write_text(json.dumps(ordered))
    print(json.dumps(dict(planned=len(jobs),by_axis=dict(collections.Counter(j['axis'] for j in jobs)),released_grids={k:sorted(v) for k,v in domains.items()})))


if __name__=='__main__':main()
