"""Restore already recovered T20 producer brackets omitted from the combined ledger."""
import hashlib,json
from pathlib import Path
from scripts.export_original_boundary_distances import ROOT,distances

def main():
    src=ROOT/'t20_original_source_distances.json';configs=ROOT/'t20_original_source_configs.json'
    values=json.loads(src.read_text(encoding='utf8'));by_output={r['original']['output']:r for r in json.loads(configs.read_text(encoding='utf8'))}
    rows=[]
    for r in values:
        original=by_output[r['source_output']];assert original['source_hash_match'] and original['config_sha256']==r['config_sha256']
        param=original['config']['parameter'];prod=original['config']['production'];bracket=prod['measured_bracket']
        assert r['theta']==param['value'] and bracket==r['boundary']['intervals'][0]['bracket']
        sid=Path(r['source_output']).parent.name;assert sid.startswith('T20__')
        rows.append(dict(scene_id='T20',engine='isaac',sample_id=sid,revision=None,source_config_sha256=r['config_sha256'],
            source_output=r['source_output'],family_id=r['family_id'],target_event=r['target_event'],theta=r['theta'],
            parameter_name=param['source_parameter']['name'],parameter_unit=param['source_parameter']['unit'],original_parameter=param,
            reference_label=r['reference_label'],original_boundary_interval=bracket,**distances(r['theta'],bracket=bracket),
            original_reference_kind='direct_original_producer_measured_bracket',original_values_recovered=True,
            original_source_path=str(src.resolve()),original_source_sha256=hashlib.sha256(src.read_bytes()).hexdigest(),
            publication_status='source_input_verified_current_release_binding_separate',normalization_status='original_domain_pending',formal_nearacc_eligible=False))
    target=ROOT/'original_value_distance_ledger/t20_original_producer_distances.jsonl'
    target.write_text(''.join(json.dumps(r)+'\n' for r in rows),encoding='utf8')
    print(json.dumps({'restored_original_records':len(rows),'new_simulations':0,'source':str(src),'output':str(target)}))
if __name__=='__main__':main()
