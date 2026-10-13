"""CPU media and a loopback vision API; no external services or real models."""

import copy
import hashlib
import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from types import SimpleNamespace

import cv2
import numpy as np
import pytest

from physedit import evaluations as ev, qwen_judge as judge, vp_metrics as vp
from physedit.evaluation_settings import validate
from physedit.runners import media_contract as media


@pytest.mark.parametrize("kind", ["vp", "qwen"])
def test_summary_uses_registered_item_groups_without_changing_media_row(kind):
    row = dict(sample_id="s", item_id="i", gravity_truth=3.71)
    original = copy.deepcopy(row)
    item = dict(event="T04", camera_id="cam01", split="test_id")
    record = dict(sample_id="s", status="insufficient_evidence", reason="retained")
    if kind == "vp":
        record["metrics"] = {
            name: dict(status="insufficient_evidence", value=None, reason="retained")
            for name in ev.VP_NAMES
        }
    summary = ev.summarize([row], [record], kind, {"i": item})
    for key, expected in item.items():
        assert summary["groups"][key][expected]["registered"] == 1
        assert summary["groups"][key][expected]["failed"] == 1
    assert row == original  # Row SHA and media provenance must remain unchanged.
    assert summary["coverage_percent"] == 0
    row["split"] = "test_ood1"
    assert list(ev.summarize([row], [record], kind, {"i": item})["groups"]["split"]) == ["test_ood1"]


def judgement(**changes):
    value = {
        k: dict(
            present=False,
            assessable=True,
            severity=0,
            evidence="The same visible contour and static background persist at frames 0 and 47.",
            basis="visible_consistency",
            evidence_frames=[0] if k == "condition_inconsistency" else [0, 47],
        )
        for k in judge.CATEGORIES
    }
    return {**value, "confidence": 0.9, "insufficient_evidence": False, **changes}


def rows(path, values):
    path.write_text("".join(json.dumps(v) + "\n" for v in values))
    return path


@pytest.mark.parametrize("missing_kind", ["source", "generated"])
@pytest.mark.parametrize("fault", ["missing", "hash_drift"])
def test_mask_export_retains_independent_complete_sequence(tmp_path, monkeypatch, missing_kind, fault):
    from scripts import sam31_frontend as frontend

    ctx = dict(condition_frame=0, source_frames=3, generated_frames=3,
               source_fps=16, generated_fps=16, source_sha256="source-sha",
               generated_sha256="generated-sha")
    row = dict(sample_id="s", item_id="i", source_video="source.mp4", source_width=10, source_height=8,
               generated_video_resized_to_source="generated.mp4")
    mask = np.ones((8, 10), np.uint8)
    digest = hashlib.sha256(mask.tobytes()).hexdigest()

    def observed(root, *args):
        directory = root / "runs/sam31_visible_projection_full30_masks"
        directory.mkdir(parents=True)
        measures = []
        for kind in ("source", "generated"):
            jid = "s__vp_" + kind
            binding = {}
            statuses = ["ok"] * 3
            for f in range(3):
                if kind == missing_kind and f == 2 and fault == "missing":
                    statuses[f] = "missing_actual_mask"
                    continue
                np.savez_compressed(directory / f"{hashlib.sha256(jid.encode()).hexdigest()[:12]}_{f}.npz", mask=mask)
                binding[str(f)] = "incorrect" if kind == missing_kind and f == 2 else digest
            measures.append(dict(id=jid, frames=[0, 1, 2], video_sha256=ctx[kind + "_sha256"], mask_sha256=binding, statuses=statuses))
        rows(root / "measurements_v4.jsonl", measures)

    monkeypatch.setattr(frontend, "prepare", lambda *args: None)
    monkeypatch.setattr(frontend, "run", observed)
    entries, failures = ev.automatic_masks([row], {"s": ctx}, {"i": {"object_name": "can"}},
                                          {}, {"sam3": "unused", "checkpoint": "unused"}, tmp_path)
    good_kind = "source" if missing_kind == "generated" else "generated"
    assert set(entries) == {"s"}
    assert set(entries["s"]) == {"source", "generated"}
    assert set(failures) == {"s"}
    assert "missing_actual_mask" in failures["s"] if fault == "missing" else "binding_missing_or_mismatched" in failures["s"]
    sequence, _ = ev.mask_sequence(entries["s"][good_kind], ctx, good_kind, "can", (10, 8))
    assert len(sequence) == 3 and all(np.array_equal(m, mask) for m in sequence)
    manifest = ev.read_rows(tmp_path / "vp_mask_manifest.jsonl")
    assert len(manifest) == 1 and manifest[0]["sample_id"] == "s"
    assert missing_kind in manifest[0]
    partial, provenance = ev.mask_sequence(entries["s"][missing_kind], ctx, missing_kind, "can", (10, 8))
    assert partial[-1] is None and len(partial) == 3
    assert provenance["unavailable_frames"] and provenance["identity_accuracy_certified"] is False


