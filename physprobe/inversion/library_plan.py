"""Library plan (2026-10-24): every (task, parameter) of the 99 Genesis tasks, one rule for all.
  g : absolute log grid 0.5 .. 25 m/s^2, ratio 1.12 (35 values) -> covers moon 1.62 .. 2.5x Earth for every task; tasks of a
      scene whose configs differ only in gravity (C01/C02/C03) share one library.
  mu: main contact pair of the readiness table (moving object + supporting plane, both set to the value -> effective pair
      friction = value under Genesis' max rule), truth x 1.15^k, k = -11..11 (k = 0 left out), clipped to [0.01, 2].
  v : tasks with speed_inversion; speed object = the speed_facts '<object>.initial_speed' entry on the main contact moving
      object, else the first one; truth x 1.12^k, k = -12..12 (k = 0 left out).
Values are ordered nearest-to-truth first and chunked (<= 6 per job, T15 friction 1 per job). Every simulation stops at
frame min(210, max horizon + 31) (physics_only.py --frames, validated per family, issue log F16) and keeps all objects
(occluders for the visible-part boxes). The truth itself is never in a library (known-answer tests); for generated videos
the existing true-parameter replays are added at evaluation time.
Usage: python library_plan.py -> library_plan.json + summary"""
import json, math
from pathlib import Path

from paths import WORK as B, CODE, gt, READINESS   # data dir (outside git) / code dir
man = json.load(open(B / 'manifest.json'))
H = json.load(open(B / 'horizons.json'))
R = {json.loads(l)['clip_id']: json.loads(l) for l in open(READINESS)}
REMOTE = '/home/wangzijun_p25/zhangshuran/core100_inversion/deploy'
G_GRID = [round(0.5 * 1.12 ** k, 5) for k in range(35)]
CHUNK = 6


def cfg_of(clip):
    f = B / 'cfg' / f'{clip}.json'
    return json.load(open(f)) if f.exists() else json.load(open(B / 't15' / f'{clip}_config.json'))


def physics_signature(c):
    """every numeric / boolean field of the config with its key path, gravity fields and strings (paths, sample names)
    dropped: two tasks with the same signature differ only in gravity"""
    out = []
    def walk(d, p):
        if isinstance(d, dict):
            for k, v in sorted(d.items()):
                if 'gravity' in k.lower(): continue
                walk(v, f'{p}.{k}')
        elif isinstance(d, list):
            for i, v in enumerate(d): walk(v, f'{p}[{i}]')
        elif isinstance(d, (bool, int, float)) and d is not None:
            out.append(f'{p}={d!r}')
    walk(c, '')
    return '\n'.join(out)


def frames_needed(clip):
    objs = H[clip]['objects']
    return min(210, max(o['horizon'] for o in objs.values()) + 31)


def ordered(vals, truth):
    return sorted(vals, key=lambda v: abs(math.log(v / truth)))


def obj_names(c):
    return {o.get('name') for o in c.get('dynamic_objects', [])}


clips = sorted(c for c in man if c != 'T06_C04' and H.get(c, {}).get('status') == 'OK')
jobs, notes = [], []
# --- gravity: share across C01-C03 of a scene when the dynamics configs are identical except gravity
groups = {}
for clip in clips:
    c = cfg_of(clip)
    key = (clip[:3], physics_signature(c), man[clip].get('runner'), man[clip]['renderer'], man[clip].get('wrapper_args', ''))
    groups.setdefault(key, []).append(clip)
g_libs = {}
for key, members in groups.items():
    lead = members[0]
    g_libs[lead] = dict(members=members, frames=max(frames_needed(m) for m in members))
for lead, gl in g_libs.items():
    truths = [-cfg_of(m)['scene_overrides']['gravity'][2] for m in gl['members']]
    vals = [v for v in G_GRID if all(abs(v / t - 1) > 0.01 for t in truths)]
    vals = ordered(vals, truths[0])
    jobs.append(dict(lib=f'{lead}_g', clip=lead, param='g', members=gl['members'], truths=truths, values=vals, frames=gl['frames']))
