"""Apply exact-hash prompt patches to a new catalog, preserving source media and labels."""
import collections
import gzip
import hashlib
import json
import shutil
from pathlib import Path
import sys

REPO=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(REPO))
from physedit.compact_prompt import counts
from physedit.prompt_contract import validate_text
from physedit.focused_prompt import clause, LIMITS

ROOT=REPO.parent/'release_72000_active'
OUT=ROOT/'prompt_completion_20261029'
REVISION=json.loads((ROOT/'PUBLISHED.json').read_text())['revision']


def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()


def main():
    with gzip.open(OUT/'prompt_patch.jsonl.gz','rt',encoding='utf-8') as f:
        patches={r['video_id']:r for r in map(json.loads,f)}
    assert len(patches)==2913
    for r in patches.values():
        facts={f[0]:f for f in r['parameter_facts']}
        for t,n,h in zip(r['prompt_variants_en'],r['prompt_variant_token_counts'],r['prompt_variant_sha256']):
            validate_text(t);assert counts(t)==n and hashlib.sha256(t.encode()).hexdigest()==h
            assert all(n[k]<=LIMITS[k] for k in LIMITS)
            assert r['external_control_disclosure']['disclosure'] in t
            # Whole required parameter clauses must appear, unrounded, in every variant.
            for key in r['required_parameter_keys']:assert clause(facts[key]) in t or clause(facts[key],True) in t
    total=0;preserved=0;updated=0;quality=collections.Counter();scenes=collections.Counter();keys=set()
    dest=OUT/'videos.jsonl.gz'
    with gzip.open(ROOT/'publication_20261029/videos.jsonl.gz','rt',encoding='utf-8') as src,gzip.open(dest,'wt',encoding='utf-8') as dst:
        for line in src:
            old=json.loads(line);row=dict(old);patch=patches.get(row['video_id'])
            if patch:
                assert row['sha256']==patch['video_sha256'] and not row.get('prompt_variants_en')
                row.update(patch);updated+=1
            else:preserved+=1
            assert len(row['prompt_variants_en'])==3 and all(row['prompt_variants_en'])
            assert row['prompt_en']==row['prompt_variants_en'][0]
            if row['download']['repo_id']=='phy2/phydataset' and 'releases/72000_author_review_20261029/shards/' in row['download']['path']:
                row['download']={**row['download'],'revision':REVISION}
            assert row['sha256']==old['sha256'] and row['quality_admission_status']==old['quality_admission_status']
            if not patch:
                assert all(row[k]==v for k,v in old.items() if k!='download')
            key=(row['engine'],row['native_sample_id'],row['camera']);assert key not in keys;keys.add(key)
            quality[row['quality_admission_status']]+=1;scenes[row['quota_scene']]+=1;total+=1
            dst.write(json.dumps(row,ensure_ascii=False)+'\n')
    assert total==72000 and updated==2913 and preserved==69087
    assert len(scenes)==20 and all(n==3600 for n in scenes.values())
    summary=dict(videos=total,prompt_variants=total*3,newly_completed_videos=updated,
        new_prompt_variants=updated*3,existing_prompt_rows_preserved=preserved,missing_prompt_rows=0,
        quality_states=dict(quality),per_quota_scene=dict(scenes),media_revision=REVISION,
        t19_prompt_coverage=3600,t19_retired_quality_status_unchanged=1830,
        max_new_token_counts={k:max(n[k] for r in patches.values() for n in r['prompt_variant_token_counts']) for k in LIMITS},
        core100_changed=False,source_manifest_sha256=sha(ROOT/'publication_20261029/videos.jsonl.gz'),
        manifest_sha256=sha(dest),patch_sha256=sha(OUT/'prompt_patch.jsonl.gz'))
    (OUT/'validation.json').write_text(json.dumps(summary,indent=2),encoding='utf-8')
    shutil.copyfile(REPO/'physedit/prompt_tokenizers/sources.json',OUT/'tokenizer_sources.json')
    shutil.copyfile(ROOT/'t14s_actual_inputs_20261029.jsonl.gz',OUT/'t14s_actual_inputs.jsonl.gz')
    evidence=OUT/'renderer_source_evidence';evidence.mkdir(exist_ok=True)
    for name in ['render_t14s_physics.py','render_sample.py','provenance.json']:
        shutil.copyfile(ROOT/'renderer_source_evidence'/name,evidence/name)
    (OUT/'README.md').write_text('''# PhysEdit 72,000-video prompt-complete catalog

This additive release completes the 2,913 missing three-view English prompt
bindings in the author-reviewed media inventory: T14S 960, T18 1,143, T19 810.
All 72,000 catalog entries now have three nonempty English variants (216,000
texts); the existing 69,087 prompt records are preserved. No media is rerendered.

Read `videos.jsonl.gz` for the complete catalog and exact pinned media download
locations. `prompt_patch.jsonl.gz` contains only the 2,913 newly completed rows.
New texts use the shared v7 renderer and the pinned T5/UMT5 tokenizer models;
counts include EOS, with limits LTX 128, CogVideoX 226 and Wan 512. No truncation
or input-number rounding is applied. All three views carry identical selected
physical inputs and necessary control disclosures. Full available physical facts
and exact body velocities remain in metadata. The fixed Core100 v6 package is
unchanged; use its bound task prompts for Core100 evaluation.

T18 discloses kinematic book withdrawal, active-frame timing, yaw, static hold,
and holding the extracted book thereafter. T14S discloses the off-screen capped
spring force and its duration; its renderer snapshot and source input hashes
are included. T19 preserves every body's initial motion using verified signed
axis velocities. Restitution-sweep T19 prompts additionally disclose the
analytic one-time-per-pair contact-impulse implementation from the renderer.
Current source snapshots do not attest to historical executable bytes.
Reference outcomes and critical-boundary labels are not used to generate text.

Prompt availability does not change visual-quality admission. In particular,
the existing 1,830 retired Genesis T19 entries retain their exclusion pending
separate visual review; prompts are available for them without claiming their
quality has passed. The catalog preserves author acceptance 1,953, historical
acceptance 31,722, other pending 36,495, and retired 1,830. Original source and
recovered-background manifest limitations in the media release remain recorded.

See `validation.json` and `summary.json` for counts/hashes. Media archives remain
at the fixed revision recorded in validation.json; this release uploads metadata
only. Historical release files are retained.
''',encoding='utf-8')
    print(json.dumps(summary))


if __name__=='__main__':main()
