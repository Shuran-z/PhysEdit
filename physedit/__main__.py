"""python -m physedit {run,status,models} ...   Run it on the hub (WSL on the workstation), which reaches every host.

    python -m physedit run public211 --models ltx_i2v,cosmos3_nano          # one pass: start what can start
    python -m physedit run public211 --models all --watch 10                # repeat every 10 min until all is done
    python -m physedit run public211 --models ltx_i2v --limit 4             # trial: 4 rows per run, own namespace
    python -m physedit status public211 --models all                        # progress, ETAs, evaluation stages
"""
import argparse
import fcntl
import os
import sys
import time

from . import config
from .driver import HUB_DIR, Driver


def main(argv=None):
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
    sub.add_parser("models", help="list the registered models")
    evaluation=sub.add_parser('evaluate',help='Evaluate existing PhyEditing media; no generation or new gravity fit')
    evaluation.add_argument('benchmark',choices=['phyediting'])
    evaluation.add_argument('--spec',required=True)
    evaluation.add_argument('--run-dir',required=True)
    evaluation.add_argument('--output-dir',required=True)
    evaluation.add_argument('--execute',action='store_true')
    a = p.parse_args(argv)

    if a.cmd=='evaluate':
        import json
        from pathlib import Path
        from .evaluations import existing_run
        result=existing_run(json.loads(Path(a.spec).read_text()),a.run_dir,a.output_dir,a.execute)
        print(json.dumps(result,ensure_ascii=False,allow_nan=False))
        return int(bool(result.get('evaluation_failed',0)))

    if a.cmd == "models":
        for key, m in config.MODELS.items():
            print("%-26s %-27s %-19s %3d frames %2d fps %d GPU" % (key, m["name"], "/".join(m["cmd"]), m["frames"],
                                                                     m["fps"], m.get("gpus", 1)))
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
