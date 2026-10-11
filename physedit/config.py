"""Fleet, models and benchmarks. Adding a model, a machine or a benchmark only touches this file.

A model's `cmd` maps a site to the shell command that generates the rows of one manifest there. Placeholders are
filled from the site's `vars` and, per job, with
    {manifest}  the worker's manifest, {dir}/manifest_{worker}.jsonl (w0 and w1 are disjoint halves)
    {worker}    w0 or w1, for commands that read other per-worker files ({dir}/prompts_{worker}.json)
    {dir}       the model's run directory on that site (manifests, generated/<row>/resized.mp4, logs/)
    {tools}     the deployed physedit runners on that site
    {gpu}       the job's GPU index(es), comma separated (also exported as CUDA_VISIBLE_DEVICES)
    {run} {job}
Media completion requires full decode, registered dimensions/frame count and clock validation.
The local PhyEditing pipeline is one-shot; interrupted outputs are retained and not automatically retried.
"""
import os

SSH = "ssh -o BatchMode=yes -o ConnectTimeout=25 -o ServerAliveInterval=30 -o ServerAliveCountMax=4"
CLUSTER_SSH = SSH + " -F " + os.path.expanduser("~/.ssh/config")
ENV = "HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 PYTHONUNBUFFERED=1"

# A site is one filesystem: all its hosts see the same paths. `shared_with`: the evaluation host reads this site's
# files at the same paths (NFS), so its videos need no copy.
Z = "/path/to/cluster"
V3 = "/path/to/models"
PS = "/path/to/adapters"
SITES = {
    "site_a": dict(root="/path/to/workspace/physedit", env=ENV + " PYTHONNOUSERSITE=1", vars=dict(
        python="/path/to/workspace/miniconda3/envs/cosmos-predict2/bin/python",
        py_physinv="/path/to/workspace/miniconda3/envs/physinv/bin/python",
        py_wan="/path/to/workspace/envs/ltx_v2v/bin/python",
        py_hunyuan="/path/to/workspace/envs/hunyuan/bin/python",
        models="/path/to/workspace/models",
        hunyuan="/path/to/workspace/models/HunyuanVideo-1.5-Diffusers-480p_i2v_step_distilled",
        cosmos_tools="/path/to/workspace/cosmos_predict2_tools",
        cosmos_model="/path/to/workspace/models/Cosmos-Predict2-2B-Video2World")),
    "site_b": dict(root="/path/to/workspace/physedit", shared_with="site_a",
                      env=ENV + " PYTHONNOUSERSITE=1 HF_HUB_CACHE=/path/to/user/.cache/huggingface/hub", vars=dict(
        python="/path/to/workspace/miniconda3/envs/cosmos-predict2/bin/python",
        py_hunyuan=f"{V3}/envs/hunyuan15/bin/python",
        hunyuan=f"{V3}/weights/hunyuanvideo15_480p_i2v_step_distilled",
        py_dc=f"{V3}/envs/dynamicrafter_py38_libmamba/bin/python",
        dc_repo=f"{V3}/repos/DynamiCrafter",
        dc_ckpt=f"{V3}/weights/dynamicrafter_1024/model.ckpt",
        py_lora="/path/to/workspace/envs/lora_tf514/bin/python",
        physics=PS,
        wan5b="/path/to/workspace/models/Wan2.2-TI2V-5B",
        wan5b_diffusers="/path/to/workspace/models/Wan2.2-TI2V-5B-Diffusers")),
    # the container's python3 needs the account's user site-packages, so no PYTHONNOUSERSITE here
    "cluster": dict(root="/path/to/cluster/physedit", env=ENV, vars=dict(
        python="python3",                                    # the driver's helpers need only the standard library
        wan_code=f"{Z}/repos/Wan2.2",
        wan_a14b=f"{Z}/Wan2.2-I2V-A14B-official-bf16",
        physalign=f"{Z}/PhysAlign-Wan2.2-I2V-A14B-community/adapter",
        cosmos3=f"{Z}/Cosmos3-Nano",
        h3="/path/to/cluster/models/MiniMax-H3-FL2VA")),
}

HOSTS = {}  # Remote execution is enabled through an explicit private fleet configuration.

CANVAS_848 = {"landscape": (848, 480), "portrait": (480, 848), "square": (640, 640)}
CANVAS_832 = {"landscape": (832, 480), "portrait": (480, 832), "square": (640, 640)}


