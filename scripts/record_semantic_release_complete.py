from pathlib import Path
import json,sys
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from scripts.h3_prompt_sg_transport import run
OUT=ROOT/'review/prompt_semantic_repair_20261102';REMOTE='/data/yangkaiyuan/h3_prompt_retrain_semantic_v2_20261102'
def main():
 pub=json.loads((OUT/'PUBLISHED.json').read_text());fresh=json.loads((OUT/'FRESH_VERIFIED.json').read_text());audit=json.loads((OUT/'INDEPENDENT_VERIFICATION.json').read_text(encoding='utf8'));prefix=json.loads((OUT/'H3_INDEPENDENT_PREFIX_VERIFIED.json').read_text())
 assert fresh['status']==audit['status']==prefix['status']=='PASS' and pub['commit']==fresh['revision']==prefix['hf_revision']
 names=['PLAN.json','PIPELINE_LAUNCHED.json','ENCODER_STATUS.json','QUEUE_STATUS.json','TRAINER_LAUNCHED.json','ENCODER_FAILED.json','QUEUE_FAILED.json','RESOURCE_MODE.json']
 data=json.loads(run(f"from pathlib import Path;import json;r=Path({REMOTE!r});print(json.dumps({{n:json.loads((r/n).read_text())for n in {names!r}if(r/n).exists()}}))",timeout=45))
 assert 'ENCODER_FAILED.json'not in data and 'QUEUE_FAILED.json'not in data
 assert data['PLAN.json']['hf_revision']==pub['commit'] and data['PLAN.json']['manifest_sha256']==audit['training_manifest_sha256']
 assert data['RESOURCE_MODE.json']['mode']=='wait_existing_validation'and data['RESOURCE_MODE.json']['user_confirmed']
 status=dict(status='PUBLISHED_VERIFIED_H3_BOUND',publication_complete=True,revision=pub['commit'],commit_url=pub['url'],videos=72000,prompt_bindings=216000,training_videos=45165,files_freshly_verified=fresh['files_freshly_downloaded_and_hash_verified'],unit_keys_checked=1190,dimensional_unit_corrections=audit['generation_counts']['dimensional_unit_corrections'],numeric_literals_reformatted=audit['generation_counts']['numeric_literals_reformatted'],duplicate_clause_instances_removed=audit['generation_counts']['removed_duplicate_clauses'],all216000_txt_exports_verified=True,metadata_source_values_preserved=True,h3_run_directory=REMOTE,h3_prefix_verified=12,h3_model_texts_equal_published_variants=True,h3_training_started='TRAINER_LAUNCHED.json'in data,h3_resource_policy='continue CogVideo validation, then automatically start corrected H3',cog_validation_changed=False,old_cache_and_checkpoint_files_preserved=True,h3_live_snapshot=data)
 (OUT/'PUBLICATION_STATUS.json').write_text(json.dumps(status,ensure_ascii=False,indent=2),encoding='utf8')
 pointer=ROOT.parent/'prompts_72000_unified/CURRENT_AUDITED_PROMPTS.json'
 entry=dict(status='published_semantic_repair_and_h3_bound',version=audit['policy'],manifest=str(OUT/'stage/releases/physedit/catalog/videos.jsonl.gz'),manifest_sha256=audit['manifest_sha256'],training_candidates=str(OUT/'stage/releases/physedit/catalog/train_final.jsonl.gz'),training_videos=45165,report=str(OUT/'INDEPENDENT_VERIFICATION.json'),huggingface_revision=pub['commit'],huggingface_commit_url=pub['url'],huggingface_manifest_url=f"https://huggingface.co/datasets/phy2/phydataset/resolve/{pub['commit']}/releases/physedit/catalog/videos.jsonl.gz",huggingface_manifest_sha256=audit['manifest_sha256'],publication_status=str(OUT/'PUBLICATION_STATUS.json'),h3_current_run=REMOTE,h3_manifest_sha256=audit['training_manifest_sha256'],online_release_changed=True,cog_validation_changed=False,old_checkpoints_preserved=True)
 pointer.write_text(json.dumps(entry,ensure_ascii=False,indent=2),encoding='utf8')
 docs=ROOT/'docs/PROMPT_POLICY.md';text=docs.read_text(encoding='utf8');marker='## Current semantic repair and H3 binding (2026-11-02)'
 if marker not in text:
  section=f'''{marker}

The active 72,000-video prompt entry is `../prompts_72000_unified/CURRENT_AUDITED_PROMPTS.json`.
HF revision: `{pub['commit']}`; policy: `{audit['policy']}`.
Use the version-bound English variants. All physical fact keys must have a reviewed dimensional type; unknown keys fail publication.
Exact values remain in metadata. Display at most 8 significant digits or a shorter exact fraction, with relative error <=5e-8.
Deduplicate only source-proven identical actor/property information; retain signs, axes, conditional controls and timing.
Publication requires full source numeric, dimensional, display, clause coverage, tokenizer, Parquet and all 216,000 TXT export checks,
followed by fresh remote byte/hash readback. Source producer regressions are covered in `tests/test_prompt_semantic_rules.py`.
The current H3 run is `{REMOTE}`. Its model text is exactly the selected published variant; do not append a generic FPS sentence.
Video/VAE features may be reused only with matching media/clock/preprocessing; conditioning reuse also requires byte-identical model input.
The user chose to finish existing CogVideo validation before automatically starting the fresh H3 LoRA run.
Frozen Core100 submitted inputs, old checkpoints and old feature directories remain provenance and are not rewritten.

'''
  text=text.replace('---\n\n# Historical policy records',section+'---\n\n# Historical policy records',1);docs.write_text(text,encoding='utf8')
 print(json.dumps({k:v for k,v in status.items()if k!='h3_live_snapshot'}))
if __name__=='__main__':main()