def test_reference_foreground_scores_survive_missing_generated_masks(clip):
    row, ctx, item, pair = clip
    result = ev.vp_case(row, ctx, item, {"source": pair["source"]}, {"trajectory_duration_seconds":1})
    for name in ("condition_foreground_ssim", "condition_foreground_psnr_db",
                 "reference_foreground_ssim", "reference_foreground_psnr_db"):
        assert result["metrics"][name]["status"] == "ok"
    assert result["status"] == "partial"
    assert result["metrics"]["trajectory_error_full"]["status"] == "failed"
    assert "missing_registered_or_sam31_generated_masks" in result["metrics"]["trajectory_error_full"]["reason"]
    summary = ev.summarize([row], [result], "vp")
    assert summary["registered"] == 1 and summary["failed"] == 1
    assert summary["metrics"]["reference_foreground_ssim"]["scored"] == 1


@pytest.fixture
def api():
    requests = []
    responses = []

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *a):
            pass

        def do_POST(self):
            requests.append(
                (
                    self.path,
                    json.loads(self.rfile.read(int(self.headers["Content-Length"]))),
                    dict(self.headers),
                )
            )
            answer = (
                responses.pop(0)
                if responses
                else dict(judgement=judgement(), model="Qwen-fixture")
            )
            code = answer.get("code", 200)
            self.send_response(code)
            if code == 302:
                self.send_header(
                    "Location", "http://localhost:1/credentials-must-not-follow"
                )
            self.end_headers()
            payload = answer.get(
                "payload",
                dict(
                    model=answer.get("model", "Qwen-fixture"),
                    choices=[
                        dict(
                            message=dict(
                                content=answer.get(
                                    "raw",
                                    json.dumps(answer.get("judgement", judgement())),
                                )
                            )
                        )
                    ],
                    usage=answer.get(
                        "usage",
                        dict(prompt_tokens=10, completion_tokens=20, total_tokens=30),
                    ),
                ),
            )
            self.wfile.write(json.dumps(payload).encode())

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    config = dict(
        backend="api",
        base_url=f"http://127.0.0.1:{server.server_port}/v1",
        model="Qwen-fixture",
        api_key_env="FIXTURE_QWEN_KEY",
    )
    yield config, requests, responses
    server.shutdown()
    thread.join()
    server.server_close()


@pytest.fixture
def clip(tmp_path):
    rng = np.random.default_rng(4)
    picture = rng.integers(30, 220, (160, 192, 3), dtype=np.uint8)
    picture[65:85, 75:95] = 20

    def video(path, count):
        writer = cv2.VideoWriter(
            str(path), cv2.VideoWriter_fourcc(*"FFV1"), 16, (192, 160)
        )
        assert writer.isOpened()
        for _ in range(count):
            writer.write(picture)
        writer.release()

    source = tmp_path / "source.avi"
    generated = tmp_path / "generated.avi"
    video(source, 53)
    video(generated, 48)
    condition = tmp_path / "condition.png"
    assert cv2.imwrite(str(condition), ev.frame(source, 5))
    prompt = tmp_path / "prompt.txt"
    prompt.write_text("registered condition")
    negative = tmp_path / "negative.txt"
    negative.write_text("")
    row = dict(
        sample_id="valid",
        item_id="i",
        split="test_id",
        event="T08",
        camera_id="cam01",
        gravity_truth=9.81,
        generated_video_resized_to_source=str(generated),
        source_video=str(source),
        source_video_sha256=media.sha256(source),
        source_width=192,
        source_height=160,
        source_native_fps=16,
        num_frames=48,
        output_fps=16,
        condition_frame_index=5,
        condition_image=str(condition),
        prompt_file=str(prompt),
        negative_prompt_file=str(negative),
    )
    media.seal_completion(row)
    ctx = ev.context(row)
    pair = {}
    for kind in ("source", "generated"):
        masks = np.zeros((48, 160, 192), np.uint8)
        masks[:, 65:85, 75:95] = 1
        path = tmp_path / (kind + "_mask.npz")
        np.savez_compressed(
            path,
            masks=masks,
            frames=np.arange(5, 53) if kind == "source" else np.arange(48),
            fps=16,
            video_sha256=(
                ctx["source_sha256"] if kind == "source" else ctx["generated_sha256"]
            ),
            target_name="book",
            mask_method="artificial_cpu_fixture",
        )
        pair[kind] = dict(path=str(path), sha256=media.sha256(path))
    return row, ctx, dict(object_name="book"), pair


