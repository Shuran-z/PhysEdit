"""Method-comparison figure for the simulator inversion (PhyResponse benchmark).

Every curve is computed here. One example scene throughout: a block slides along a table with Coulomb friction,
leaves the edge, flies, and lands on the floor. A known pinhole camera views the motion obliquely. Three ways to
measure the physics from the tracked boxes of one video:
  (a) 2D bounding box: parabola fit to the image-plane trajectory, pixel -> metre with the known camera -> g
  (b) depth lifting: lift the box centre with a monocular depth estimate (few-percent error), fit along gravity -> g
  (c) simulator inversion: replay the task scene over a discrete log grid of parameter values, project the boxes,
      Huber loss against the tracked boxes inside the predictability window, free onset shift, local quadratic,
      delta threshold -> g, mu, v.
The matching and estimate follow physprobe/inversion/evaluator.py (loss normalisation, Huber k, shift grid,
condition-frame alignment, GATE, estimate_band with the 5-point weighted quadratic).

Writes: inversion_method_comparison.svg / .pdf and inversion_method_comparison.json (the computed numbers) next to this script.
Run: python docs/figures/make_inversion_figure.py
"""
import json
import math
from pathlib import Path

import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle, FancyBboxPatch, FancyArrowPatch, Polygon

OUT = Path(__file__).resolve().parent
RNG_SEED = 7

# ----------------------------------------------------------------------------------------------------------------
# Scene, camera, clock
# ----------------------------------------------------------------------------------------------------------------
G_TRUE, MU_TRUE, V_TRUE = 9.81, 0.20, 2.50   # physics shown by the example video (= the task's values)
H_TABLE = 0.90            # table height (m); table top spans x in [-1.6, 0], edge at x = 0
X0 = -1.00                # initial block centre (m)
S_BLOCK = 0.15            # cube edge (m)
FPS = 24.0
DT = 1.0 / FPS
F_SIM = 81                # simulated frames (sim frame 0 = condition frame = initial state)
N_OBS = 49                # frames of the generated video
ONSET_OBS = 3             # the video starts the motion at its frame 3 (unknown to every method)
CF = 0                    # condition frame (videos generated from the first frame)
SIGMA_PX = 1.5            # tracking noise (px)
HUBER_K = 0.02            # Huber knee, in units of the box diagonal (evaluator: huber(x, k=0.02))
SHIFTS = np.arange(-20, 20 + 0.01, 0.25)
MIN_FRAMES = 3
GATE = 10.0               # best loss above this (~3 sigma rms) -> not explained
DELTA = 1.0               # identifiability threshold (calibrated on reference videos)
MU_FLOOR = 0.45           # floor friction after landing

IMG_W, IMG_H, FOCAL = 832, 480, 640.0
TARGET = np.array([-0.30, 0.0, 0.55])
CAM_DIST, CAM_YAW, CAM_PITCH = 3.0, math.radians(35.0), math.radians(22.0)


def camera():
    d = np.array([math.sin(CAM_YAW) * math.cos(CAM_PITCH), -math.cos(CAM_YAW) * math.cos(CAM_PITCH), math.sin(CAM_PITCH)])
    C = TARGET + CAM_DIST * d
    fwd = (TARGET - C) / np.linalg.norm(TARGET - C)
    right = np.cross(fwd, [0, 0, 1.0]); right /= np.linalg.norm(right)
    down = np.cross(fwd, right)
    R = np.stack([right, down, fwd])          # world -> camera rows (x right, y down, z forward)
    return C, R


CAM_C, CAM_R = camera()


def project(P):
    """world points (..., 3) -> pixels (..., 2) and camera depth (...)"""
    Pc = (np.asarray(P) - CAM_C) @ CAM_R.T
    u = FOCAL * Pc[..., 0] / Pc[..., 2] + IMG_W / 2
    v = FOCAL * Pc[..., 1] / Pc[..., 2] + IMG_H / 2
    return np.stack([u, v], -1), Pc[..., 2]


def backproject(uv, Z):
    """pixels + camera depth -> world points"""
    x = (uv[..., 0] - IMG_W / 2) / FOCAL * Z
    y = (uv[..., 1] - IMG_H / 2) / FOCAL * Z
    Pc = np.stack([x, y, Z], -1)
    return Pc @ CAM_R + CAM_C


CORNERS = np.array([[sx, sy, sz] for sx in (-.5, .5) for sy in (-.5, .5) for sz in (-.5, .5)]) * S_BLOCK


def boxes_of(centres):
    uv, _ = project(centres[:, None, :] + CORNERS[None])
    return np.concatenate([uv.min(1), uv.max(1)], -1)          # x1, y1, x2, y2


