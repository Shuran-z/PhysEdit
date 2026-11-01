"""Bind recovered original T19 intervals to exact current-release media.

Media equality or a reviewed exact-input replacement is required. This restores
numerical distances only; it does not grant missing event/normalization truth.
"""
import collections,copy,gzip,hashlib,json
from pathlib import Path
from physedit.boundary import distance
from scripts.export_original_boundary_distances import ROOT

def bind(originals,current,revision):
    index=collections.defaultdict(list)
    for r in current:index[(r['engine'],r['native_sample_id'])].append(r)
    out=[];unmatched=[]
    for old in originals:
        matched=[]
        for video in index[(old['engine'],old['sample_id'])]:
            prior=(old.get('videos') or {}).get(video['camera'],{}).get('sha256')
            if not prior:continue
            mode='exact_video_sha256'
            if prior!=video['sha256']:
                u=video.get('media_version_update',{})
                if not (u.get('previous_sha256')==prior and u.get('current_sha256')==video['sha256'] and u.get('input_config_bytes_identical') is True and u.get('new_media_hf_sha_verified') is True):continue
                mode='reviewed_updated_media_identical_source_inputs'
            facts={v[0]:v[1] for v in video.get('parameter_facts',[])}
            if old.get('parameter_name')=='impact_eccentricity':
                assert abs(facts['impact_eccentricity_m']-old['theta'])<1e-10
            matched.append({'video_id':video['video_id'],'camera':video['camera'],'video_sha256':video['sha256'],'download':video['download'],'match_method':mode})
        if not matched:
            unmatched.append({'sample_id':old['sample_id'],'family_id':old.get('family_id'),'reason':'no exact current media/input match'});continue
        row=copy.deepcopy(old);row.pop('distance_record_id',None)
        row.update(revision=revision,repo_id='phy2/phydataset',publication_status='current_release_bound_original_reference',current_release_binding_verified=True,current_release_videos=matched,original_boundary_source_revision=old.get('revision'),original_boundary_source_status=old.get('publication_status'),numerical_binding_only=True)
        # Normalization must come from the original declared domain, not selected samples.
        row['normalization_status']='original_domain_pending' if not row.get('normalization_span') else 'source_domain_recorded'
        row['binding_evidence']='exact camera hashes, or published reviewed input-identical media replacement; original measured bracket retained'
        out.append(row)
    return out,unmatched

def main():
    pointer=json.loads(Path('../release_72000_active/ACTIVE_CATALOG.json').read_text(encoding='utf8'))
    manifest=Path(pointer['manifest']);assert hashlib.sha256(manifest.read_bytes()).hexdigest()==pointer['manifest_sha256']
    with gzip.open(manifest,'rt',encoding='utf8') as f:current=[r for r in map(json.loads,f) if r['quota_scene']=='T19']
    source=ROOT/'original_value_distance_ledger/combined_distance_inputs.jsonl'
    originals=[r for r in map(json.loads,source.read_text(encoding='utf8').splitlines()) if r['scene_id']=='T19' and not r.get('current_release_binding_verified')]
    rows,unmatched=bind(originals,current,pointer['revision'])
    target=ROOT/'original_value_distance_ledger/t19_current_release_distances.jsonl'
    target.write_text(''.join(json.dumps(r)+'\n' for r in rows),encoding='utf8')
    summary={'current_release_revision':pointer['revision'],'original_records_checked':len(originals),'bound_original_records':len(rows),'bound_unique_trajectories':len({(r['engine'],r['sample_id']) for r in rows}),'bound_current_video_entries':len({v['video_id'] for r in rows for v in r['current_release_videos']}),'reviewed_updated_video_entries':len({v['video_id'] for r in rows for v in r['current_release_videos'] if v['match_method']!='exact_video_sha256'}),'unmatched_original_records':len(unmatched),'current_T19_video_entries':len(current),'formal_NearAcc_granted':False,'unmatched':unmatched}
    (ROOT/'t19_current_release_binding_summary_20261030.json').write_text(json.dumps(summary,indent=2),encoding='utf8')
    print(json.dumps({k:v for k,v in summary.items() if k!='unmatched'}))
if __name__=='__main__':main()
