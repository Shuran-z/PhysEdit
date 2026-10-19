"""Recover actual T12 joint-grid slices, without inventing A/B/C families."""
import collections,json
from pathlib import Path
ROOT=Path('review/scene_family_completion_20261018')

def main():
    points={}
    for path in sorted(ROOT.glob('published_batch_*.json')):
        for record in json.loads(path.read_text(encoding='utf-8')):
            config=record.get('config',{});exp=config.get('experiment',{});sid=exp.get('trajectory_id','')
            if not sid.startswith('T12F880R002__'):continue
            physics=exp['controlled_physics']
            values=dict(speed=physics['stapler']['initial_velocity_mps'][0],friction=physics['stapler']['friction'],target_mass=physics['tissue_box']['mass_kg'])
            point=dict(sample_id=sid,background=exp['background_id'],gravity=exp['gravity_id'],values=values,random_seed=exp.get('random_seed'),revision=record['revision'],source=record['path'],source_sha256=record['sha256'])
            if sid in points and points[sid]['values']!=values:raise ValueError('published T12 parameter conflict')
            points[sid]=point
    result=[]
    for axis in ['speed','friction','target_mass']:
        groups=collections.defaultdict(list)
        for p in points.values():
            fixed=tuple(sorted((k,v) for k,v in p['values'].items() if k!=axis))
            groups[(p['background'],p['gravity'],fixed)].append(p)
        for (bg,g,fixed),rows in sorted(groups.items()):
            rows.sort(key=lambda p:p['values'][axis])
            result.append(dict(axis=axis,background=bg,gravity=g,fixed_parameter_values=dict(fixed),points=rows,distinct_parameter_values=len({r['values'][axis] for r in rows}),distinct_random_seeds=len({r['random_seed'] for r in rows}),status='actual_parameter_slice_event_boundary_unfinished'))
    (ROOT/'t12_parameter_slices.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
    summary=dict(published_configs=len(points),by_axis={axis:dict(slices=sum(r['axis']==axis for r in result),multi_value_slices=sum(r['axis']==axis and r['distinct_parameter_values']>=2 for r in result),multi_value_single_seed_slices=sum(r['axis']==axis and r['distinct_parameter_values']>=2 and r['distinct_random_seeds']==1 for r in result)) for axis in ['speed','friction','target_mass']})
    (ROOT/'t12_parameter_slices_summary.json').write_text(json.dumps(summary,indent=2),encoding='utf-8');print(json.dumps(summary))

if __name__=='__main__':main()