# ----------------------------------------------------------------------------------------------------------------
# Simulator: Coulomb sliding -> projectile -> landing (contact outcome varies between replays)
# ----------------------------------------------------------------------------------------------------------------
def simulate(g, mu, v, n=F_SIM, replay=0, accel_extra=0.0):
    """block centre per frame; time origin = frame 0. replay: contact-solver seed of the landing.
    accel_extra: an extra horizontal acceleration while sliding (only used to build the unexplained example)."""
    rng = np.random.default_rng(1000 + replay)
    u_kick, lat, e = rng.uniform(0.25, 0.65), rng.normal(0, 0.12), rng.uniform(0.05, 0.30)
    zc = H_TABLE + S_BLOCK / 2
    a = -mu * g + accel_extra                       # horizontal acceleration on the table
    t = np.arange(n) * DT
    P = np.zeros((n, 3)); phase = np.zeros(n, int)   # 0 slide/rest on table, 1 flight, 2 after landing
    # slide
    if a < 0:
        disc = v * v + 2 * a * (0 - X0)
        t_stop = -v / a
    else:
        disc = v * v + 2 * a * (0 - X0); t_stop = np.inf
    if disc < 0:                                     # stops on the table
        tt = np.minimum(t, t_stop)
        P[:, 0] = X0 + v * tt + 0.5 * a * tt * tt; P[:, 2] = zc
        return P, phase, dict(t_edge=np.inf, t_land=np.inf)
    v_e = math.sqrt(disc)
    t_e = (v_e - v) / a if a != 0 else -X0 / v
    t_f = math.sqrt(2 * H_TABLE / g)
    for i, ti in enumerate(t):
        if ti <= t_e:
            P[i] = [X0 + v * ti + 0.5 * a * ti * ti, 0, zc]
        elif ti <= t_e + t_f:
            s = ti - t_e; P[i] = [v_e * s, 0, zc - 0.5 * g * s * s]; phase[i] = 1
        else:
            s = ti - t_e - t_f
            x_l = v_e * t_f; vx, vy = v_e * u_kick, v_e * lat
            vz = e * g * t_f
            t_b = 2 * vz / g                         # one bounce, then slide to rest
            hop = vz * s - 0.5 * g * s * s if s < t_b else 0.0
            vh = math.hypot(vx, vy); ts = min(s, vh / (MU_FLOOR * g))
            dist = vh * ts - 0.5 * MU_FLOOR * g * ts * ts
            P[i] = [x_l + dist * vx / vh, dist * vy / vh, S_BLOCK / 2 + max(hop, 0.0)]; phase[i] = 2
    return P, phase, dict(t_edge=t_e, t_land=t_e + t_f, v_edge=v_e)


# ----------------------------------------------------------------------------------------------------------------
# Observation: the generated video (motion starts at frame ONSET_OBS), tracked boxes with 1.5 px noise
# ----------------------------------------------------------------------------------------------------------------
def observe(g, mu, v, rng, accel_extra=0.0, replay=99):
    P, phase, info = simulate(g, mu, v, n=N_OBS, replay=replay, accel_extra=accel_extra)
    k = np.arange(N_OBS); src = np.clip(k - ONSET_OBS, 0, None)
    Pobs = P[src]; ph = np.where(k < ONSET_OBS, 0, phase[src])
    clean = boxes_of(Pobs)
    noisy = clean + rng.normal(0, SIGMA_PX, clean.shape)
    return dict(k=k, P=Pobs, phase=ph, clean=clean, boxes=noisy, info=info)


# ----------------------------------------------------------------------------------------------------------------
# Predictability window: frames where repeated replays of the task agree to within 1.5 px
# ----------------------------------------------------------------------------------------------------------------
def predictability_horizon(n_rep=16):
    B = np.stack([boxes_of(simulate(G_TRUE, MU_TRUE, V_TRUE, replay=r)[0]) for r in range(n_rep)])
    spread = np.abs(B - B[0:1]).max((0, 2))
    bad = np.where(spread > SIGMA_PX)[0]
    return (int(bad[0]) - 1 if len(bad) else F_SIM - 1), spread


# ----------------------------------------------------------------------------------------------------------------
# Matching (evaluator.py): condition-frame alignment, free shift, Huber on box residuals / box diagonal
# ----------------------------------------------------------------------------------------------------------------
def huber(x, k=HUBER_K):
    a = np.abs(x); return np.where(a <= k, 0.5 * x * x, k * (a - 0.5 * k))


def loss_curve(ob, sim_boxes, horizon):
    s0 = CF + np.arange(len(ob)).astype(float)          # same frame rate: observed frame k <-> sim frame k
    i0 = 0
    d0 = float(np.linalg.norm(ob[i0, 2:] - ob[i0, :2]))
    out_L, out_d = [], []
    for sb in sim_boxes:
        F = len(sb)
        o = ob - (ob[i0] - sb[CF])                       # condition-frame calibration
        S = s0[None, :] + SHIFTS[:, None]
        in_t = (S >= CF) & (S <= horizon)
        Sc = np.clip(S, 0, F - 1); f0 = np.floor(Sc).astype(int); w = (Sc - f0)[..., None]; f1 = np.minimum(f0 + 1, F - 1)
        pred = (1 - w) * sb[f0] + w * sb[f1]
        rr = np.where(in_t[..., None], (pred - o[None]) / d0, 0.0)
        lf = huber(rr).sum(-1) / (2 * (SIGMA_PX / d0) ** 2)
        cnt = in_t.sum(1)
        per = np.where(in_t, lf, 0.0).sum(1) / np.maximum(cnt, 1)
        per = np.where(cnt >= MIN_FRAMES, per, np.inf)
        j = int(np.argmin(per)); out_L.append(float(per[j])); out_d.append(float(SHIFTS[j]))
    return np.array(out_L), np.array(out_d)


