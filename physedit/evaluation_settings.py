"""Evaluation registration; no model imports or network access."""

import math
from urllib.parse import urlsplit


def fields(value, allowed, name):
    if not isinstance(value, dict):
        raise ValueError(name + " must be an object")
    unknown = set(value) - set(allowed)
    if unknown:
        raise ValueError(
            "Unsupported " + name + " fields: " + ", ".join(sorted(unknown))
        )


def validate(evaluation):
    fields(evaluation, {"metrics", "qwen", "vp"}, "evaluation")
    metrics = evaluation.get("metrics")
    if (
        not isinstance(metrics, list)
        or not metrics
        or any(not isinstance(m, str) for m in metrics)
        or len(set(metrics)) != len(metrics)
    ):
        raise ValueError(
            "evaluation.metrics must be a nonempty list of unique metric names"
        )
    if set(metrics) - {"gravtrace", "vp", "qwen"}:
        raise ValueError("Unsupported evaluation.metrics")
    for key in ("qwen", "vp"):
        if key in evaluation and key not in metrics:
            raise ValueError("evaluation." + key + " configured but not enabled")
    vp = evaluation.get("vp", {"mask_backend": "sam31"})
    fields(vp, {"mask_backend", "mask_manifest", "mask_review_manifest", "reference_duration_seconds", "reference_fps", "trajectory_duration_seconds", "trajectory_sampling_fps"}, "evaluation.vp")
    duration = vp.get('trajectory_duration_seconds', 5.0)
    fps = vp.get('trajectory_sampling_fps', 30.0)
    if (type(duration) not in (int, float) or type(fps) not in (int, float)
            or not math.isfinite(duration) or not math.isfinite(fps) or duration <= 0 or fps <= 0
            or duration * fps < 1 or not math.isclose(duration * fps, round(duration * fps), abs_tol=1e-8)
            or not math.isclose(fps, round(fps), abs_tol=1e-8)):
        raise ValueError('invalid_registered_trajectory_time_grid')
    for key, default in (("reference_duration_seconds", 1.0), ("reference_fps", 30.0)):
        value = vp.get(key, default)
        if type(value) not in (int, float) or not math.isfinite(value) or value <= 0:
            raise ValueError("evaluation.vp." + key + " must be positive and finite")
    pairs = vp.get("reference_duration_seconds", 1.0) * vp.get("reference_fps", 30.0)
    if not math.isfinite(pairs) or pairs < 1 or not math.isclose(pairs, round(pairs), rel_tol=1e-10, abs_tol=1e-8):
        raise ValueError("evaluation.vp requires an integral fixed reference time grid")
    if "mask_review_manifest" in vp and (not isinstance(vp["mask_review_manifest"], str) or not vp["mask_review_manifest"].strip()):
        raise ValueError("evaluation.vp.mask_review_manifest must be a nonempty path")
    backend = vp.get("mask_backend", "sam31")
    if backend not in ("sam31", "registered"):
        raise ValueError("evaluation.vp.mask_backend must be sam31 or registered")
    if backend == "registered" and (
        not isinstance(vp.get("mask_manifest"), str) or not vp["mask_manifest"].strip()
    ):
        raise ValueError("evaluation.vp.mask_manifest is required for registered masks")
    if backend == "sam31" and "mask_manifest" in vp:
        raise ValueError("evaluation.vp.mask_manifest requires registered backend")
    if "qwen" in metrics:
        q = evaluation.get("qwen")
        fields(
            q,
            {
                "backend",
                "model",
                "model_dir",
                "base_url",
                "api_key_env",
                "python",
                "gpu_devices",
                "timeout_seconds",
                "max_new_tokens",
                "extra_body",
                "video_fps",
                "max_video_frames",
                "max_pixels",
            },
            "evaluation.qwen",
        )
        if q.get("backend") not in ("api", "local"):
            raise ValueError("evaluation.qwen.backend must be api or local")
        if not isinstance(q.get("model"), str) or not q["model"].strip():
            raise ValueError(
                "evaluation.qwen.model must declare the actual model/version"
            )
        if q["backend"] == "api":
            url = urlsplit(q.get("base_url", ""))
            if (
                url.scheme not in ("http", "https")
                or not url.hostname
                or url.username
                or url.password
                or url.query
                or url.fragment
            ):
                raise ValueError(
                    "evaluation.qwen.base_url must be an HTTP(S) URL without credentials/query"
                )
            if url.scheme == "http" and url.hostname not in (
                "127.0.0.1",
                "localhost",
                "::1",
            ):
                raise ValueError("Remote evaluation.qwen.base_url requires HTTPS")
            if set(q) & {"model_dir", "python", "gpu_devices"}:
                raise ValueError("Local Qwen settings cannot be used with API backend")
            if "api_key_env" in q and (
                not isinstance(q["api_key_env"], str)
                or not q["api_key_env"].isidentifier()
            ):
                raise ValueError(
                    "evaluation.qwen.api_key_env must name an environment variable"
                )
            extra = q.get("extra_body", {})
            fields(
                extra,
                {"enable_thinking", "chat_template_kwargs"},
                "evaluation.qwen.extra_body",
            )
            if (
                "enable_thinking" in extra
                and type(extra["enable_thinking"]) is not bool
            ):
                raise ValueError("enable_thinking must be boolean")
            if "chat_template_kwargs" in extra:
                fields(
                    extra["chat_template_kwargs"],
                    {"enable_thinking"},
                    "chat_template_kwargs",
                )
                if any(
                    type(v) is not bool for v in extra["chat_template_kwargs"].values()
                ):
                    raise ValueError("chat_template_kwargs flags must be boolean")
        else:
            if not isinstance(q.get("model_dir"), str) or not q["model_dir"]:
                raise ValueError(
                    "evaluation.qwen.model_dir is required for local backend"
                )
            if set(q) & {"base_url", "api_key_env", "extra_body", "timeout_seconds"}:
                raise ValueError("API settings cannot be used with local Qwen backend")
            for k in ("python", "gpu_devices"):
                if k in q and (not isinstance(q[k], str) or not q[k].strip()):
                    raise ValueError(
                        "evaluation.qwen." + k + " must be a nonempty string"
                    )
        tokens = q.get("max_new_tokens", 1024)
        if type(q.get('video_fps', 2.0)) not in (int, float) or not math.isfinite(q.get('video_fps', 2.0)) or q.get('video_fps', 2.0) <= 0:
            raise ValueError('evaluation.qwen.video_fps must be positive and finite')
        for name, default, minimum in [('max_video_frames', 64, 2), ('max_pixels', 602112, 3136)]:
            if type(q.get(name, default)) is not int or q.get(name, default) < minimum:
                raise ValueError('evaluation.qwen.'+name+' is below the supported budget')
        if type(tokens) is not int or tokens < 1:
            raise ValueError(
                "evaluation.qwen.max_new_tokens must be a positive integer"
            )
        timeout = q.get("timeout_seconds", 120)
        if (
            type(timeout) not in (int, float)
            or not math.isfinite(timeout)
            or timeout <= 0
        ):
            raise ValueError(
                "evaluation.qwen.timeout_seconds must be positive and finite"
            )
    return metrics