def test_full_vp_actual_cpu_media_and_known_agreement(clip):
    row, ctx, item, pair = clip
    result = ev.vp_case(row, ctx, item, pair, {'trajectory_duration_seconds':1})
    assert result["status"] == "ok", result
    assert set(result["metrics"]) == set(ev.VP_NAMES)
    for name, m in result["metrics"].items():
        expected = (
            "+inf" if "psnr" in name else 1 if "ssim" in name or "iou" in name else 0
        )
        assert m["value"] == (expected if isinstance(expected, str) else pytest.approx(expected, abs=1e-6)), (name, m)
    assert (
        result["metrics"]["background_flicker_full"]["diagnostic"][
            "percentile_fallback"
        ]
        is False
    )


def test_motion_formulas_distinguish_perturbed_motion():
    def track(factor):
        masks = []
        for i in range(10):
            mask = np.zeros((70, 100), bool)
            mask[20:30, 10 + factor * i : 20 + factor * i] = True
            masks.append(mask)
        return masks

    source = track(2)
    assert vp.trajectory_error(source, source, 0, 0, source_times=np.arange(10)/9, generated_times=np.arange(10)/9, duration_seconds=1) == 0
    assert vp.trajectory_error(source, track(1), 0, 0, source_times=np.arange(10)/9, generated_times=np.arange(10)/9, duration_seconds=1) > 0
    assert vp.motion_region_iou(source, source, 0, 0) == 1
    assert 0 < vp.motion_region_iou(source, track(1), 0, 0) < 1
    assert vp.silhouette_structure_error(source, 0) == 0
    blank = [np.zeros((160, 192, 3), np.uint8)] * 5
    assert vp.camera_motion_diagnostics(blank, 0)["error"] is None


def test_real_media_fixed_window_keeps_condition_scores_when_continuation_short(clip):
    row, ctx, item, pair = clip
    result = ev.vp_case(row, ctx, item, pair, {"reference_duration_seconds": 4})
    assert result["sample_id"] == row["sample_id"]
    assert result["reference_alignment"] == "post_condition_fixed_real_time"
    assert result["pixel_settings"]["reference_duration_seconds"] == 4
    for name in ("reference_ssim", "reference_psnr_db", "reference_foreground_ssim", "reference_foreground_psnr_db"):
        assert result["metrics"][name]["status"] == "insufficient_evidence"
        assert "incomplete_fixed_reference_window" in result["metrics"][name]["reason"]
    assert result["metrics"]["condition_ssim"]["status"] == "ok"
    assert result["metrics"]["condition_psnr_db"]["value"] == "+inf"
    json.dumps(result, allow_nan=False)


def test_real_media_registered_native_alignment_and_reference_mask_only(clip):
    row, ctx, item, pair = clip
    pair["generated"]["sha256"] = "invalid"
    result = ev.vp_case(row, ctx, item, pair, {'trajectory_duration_seconds':1})
    alignment = result["pixel_alignment"]
    assert alignment["requested_pairs"] == 30
    assert alignment["requested_times_seconds"][-1] == 1
    assert alignment["source_absolute_indices"][-1] == 21
    assert alignment["generated_indices"][-1] == 16
    assert 0 not in alignment["generated_indices"]
    assert result["metrics"]["reference_foreground_ssim"]["status"] == "ok"
    assert result["metrics"]["reference_foreground_psnr_db"]["diagnostic"]["positive_infinity_frames"] == 30
    assert result["metrics"]["trajectory_error_full"]["status"] == "failed"
    json.dumps(result, allow_nan=False)


