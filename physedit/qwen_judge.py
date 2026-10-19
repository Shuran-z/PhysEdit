"""Visible-evidence judge with local weights or a vision Chat Completions API.

Importing this module never reads credentials, loads weights or makes requests.
Both backends receive the conditioning image and a full generated video.
Local processing explicitly encodes video tokens; API services must support video_url.
"""

import argparse
import base64
import hashlib
import json
import math
import os
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import Request, build_opener, HTTPRedirectHandler

PROMPT_PATH = Path(__file__).with_name("qwen_prompt.json")
CATEGORIES = (
    "abnormal_deformation",
    "identity_change",
    "interpenetration",
    "camera_motion",
    "condition_inconsistency",
)


class InvalidJudgeResponse(ValueError):
    """Retain model output and input provenance when validation rejects it."""

    def __init__(self, reason, response):
        super().__init__(reason)
        self.response = response


def parse_judgement(raw, *, require_assessable=False):
    text = raw.strip()
    if text.startswith("```"):
        lines = text.splitlines()
        if lines[-1].strip() != "```":
            raise ValueError("unterminated_json_fence")
        text = "\n".join(lines[1:-1])
    result = json.loads(text)
    if not isinstance(result, dict) or set(result) != set(CATEGORIES) | {
        "confidence",
        "insufficient_evidence",
    }:
        raise ValueError("judge_schema_keys")
    for key in CATEGORIES:
        value = result[key]
        fields = {
            "present",
            "severity",
            "evidence",
        }
        if not isinstance(value, dict) or set(value) not in (fields, fields | {'assessable'}, fields | {'assessable', 'basis', 'evidence_frames'}):
            raise ValueError("judge_category_schema: " + key)
        if require_assessable and 'assessable' not in value:
            raise ValueError('judge_missing_category_assessability: '+key)
        if 'assessable' in value and type(value['assessable']) is not bool:
            raise ValueError('judge_assessability_not_boolean: '+key)
        if (
            type(value["present"]) is not bool
            or type(value["severity"]) is not int
            or value["severity"] not in range(4)
            or not isinstance(value["evidence"], str)
        ):
            raise ValueError("judge_category_types: " + key)
        if value["present"] != (value["severity"] > 0):
            raise ValueError("judge_category_inconsistent: " + key)
        if value.get('assessable') is False and value['present']:
            raise ValueError('judge_unobservable_category_claimed_violation: '+key)
        if require_assessable and not value['evidence'].strip():
            raise ValueError('judge_missing_visual_reason: '+key)
    if (
        type(result["confidence"]) not in (int, float)
        or not math.isfinite(result["confidence"])
        or not 0 <= result["confidence"] <= 1
        or type(result["insufficient_evidence"]) is not bool
    ):
        raise ValueError("judge_confidence_or_evidence_schema")
    if require_assessable:
        any_visible = any(result[k]['assessable'] for k in CATEGORIES)
        if result['insufficient_evidence'] == any_visible:
            raise ValueError('judge_overall_evidence_inconsistent')
        if any_visible and result['confidence'] == 0:
            raise ValueError('judge_zero_confidence_claimed_assessment')
    return result


def messages(evidence):
    from .judge_video import video_description, verify_evidence
    verify_evidence(evidence, PROMPT_PATH)
    prompt = json.loads(PROMPT_PATH.read_text())["prompt"]
    if evidence.get('protocol') != 'visible_video_full_v2':
        raise ValueError('judge_requires_registered_video_input')
    video = Path(evidence['video']['path'])
    if video.stat().st_size > 128*1024*1024:
        raise ValueError('judge_video_api_payload_too_large')
    if file_sha(video) != evidence['video']['sha256']:
        raise ValueError('judge_video_drift')
    import mimetypes
    mime = mimetypes.guess_type(str(video))[0] or 'video/mp4'
    content = [
        {'type':'text','text':'Declared conditioning image, not a reference continuation:'},
        {'type':'image_url','image_url':{'url':'data:image/png;base64,'+base64.b64encode(Path(evidence['condition']['path']).read_bytes()).decode('ascii')}},
        {'type':'text','text':video_description(evidence)},
        {'type':'video_url','video_url':{'url':'data:'+mime+';base64,'+base64.b64encode(video.read_bytes()).decode('ascii')}},
        {'type':'text','text':prompt},
    ]
    return [{"role": "user", "content": content}]


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise HTTPError(req.full_url, code, "redirect_refused", headers, fp)