def diffusers(python, weights, pipeline, args):
    """the shared diffusers image-to-video runner (LTX, CogVideoX, Wan 5B, HunyuanVideo)"""
    return (python + " {tools}/diffusers_i2v.py --generation-manifest {manifest} --model-dir " + weights
            + " --pipeline " + pipeline + " --cuda-visible-devices {gpu} --torch-dtype bfloat16 --skip-existing " + args)


A14B = ("cd {wan_code} && python3 {tools}/wan22_a14b.py --code-dir {wan_code} --manifest {manifest} --ckpt-dir {wan_a14b}"
        " --status-jsonl {dir}/logs/{worker}_status.jsonl --state-json {dir}/logs/{worker}_state.json")

# name: label in the result tables; frames/fps: what the model generates; canvas: generation size per source
# orientation (else the runner's own); mode: which benchmark template the rows come from (i2v or v2v); gpus: per job;
# split: the runner takes its whole manifest as one batch, so the two workers get disjoint halves;
# fields: extra manifest fields, optionally per run (strings are formatted with the row and {inputs[name]});
# sec_per_row: expected generation time, for ETAs before the first rows finish.
MODELS = {
    # LTX and CogVideoX need sides divisible by 32: aspect-preserving canvases as in September
    "ltx_i2v": dict(name="LTX-Video-2B", frames=161, fps=25, sec_per_row=46,
        canvas={"landscape": (704, 480), "portrait": (480, 704), "square": (480, 480)}, cmd={"site_a": diffusers(
        "{python}", "{models}/LTX-Video-diffusers", "ltx_i2v", "--num-inference-steps 50 --guidance-scale 3.0 --num-frames 161")}),
    "cogvideox_i2v": dict(name="CogVideoX1.5-5B-I2V", frames=81, fps=16, sec_per_row=514,
        canvas={"landscape": (768, 480), "portrait": (480, 768), "square": (480, 480)}, cmd={"site_a": diffusers(
        "{python}", "{models}/CogVideoX1.5-5B-I2V", "cogvideox_i2v", "--num-inference-steps 50 --guidance-scale 6.0 --num-frames 81")}),
    "wan_ti2v5b": dict(name="Wan2.2-TI2V-5B", frames=121, fps=24, sec_per_row=210, cmd={"site_a": diffusers(
        "{py_wan}", "{models}/Wan2.2-TI2V-5B-Diffusers", "wan_i2v", "--num-inference-steps 50 --guidance-scale 5.0 --flow-shift 5.0"
        " --height 480 --width 832 --num-frames 121 --offload-mode model")}),
    "cosmos": dict(name="Cosmos-Predict2-2B", frames=81, fps=16, mode="v2v", sec_per_row=450, cmd={"site_a":
        "{python} {tools}/cosmos_predict2.py --generation-manifest {manifest} --cosmos-tools {cosmos_tools}"
        " --python {python} --model-dir {cosmos_model} --cuda-visible-devices {gpu} --skip-existing"}),
    "hunyuan15_i2v": dict(name="HunyuanVideo-1.5-I2V", frames=121, fps=24, canvas=CANVAS_848, sec_per_row=900,
        cmd=dict.fromkeys(("site_a", "site_b"), diffusers("{py_hunyuan}", "{hunyuan}", "hunyuan15_i2v",
            "--num-frames 121 --num-inference-steps 12 --guidance-scale 1.0 --flow-shift 7.0 --offload-mode sequential"))),
    "dynamicrafter_i2v": dict(name="DynamiCrafter-1024", frames=16, fps=10, letterbox=True, split=True, sec_per_row=60,
        cmd={"site_b":
        "{py_dc} {tools}/dynamicrafter.py --generation-manifest {manifest} --repo-dir {dc_repo} --checkpoint {dc_ckpt}"
        " --cuda-visible-devices {gpu} --ddim-steps 50 --skip-existing && {python} {tools}/crop_letterbox.py {manifest}"}),
    "videogpa_ti2v5b": dict(name="VideoGPA-Wan2.2-TI2V-5B", frames=81, fps=24, prompts_json=True, sec_per_row=150, cmd={"site_b":
        "PYTHONPATH={physics}/repos/VideoGPA/Wan2.2:{physics}/deps/videogpa {py_lora} {tools}/videogpa_wan22.py"
        " --model_path {wan5b} --prompt_json {dir}/prompts_{worker}.json --output_dir {dir}/raw"
        " --lora_path {physics}/weights/VideoGPA-Wan2.2TI2V-lora --lora_weight 0.2 --gpu_id 0 --seed 20260920"
        " --frame_num 81 --max_area 399360 --sampling_steps 50 --fps 24 --offload_model"
        " && {python} {tools}/videogpa_finalize.py {manifest} {dir}/raw 20260920"}),
    # PhysRVG takes one canvas per process; x5 conditions on the 5 source frames ending at the condition frame
    "physrvg_ti2v5b": dict(name="PhysRVG-Wan2.2-TI2V-5B", frames=49, fps=15, canvas=CANVAS_832, split_orientation=True,
        sec_per_row=150, fields={"x5": {"source_video": "{inputs[prefix5]}/{source_sample_id}.mp4"}}, cmd={"site_b":
        "for o in landscape portrait square; do [ -s {dir}/manifest_{worker}_$o.jsonl ] || continue;"
        " case $o in landscape) H=480 W=832;; portrait) H=832 W=480;; square) H=640 W=640;; esac;"
        " PYTHONPATH={physics}/repos/PhysRVG:{physics}/deps/physrvg {py_lora} {tools}/physrvg.py"
        " --manifest {dir}/manifest_{worker}_$o.jsonl --model-id {wan5b_diffusers}"
        " --lora-checkpoint {physics}/weights/PhysRVG/lora/checkpoint --model-label PhysRVG-Wan2.2-TI2V-5B"
        " --output-root {dir} --status-jsonl {dir}/logs/{worker}_status_$o.jsonl --device 0 --height $H --width $W"
        " --num-frames 49 --num-inference-steps 16 --fps 15 --offload-mode model"
        " --condition-policy $([ {run} = x5 ] && echo source_history5 || echo static_frame) || exit 1; done"}),
    "cosmos3_nano": dict(name="Cosmos3-Nano", frames=189, fps=24, canvas=CANVAS_832, sec_per_row=480,
        fields={"cosmos_num_inference_steps": 35, "cosmos_guidance_scale": 6.0}, cmd={"cluster":
        "{py_models} {tools}/cosmos3.py --model {cosmos3} --manifest {manifest} --node {job}"
        " --status-jsonl {dir}/logs/{worker}_status.jsonl --state-json {dir}/logs/{worker}_state.json"
        " --ffmpeg $({py_models} -c 'import imageio_ffmpeg; print(imageio_ffmpeg.get_ffmpeg_exe())')"}),
    "wan22_i2v_a14b": dict(name="Wan2.2-I2V-A14B", frames=81, fps=16, sec_per_row=870, fields={"sample_steps": 40},
        cmd={"cluster": A14B}),
    "physalign_wan22_i2v_a14b": dict(name="PhysAlign-Wan2.2-I2V-A14B", frames=81, fps=16, sec_per_row=870,
        fields={"sample_steps": 40}, cmd={"cluster": A14B + " --physalign-adapter-dir {physalign}"}),
    "minimax_h3": dict(name="MiniMax-H3", frames=124, fps=24, gpus=2, sec_per_row=1200,
        canvas={"landscape": (896, 512), "portrait": (512, 896), "square": (640, 640)}, cmd={"cluster":
        "{py_models} {tools}/minimax_h3.py --source-manifest {manifest} --out-root {dir}/logs/{worker} --model {h3} --steps 50"}),
}

BENCHMARKS = {
    "phyediting": dict(kind="local_single_view", runs={"frozen": "SAM3.1 single-view parameter measurement"}),
}


def _load_private_fleet(path):
    import runpy
    settings = runpy.run_path(os.path.abspath(os.path.expanduser(path)))
    for key in ("SITES", "HOSTS"):
        if not isinstance(settings.get(key), dict):
            raise ValueError("private_fleet_requires_mapping_" + key)
    for key in ("SITES", "HOSTS", "MODELS", "BENCHMARKS"):
        if key in settings:
            if not isinstance(settings[key], dict):
                raise ValueError("private_fleet_requires_mapping_" + key)
            globals()[key] = settings[key]


if os.environ.get("PHYSEDIT_FLEET_CONFIG"):
    _load_private_fleet(os.environ["PHYSEDIT_FLEET_CONFIG"])
