"""Bind author-approved T08 refinement, with its numerical profile explicit.

Read and verify existing states; never change inputs, labels or launch physics.
Search-bracket width is not presented as a confidence interval on the original
GPU/real-world threshold. Non-target source-event differences remain explicit.
"""
import argparse
import copy
import hashlib
import json
from pathlib import Path

from physedit.core100_critical import load
from review.cvpr_experiments_20261031.archive_hunyuan_checkpoint_sftp import rpc,SG_OPTIONS,SG

ROOT=Path(__file__).resolve().parents[1];WORK=ROOT/'review/core100_v2_resolution_20261102'
REMOTE=r'''
import copy,gzip,hashlib,json,math
from pathlib import Path
root=Path('/data/yangkaiyuan/core100_t08_published_context_v7_20261029')
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
for name,digest in EXPECTED.items():assert sha(root/name)==digest,(name,'changed remote artifact')
jobs=json.loads((root/'t08_jobs.json').read_text());job=next(j for j in jobs if j['clip_id']==CID)
report=json.loads((root/'searches'/CID/'result.json').read_text());base=job['base_config']
assert report['status']=='conditional_core_search_completed'and not report['invalid_probes']and not report['unresolved_intervals']
actor='t08_lower_impactor_book';names=['t08_lower_impactor_book','t08_upper_payload_book','t08_target_mug']
renderer=root/'renderer_t08_aggregate_cpu64.py';text=renderer.read_text()
assert "precision='64'"in text and 'backend=stage06.gs.cpu'in text
points=[];source_positions=None;repeat_error=None
for point,kind in[(p,'point')for p in report['probes']]+[(report['source_repeat'],'source_repeat')]:
 path=Path(point['state_path']);raw=gzip.decompress(path.read_bytes());assert hashlib.sha256(raw).hexdigest()==point['state_sha256']
 cfgpath=path.parent/'config.json';assert sha(cfgpath)==point['config_sha256'];cfg=json.loads(cfgpath.read_text());s=json.loads(raw)
 assert point['renderer_sha256']==sha(renderer)
 expected=copy.deepcopy(base['dynamic_objects']);obj=next(o for o in expected if o['name']==actor)
 vector=obj['motion']['initial_velocity'];norm=math.sqrt(sum(v*v for v in vector));assert abs(norm-job['theta'])<1e-9
 obj['motion']['initial_velocity']=[v*point['theta']/norm for v in vector]
 assert cfg['dynamic_objects']==expected
 assert {o['name']:o.get('spec',o)for o in s['dynamic_objects']}=={o['name']:o for o in expected}
 assert cfg.get('runtime_forces')==base.get('runtime_forces')
 assert cfg['seed']==base['seed']and cfg['random_seed']==base['random_seed']
 physical=lambda v:{k:x for k,x in v.items()if not k.startswith('raytracing')and k!='use_raytracing'}
 assert physical(cfg['scene_overrides'])==physical(base['scene_overrides'])==physical(s['scene_overrides'])
 assert cfg['experiment']['book_initial_speed_mps']==point['theta']
 assert len(s['frames'])==210 and s['render']['fps']==30 and s['render']['pre_static_frames']==30
 assert s['render']['physics_steps_per_render_frame']==64 and s['scene_overrides']['dt']*64==1/30
 assert all(math.isfinite(v)for f in s['frames']for o in f['objects']for v in o['position'])
 threshold=base['experiment']['table_top_z']-.08;frames=s['frames'][5:155]
 minima={n:min(o['position'][2]for f in frames for o in f['objects']if o['name']==n)for n in names}
 labels={n+'_below_table_8cm':int(minima[n]<threshold)for n in names};assert labels==point['labels']
 peak=max((c['penetration_m']for f in frames for c in f.get('contacts',[])),default=0.)
 assert abs(peak-point['native_peak_m'])<1e-12 and point['quality_passed']and peak<=.001
 positions=[[o['position']for o in f['objects']]for f in s['frames']]
 if kind=='point'and point['theta']==job['theta']:source_positions=positions
 if kind=='source_repeat':
  assert source_positions is not None
  repeat_error=max(math.dist(x,y)for a,b in zip(source_positions,positions)for x,y in zip(a,b));assert repeat_error==0
 points.append(dict(theta=point['theta'],kind=kind,labels=labels,state_path=str(path),state_sha256=point['state_sha256'],
  config_path=str(cfgpath),config_sha256=point['config_sha256'],renderer_sha256=point['renderer_sha256'],
  native_peak_m=peak,minimum_center_z_m=minima,threshold_z_m=threshold,
  primary_z_margin_m=minima['t08_target_mug']-threshold,physical_inputs_axis_seed_and_clock_verified=True))
 del s,raw,positions
bootstrap=Path('/data/yangkaiyuan/boundary_five_scene_20261028/egl_bootstrap.py')
print(json.dumps(dict(clip_id=CID,job=job,report=report,verified_points=points,source_repeat_error_m=repeat_error,
 bootstrap_path=str(bootstrap),bootstrap_sha256=sha(bootstrap),bootstrap_source=bootstrap.read_text(),
 verified_remote_hashes=EXPECTED,new_simulations=0,source_files_modified=False)))
'''