def estimate_band(vs, ys, delta=DELTA):
    """evaluator.estimate_band (VERTEX = local5): values within delta of the minimum are indistinguishable."""
    vs, ys = np.asarray(vs, float), np.asarray(ys, float)
    o = np.argsort(vs); vs, ys = vs[o], ys[o]; n = len(vs)
    i = int(np.argmin(ys)); m = ys <= ys[i] + delta; idx = np.where(m)[0]; jlo, jhi = int(idx.min()), int(idx.max())
    if (m[0] and m[-1]) or (m[0] and jhi >= n - 2) or (m[-1] and jlo <= 1):
        return dict(kind='unidentifiable', est=None, band=(float(vs[0]), float(vs[-1])))
    if m[0]: return dict(kind='upper_bound', est=None, band=(float(vs[0]), float(vs[min(jhi + 1, n - 1)])))
    if m[-1]: return dict(kind='lower_bound', est=None, band=(float(vs[max(jlo - 1, 0)]), float(vs[-1])))
    lo_lim, hi_lim = float(vs[jlo - 1]), float(vs[jhi + 1])
    sel = np.arange(max(i - 2, 0), min(i + 3, n))
    x = np.log(vs[sel]); w = np.exp(-(ys[sel] - ys[i]) / (4 * delta))
    a, b, c = np.polyfit(x, ys[sel], 2, w=w)
    llo, lhi = math.log(lo_lim), math.log(hi_lim)
    if a > 0:
        x0 = -b / (2 * a); hw = math.sqrt(delta / a)
        est = math.exp(min(max(x0, llo), lhi))
        qlo, qhi = math.exp(min(max(x0 - hw, llo), lhi)), math.exp(min(max(x0 + hw, llo), lhi))
    else:
        est = float(vs[i]); qlo, qhi = float(vs[jlo]), float(vs[jhi])
    band = (max(min(qlo, float(vs[jlo])), lo_lim), min(max(qhi, float(vs[jhi])), hi_lim))
    est = min(max(est, band[0]), band[1])
    kind = 'interval' if band[1] / band[0] > 1.25 else 'point'
    return dict(kind=kind, est=est if kind == 'point' else None, center=est, band=(float(band[0]), float(band[1])),
                quad=(float(a), float(b), float(c)), sel=[float(s) for s in vs[sel]], i_min=i)


# ----------------------------------------------------------------------------------------------------------------
# Libraries (truth never on the grid)
# ----------------------------------------------------------------------------------------------------------------
def grids():
    g = 0.5 * 1.12 ** np.arange(0, 60); g = g[g <= 25.0]
    j = np.arange(-8, 9)
    mu = MU_TRUE * 1.15 ** (j + 0.4)
    v = V_TRUE * 1.12 ** (j + 0.4)
    return dict(g=g, mu=mu, v=v)


def run_library(param, values, ob, horizon):
    sims = []
    for x in values:
        kw = dict(g=G_TRUE, mu=MU_TRUE, v=V_TRUE); kw[param] = x
        sims.append(boxes_of(simulate(**kw, replay=0)[0]))
    L, d = loss_curve(ob, sims, horizon)
    return L, d, sims


# ----------------------------------------------------------------------------------------------------------------
# Baselines
# ----------------------------------------------------------------------------------------------------------------
def quad_fit(t, y):
    """y = c0 + c1 t + c2 t^2; returns coefficients and the standard error of c2"""
    A = np.stack([np.ones_like(t), t, t * t], 1)
    coef, res, *_ = np.linalg.lstsq(A, y, rcond=None)
    dof = max(len(t) - 3, 1)
    s2 = float(((A @ coef - y) ** 2).sum()) / dof
    cov = s2 * np.linalg.inv(A.T @ A)
    return coef, math.sqrt(cov[2, 2])


def baseline_2d(obs, frames):
    """parabola in the image plane; pixels -> metres at the depth where the block meets the floor, found by
    intersecting the camera ray through the bottom of its box with the floor (known camera, floor z = 0)"""
    bx = obs['boxes']; uc = 0.5 * (bx[:, 0] + bx[:, 2]); vc = 0.5 * (bx[:, 1] + bx[:, 3])
    t = obs['k'] * DT
    land = int(np.where(obs['phase'] == 2)[0][0])
    foot = np.array([uc[land], bx[land, 3]])
    ray = backproject(foot, 1.0) - CAM_C
    lam = -CAM_C[2] / ray[2]
    Z = float((lam * ray) @ CAM_R[2])
    scale = Z / FOCAL                                    # metres per pixel
    coef, se = quad_fit(t[frames], vc[frames])
    g = 2 * coef[2] * scale
    height = -(vc - vc[frames][0]) * scale + 0.0         # image-derived height (m), relative to take-off
    return dict(g=float(g), g_se=float(2 * se * scale), scale=scale, Z=Z, coef=coef, height=height, t=t)


def baseline_depth(obs, frames, rng, scale_err=0.04, frame_err=0.02):
    bx = obs['boxes']; uv = np.stack([0.5 * (bx[:, 0] + bx[:, 2]), 0.5 * (bx[:, 1] + bx[:, 3])], 1)
    _, Ztrue = project(obs['P'])
    Zest = Ztrue * (1 + scale_err + rng.normal(0, frame_err, len(Ztrue)))
    Pw = backproject(uv, Zest)
    t = obs['k'] * DT
    coef, se = quad_fit(t[frames], Pw[frames, 2])
    return dict(g=float(-2 * coef[2]), g_se=float(2 * se), coef=coef, z=Pw[:, 2], t=t, Zest=Zest, Ztrue=Ztrue)