@pytest.mark.parametrize(
    "mutation", ["hash", "video", "clock", "scope", "empty", "missing"]
)
def test_mask_fault_does_not_erase_independent_pixel_scores(clip, mutation):
    row, ctx, item, pair = clip
    if mutation == "missing":
        pair = {}
    elif mutation == "hash":
        pair["generated"]["sha256"] = "stale"
    else:
        path = Path(pair["generated"]["path"])
        with np.load(path) as z:
            data = {k: z[k] for k in z.files}
        if mutation == "video":
            data["video_sha256"] = "stale"
        if mutation == "clock":
            data["fps"] = 30
        if mutation == "scope":
            data["frames"] = np.arange(1, 49)
        if mutation == "empty":
            data["masks"] = np.zeros_like(data["masks"])
        np.savez_compressed(path, **data)
        pair["generated"]["sha256"] = media.sha256(path)
    result = ev.vp_case(row, ctx, item, pair, {'trajectory_duration_seconds':1})
    assert result["status"] == "partial"
    assert result["metrics"]["condition_ssim"]["status"] == "ok"
    assert result["metrics"]["trajectory_error_full"]["status"] != "ok"
    assert result["metrics"]["trajectory_error_full"]["value"] is None


def test_shared_evidence_real_api_request_and_redaction(
    tmp_path, clip, api, monkeypatch
):
    row, ctx, _, _ = clip
    config, requests, responses = api
    monkeypatch.setenv("FIXTURE_QWEN_KEY", "fixture-secret")
    answer = judgement()
    answer["identity_change"]["evidence"] = "fixture-secret should never persist"
    responses.append(
        dict(
            judgement=answer,
            model="Qwen-fixture",
            usage={"prompt_tokens": 3, "secret": "fixture-secret"},
        )
    )
    evidence = ev.qwen_evidence(row, ctx, tmp_path / "evidence")
    ev.verify_evidence(evidence)
    result = judge.call_api(config, evidence)
    assert "fixture-secret" not in json.dumps(result)
    assert result["usage"] == {"prompt_tokens": 3}
    path, body, headers = requests[0]
    assert (
        path == "/v1/chat/completions"
        and headers["Authorization"] == "Bearer fixture-secret"
    )
    assert body["stream"] is False and body["temperature"] == 0
    parts = body["messages"][0]["content"]
    assert sum(p["type"] == "image_url" for p in parts) == 1
    assert sum(p["type"] == "video_url" for p in parts) == 1
    assert [f["frame_index"] for f in evidence["frames"]] == [0, 7, 13, 20, 27, 34, 40, 47]
    assert json.loads(judge.PROMPT_PATH.read_text())["prompt"] in parts[-1]["text"]
    assert body["messages"] == judge.messages(evidence)
    Path(evidence["frames"][0]["path"]).write_bytes(b"drift")
    with pytest.raises(ValueError, match="judge_image_drift"):
        ev.verify_evidence(evidence)


@pytest.mark.parametrize("code", [401, 500, 302])
def test_api_error_or_redirect_no_retry_no_credentials_in_reason(
    tmp_path, clip, api, monkeypatch, code
):
    config, requests, responses = api
    monkeypatch.setenv("FIXTURE_QWEN_KEY", "fixture-secret")
    evidence = ev.qwen_evidence(clip[0], clip[1], tmp_path / "evidence")
    responses.append(dict(code=code, payload={"error": "fixture-secret"}))
    with pytest.raises(RuntimeError, match="api_http_status_" + str(code)) as error:
        judge.call_api(config, evidence)
    assert "fixture-secret" not in str(error.value) and len(requests) == 1


def test_remote_missing_key_rejected_before_transport(monkeypatch):
    monkeypatch.delenv("QWEN_API_KEY", raising=False)
    monkeypatch.setattr(
        judge, "build_opener", lambda *a: pytest.fail("must not request")
    )
    with pytest.raises(RuntimeError, match="missing_api_key_environment"):
        judge.call_api(dict(base_url="https://example.invalid/v1", model="Qwen"), {})