def read(p):return json.loads(Path(p).read_text(encoding='utf8'))

def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()

def canonical(value):
    if isinstance(value,str):
        for prefix in ['/data/yangkaiyuan/boundary_five_scene_20261028/importer','/data2/wangzijun_p25/liyuhan/phydataset/ase_asset_importer','/home/wangzijun_p25/liyuhan/phydataset/ase_asset_importer']:
            value=value.replace(prefix,'<IMPORTER>')
        return value
    if isinstance(value,list):return[canonical(v)for v in value]
    if isinstance(value,dict):return{k:canonical(v)for k,v in value.items()}
    return value

def save_report(stem,data,pointer):
    raw=json.dumps(data,indent=2,ensure_ascii=False).encode();digest=hashlib.sha256(raw).hexdigest();path=WORK/(stem+'_'+digest[:12]+'.json');path.write_bytes(raw)
    (WORK/pointer).write_text(json.dumps(dict(path=path.relative_to(ROOT).as_posix(),sha256=digest),indent=2))
    return path

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--clip',choices=['T08_C01','T08_C02','T08_C03']);args=parser.parse_args()
    artifacts=read(WORK/'t08_refined_existing_artifacts.json')
    if args.clip:
        expected={name:artifacts[name]['sha256']for name in ['t08_jobs.json','renderer_t08_aggregate_cpu64.py','worker.py']}
        expected['searches/'+args.clip+'/result.json']=artifacts[args.clip+'/result.json']['sha256']
        report=rpc(SG_OPTIONS,SG,'CID='+repr(args.clip)+'\nEXPECTED='+repr(expected)+'\n'+REMOTE)
        report['audit_script_sha256']=sha(Path(__file__))
        path=save_report(args.clip+'_refined_state_audit',report,args.clip+'_REFINED_STATE_AUDIT.json')
        print(json.dumps(dict(clip_id=args.clip,verified_points=len(report['verified_points']),source_repeat_error_m=report['source_repeat_error_m'],path=str(path))));return
    authority=WORK/'AUTHOR_T08_NUMERICAL_REFINEMENT_20261102.json';approval=read(authority)
    assert approval['decision']=='允许数值细化，单列配置与不确定性'
    registry,_=load();rows={r['clip_id']:r for r in registry['cases']};published={r['clip_id']:r for r in read(WORK/'t08_published_runtime_inputs.json')}
    cases=[];files=[authority,WORK/'t08_refined_existing_artifacts.json',WORK/'t08_published_runtime_inputs.json',Path(__file__)]
    for cid in approval['scope']:
        pointer=read(WORK/(cid+'_REFINED_STATE_AUDIT.json'));path=ROOT/pointer['path'];assert sha(path)==pointer['sha256'];files.append(path)
        audit=read(path);job=audit['job'];result=audit['report'];old=published[cid];row=rows[cid]
        assert audit['audit_script_sha256']==sha(Path(__file__))
        assert old['stored_sha256']==job['published_runtime_state_stored_sha256']==row['reference_native_state_binding']['stored_state_sha256']
        assert old['decoded_sha256']==job['published_runtime_state_decoded_sha256']
        assert canonical({o['name']:o.get('spec',o)for o in old['dynamic_objects']})==canonical({o['name']:o for o in job['base_config']['dynamic_objects']})
        original=canonical(old['solver']);refined=canonical(job['base_config']['scene_overrides'])
        changes={k:dict(original=original.get(k),refined=refined.get(k))for k in set(original)|set(refined)if original.get(k)!=refined.get(k)}
        assert set(changes)=={'substeps','constraint_timeconst','raytracing','use_raytracing'}
        assert changes['substeps']==dict(original=4,refined=8)and changes['constraint_timeconst']==dict(original=.002,refined=.0005)
        assert old['experiment']['random_seed']==job['base_config']['random_seed']
        source=next(p for p in audit['verified_points']if p['kind']=='point'and p['theta']==job['theta'])
        primary='t08_target_mug_below_table_8cm';assert source['labels'][primary]==row['reference_events'][primary]==1
        assert result['source_theta']==row['theta']and result['sample_id']==row['sample_id']and result['normalization_domain']==row['normalization_domain']
        intervals=[]
        for interval in result['intervals']:
            if interval['event']!=primary:continue
            endpoints=[next(p for p in audit['verified_points']if p['kind']=='point'and p['theta']==theta)for theta in interval['bracket']]
            assert [p['labels'][primary]for p in endpoints]==interval['labels']and set(interval['labels'])=={0,1}
            intervals.append(dict(event=primary,bracket=interval['bracket'],endpoint_labels=interval['labels'],endpoints=endpoints,
                parameter_bracket_width=interval['bracket'][1]-interval['bracket'][0]))
        assert intervals
        cases.append(dict(clip_id=cid,reference_video_sha256=row['reference_video_sha256'],source_state_sha256=old['decoded_sha256'],
            original_physical_specs_preserved=True,original_event_labels_preserved=True,parameter=row['parameter'],theta=row['theta'],
            horizon_s=row['horizon_s'],condition_frame_index=4,end_frame_index=154,normalization_domain=row['normalization_domain'],intervals=intervals,
            source_primary_event_matches=True,non_target_source_event_differences={e:dict(original=y,refined=source['labels'][e])for e,y in row['reference_events'].items()if source['labels'].get(e)!=y},
            source_repeat_max_position_difference_m=audit['source_repeat_error_m'],verified_probe_count=len(audit['verified_points']),
            numerical_reference_profile=dict(id='t08_cpu64_sub8_tc0p0005',backend='genesis_cpu',precision_bits=64,
                dt_s=refined['dt'],physics_steps_per_render_frame=64,substeps=8,constraint_timeconst_s=.0005,
                source_seed=job['base_config']['random_seed'],seed_provenance=job['seed_note'],solver_changes=changes,
                reference_kind='author_approved_numerical_refinement',original_rendering_search_value=False,
                uncertainty=dict(search_bracket='Observed opposite-label interval at this fixed numerical profile; not a confidence interval.',
                    original_to_refined_boundary_shift='Not quantified: the original GPU32 probe has contact anomalies.',
                    convergence_to_real_physics='Not established by source repeatability or bracket width.',
                    endpoint_repeatability='Endpoints were each evaluated once; source was independently repeated with identical positions.')),
            formal_scope='Only primary mug below-table event distance. No transfer of refined non-target event labels, exact timing, full-chain EventExact or original-rendering critical values.',
            refined_state_audit=path.relative_to(ROOT).as_posix(),full_chain_automatically_admitted=False))
    report=dict(cases=cases,author_authorization=approval,new_simulations=0,frozen_inputs_modified=False,
        source_hashes={p.relative_to(ROOT).as_posix():sha(p)for p in files})
    path=save_report('t08_author_approved_refinement',report,'T08_APPROVED_REFINEMENT.json')
    print(json.dumps(dict(cases=[r['clip_id']for r in cases],path=str(path),new_simulations=0)))


if __name__=='__main__':main()