# ----------------------------------------------------------------------------------------------------------------
# Compute everything
# ----------------------------------------------------------------------------------------------------------------
def compute():
    rng = np.random.default_rng(RNG_SEED)
    obs = observe(G_TRUE, MU_TRUE, V_TRUE, rng)
    horizon, spread = predictability_horizon()
    air = np.where(obs['phase'] == 1)[0]
    moving = np.where((obs['k'] >= ONSET_OBS) & (obs['phase'] < 2))[0]
    b2 = baseline_2d(obs, air); b2_all = baseline_2d(obs, moving)
    bd = baseline_depth(obs, air, np.random.default_rng(RNG_SEED + 1))
    bd_all = baseline_depth(obs, moving, np.random.default_rng(RNG_SEED + 1))
    G = grids(); res = {}
    for p in ('g', 'mu', 'v'):
        L, d, sims = run_library(p, G[p], obs['boxes'], horizon)
        e = estimate_band(G[p], L)
        res[p] = dict(values=G[p], loss=L, shift=d, sims=sims, est=e)
    # a second video that no value explains: the block speeds up on the table (+3 m/s^2) before it leaves the edge
    obs_bad = observe(G_TRUE, MU_TRUE, V_TRUE, np.random.default_rng(RNG_SEED + 2), accel_extra=3.0 + MU_TRUE * G_TRUE)
    Lb, _, _ = run_library('g', G['g'], obs_bad['boxes'], horizon)
    return dict(obs=obs, horizon=horizon, spread=spread, air=air, moving=moving, b2=b2, b2_all=b2_all, bd=bd,
                bd_all=bd_all, res=res, bad=dict(obs=obs_bad, loss=Lb))


# ----------------------------------------------------------------------------------------------------------------
# Figure
# ----------------------------------------------------------------------------------------------------------------
C_OBS = '#D55E00'      # tracked observation (Okabe-Ito vermillion)
C_SIM = '#0072B2'      # simulation / library (Okabe-Ito blue)
C_SIM_L = '#9CC3E0'    # other library members
C_FIT = '#222222'      # baseline fits
C_MUTE = '#9A9A9A'
C_INK = '#222222'
C_INK2 = '#555555'
C_BAND = '#D6E6F3'
C_OURS_BG = '#F1F6FB'
FS = 7.0


def setup_mpl():
    plt.rcParams.update({
        'font.family': 'sans-serif', 'font.sans-serif': ['Arial', 'Helvetica', 'DejaVu Sans'],
        'font.size': FS, 'axes.labelsize': FS, 'xtick.labelsize': FS, 'ytick.labelsize': FS,
        'axes.linewidth': 0.6, 'xtick.major.width': 0.6, 'ytick.major.width': 0.6,
        'xtick.major.size': 2.0, 'ytick.major.size': 2.0, 'xtick.minor.size': 1.2, 'ytick.minor.size': 1.2,
        'xtick.major.pad': 1.5, 'ytick.major.pad': 1.5, 'axes.labelpad': 1.5,
        'axes.edgecolor': '#444444', 'xtick.color': '#444444', 'ytick.color': '#444444', 'axes.labelcolor': C_INK,
        'svg.fonttype': 'none', 'svg.hashsalt': 'phyresponse', 'pdf.fonttype': 42, 'ps.fonttype': 42,
        'axes.spines.top': False, 'axes.spines.right': False, 'lines.solid_capstyle': 'round',
    })


W_IN, H_IN = 6.9, 4.62


def ax_in(fig, x, y, w, h, **kw):
    return fig.add_axes([x / W_IN, y / H_IN, w / W_IN, h / H_IN], **kw)


def fig_text(fig, x, y, s, **kw):
    kw.setdefault('fontsize', FS); kw.setdefault('color', C_INK)
    return fig.text(x / W_IN, y / H_IN, s, **kw)


def chip(fig, x, y, s, w=0.70, h=0.165, strong=False):
    p = FancyBboxPatch((x / W_IN, y / H_IN), w / W_IN, h / H_IN, boxstyle='round,pad=0,rounding_size=0.006',
                       transform=fig.transFigure, fc='white', ec=(C_SIM if strong else '#8A8A8A'), lw=0.6)
    fig.patches.append(p)
    fig_text(fig, x + w / 2, y + h / 2, s, ha='center', va='center_baseline')


def arrow(fig, x0, y0, x1, y1, color='#8A8A8A', rad=0.0):
    a = FancyArrowPatch((x0 / W_IN, y0 / H_IN), (x1 / W_IN, y1 / H_IN), transform=fig.transFigure,
                        arrowstyle='-|>,head_length=3,head_width=1.6', lw=0.7, color=color,
                        connectionstyle=f'arc3,rad={rad}', shrinkA=0, shrinkB=0)
    fig.patches.append(a)


def table_hull():
    xs, ys, zs = (-1.6, 0.0), (-0.4, 0.4), (0.0, H_TABLE)
    uv, _ = project(np.array([[x, y, z] for x in xs for y in ys for z in zs]))
    pts = uv[np.lexsort((uv[:, 1], uv[:, 0]))]
    def cross(o, a, b): return (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0])
    lower, upper = [], []
    for q in pts:
        while len(lower) >= 2 and cross(lower[-2], lower[-1], q) <= 0: lower.pop()
        lower.append(tuple(q))
    for q in pts[::-1]:
        while len(upper) >= 2 and cross(upper[-2], upper[-1], q) <= 0: upper.pop()
        upper.append(tuple(q))
    hull = np.array(lower[:-1] + upper[:-1])
    top = project(np.array([[x, y, H_TABLE] for x, y in ((-1.6, -0.4), (0, -0.4), (0, 0.4), (-1.6, 0.4))]))[0]
    return hull, top