@pytest.mark.parametrize(
    "mutation", ["severity", "inconsistent", "confidence", "extra", "prose"]
)
def test_strict_judge_schema(mutation):
    value = judgement()
    if mutation == "severity":
        value["camera_motion"]["severity"] = True
    if mutation == "inconsistent":
        value["camera_motion"]["present"] = True
    if mutation == "confidence":
        value["confidence"] = float("nan")
    if mutation == "extra":
        value["new_score"] = 1
    raw = json.dumps(value)
    if mutation == "prose":
        raw = "Here is the score: " + raw
    with pytest.raises(ValueError):
        judge.parse_judgement(raw)
    assert (
        judge.parse_judgement("```json\n" + json.dumps(judgement()) + "\n```")
        == judgement()
    )


@pytest.mark.parametrize(
    "mutation",
    [
        "unsafe_url",
        "literal_key",
        "unknown_flag",
        "reserved_body",
        "mask_path",
        "wrong_local_fields",
    ],
)
def test_config_faults_rejected(mutation):
    config = dict(
        metrics=["gravtrace", "vp", "qwen"],
        vp=dict(mask_backend="sam31"),
        qwen=dict(
            backend="api", base_url="https://example.invalid/v1", model="Qwen3.5-9B"
        ),
    )
    if mutation == "unsafe_url":
        config["qwen"]["base_url"] = "http://remote.invalid/v1"
    if mutation == "literal_key":
        config["qwen"]["api_key"] = "secret"
    if mutation == "unknown_flag":
        config["unknown"] = True
    if mutation == "reserved_body":
        config["qwen"]["extra_body"] = {"messages": []}
    if mutation == "mask_path":
        config["vp"] = {"mask_backend": "registered", "mask_manifest": ""}
    if mutation == "wrong_local_fields":
        config["qwen"]["model_dir"] = "unused"
    with pytest.raises(ValueError):
        validate(config)


def test_all_registered_rows_preserved_per_metric_and_group(tmp_path, clip, api):
    row, ctx, item, pair = clip
    config, requests, responses = api
    missing = dict(
        row,
        sample_id="missing",
        input_failure="missing_source_video",
        split="test_ood1",
    )
    unsupported = dict(
        row,
        sample_id="unsupported",
        input_failure="not_applicable_registered_window",
        split="test_ood2",
    )
    manifest = rows(
        tmp_path / "masks.jsonl", [dict(sample_id=row["sample_id"], **pair)]
    )
    evaluation = dict(
        metrics=["gravtrace", "vp", "qwen"],
        vp=dict(trajectory_duration_seconds=1, mask_backend="registered", mask_manifest=str(manifest)),
        qwen=config,
    )
    validate(evaluation)
    result = ev.run_additional(
        {"evaluation": evaluation},
        [row, missing, unsupported],
        {"i": item},
        {},
        tmp_path / "evaluation",
    )
    assert result["vp"]["protocol"] == "phyediting_vp_v3"
    for stage in ("vp", "qwen"):
        assert result[stage]["registered"] == 3 and result[stage]["scored"] == 1
        assert result[stage]["coverage_percent"] == pytest.approx(100 / 3)
        assert result[stage]["groups"]["split"]["test_ood1"]["failed"] == 1
        ledger = ev.read_rows(tmp_path / "evaluation" / f"{stage}_results.jsonl")
        assert [r["sample_id"] for r in ledger] == ["valid", "missing", "unsupported"]
        assert "missing_source_video" in ledger[1]["reason"]
    assert len(requests) == 1
    assert (
        ev.attach_summary({"failures": []}, result, evaluation["metrics"])[
            "evaluation_failed"
        ]
        == 2
    )


