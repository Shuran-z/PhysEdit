"""Restore missing v1 assets with the original generator and recorded mesh hash.

Published asset files are never overwritten. The manifest is explicitly reconstructed;
its historical bytes were not recorded. No v5 background is substituted.
"""
import hashlib
import importlib.util
import json
from pathlib import Path
import sys


def main():
    root=Path('/home/wangzijun_p25/liyuhan/phydataset/ase_asset_importer')
    sys.path.insert(0,str(root/'scripts'))
    source=root/'scripts/generate_backgrounds_v1.py'
    spec=importlib.util.spec_from_file_location('original_background_v1',source)
    generator=importlib.util.module_from_spec(spec);spec.loader.exec_module(generator)
    base=root/'assets_generated/backgrounds_v1'
    profile=json.loads((root/'configs/background_profiles_v1/library_shelf_v1.json').read_text())
    stage=Path('/data_cached/wangzijun_p25/liyuhan/remaining_family_scans_20261023/background_v1_recovery');(stage/'geometry').mkdir(parents=True,exist_ok=True)
    (stage/'textures').mkdir(exist_ok=True)
    textures={m.name:generator.geom.write_texture_set(stage/'textures',m,800+i)
              for i,m in enumerate(generator.MATERIALS)}
    mesh=generator.library_shelf();obj=stage/'geometry/library_shelf_v1.obj'
    generator.geom.write_obj(obj,mesh,generator.MATERIALS,textures,'../textures')
    digest=hashlib.sha256(obj.read_bytes()).hexdigest()
    if digest!=profile['geometry_sha256']:raise ValueError('regenerated original geometry does not match recorded hash')
    for names in textures.values():
        for name in names.values():
            if not isinstance(name,str):continue
            if not (base/'textures'/name).is_file():
                # Basecolor has a second original improvement pass; do not
                # silently replace a missing final texture with its precursor.
                raise ValueError('original texture missing: '+name)
            (stage/'textures'/name).write_bytes((base/'textures'/name).read_bytes())
    manifest=stage/'library_shelf_v1.json'
    manifest.write_text(json.dumps(generator.manifest('library_shelf_v1',obj,mesh.bounds()),indent=2))
    receipt=dict(status='original_geometry_restored',geometry_sha256=digest,recorded_geometry_sha256=profile['geometry_sha256'],
        generator_sha256=hashlib.sha256(source.read_bytes()).hexdigest(),
        geometry_generator_sha256=hashlib.sha256(Path(generator.geom.__file__).read_bytes()).hexdigest(),
        manifest_origin='reconstructed by original v1 generator; historical manifest hash unavailable',
        manifest_path=str(manifest),manifest_sha256=hashlib.sha256(manifest.read_bytes()).hexdigest(),existing_assets_overwritten=0,
        asset_relocation='Recovered files are in a private writable directory; original read-only asset tree is untouched.')
    (stage/'receipt.json').write_text(json.dumps(receipt,indent=2));print(json.dumps(receipt))


if __name__=='__main__':main()