def draw_scene(ax, hull, top):
    ax.add_patch(Polygon(hull, closed=True, fc='#E9E9E9', ec='#B0B0B0', lw=0.5, zorder=0))
    ax.add_patch(Polygon(top, closed=True, fc='#F8F8F8', ec='#B0B0B0', lw=0.5, zorder=0))


def boxes_patch(ax, b, **kw):
    for x1, y1, x2, y2 in b:
        ax.add_patch(Rectangle((x1, y1), x2 - x1, y2 - y1, fill=False, **kw))


XLIM_F = (0.8, 1.2)


def forest(ax, rows):
    """rows: (label, kind, a, b) in units of value / true. kind 'base': point a with half width b (black);
    'ours': accepted range a..b (blue band) with the point estimate in rows[...][4]; 'none': not measured"""
    n = len(rows)
    ax.axvline(1.0, color=C_INK, lw=0.6, ls=(0, (2, 1.5)), zorder=1)
    for i, row in enumerate(rows):
        lab, kind, a, b = row[:4]; y = n - 1 - i
        if kind == 'ours':
            ax.add_patch(Rectangle((a, y - 0.2), b - a, 0.4, fc=C_BAND, ec=C_SIM, lw=0.6, zorder=2))
            if row[4] is not None: ax.plot([row[4]], [y], 'o', ms=3.0, color=C_SIM, zorder=3)
        elif kind == 'base':
            ax.plot([max(a - b, XLIM_F[0]), min(a + b, XLIM_F[1])], [y, y], color=C_FIT, lw=0.8, zorder=2)
            ax.plot([a], [y], 'o', ms=3.0, color=C_FIT, zorder=3)
        else:
            ax.text(1.0, y, 'not measured', ha='center', va='center', color=C_INK2, fontsize=FS,
                    bbox=dict(fc='white', ec='none', pad=0.6), zorder=3)
    ax.set_xlim(*XLIM_F); ax.set_ylim(-0.6, n - 0.4)
    ax.set_yticks(range(n)); ax.set_yticklabels([r[0] for r in rows[::-1]])
    ax.tick_params(axis='y', length=0, pad=3)
    ax.spines['left'].set_visible(False)
    ax.set_xticks([0.8, 0.9, 1.0, 1.1, 1.2]); ax.set_xticklabels(['0.8', '', '1', '', '1.2'])
    ax.patch.set_alpha(0)


def traj_panel(ax, t, h, idx, fit_coef, fit_all, label_fit, sub0, t_end):
    """height-vs-time panel of a baseline"""
    slide, air, land, mov = idx
    for s in (slide, land):
        ax.plot(t[s], h[s], 'o', ms=2.4, mfc='none', mec=C_MUTE, mew=0.6, zorder=2)
    ax.plot(t[air], h[air], 'o', ms=2.7, color=C_OBS, mew=0, zorder=3)
    tt = np.linspace(t[mov[0]], t[mov[-1]], 120)
    ax.plot(tt, np.polyval(fit_all[::-1], tt) - sub0, color=C_MUTE, lw=0.7, ls=(0, (3, 2)), zorder=1)
    ta = np.linspace(t[air[0]] - 0.015, t[air[-1]] + 0.015, 60)
    ax.plot(ta, np.polyval(fit_coef[::-1], ta) - sub0, color=C_FIT, lw=1.0, zorder=4)
    ax.set_xlim(0, t_end); ax.set_ylim(-1.18, 0.42)
    ax.set_yticks([-1, 0]); ax.set_ylabel('height (m)', labelpad=1)
    ax.set_xticks([0, 0.5, 1.0, 1.5, 2.0]); ax.set_xlabel('time (s)', labelpad=0.5)
    ax.text(0.03, 0.12, 'sliding: not free flight, unused', ha='left', va='bottom', color=C_INK2)
    ax.text(t[air[-1]] + 0.06, -0.22, label_fit, va='center', ha='left', color=C_INK, linespacing=1.1)
    ax.text(t[land[-1]], -0.84, 'after landing: unused', ha='right', va='bottom', color=C_INK2)