@pytest.mark.parametrize("failure", ["insufficient", "schema", "model_drift"])
def test_judge_failures_and_model_drift_retained(tmp_path, clip, api, failure):
    row, _, item, _ = clip
    config, requests, responses = api
    if failure == "model_drift":
        responses.extend([dict(model="version-A"), dict(model="version-B")])
        second = dict(
            row,
            sample_id="second",
            generated_video_resized_to_source=str(
                Path(row["generated_video_resized_to_source"]).with_name("second.avi")
            ),
        )
        Path(second["generated_video_resized_to_source"]).write_bytes(
            Path(row["generated_video_resized_to_source"]).read_bytes()
        )
        media.seal_completion(second)
        cases = [row, second]
    else:
        cases = [row]
        responses.append(
            dict(judgement=judgement(insufficient_evidence=True, **{k:dict(assessable=False,present=False,severity=0,evidence="Not observable") for k in judge.CATEGORIES}))
            if failure == "insufficient"
            else dict(raw="not JSON")
        )
    result = ev.run_additional(
        {"evaluation": dict(metrics=["qwen"], qwen=config)},
        cases,
        {"i": item},
        {},
        tmp_path / "eval",
    )
    assert result["qwen"]["scored"] == (1 if failure == "model_drift" else 0)
    assert result["qwen"]["failed"] == 1 and len(requests) == len(cases)
    record = ev.read_rows(tmp_path / "eval/qwen_results.jsonl")[-1]
    assert record["status"] == (
        "insufficient_evidence" if failure == "insufficient" else "failed"
    )
    if failure == "model_drift":
        assert "model_changed" in record["reason"]
        assert record["served_model"] == "version-B" and "raw" in record
    if failure == "schema":
        assert record['raw'] == 'not JSON' and 'evidence' in record
        assert 'judgement' not in record


@pytest.mark.parametrize('failure', ['invalid_json', 'missing_assessability', 'truncated'])
def test_api_rejected_answer_retained_redacted_and_unscored(tmp_path, clip, api, monkeypatch, failure):
    row, _, item, _ = clip
    config, requests, responses = api
    monkeypatch.setenv('FIXTURE_QWEN_KEY', 'fixture-secret')
    answer = judgement()
    answer['identity_change']['evidence'] = 'fixture-secret echoed by service'
    if failure == 'missing_assessability':
        del answer['identity_change']['assessable']
    raw = 'invalid JSON fixture-secret' if failure == 'invalid_json' else json.dumps(answer)
    responses.append(dict(payload=dict(
        model='fixture-secret-model',
        choices=[dict(finish_reason='length' if failure == 'truncated' else 'stop',
                      message=dict(content=raw))],
        usage=dict(prompt_tokens=12, secret='fixture-secret'))))
    result = ev.run_additional({'evaluation':dict(metrics=['qwen'], qwen=config)},
        [row], {'i':item}, {}, tmp_path/'eval')
    record = ev.read_rows(tmp_path/'eval/qwen_results.jsonl')[0]
    assert len(requests) == 1  # No automatic retry of a failed model answer.
    assert record['status'] == ('partial' if failure == 'missing_assessability' else 'failed') and record['sample_id'] == row['sample_id']
    assert record['raw'] == raw.replace('fixture-secret', '[REDACTED]')
    assert record['served_model'] == '[REDACTED]-model'
    assert record['usage'] == {'prompt_tokens':12} and 'evidence' in record
    assert 'fixture-secret' not in json.dumps(record)
    assert ('judgement' in record) == (failure == 'missing_assessability')
    assert result['qwen']['scored'] == 0 and result['qwen']['registered'] == 1
    assert result['qwen']['category_coverage']['identity_change']['assessed'] == 0
    assert result['qwen']['semantic_accuracy_validated'] is False


def test_local_load_failure_retains_every_case_loads_once(tmp_path, monkeypatch):
    calls = []

    def fail(config):
        calls.append(config)
        raise RuntimeError("synthetic missing weights")

    monkeypatch.setattr(judge, "LocalJudge", fail)
    spec = tmp_path / "local.json"
    spec.write_text("{}")
    jobs = rows(
        tmp_path / "jobs.jsonl",
        [dict(sample_id="a", evidence={}), dict(sample_id="b", evidence={})],
    )
    output = tmp_path / "output.jsonl"
    judge.main(["--spec", str(spec), "--jobs", str(jobs), "--output", str(output)])
    records = ev.read_rows(output)
    assert len(calls) == 1 and [r["sample_id"] for r in records] == ["a", "b"]
    assert all(
        r["status"] == "failed" and "load_failure" in r["reason"] for r in records
    )


