"""Recover declared normalization ranges without changing thresholds or simulations."""
import collections,hashlib,json,re,gzip
from pathlib import Path
from scripts.export_original_boundary_distances import ROOT

def span_of(r):
    return r.get('normalization_span') or (r.get('boundary') or {}).get('normalization_span') or (r.get('normalization_basis') or {}).get('normalization_span')
def gravity(s):
    m=re.search(r'__(g\d{2}_[a-z_]+?)__',s);return m.group(1) if m else None
def main():
    combined=ROOT/'original_value_distance_ledger/combined_distance_inputs.jsonl'
    rows=[json.loads(l) for l in combined.read_text(encoding='utf8').splitlines()]
    exact=collections.defaultdict(list);declared=collections.defaultdict(list)
    for name in ['t02_published_scoring_registry.json','t14_all_context_reference_candidates_20261020.json','t04_probe_distance_registry.json']:
        p=ROOT/name
        for r in json.loads(p.read_text(encoding='utf8')):
            span=span_of(r)
            if span:exact[(r.get('engine','genesis'),r['sample_id'])].append((r,span,str(p),hashlib.sha256(p.read_bytes()).hexdigest()))
    p=ROOT/'five_scene_prepared_plan_20261020.json';digest=hashlib.sha256(p.read_bytes()).hexdigest()
    for job in json.loads(p.read_text(encoding='utf8')):
        domain=job['normalization_domain'];span=domain[1]-domain[0]
        for ep in job['endpoints']:
            r=dict(engine='genesis',sample_id=ep['sample_id'],family_id=job['family_id'],theta=ep['theta'],normalization_domain=domain,revision=ep['revision'])
            exact[('genesis',ep['sample_id'])].append((r,span,str(p),digest))
            declared[(job['scene_id'],job['family_id'],ep['revision'],gravity(ep['sample_id']))].append((domain,str(p),digest))
    launches=ROOT/'conditional_family_launches_20261023.json'
    plans={ROOT/l.get('local_plan','conditional_'+l['kind']+'_jobs_20261023.json.gz') for l in json.loads(launches.read_text(encoding='utf8'))}
    for p in plans:
        raw=p.read_bytes();digest=hashlib.sha256(raw).hexdigest()
        for job in json.loads(gzip.decompress(raw)):
            domain=job.get('normalization_domain')
            if not domain:continue
            donor=dict(engine='genesis',sample_id=job['sample_id'],family_id=job['family_id'],theta=job['theta'],normalization_domain=domain,revision=job['revision'])
            exact[('genesis',job['sample_id'])].append((donor,domain[1]-domain[0],str(p),digest))
    out=ROOT/'normalization_recovery_20261030.json'
    patches=json.loads(out.read_text(encoding='utf8'))['patches'] if out.exists() else {}
    producer_path=ROOT/'isaac_producer_domains_20261030.json'
    producer=json.loads(producer_path.read_text(encoding='utf8')) if producer_path.exists() else {}
    producer_domains={r['cell']:r for r in producer.get('domains',[])}
    matched_path=Path('review/release_boundary_binding_20261018/matched_registry.json')
    matched={r['sample_id']:r for r in json.loads(matched_path.read_text(encoding='utf8'))}
    t01=json.loads((ROOT/'t01_formal_source_contract_20261030.json').read_text(encoding='utf8'))
    t01_bind={r['sample_id']:r for r in json.loads(Path('review/original_search_tasks_20261018/t01_original_family_bindings.json').read_text(encoding='utf8'))}
    repair=json.loads((ROOT/'isaac_repair_domains_20261030.json').read_text(encoding='utf8'))
    repair_rows={r['sample_id']:r for r in json.loads((ROOT/'isaac_repair_distance_registry.json').read_text(encoding='utf8'))}
    for r in rows:
        if span_of(r) or r['reference_category'] in ['rendering_star','diagnostic_proxy']:continue
        options=[]
        for donor,span,path,digest in exact[(r['engine'],r['sample_id'])]:
            same_axis=(donor.get('family_id')==r.get('family_id') or donor.get('family_id')==r.get('parameter_name'))
            if same_axis and abs(donor['theta']-r['theta'])<1e-10:
                options.append((float(span),donor.get('normalization_domain'),path,digest,'exact_sample_axis_theta'))
        if not options and r['engine']=='genesis':
            ds=declared[(r['scene_id'],r.get('family_id'),r.get('revision'),gravity(r['sample_id']))]
            domains={tuple(d) for d,_,_ in ds}
            if len(domains)==1:
                domain,path,digest=ds[0];options.append((domain[1]-domain[0],domain,path,digest,'consistent_declared_family_revision_gravity_domain'))
        if not options and r['engine']=='isaac' and producer.get('input_hashes_verified'):
            original=matched.get(r['sample_id'],{})
            output=r.get('source_output') or original.get('source_output','')
            confirmed=(original.get('delivery_hashes_match') and original.get('source_config_matches')) or r.get('original_reference_kind')=='direct_original_producer_measured_bracket'
            cell=r['sample_id'].split('__boundary_')[0];d=producer_domains.get(cell)
            if confirmed and '/repro_t16_t20_13200_20260919/' in output and d:
                domain=d['domain']
                if domain[0]-1e-10<=r['theta']<=domain[1]+1e-10:
                    options.append((domain[1]-domain[0],domain,str(producer_path),hashlib.sha256(producer_path.read_bytes()).hexdigest(),'original_producer_hash_verified_global_input_grid'))
        if not options and r['engine']=='genesis' and r['scene_id']=='T01':
            binding=t01_bind.get(r['sample_id'],{});family=r.get('family_id');g=gravity(r['sample_id'])
            if binding.get('contract_sha256')==t01['sha256'] and family in ['A','B','C']:
                field={'A':'ramp_friction','B':'gap_12_m','C':'chain_friction'}[family]
                values=[p[field] for p in t01['data']['global_coverage_points_by_gravity'].get(g,[]) if p['axis']==family]
                if values and min(values)<=r['theta']<=max(values):
                    domain=[min(values),max(values)];options.append((domain[1]-domain[0],domain,str(ROOT/'t01_formal_source_contract_20261030.json'),t01['sha256'],'exact_original_contract_declared_axis_coverage'))
        if not options and r['engine']=='isaac':
            original=repair_rows.get(r['sample_id'],{});depth=str(r.get('family_id','d0')[1:]);scene=r['scene_id']
            if '/repair_t16_t19_20260923/' in original.get('source_output','') and original.get('theta')==r['theta']:
                param=original['parameter']['source_parameter']['name'];axis=repair['data']['AXES'].get(scene,{}).get(depth)
                domain=repair['data']['RANGES'].get(scene,{}).get(depth)
                if domain and param==axis and domain[0]<=r['theta']<=domain[1]:
                    options.append((domain[1]-domain[0],domain,str(ROOT/'isaac_repair_domains_20261030.json'),repair['sha256'],'exact_original_repair_axis_range'))
        spans={round(x[0],12) for x in options}
        if len(spans)!=1:continue
        span,domain,path,digest,method=options[0]
        if span<=0:continue
        patches[r['distance_record_id']]={'normalization_span':span,'normalization_domain':domain,'normalization_recovery_evidence':{'source':path,'source_sha256':digest,'method':method,'theta':r['theta'],'family_id':r.get('family_id'),'engine':r['engine'],'sample_id':r['sample_id']}}
    for patch in patches.values():
        evidence=patch['normalization_recovery_evidence'];source=Path(evidence['source'])
        if source.name in ['t01_formal_source_contract_20261030.json','isaac_repair_domains_20261030.json']:
            wrapped=json.loads(source.read_text(encoding='utf8'));digest=hashlib.sha256(source.read_bytes()).hexdigest()
            assert evidence['source_sha256'] in [wrapped['sha256'],digest]
            evidence.update(original_source_sha256=wrapped['sha256'],source_sha256=digest)
    out.write_text(json.dumps({'patches':patches,'new_simulations':0},indent=2),encoding='utf8')
    print(json.dumps({'recovered_ledger_records':len(patches),'by_scene':dict(collections.Counter(r['scene_id'] for r in rows if r['distance_record_id'] in patches))}))
if __name__=='__main__':main()
