"""Read current T11 released coordinates and rendering stars, retaining force recipes."""
import collections
import json
from pathlib import Path

from scripts.export_original_boundary_distances import distances

ROOT=Path('review/scene_family_completion_20261018')


def main():
    selection={r['sample_id']:r for r in json.loads((ROOT/'t11_latest_selection_20261019.json').read_text(encoding='utf-8'))}
    release=json.loads((ROOT/'new_release_manifests_20261019.json').read_text(encoding='utf-8'))[0]
    params=[];groups=collections.defaultdict(list)
    for path in ROOT.glob('t11_latest_*_evidence_20261019.json'):
        for r in json.loads(path.read_text(encoding='utf-8')):
            f=next(f for f in r['files'] if '/configs/' in f['archive_path']);c=f['data'];e=c['experiment'];design=e['formal_design'];p=e['parameter'];published=selection[r['sample_id']]
            videos={m['camera_id']:dict(archive=published['shard'],member=m['video'],sha256=next(f['sha256'] for f in published['files'] if f['archive_path']==m['video'])) for m in published['media']}
            row=dict(scene_id='T11',engine='genesis',sample_id=r['sample_id'],repo_id='phy2/phydataset',revision=release['revision'],release='data/T11/genesis_720p_reconciled_20261017',
                videos=videos,background=e['background_id'],gravity=e['gravity_id'],family_id=design['changed_variable'],parameter_name=p['parameter_name'],theta=p['parameter_value'],parameter_unit=p['parameter_unit'],
                original_branch=design['boundary_role'],original_metadata_path=f['path'],original_config_sha256=f['sha256'],actual_parameter_recipe=p,runtime_forces=c.get('runtime_forces',[]),
                extra_validation_separate=True,coordinate_note='Declared historical coordinate may parameterize a force recipe; actual initial velocity and forces retained explicitly.')
            params.append(row)
            if design['boundary_role'] in ['theta_minus','theta_star','theta_plus']:groups[(e['background_id'],e['gravity_id'],design['changed_variable'])].append(row)
    stars=[];conflicts=[]
    for key,rows in groups.items():
        centres={r['theta'] for r in rows if r['original_branch']=='theta_star'}
        if len(centres)!=1:conflicts.append(dict(context=key,centres=sorted(centres)));continue
        centre=next(iter(centres))
        for r in rows:stars.append({**r,'original_rendering_star':centre,'reference_kind':'recorded_rendering_star_not_automatically_a_solved_boundary',**distances(r['theta'],point=centre)})
    out=ROOT/'original_value_distance_ledger';out.mkdir(exist_ok=True)
    for name,rows in [('t11_current_published_parameters.jsonl',params),('t11_recorded_rendering_star_distances.jsonl',stars)]:
        (out/name).write_text(''.join(json.dumps(r,ensure_ascii=False)+'\n' for r in rows),encoding='utf-8')
    summary=dict(published_parameters=len(params),star_distance_samples=len(stars),contexts=len(groups),families=dict(collections.Counter(r['family_id'] for r in stars)),conflicts=conflicts)
    (out/'t11_binding_summary.json').write_text(json.dumps(summary,indent=2));print(json.dumps(summary))


if __name__=='__main__':main()
