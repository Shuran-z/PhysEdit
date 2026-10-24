"""Search each failed source at its own seed, without forcing the other label."""
import collections
import copy
import gzip
import hashlib
import json
from scripts.export_original_boundary_distances import ROOT


def main():
    old=json.loads((ROOT/'five_scene_remaining_source_jobs_20261023.json').read_text())
    grids=collections.defaultdict(set)
    for scene,name in [('T01','t01_measured_published_events_20261019.json'),('T04','t04_measured_published_events.json'),('T05','t05_measured_published_events.json'),('T08','t08_measured_published_events.json')]:
        for row in json.loads((ROOT/name).read_text()):
            family=row['original_family']['family'] if scene=='T01' else row['family_id']
            theta=row['original_family'].get('theta') if scene=='T01' else row.get('theta')
            if family and theta is not None:grids[(scene,family,*row['sample_id'].split('__')[1:3])].add(theta)
    for line in (ROOT/'original_value_distance_ledger/t11_current_published_parameters.jsonl').read_text().splitlines():
        row=json.loads(line)
        if isinstance(row['theta'],(float,int)):grids[('T11',row['family_id'],*row['sample_id'].split('__')[1:3])].add(row['theta'])
    jobs=[]
    for original in old:
        for index,endpoint in enumerate(original['endpoints']):
            legacy=copy.deepcopy(original);legacy['seed_endpoint']=index
            config=copy.deepcopy(endpoint['config']);raw=json.dumps(config,sort_keys=True).encode()
            grid=sorted(grids[(original['scene_id'],original['family_id'],*endpoint['sample_id'].split('__')[1:3])]|set(original['bracket']))
            lo,hi=original['normalization_domain'];grid=[v for v in grid if lo<=v<=hi]
            job=dict(scene_id=original['scene_id'],family_id=original['family_id'],sample_id=endpoint['sample_id'],
                theta=endpoint['theta'],revision=endpoint['revision'],source_state_sha256=endpoint['state_sha256'],
                source_config_sha256=hashlib.sha256(raw).hexdigest(),base_config=config,original_pair_job=legacy,
                fixed_context_sha256=original['source_window']['fixed_context_sha256'],grid=grid,
                normalization_domain=[lo,hi],parameter_unit=config['experiment'].get('parameter',{}).get('parameter_unit','original_family_coordinate'),
                expected={original['target_event']:endpoint['label']},tolerance=original['tolerance'],
                renderer=original['renderer'],backend_sources=original['backend_sources'],probe_timeout_seconds=7200,
                source_config_origin='exact endpoint configuration embedded in frozen published refinement plan',
                grid_scope='released same-family background/gravity values, holding selected source configuration and seed')
            if original.get('auditor'):job['auditor']=original['auditor']
            jobs.append(job)
    groups=collections.defaultdict(list)
    for job in jobs:groups[(job['scene_id'],job['family_id'])].append(job)
    ordered=[]
    while any(groups.values()):
        for key in sorted(groups):
            if groups[key]:ordered.append(groups[key].pop(0))
    (ROOT/'five_scene_conditional_source_jobs_20261023.json.gz').write_bytes(gzip.compress(json.dumps(ordered).encode(),mtime=0))
    summary=dict(original_failed_intervals=len(old),source_jobs=len(jobs),by_scene=dict(collections.Counter(j['scene_id'] for j in jobs)),
        source_seed_changes=sum(j['endpoints'][0]['config'].get('random_seed')!=j['endpoints'][1]['config'].get('random_seed') or j['endpoints'][0]['config'].get('seed')!=j['endpoints'][1]['config'].get('seed') for j in old),
        original_intervals_and_labels_retained=True)
    (ROOT/'five_scene_conditional_source_preparation_20261023.json').write_text(json.dumps(summary,indent=2));print(json.dumps(summary))


if __name__=='__main__':main()