# --- friction and speed: per task
for clip in clips:
    c = cfg_of(clip); r = R[clip]; names = obj_names(c)
    mcf = r['main_contact_friction'] if isinstance(r['main_contact_friction'], dict) else json.loads(r['main_contact_friction'])
    mu = float(mcf['effective_mu_max_rule'])
    fobjs = [o for o in (mcf['moving'], mcf['plane']) if o in names]
    if clip.startswith('T15'): fobjs = ['(t15 runner: tabletop plane)']
    if not fobjs: notes.append(f'{clip}: no friction object found ({mcf["moving"]}, {mcf["plane"]})')
    else:
        if len(fobjs) == 1 and not clip.startswith('T15'): notes.append(f'{clip}: friction plane {mcf["plane"]} not a config object; varying {fobjs[0]} only')
        vals = sorted({round(min(2.0, max(0.01, mu * 1.15 ** k)), 6) for k in range(-11, 12) if k != 0})
        if mcf['plane'] not in names and not clip.startswith('T15'):
            # the plane is a background mesh at Genesis' default friction 1.0: below that the pair friction stays 1.0
            # (max rule), so only values above 1.0 change anything (issue log B20)
            vals = [v for v in vals if v > 1.0]
        vals = ordered([v for v in vals if abs(v / mu - 1) > 0.01], mu)
        jobs.append(dict(lib=f'{clip}_mu', clip=clip, param='mu', members=[clip], truths=[mu], values=vals, frames=frames_needed(clip),
                         friction_objects=','.join(fobjs)))
    if r['speed_inversion']:
        sf = r['speed_facts'] if isinstance(r['speed_facts'], dict) else json.loads(r['speed_facts'])
        cand = [(k.rsplit('.', 1)[0], float(v)) for k, v in sf.items() if k.endswith('.initial_speed')]
        pick = next((x for x in cand if x[0] == mcf['moving']), cand[0] if cand else None)
        if pick is None or (not clip.startswith('T15') and pick[0] not in names):
            notes.append(f'{clip}: speed object not found ({sf})'); continue
        obj, v0 = pick
        vals = ordered([round(v0 * 1.12 ** k, 6) for k in range(-12, 13) if k != 0], v0)
        jobs.append(dict(lib=f'{clip}_v', clip=clip, param='v', members=[clip], truths=[v0], values=vals, frames=frames_needed(clip), speed_object=obj))

# --- chunk into queue jobs
plan = []
for j in jobs:
    m = man[j['clip']]
    n = 1 if (j['clip'].startswith('T15') and j['param'] == 'mu') else CHUNK
    movers = [j['speed_object']] if j.get('speed_object') else []
    for i in range(0, len(j['values']), n):
        q = dict(tag=f"{j['lib']}_{i // n:02d}", lib=j['lib'], clip=j['clip'], param=j['param'], values=j['values'][i:i + n],
                 renderer=m['renderer'], renderer_args=m.get('renderer_args', ''), movers=movers + ['ALL'] if movers else ['ALL'],
                 config=f"{REMOTE}/cfg/{j['clip']}.json", wrapper_args=(m.get('wrapper_args', '') + f" --frames {j['frames']}").strip())
        if j.get('friction_objects'): q['friction_objects'] = j['friction_objects']
        if m.get('runner') == 't15':
            q.update(runner='t15', config=f"{REMOTE}/t15/{j['clip']}_config.json", physics=f"{REMOTE}/t15/{j['clip']}_physics.json")
            q.pop('wrapper_args')
        plan.append(q)
json.dump(dict(libraries=jobs, notes=notes), open(B / 'library_index.json', 'w'), indent=1)
json.dump(plan, open(B / 'library_plan.json', 'w'), indent=1)
shared = [j for j in jobs if j['param'] == 'g' and len(j['members']) > 1]
print(f"{len(jobs)} libraries ({sum(j['param'] == 'g' for j in jobs)} g [{len(shared)} shared by {sum(len(j['members']) for j in shared)} tasks], "
      f"{sum(j['param'] == 'mu' for j in jobs)} mu, {sum(j['param'] == 'v' for j in jobs)} v), {len(plan)} queue jobs, {sum(len(q['values']) for q in plan)} simulations")
for n_ in notes: print('  NOTE', n_)