def call_api(config, evidence):
    base = config["base_url"].rstrip("/")
    endpoint = (
        base if base.endswith("/chat/completions") else base + "/chat/completions"
    )
    key = os.environ.get(config.get("api_key_env", "QWEN_API_KEY"))
    if not key and urlsplit(base).hostname not in ("localhost", "127.0.0.1", "::1"):
        raise RuntimeError("missing_api_key_environment")
    body = dict(
        model=config["model"],
        messages=messages(evidence),
        temperature=0,
        max_tokens=config.get("max_new_tokens", 1024),
        stream=False,
    )
    body.update(config.get("extra_body", {}))
    headers = {"Content-Type": "application/json"}
    if key:
        headers["Authorization"] = "Bearer " + key
    request = Request(
        endpoint, data=json.dumps(body).encode(), headers=headers, method="POST"
    )
    try:
        with build_opener(NoRedirect()).open(
            request, timeout=config.get("timeout_seconds", 120)
        ) as response:
            if response.status != 200:
                raise RuntimeError("api_http_status_" + str(response.status))
            # Bounded response; never persist transport headers or error bodies.
            raw = response.read(4 * 1024 * 1024 + 1)
            if len(raw) > 4 * 1024 * 1024:
                raise RuntimeError("api_response_too_large")
            payload = json.loads(raw)
    except HTTPError as error:
        code = error.code
        error.close()
        raise RuntimeError("api_http_status_" + str(code)) from None
    except (URLError, TimeoutError, OSError):
        raise RuntimeError("api_transport_failure") from None
    choice = payload["choices"][0]
    content = choice["message"]["content"]
    if not isinstance(content, str):
        raise ValueError("api_response_content_not_text")
    # A misbehaving service may echo credentials. Keep no credential in artifacts.
    if key:
        content = content.replace(key, "[REDACTED]")
    model = payload.get("model")
    # Only numeric usage counters are useful for evaluation provenance.
    usage = payload.get("usage")
    usage = (
        {
            k: v
            for k, v in usage.items()
            if k in ("prompt_tokens", "completion_tokens", "total_tokens")
            and type(v) is int
            and v >= 0
        }
        if isinstance(usage, dict)
        else None
    )
    response = dict(
        raw=content,
        served_model=(model.replace(key, "[REDACTED]") if key else model)
        if isinstance(model, str) else None,
        usage=usage,
        backend="api",
        transport="native_video_url",
        server_video_sampling="service_defined_not_verified_by_client",
    )
    try:
        if choice.get("finish_reason") not in (None, "stop"):
            raise ValueError("api_response_incomplete_or_filtered")
        if model is not None and (not isinstance(model, str) or not model.strip()):
            raise ValueError("api_response_model_not_text")
        from .judge_validation import validate_response
        validated = validate_response(content, evidence)
        response.update(validated)
    except ValueError as error:
        raise InvalidJudgeResponse(str(error), response) from None
    return response


