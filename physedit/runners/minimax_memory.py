"""Memory placement for full precision MiniMax-H3 FL2VA inference."""
from functools import wraps


def configure_resident_denoiser(conditioner, generator):
    """Keep the denoiser on one GPU and stage conditioning and codec layers.

    This changes tensor placement only. The model checkpoint, dtype, attention
    implementation and sampling schedule remain unchanged.
    """
    import torch
    from accelerate import cpu_offload, cpu_offload_with_hook

    if torch.cuda.device_count() != 1:
        raise ValueError("resident-denoiser requires exactly one visible GPU")
    encoder = conditioner.text_encoder
    if type(encoder).__name__ != "Qwen3VLForConditionalGeneration":
        raise ValueError("resident-denoiser requires the MiniMax-H3 Qwen3VL conditioner")
    manager = conditioner._components_manager
    if manager is not generator._components_manager:
        raise ValueError("resident-denoiser requires a shared component manager")
    modules = {name: module for name, module in generator.components.items()
               if isinstance(module, torch.nn.Module)}
    if set(modules) != {"transformer", "vae", "audio_vae"}:
        raise ValueError("resident-denoiser requires transformer, vae and audio_vae components")
    sizes = {name: sum(p.numel() * p.element_size() for p in module.parameters())
             for name, module in modules.items()}
    capacity = torch.cuda.get_device_properties(0).total_memory
    if capacity - sizes["transformer"] < 16 * 1024**3:
        raise ValueError("resident-denoiser needs 16 GiB of device capacity beyond denoiser parameters")

    manager.disable_auto_cpu_offload()
    modules["transformer"].to("cuda:0")

    def staged(original, hook):
        @wraps(original)
        def call(*args, **kwargs):
            try:
                return original(*args, **kwargs)
            finally:
                hook.offload()
        return call

    for name in ("vae", "audio_vae"):
        module = modules[name]
        _, hook = cpu_offload_with_hook(module, execution_device=torch.device("cuda:0"))
        for method in ("encode", "decode"):
            setattr(module, method, staged(getattr(module, method), hook))
    cpu_offload(encoder, execution_device=torch.device("cuda:0"), offload_buffers=False,
                preload_module_classes=["Qwen3VLVisionModel", "Qwen3VLTextDecoderLayer"])
    return {"policy": "resident-denoiser", "component_parameter_bytes": sizes}
