"""Versioned sampling settings; never infer a checkpoint variant from a path."""
from copy import deepcopy

VERSION = 'phyediting_sampling_v2'
# Checkpoint variants are part of the experiment registration. Resolution is
# separately recorded by the existing aspect-preserving canvas policy.
PROFILES = {
    'ltx_i2v': dict(checkpoint='LTX-Video-2B non-distilled', steps=50, guidance=3.0),
    'cogvideox_i2v': dict(checkpoint='CogVideoX1.5-5B-I2V', steps=50, guidance=6.0),
    'wan_ti2v5b': dict(checkpoint='Wan2.2-TI2V-5B', steps=50, guidance=5.0, flow_shift=5.0),
    'hunyuan15_i2v': dict(checkpoint='HunyuanVideo-1.5 480p I2V step-distilled', steps=12, guidance=1.0, flow_shift=7.0),
    'cosmos': dict(checkpoint='Cosmos-Predict2-2B-Video2World 16fps', steps=None, guidance=7.0),
    'dynamicrafter_i2v': dict(checkpoint='DynamiCrafter-1024', steps=50, guidance=7.5, frame_stride=10, eta=1.0, guidance_rescale=0.7),
    'videogpa_ti2v5b': dict(checkpoint='VideoGPA Wan2.2-TI2V-5B LoRA', steps=50, guidance=5.0, flow_shift=5.0, lora_strength=0.2),
    # The published 8-step setting is an RL training example, not an I2V
    # inference recommendation. Preserve the local adaptation and disclose it.
    'physrvg_ti2v5b': dict(checkpoint='PhysRVG Wan2.2-TI2V-5B LoRA', steps=16, guidance=5.0, do_cfg=False, recommendation='local I2V adaptation; official example is V2V RL training'),
    'cosmos3_nano': dict(checkpoint='Cosmos3-Nano', steps=35, guidance=6.0, flow_shift=10.0),
    'wan22_i2v_a14b': dict(checkpoint='Wan2.2-I2V-A14B', steps=40, guidance=[3.5, 3.5], flow_shift=5.0),
    'physalign_wan22_i2v_a14b': dict(checkpoint='community PhysAlign adapter on Wan2.2-I2V-A14B', steps=40, guidance=[3.5, 3.5], flow_shift=5.0, recommendation='base-model settings; community conversion requires separate provenance'),
    'minimax_h3': dict(checkpoint='MiniMax-H3 FL2VA', steps=50, guidance=None, recommendation='CFG inherited from checkpoint modular pipeline; 50 steps is local runner setting'),
}


def parameters(model):
    return dict(protocol=VERSION, **deepcopy(PROFILES[model]))