class LocalJudge:
    def __init__(self, config):
        import torch
        import transformers

        model_dir = Path(config["model_dir"]).expanduser().resolve()
        if not model_dir.is_dir():
            raise ValueError("local_qwen_model_missing")
        if not torch.cuda.is_available():
            raise RuntimeError("local_qwen_cuda_unavailable")
        from transformers import AutoProcessor

        model_config = json.loads((model_dir / "config.json").read_text())
        classes = {
            "qwen2_5_vl": "Qwen2_5_VLForConditionalGeneration",
            "qwen3_vl": "Qwen3VLForConditionalGeneration",
            "qwen3_vl_moe": "Qwen3VLMoeForConditionalGeneration",
            "qwen3_5": "Qwen3_5ForConditionalGeneration",
            "qwen3_5_moe": "Qwen3_5MoeForConditionalGeneration",
        }
        model_type = model_config.get("model_type")
        if model_type not in classes:
            raise ValueError("unsupported_local_qwen_model_type: " + str(model_type))
        class_name = classes[model_type]
        model_class = getattr(transformers, class_name, None)
        if model_class is None:
            raise RuntimeError("local_qwen_model_class_unavailable: " + class_name)

        # No remote code, model downloads or implicit remote model IDs.
        self.model = model_class.from_pretrained(
            str(model_dir),
            local_files_only=True,
            torch_dtype=torch.bfloat16,
            device_map="cuda",
            attn_implementation="sdpa",
        ).eval()
        self.processor = AutoProcessor.from_pretrained(
            str(model_dir), local_files_only=True
        )
        self.config = config
        self.versions = {
            "torch": torch.__version__,
            "transformers": transformers.__version__,
            "model_type": model_type,
            "model_class": class_name,
        }
        files = sorted(
            p
            for p in model_dir.rglob("*")
            if p.is_file()
            and (
                p.suffix in (".json", ".safetensors", ".bin")
                or p.name in ("tokenizer.model", "merges.txt")
            )
        )
        self.model_files = {str(p.relative_to(model_dir)): file_sha(p) for p in files}

    def __call__(self, evidence):
        import torch
        from .judge_video import local_inputs
        inputs, audit = local_inputs(self.processor, evidence, json.loads(PROMPT_PATH.read_text())['prompt'])
        inputs = inputs.to(self.model.device)
        with torch.inference_mode():
            generated = self.model.generate(
                **inputs,
                max_new_tokens=self.config.get("max_new_tokens", 1024),
                do_sample=False,
            )
        raw = self.processor.batch_decode(
            generated[:, inputs["input_ids"].shape[1] :], skip_special_tokens=True
        )[0]
        response = dict(
            raw=raw,
            backend="local",
            served_model=self.config["model"],
            versions=self.versions,
            model_file_sha256=self.model_files,
            processor_inputs=audit,
            transport="native_video_tensor",
        )
        try:
            from .judge_validation import validate_response
            response.update(validate_response(raw, evidence))
        except ValueError as error:
            raise InvalidJudgeResponse(str(error), response) from error
        return response


def file_sha(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def main(argv=None):
    p = argparse.ArgumentParser(
        description="One local Qwen judgement batch; no generation or fitting."
    )
    p.add_argument("--spec", required=True)
    p.add_argument("--jobs", required=True)
    p.add_argument("--output", required=True)
    a = p.parse_args(argv)
    config = json.loads(Path(a.spec).read_text())
    jobs = [json.loads(s) for s in Path(a.jobs).read_text().splitlines() if s.strip()]
    model = None
    load_failure = None
    with Path(a.output).open("x") as out:
        for job in jobs:
            record = {"sample_id": job["sample_id"]}
            try:
                if load_failure:
                    raise RuntimeError(load_failure)
                if model is None:
                    try:
                        model = LocalJudge(config)
                    except Exception as e:
                        load_failure = "local_model_load_failure: " + type(e).__name__
                        raise RuntimeError(load_failure) from None
                record.update(status="ok", **model(job["evidence"]))
            except Exception as e:
                if isinstance(e, InvalidJudgeResponse):
                    record.update(e.response)
                record.update(status="failed", reason=type(e).__name__ + ": " + str(e))
            out.write(json.dumps(record, allow_nan=False) + "\n")
            out.flush()


if __name__ == "__main__":
    main()
