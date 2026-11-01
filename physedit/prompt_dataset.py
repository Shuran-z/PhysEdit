"""Join a researcher-selected inventory to versioned English model inputs.

This join does not assign train/test membership or quality approval. Selection
must already follow the registered split and quality rules. Answer fields from
the selection are deliberately not copied into the model-input output.
"""
import argparse
import gzip
import json
from pathlib import Path
from .prompt_contract import VERSION, validate_text, sha, parameter_facts_sha

def rows(path):
    path=Path(path)
    with (gzip.open(path,'rt',encoding='utf-8') if path.suffix=='.gz' else path.open(encoding='utf-8')) as f:
        for line in f:
            if line.strip():yield json.loads(line)

def export(catalogs, selection, output, enrich_items=False, prompt_variant=1):
    index={}
    for path in catalogs:
        for row in rows(path):
            key=(row['video_id'],row.get('release','annotation_inventory_20261014'))
            if key in index and index[key]['prompt_en']!=row['prompt_en']:
                raise ValueError('conflicting_versioned_prompt:'+str(key))
            index[key]=row
    result=[]
    for i,selected in enumerate(rows(selection),1):
        key=(selected['video_id'],selected.get('release','annotation_inventory_20261014'))
        if key not in index:raise ValueError('missing_exact_release_prompt:'+str(key))
        row=index[key]
        variant=selected.get('prompt_variant',prompt_variant)
        if variant not in (1,2,3):raise ValueError('invalid_prompt_variant')
        row=dict(row)
        texts=row.get('prompt_variants_en',[]);hashes=row.get('prompt_variant_sha256',[])
        if len(texts)!=3 or len(hashes)!=3:raise ValueError('released_three_variant_prompt_required')
        for text,digest in zip(texts,hashes):
            if sha(validate_text(text))!=digest:raise ValueError('catalog_prompt_hash_mismatch')
        if selected.get('generation_required_parameter_keys'):
            from .compact_prompt import build
            missing=set(selected['generation_required_parameter_keys'])-set(row['selected_parameter_keys'])
            if missing:
                disclosure=row.get('external_control_disclosure',{}).get('disclosure')
                leads={1:'Fixed camera. '+disclosure,2:'Keep the camera fixed. '+disclosure,3:disclosure+' Camera stays fixed.'}if disclosure else None
                from .compact_prompt import build_variants
                update=build_variants([[k,'',v,u]for k,v,u in row['parameter_facts']],required_keys=set(row['selected_parameter_keys'])|set(selected['generation_required_parameter_keys']),lead_variants=leads)
                from .focused_prompt import build_focused
                update={**update,**build_focused({**row,**update})}
                row={**row,**update};texts=row['prompt_variants_en'];hashes=row['prompt_variant_sha256']
        prompt=validate_text(texts[variant-1])
        row['prompt_token_counts']=row['prompt_variant_token_counts'][variant-1]
        # Anonymous IDs prevent source file names from becoming model text.
        record={'sample_id':f'sample_{i:07d}','prompt':prompt,'prompt_language':'en',
                'prompt_policy':row['prompt_policy'],'prompt_sha256':sha(prompt),
                'generation_parameter_facts':[[k,'',v,u] for k,v,u in row['parameter_facts']]}
        record.update(generation_prompt_variants_en=texts,generation_prompt_variant_sha256=hashes,
                      generation_parameter_facts_sha256=parameter_facts_sha(record['generation_parameter_facts']))
        for field in ['external_control_disclosure','external_control_inputs','external_control_evidence','prompt_variant_focus','focus_parameter_groups','selected_keys_expressed_in_control_disclosure']:
            if field in row:record[field]=row[field]
        for field in ['prompt_token_counts','selected_parameter_keys','omitted_parameter_keys']:
            if field in row:record[field]=row[field]
        if selected.get('generation_required_parameter_keys'):record['generation_required_parameter_keys']=selected['generation_required_parameter_keys']
        for field in ['condition_image','video_path']:
            value=selected.get(field,row.get(field))
            if value:record[field]=value
        if enrich_items:
            # Research item metadata stays in the item file. Downstream builders
            # read only these declared facts for model conditioning.
            record={**selected,**record,'generation_prompt':prompt}
        record['prompt_variant']=variant
        result.append(record)
    Path(output).write_text(''.join(json.dumps(r,ensure_ascii=True)+'\n' for r in result),encoding='utf-8')
    return len(result)

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--catalog',action='append',required=True)
    p.add_argument('--selection',required=True)
    p.add_argument('--out',required=True)
    p.add_argument('--enrich-items',action='store_true',help='Keep researcher item fields and attach English facts for existing benchmark entry points; do not send the entire researcher item to a model')
    p.add_argument('--prompt-variant',type=int,choices=[1,2,3],default=1)
    a=p.parse_args();print('English records exported:',export(a.catalog,a.selection,a.out,a.enrich_items,a.prompt_variant))

if __name__=='__main__':main()
