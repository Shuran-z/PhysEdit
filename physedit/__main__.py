"""PhysEdit: physical video generation, tracking and evaluation.

    physedit plan pipeline.json
    physedit run pipeline.json --execute
    physedit status runs/pipeline
    physedit models --json

Multi-host tasks use benchmark keys declared in PHYSEDIT_FLEET_CONFIG.
"""
import argparse
import fcntl
import os
import sys
import time

from . import config
from .driver import HUB_DIR, Driver


def _short_command(argv):
    """Expand convenient local commands into the existing explicit CLI."""
    if not argv:
        return argv
    command = argv[0]
    if command == "plan":
        if "--execute" in argv:
            raise ValueError("plan does not execute; use run with --execute")
        argv = ["run", *argv[1:]]
        command = "run"
    if command in ("run", "evaluate") and len(argv) > 1 and argv[1].lower().endswith(".json"):
        from pathlib import Path
        spec, extra = argv[1], argv[2:]
        expanded = [command, "phyediting", "--spec", spec, *extra]
        if command == "run" and not any(a == "--run-dir" or a.startswith("--run-dir=") for a in extra):
            expanded += ["--run-dir", str(Path("runs") / Path(spec).stem)]
        return expanded
    if command == "status" and len(argv) > 1 and not argv[1].startswith("-") and argv[1] not in config.BENCHMARKS:
        return ["status", "phyediting", "--run-dir", argv[1], *argv[2:]]
    return argv


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    if argv[:1] == ['prepare-gravity100']:
        from .gravity100 import prepare_main
        return prepare_main(argv[1:])
    if argv[:1] == ['measure'] and (len(argv) == 1 or argv[1] in ('-h', '--help')):
        parser = argparse.ArgumentParser(prog='physedit measure',
                    description='Measure gravity, kinetic friction and initial velocity from single-view observations.')
        commands = parser.add_subparsers(dest='parameter')
        for name, description in [('gravity', 'fit gravity from registered observations'),
                                  ('friction', 'estimate effective kinetic friction from sliding'),
                                  ('velocity', 'score initial velocity from saved predictions'),
                                  ('coverage-velocity', 'fit initial velocity from image trajectories'),
                                  ('kinematic-velocity', 'fit initial velocity on a known plane'),
                                  ('can-pixel-velocity', 'fit initial velocity from can contours'),
                                  ('book-pixel-velocity', 'fit initial velocity from book contours')]:
            commands.add_parser(name, help=description)
        parser.print_help()
        parser.exit(0)
    if argv and argv[0] in ("track", "measure"):
        if argv[0] == "track":
            from scripts.sam31_frontend import main as entry
        elif len(argv) > 1 and argv[1] == 'gravity':
            from gravtrace.__main__ import main as entry
            argv = [argv[0], 'fit', *argv[2:]]
        else:
            from scripts.phyediting_motion_parameters import main as entry
        original_argv = sys.argv
        try:
            sys.argv = ["physedit " + argv[0], *argv[1:]]
            return entry()
        finally:
            sys.argv = original_argv
    p = argparse.ArgumentParser(prog="physedit", description="Generate and evaluate video models on a PhysEdit benchmark.",
                                formatter_class=argparse.RawDescriptionHelpFormatter, epilog=__doc__)
    sub = p.add_subparsers(dest="cmd", required=True)
    for name in ("run", "status"):
        s = sub.add_parser(name)
        s.add_argument("benchmark", choices=sorted(config.BENCHMARKS))
        s.add_argument("--spec", help="PhyEditing local pipeline JSON registration")
        s.add_argument("--run-dir", help="PhyEditing immutable output directory")
        s.add_argument("--execute", action="store_true", help="PhyEditing explicit execution; default is plan only")
        s.add_argument("--models", default="all", help="comma-separated model keys (see `models`), or all")
        s.add_argument("--runs", help="comma-separated runs (default: every run of the benchmark)")
        s.add_argument("--tag", default="", help="separate namespace for a trial; trials are not evaluated")
        s.add_argument("--limit", type=int, help="only the first N rows of every run (tag defaults to smokeN)")
        s.add_argument("--hosts", help="comma-separated hosts the pass may use (default: all in config.HOSTS)")
        if name == "run":
            s.add_argument("--watch", type=float, metavar="MIN", help="repeat the pass every MIN minutes until done")
            s.add_argument("--dry-run", action="store_true", help="print what a pass would do, change nothing")
            s.add_argument("--retry", action="store_true",
                           help="restart workers that hit the restart limit and rerun failed evaluation stages")
    model_parser = sub.add_parser("models", help="list the registered one-click models")
    model_parser.add_argument("--json", action="store_true", help="sampling settings and native clock")
    sub.add_parser("plan", help="inspect a local pipeline configuration")
    sub.add_parser("track", help="SAM3.1 target tracking; use track --help")
    sub.add_parser("measure", help="gravity, friction and initial-velocity measurements; use measure --help")
    evaluation=sub.add_parser('evaluate',help='Evaluate existing PhyEditing media; no generation or new gravity fit')
    evaluation.add_argument('benchmark',choices=['phyediting'])
    evaluation.add_argument('--spec',required=True)
    evaluation.add_argument('--run-dir','--run',required=True)
    evaluation.add_argument('--output-dir','--out',required=True)
    evaluation.add_argument('--execute',action='store_true')
    try:
        argv = _short_command(argv)
    except ValueError as error:
        p.error(str(error))
    a = p.parse_args(argv)
    if a.cmd == 'plan':
        p.error('plan requires a JSON configuration: physedit plan pipeline.json')

    if a.cmd=='evaluate':
        import json
        from pathlib import Path
        from .evaluations import existing_run
        result=existing_run(json.loads(Path(a.spec).read_text()),a.run_dir,a.output_dir,a.execute)
        print(json.dumps(result,ensure_ascii=False,allow_nan=False))
        return int(bool(result.get('evaluation_failed',0)))

    if a.cmd == "models":
        from .runners.oneclick_registry import MODELS
        from .runners.model_parameters import parameters
        if a.json:
            import json
            from dataclasses import asdict
            print(json.dumps({key: dict(**asdict(m), sampling=parameters(key),
                supported_modes=(['i2v', 'v2v'] if key == 'ltx_i2v' else
                                 ['v2v_one_condition_frame', 'v2v_future'] if key == 'cosmos' else [m.mode]),
                future_prediction=(dict(history_frames=5, native_frames=81, evaluated_frames=77,
                                        predicted_frames=76, fps=16, post_condition_seconds=4.75)
                                   if key == 'cosmos' else None),
                post_condition_seconds=(m.frames-1)/m.fps) for key,m in MODELS.items()}, indent=2))
        else:
            for key, m in MODELS.items():
                settings = parameters(key)
                modes = ('i2v/v2v' if key == 'ltx_i2v' else 'i2v/v2v_future' if key == 'cosmos' else m.mode)
                print(f"{key:28} {m.frames:3} frames {m.fps:2} fps {modes:25} steps={settings['steps']} guidance={settings['guidance']}")
        return
    if a.benchmark == 'phyediting':
        if a.cmd == 'status':
            if not a.run_dir:
                p.error('PhyEditing status requires --run-dir')
            from pathlib import Path
            import json
            root = Path(a.run_dir)
            if not (root/'registered.json').is_file():
                p.error('PhyEditing run has no registered.json: '+str(root))
            print(json.dumps({name: json.loads((root/name).read_text()) for name in
                              ('registered.json', 'completed.json', 'failure.json') if (root/name).exists()}))
            return
        if not a.spec or not a.run_dir:
            p.error('PhyEditing run requires --spec and --run-dir')
        if a.watch or a.retry or a.hosts or a.limit or a.tag or a.runs or a.models != 'all':
            p.error('PhyEditing is local and one-shot; use the spec, no fleet/watch/retry/subset flags')
        from .phyediting import main as pipeline_main
        command = ['--spec', a.spec, '--run-dir', a.run_dir]
        if a.execute:
            command.append('--execute')
        if a.dry_run:
            command.append('--dry-run')
        return pipeline_main(command)
    if a.execute or a.spec or a.run_dir:
        p.error('spec/run-dir/execute are PhyEditing-only options')
    models = list(config.MODELS) if a.models == "all" else a.models.split(",")
    unknown = sorted(set(models) - set(config.MODELS))
    if unknown:
        p.error("unknown model(s): %s (see `python -m physedit models`)" % ", ".join(unknown))
    runs = a.runs.split(",") if a.runs else None
    if runs and set(runs) - set(config.BENCHMARKS[a.benchmark]["runs"]):
        p.error("runs of %s: %s" % (a.benchmark, ", ".join(config.BENCHMARKS[a.benchmark]["runs"])))
    tag = a.tag or ("smoke%d" % a.limit if a.limit else "")
    dry = a.cmd == "run" and a.dry_run
    hosts = a.hosts.split(",") if a.hosts else None
    if hosts and set(hosts) - set(config.HOSTS):
        p.error("unknown host(s): %s" % ", ".join(sorted(set(hosts) - set(config.HOSTS))))
    d = Driver(a.benchmark, models, runs, tag, a.limit, hosts, dry=dry, retry=a.cmd == "run" and a.retry,
               log=lambda *x: print(*x, flush=True))
    if a.cmd == "status":
        print(d.report(d.survey()))
        return

    os.makedirs(HUB_DIR, exist_ok=True)
    lock = open(os.path.join(HUB_DIR, d.bench + ".lock"), "w")
    try:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)      # one driver per benchmark namespace
    except BlockingIOError:
        sys.exit("another `physedit run %s` is active (lock %s)" % (d.bench, lock.name))
    while True:
        items = d.step()
        print(d.report(items) + "\n", flush=True)
        if dry or not a.watch or d.finished(items):
            break
        time.sleep(a.watch * 60)


if __name__ == "__main__":
    sys.exit(main())