def make_figure(D):
    setup_mpl()
    fig = plt.figure(figsize=(W_IN, H_IN))
    obs, res, air, hz = D['obs'], D['res'], D['air'], D['horizon']
    hull, top = table_hull()
    k = obs['k']; t = k * DT; t_end = t[-1] + DT
    bx = obs['boxes']; vc = 0.5 * (bx[:, 1] + bx[:, 3])
    slide = np.where(obs['phase'] == 0)[0]; land = np.where(obs['phase'] == 2)[0]
    mov = D['moving']; idx = (slide, air, land, mov)

    # layout (inches)
    XL, VW = 0.05, 1.20
    XC = 1.40
    XP, WPAB = 2.40, 2.58
    WP1, XP2, WP2 = 1.20, 3.92, 1.06
    XO, WO = 5.30, 0.62
    XT = XO + WO + 0.08
    row = dict(a=(3.66, 0.58), b=(2.46, 0.58), c=(0.42, 1.36))
    head = dict(a=4.50, b=3.30, c=2.07)

    bg = FancyBboxPatch((1.33 / W_IN, 0.03 / H_IN), (W_IN - 1.36) / W_IN, 2.20 / H_IN,
                        boxstyle='round,pad=0,rounding_size=0.012', transform=fig.transFigure, fc=C_OURS_BG, ec='none', zorder=-5)
    fig.patches.append(bg)
    fig.add_artist(plt.Line2D([1.36 / W_IN, (W_IN - 0.03) / W_IN], [3.43 / H_IN] * 2, transform=fig.transFigure, color='#D9D9D9', lw=0.6))

    # ---- shared input: the generated video with its tracked boxes
    vh = VW * IMG_H / IMG_W; vy = 2.30
    axv = ax_in(fig, XL, vy, VW, vh)
    draw_scene(axv, hull, top)
    boxes_patch(axv, bx[np.arange(ONSET_OBS, N_OBS, 2)], ec=C_OBS, lw=0.5)
    axv.set_xlim(0, IMG_W); axv.set_ylim(IMG_H, 0); axv.set_xticks([]); axv.set_yticks([])
    for s in axv.spines.values(): s.set_visible(True); s.set_color('#777777'); s.set_linewidth(0.6)
    fig_text(fig, XL + VW / 2, vy + vh + 0.08, 'Generated video', ha='center', fontweight='bold', fontsize=7.5)
    fig_text(fig, XL + VW / 2, vy - 0.06, 'tracked object boxes', ha='center', va='top', color=C_OBS)
    fig_text(fig, XL + VW / 2, vy - 0.20, 'slide, take-off, flight,\nlanding', ha='center', va='top', color=C_INK2,
             linespacing=1.1)

    # ---- headers, inputs, arrows
    names = dict(a='(a) 2D bounding box', b='(b) Depth lifting', c='(c) Simulator inversion (ours)')
    for r, s in names.items():
        fig_text(fig, XC, head[r], s, fontweight='bold', fontsize=7.5, va='center', color=(C_SIM if r == 'c' else C_INK))
    ch = dict(a=['tracked boxes', 'camera'], b=['tracked boxes', 'camera', 'depth model'],
              c=['tracked boxes', 'camera', 'task scene'])
    mids = {}
    for r, items in ch.items():
        yb, hh = row[r]; n = len(items); gap = 0.215
        y0 = yb + hh / 2 + (n - 1) * gap / 2 - 0.0825 + (0.08 if r == 'c' else 0.0)
        for i, s in enumerate(items):
            chip(fig, XC, y0 - i * gap, s, strong=(r == 'c'))
        mids[r] = y0 - (n - 1) * gap / 2 + 0.0825
    fig_text(fig, XC + 0.35, y0 - 2 * 0.215 - 0.03, 'initial state', ha='center', va='top', color=C_INK2)
    for r, rad in (('a', -0.2), ('b', 0.0), ('c', 0.2)):
        arrow(fig, XL + VW + 0.03, vy + vh / 2, XC - 0.03, mids[r], rad=rad)

    # ---- (a) image-plane parabola, pixels -> metres
    b2, b2a = D['b2'], D['b2_all']
    yb, hh = row['a']; ax = ax_in(fig, XP, yb, WPAB, hh)
    sc = b2['scale']; ref = vc[air[0]]
    traj_panel(ax, t, -(vc - ref) * sc, idx, -np.array(b2['coef']) * sc, -np.array(b2a['coef']) * sc,
               f'image-plane parabola, px → m\n(dashed: all frames, g = {b2a["g"]:.1f})', -ref * sc, t_end)

    # ---- (b) depth lifting
    bd, bda = D['bd'], D['bd_all']
    yb, hh = row['b']; ax = ax_in(fig, XP, yb, WPAB, hh)
    z0 = bd['z'][air[0]]
    traj_panel(ax, t, bd['z'] - z0, idx, np.array(bd['coef']), np.array(bda['coef']),
               f'3D parabola along gravity\n(dashed: all frames, g = {bda["g"]:.1f})', z0, t_end)

    # ---- (c1) image plane: tracked boxes vs library replays inside the predictability window
    rg = res['g']; e = rg['est']; vals = rg['values']; L = rg['loss']; ib = int(np.argmin(L))
    yb, hh = row['c']
    ax = ax_in(fig, XP, yb, WP1, hh)
    draw_scene(ax, hull, top)
    S_best = k + rg['shift'][ib]
    inwin = (S_best >= CF) & (S_best <= hz) & (k >= ONSET_OBS)
    outwin = ~((S_best >= CF) & (S_best <= hz)) & (k >= ONSET_OBS)
    o = bx - (bx[0] - rg['sims'][ib][CF])
    ss = np.arange(CF, hz + 1)
    for j in (ib - 3, ib - 1, ib + 1, ib + 3):
        sb = rg['sims'][j]
        ax.plot(0.5 * (sb[ss, 0] + sb[ss, 2]), 0.5 * (sb[ss, 1] + sb[ss, 3]), color=C_SIM_L, lw=0.8, zorder=2)
    sb = rg['sims'][ib]
    ax.plot(0.5 * (sb[ss, 0] + sb[ss, 2]), 0.5 * (sb[ss, 1] + sb[ss, 3]), color=C_SIM, lw=1.2, zorder=3)
    boxes_patch(ax, o[inwin][::2], ec=C_OBS, lw=0.55, zorder=4)
    boxes_patch(ax, o[outwin][::2], ec=C_MUTE, lw=0.55, ls=(0, (1.6, 1.2)), zorder=4)
    sel = k >= ONSET_OBS
    xs, ys = o[sel][:, [0, 2]].ravel(), o[sel][:, [1, 3]].ravel()
    x0_, x1_, y0_, y1_ = xs.min() - 70, xs.max() + 12, ys.min() - 22, ys.max() + 12
    asp = hh / WP1
    if (y1_ - y0_) / (x1_ - x0_) < asp:
        pad = ((x1_ - x0_) * asp - (y1_ - y0_)) / 2; y0_, y1_ = y0_ - pad, y1_ + pad
    else:
        pad = ((y1_ - y0_) / asp - (x1_ - x0_)) / 2; x0_, x1_ = x0_ - pad, x1_ + pad
    ax.set_xlim(x0_, x1_); ax.set_ylim(y1_, y0_)
    ax.set_xticks([]); ax.set_yticks([])
    for s in ax.spines.values(): s.set_visible(True); s.set_color('#777777'); s.set_linewidth(0.6)
    # legend (computed marks drawn as handles)
    from matplotlib.lines import Line2D
    from matplotlib.patches import Patch
    hd = [Patch(fc='none', ec=C_OBS, lw=0.6, label='compared'),
          Patch(fc='none', ec=C_MUTE, lw=0.6, ls=(0, (1.6, 1.2)), label='not compared'),
          Line2D([], [], color=C_SIM, lw=1.2, label='best value'),
          Line2D([], [], color=C_SIM_L, lw=0.8, label='other values')]
    lg = ax.legend(handles=hd, loc='lower left', fontsize=FS, frameon=True, framealpha=0.92, edgecolor='none',
                   handlelength=1.3, handleheight=0.7, handletextpad=0.4, borderpad=0.3, labelspacing=0.25, borderaxespad=0.2)
    lg.get_frame().set_linewidth(0)
    fig_text(fig, XP, yb + hh + 0.06, 'image plane, g library', va='bottom', color=C_INK)
    w0, w1 = int(k[inwin][0]), int(k[inwin][-1])
    fig_text(fig, XP + WP1 / 2, yb - 0.06, f'predictability window: frames {w0}–{w1}', ha='center', va='top', color=C_INK2)

    # ---- (c2) loss over the discrete library
    ax = ax_in(fig, XP2, yb, WP2, hh)
    a_, b_, c_ = e['quad']; ymin = L[ib]; lo, hi = e['band']
    xr = (vals[ib] / 1.12 ** 4.5, vals[ib] * 1.12 ** 4.5)
    ax.axvspan(lo, hi, color=C_BAND, lw=0, zorder=0)
    xq = np.exp(np.linspace(math.log(e['sel'][0]) - 0.04, math.log(e['sel'][-1]) + 0.04, 120))
    ax.plot(xq, a_ * np.log(xq) ** 2 + b_ * np.log(xq) + c_, color=C_SIM, lw=0.9, zorder=2)
    ax.axhline(ymin + DELTA, color=C_INK, lw=0.6, ls=(0, (3, 2)), zorder=1)
    m = (vals >= xr[0]) & (vals <= xr[1])
    ax.plot(vals[m], L[m], 'o', ms=3.4, mfc='white', mec=C_SIM, mew=0.9, zorder=3, clip_on=True)
    ax.axvline(G_TRUE, color=C_INK, lw=0.6, zorder=1)
    ax.set_xscale('log'); ax.set_xlim(*xr)
    ytop = 13.0; ax.set_ylim(0, ytop)
    ax.set_xticks([6, 8, 10, 12, 15]); ax.set_xticklabels(['6', '8', '10', '12', '15'])
    ax.xaxis.set_minor_locator(matplotlib.ticker.NullLocator())
    ax.set_yticks([0, 5, 10])
    ax.set_xlabel('g (m/s², log scale)', labelpad=0.5); ax.set_ylabel('loss', labelpad=1)
    ax.text(xr[0] * 1.02, ymin + DELTA + 0.3, 'min + δ', va='bottom', color=C_INK)
    ax.text(G_TRUE * 1.015, 0.2, 'true', va='bottom', ha='left')
    ax.text(math.sqrt(lo * hi), ytop * 0.985, 'accepted', ha='center', va='top', color=C_SIM)
    lx = XP2 - 0.24
    fig.text(lx / W_IN, (yb + hh + 0.06) / H_IN, '○', fontsize=FS, color=C_SIM, va='bottom')
    fig_text(fig, lx + 0.09, yb + hh + 0.06, 'library value', va='bottom')
    fig.add_artist(plt.Line2D([(lx + 0.72) / W_IN, (lx + 0.86) / W_IN], [(yb + hh + 0.105) / H_IN] * 2,
                              transform=fig.transFigure, color=C_SIM, lw=0.9))
    fig_text(fig, lx + 0.89, yb + hh + 0.06, 'quadratic', va='bottom')

    fig_text(fig, 3.62, head['c'], f'Huber loss on box residuals / {SIGMA_PX} px, free onset shift ≤ 20 frames', va='center', color=C_INK2)

    # ---- outputs
    fig_text(fig, XO + WO / 2, head['a'], 'estimate / true', ha='center', va='center', color=C_INK2)
    fig_text(fig, XT, head['a'], 'value', ha='left', va='center', color=C_INK2)
    unit = dict(g='m/s²', mu='', v='m/s')
    for r, b in (('a', D['b2']), ('b', D['bd'])):
        yb, hh = row[r]
        ax = ax_in(fig, XO, yb, WO, hh + 0.04)
        forest(ax, [('g', 'base', b['g'] / G_TRUE, 2 * b['g_se'] / G_TRUE), ('μ', 'none', 0, 0), ('v', 'none', 0, 0)])
        ax.text(1.0, 2, '', transform=ax.get_yaxis_transform())
        fig_text(fig, XT, yb + (hh + 0.04) * (2 + 0.6) / 3.2, f"{b['g']:.2f} ± {2 * b['g_se']:.2f}", va='center')
    yb, hh = row['c']
    fy, fh = yb + 0.80, 0.50
    ax = ax_in(fig, XO, fy, WO, fh)
    rows = []
    for p, lab, tv in (('g', 'g', G_TRUE), ('mu', 'μ', MU_TRUE), ('v', 'v', V_TRUE)):
        ee = res[p]['est']; rows.append((lab, 'ours', ee['band'][0] / tv, ee['band'][1] / tv,
                                         ee['est'] / tv if ee.get('est') is not None else None))
    forest(ax, rows)
    fmt = dict(g='{:.2f}', mu='{:.3f}', v='{:.2f}')
    for i, p in enumerate(('g', 'mu', 'v')):
        ee = res[p]['est']; yy = fy + fh * ((2 - i) + 0.6) / 3.2
        s = (fmt[p].format(ee['est']) if ee.get('est') is not None else '') + '  ' + (fmt[p] + '–' + fmt[p]).format(*ee['band'])
        fig_text(fig, XT, yy, fmt[p].format(ee['est']) if ee.get('est') is not None else '', va='center')
        fig_text(fig, XT + 0.30, yy, (fmt[p] + '–' + fmt[p]).format(*ee['band']), va='center', color=C_INK2,
                 fontsize=FS)
    fig_text(fig, XO - 0.10, fy + fh + 0.14,
             f'true: g {G_TRUE:.2f} m/s², μ {MU_TRUE:.2f}, v {V_TRUE:.2f} m/s', va='center', color=C_INK2)

    # not explained: another video, the block speeds up on the table
    bad = D['bad']['loss']
    axn = ax_in(fig, XO + 0.22, yb + 0.02, 1.20, 0.30)
    axn.plot(vals, bad, 'o', ms=1.8, color=C_SIM, zorder=3)
    axn.axhline(GATE, color=C_INK, lw=0.6, ls=(0, (3, 2)))
    axn.set_xscale('log'); axn.set_xlim(0.45, 28)
    axn.set_xticks([1, 10]); axn.set_xticklabels(['1', '10'])
    axn.xaxis.set_minor_locator(matplotlib.ticker.NullLocator())
    axn.set_ylim(0, 1.15 * bad.max()); axn.set_yticks([GATE]); axn.set_yticklabels(['≈3σ'])
    axn.set_xlabel('g (m/s²)', labelpad=0.5); axn.patch.set_alpha(0)
    fig_text(fig, XO - 0.10, yb + 0.40, 'block speeds up on the table:\nno g below ≈3σ, not explained', va='bottom',
             color=C_INK, linespacing=1.1)
    return fig