def test_existing_run_plan_and_execute_never_generate_or_fit(
    tmp_path, clip, api, monkeypatch
):
    row, _, item, _ = clip
    config, _, _ = api
    run = tmp_path / "run"
    run.mkdir()
    items = rows(tmp_path / "items.jsonl", [dict(item, id="i")])
    (run / "items.jsonl").write_bytes(items.read_bytes())
    spec = dict(
        items=str(items),
        model="ltx_i2v",
        model_dir="unused",
        data_root="unused",
        compact="unused",
        sam3="unused",
        checkpoint="unused",
        evaluation=dict(metrics=["qwen"], qwen=config),
    )
    (run / "registered.json").write_text(
        json.dumps(
            dict(
                spec=spec,
                plan=dict(registered=1, input_items_sha256=media.sha256(items)),
            )
        )
    )
    rows(run / "observed_rows.jsonl", [row])
    rows(run / "initial_jobs.jsonl", [dict(id="valid")])
    from scripts import phyediting_gen as gen

    monkeypatch.setattr(gen, "safe_fit", lambda *a: pytest.fail("must not fit"))
    monkeypatch.setattr(gen, "build", lambda *a: pytest.fail("must not generate"))
    target = tmp_path / "eval"
    plan = ev.existing_run(spec, run, target)
    assert (
        not target.exists()
        and plan["generation_started"] is False
        and plan["fitter_started"] is False
    )
    result = ev.existing_run(spec, run, target, execute=True)
    assert (
        result["evaluations"]["qwen"]["scored"] == 1
        and result["evaluation_failed"] == 0
    )
    assert result["scored"] == 0  # No invented gravity prediction.
    assert (target / "combined_summary.json").is_file()
    items.write_text("{}")
    with pytest.raises(ValueError, match="items_drift"):
        ev.existing_run(spec, run, tmp_path / "other")


@pytest.mark.parametrize("model_type,class_name", [
    ("qwen2_5_vl", "Qwen2_5_VLForConditionalGeneration"),
    ("qwen3_vl", "Qwen3VLForConditionalGeneration"),
    ("qwen3_vl_moe", "Qwen3VLMoeForConditionalGeneration"),
    ("qwen3_5", "Qwen3_5ForConditionalGeneration"),
    ("qwen3_5_moe", "Qwen3_5MoeForConditionalGeneration"),
])
def test_local_loader_and_messages_use_same_registered_images(
    tmp_path, clip, monkeypatch, model_type, class_name
):
    import sys
    from contextlib import nullcontext

    model_dir = tmp_path / "weights"
    model_dir.mkdir()
    (model_dir / "config.json").write_text(json.dumps({"model_type": model_type}))
    seen = {}

    class Inputs(dict):
        def to(self, device):
            assert device == "cuda"
            return self

    class Model:
        device = "cuda"

        @classmethod
        def from_pretrained(cls, path, **kwargs):
            assert (
                path == str(model_dir.resolve()) and kwargs["local_files_only"] is True
            )
            assert (
                kwargs["device_map"] == "cuda"
                and kwargs["attn_implementation"] == "sdpa"
            )
            return cls()

        def eval(self):
            return self

        def generate(self, **kwargs):
            assert kwargs["do_sample"] is False and kwargs["max_new_tokens"] == 1024
            return np.zeros((1, 5))

    class Processor:
        @classmethod
        def from_pretrained(cls, path, **kwargs):
            assert kwargs["local_files_only"] is True
            return cls()

        def apply_chat_template(self, messages, **kwargs):
            assert kwargs["tokenize"] is False
            seen["messages"] = messages
            return "template with video token"

        def __call__(self, **kwargs):
            seen["processor"] = kwargs
            assert len(kwargs["images"]) == len(kwargs["videos"]) == 1
            assert kwargs["videos"][0].shape == (8,160,192,3)
            return Inputs(input_ids=np.zeros((1,2)), pixel_values_videos=np.ones((8,4)), video_grid_thw=np.array([[4,2,2]]))

        def batch_decode(self, *a, **kw):
            return [json.dumps(judgement())]

    monkeypatch.setitem(
        sys.modules,
        "torch",
        SimpleNamespace(
            __version__="fixture",
            cuda=SimpleNamespace(is_available=lambda: True),
            bfloat16="bf16",
            inference_mode=nullcontext,
        ),
    )
    monkeypatch.setitem(
        sys.modules,
        "transformers",
        SimpleNamespace(
            __version__="fixture",
            **{class_name: Model},
            AutoProcessor=Processor,
        ),
    )
    evidence = ev.qwen_evidence(clip[0], clip[1], tmp_path / "evidence")
    model = judge.LocalJudge(dict(model_dir=str(model_dir), model="Qwen-fixture"))
    result = model(evidence)
    assert result["model_file_sha256"]["config.json"] == media.sha256(
        model_dir / "config.json"
    )
    api_parts = judge.messages(evidence)[0]["content"]
    local_parts = seen["messages"][0]["content"]
    assert [p["text"] for p in api_parts if p["type"] == "text"] == [
        p["text"] for p in local_parts if p["type"] == "text"
    ]
    images = [p["image"] for p in local_parts if p["type"] == "image"]
    assert len(images) == 1 and np.array_equal(
        np.array(images[0]), cv2.imread(evidence["condition_image"])[:, :, ::-1]
    )
    assert result["judgement"] == judgement()


