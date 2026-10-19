"""What one site holds for a benchmark, as JSON. Run by the driver as `python - ARGS < survey.py` (read-only).

items:     per run/model directory: manifest rows, finished videos, their newest modification times, worker events,
           and the spec its manifest was built from
eval:      per model/stage (and the table): start/end events of the evaluation jobs
published: per run/model: whether the evaluation manifest was written by physedit or predates it
"""
import glob
import json
import os
import sys
import types
from pathlib import Path


def events(path):
    try:
        return [l.split() for l in open(path, errors="replace") if l.startswith(("start ", "end "))][-12:]
    except OSError:
        return []


args = json.loads(sys.argv[1])
validator = types.ModuleType('media_contract')
exec(args['media_contract_source'], validator.__dict__)
out = {"items": {}, "eval": {}, "published": {}}
for d in glob.glob(args["dir"] + "/*/*/"):
    run, model = Path(d).parts[-2:]
    if run in ("eval", "input"):
        continue
    manifest, spec = d + "manifest.jsonl", d + "spec.json"
    times, validated_files, validation_failures, media_sha256 = [], [], {}, {}
    for row in ([json.loads(l) for l in open(manifest) if l.strip()] if os.path.exists(manifest) else []):
        if row.get('input_failure'):
            validation_failures[row['sample_id']] = row['input_failure']
            continue
        try:
            media = validator.validate_row(row)
            output = row.get('final_resized') or row['generated_video_resized_to_source']
            times.append(os.path.getmtime(output))
            relative = os.path.relpath(output, d)
            validated_files.append(relative)
            media_sha256[relative] = media['video_sha256']
        except Exception as error:
            validation_failures[row['sample_id']] = str(error)
    times.sort(reverse=True)
    out["items"][run + "/" + model] = dict(
        rows=sum(1 for _ in open(manifest)) if os.path.exists(manifest) else None, done=len(times), recent=times[:21],
        validated_files=validated_files, validation_failures=validation_failures, media_sha256=media_sha256,
        replica=os.path.exists(d+"replica.json"),
        events={w: events("%slogs/%s.events" % (d, w)) for w in ("w0", "w1")},
        spec=json.load(open(spec)) if os.path.exists(spec) else None)
for f in glob.glob(args["dir"] + "/eval/*.events") + glob.glob(args["dir"] + "/eval/*/*.events"):
    out["eval"][os.path.relpath(f, args["dir"] + "/eval")[:-len(".events")]] = events(f)
for key, path in args.get("publish", {}).items():
    try:
        with open(path) as f:
            out["published"][key] = "physedit" if "physedit" in json.loads(f.readline()) else "legacy"
    except (OSError, ValueError):
        pass
print(json.dumps(out))