def main():
    D = compute()
    res = D['res']
    nums = dict(
        true=dict(g=G_TRUE, mu=MU_TRUE, v=V_TRUE),
        frames=dict(onset=ONSET_OBS, airborne=[int(D['air'][0]), int(D['air'][-1])],
                    first_on_floor=int(np.where(D['obs']['phase'] == 2)[0][0]), sim_horizon=D['horizon']),
        baseline_2d=dict(g=D['b2']['g'], g_se=D['b2']['g_se'], depth_used_m=D['b2']['Z'],
                         g_all_moving_frames=D['b2_all']['g']),
        baseline_depth=dict(g=D['bd']['g'], g_se=D['bd']['g_se'], g_all_moving_frames=D['bd_all']['g'],
                            depth_scale_error=0.04, depth_frame_noise=0.02),
        ours={p: dict(kind=res[p]['est']['kind'], band=res[p]['est']['band'], center=res[p]['est'].get('center'),
                      min_loss=float(res[p]['loss'].min()), best_shift=float(res[p]['shift'][int(np.argmin(res[p]['loss']))]),
                      n_library=int(len(res[p]['values'])),
                      truth_in_band=bool(res[p]['est']['band'][0] <= dict(g=G_TRUE, mu=MU_TRUE, v=V_TRUE)[p] <= res[p]['est']['band'][1]))
              for p in ('g', 'mu', 'v')},
        not_explained_example=dict(min_loss=float(D['bad']['loss'].min()), gate=GATE,
                                   g_at_min=float(res['g']['values'][int(np.argmin(D['bad']['loss']))])),
    )
    (OUT / 'inversion_method_comparison.json').write_text(json.dumps(nums, indent=1))
    print(json.dumps(nums, indent=1))
    fig = make_figure(D)
    for ext in ('svg', 'pdf'):
        fig.savefig(OUT / f'inversion_method_comparison.{ext}', metadata={'Date': None} if ext == 'svg' else {'CreationDate': None})


if __name__ == '__main__':
    main()