def test_local_process_failure_does_not_retry_or_drop_rows(tmp_path, clip, monkeypatch):
    row, _, item, _ = clip
    calls = []

    def fail(command, **kwargs):
        calls.append(command)
        assert (
            str(Path(ev.__file__).resolve().parents[1]) in kwargs["env"]["PYTHONPATH"]
        )
        raise FileNotFoundError("fixture interpreter unavailable")

    monkeypatch.setattr(ev.subprocess, "run", fail)
    missing = dict(row, sample_id="missing", input_failure="missing_source_video")
    config = dict(
        metrics=["qwen"],
        qwen=dict(
            backend="local",
            model="Qwen-fixture",
            model_dir="/fixture",
            python="/fixture/python",
        ),
    )
    result = ev.run_additional(
        {"evaluation": config}, [row, missing], {"i": item}, {}, tmp_path / "eval"
    )
    assert (
        len(calls) == 1
        and result["qwen"]["registered"] == result["qwen"]["failed"] == 2
    )
    records = ev.read_rows(tmp_path / "eval/qwen_results.jsonl")
    assert (
        "local_qwen_process_failure" in records[0]["reason"]
        and "missing_source_video" in records[1]["reason"]
    )


def test_api_transport_and_incomplete_response_fail_closed(
    tmp_path, clip, api, monkeypatch
):
    config, _, responses = api
    evidence = ev.qwen_evidence(clip[0], clip[1], tmp_path / "evidence")
    responses.append(
        dict(
            payload={
                "choices": [
                    dict(
                        finish_reason="length",
                        message=dict(content=json.dumps(judgement())),
                    )
                ]
            }
        )
    )
    with pytest.raises(ValueError, match="incomplete_or_filtered"):
        judge.call_api(config, evidence)

    class Opener:
        def open(self, *a, **kw):
            raise TimeoutError("fixture timeout")

    monkeypatch.setattr(judge, "build_opener", lambda *a: Opener())
    with pytest.raises(RuntimeError, match="api_transport_failure"):
        judge.call_api(config, evidence)


def test_wrong_condition_cannot_score_vp_or_call_judge(tmp_path, clip, api):
    row, _, item, _ = clip
    config, requests, _ = api
    wrong = np.zeros((160, 192, 3), np.uint8)
    assert cv2.imwrite(row["condition_image"], wrong)
    media.seal_completion(
        row
    )  # Even a newly sealed file must match the declared source frame.
    evaluation = dict(
        metrics=["vp", "qwen"],
        qwen=config,
        vp=dict(
            mask_backend="registered", mask_manifest=str(tmp_path / "absent.jsonl")
        ),
    )
    result = ev.run_additional(
        {"evaluation": evaluation}, [row], {"i": item}, {}, tmp_path / "eval"
    )
    assert result["vp"]["failed"] == result["qwen"]["failed"] == 1 and not requests
    assert all(
        "condition_image_reference_pixel_mismatch" in result[s]["failures"][0]["reason"]
        for s in ("vp", "qwen")
    )
