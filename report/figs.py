"""Result figures for the AgenticScientist method article. Reads data/*.json, writes fig/*.pdf (vector)."""
import collections
import json
import sys
from pathlib import Path

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.lines import Line2D
from matplotlib.patches import FancyArrowPatch, Rectangle
import matplotlib.patheffects as pe
HALO = [pe.withStroke(linewidth=2.2, foreground='white')]

HERE = Path(__file__).resolve().parent
D, F = HERE / 'data', HERE / 'fig'
F.mkdir(exist_ok=True)
R = json.loads((D / 'runs.json').read_text())
T = json.loads((D / 'transfer.json').read_text())
LB = json.loads((D / 'leaderboard_tracks.json').read_text())

INK, INK2, MUTED, GRID, AXIS = '#0b0b0b', '#52514e', '#898781', '#e1e0d9', '#c3c2b7'
BOARD = {'temporal': '#2a78d6', 'heart': '#eb6834', 'embryo': '#1baf7a', 'perturbation': '#eda100'}
BNAME = {'temporal': 'T1 · temporal', 'heart': 'T2 · heart', 'embryo': 'T2 · embryo', 'perturbation': 'T3 · knockout'}
NEUTRAL, NEUTRAL_L = '#a9a8a2', '#dddcd6'
plt.rcParams.update({
    'font.family': 'Arimo', 'font.size': 7, 'axes.titlesize': 7.5, 'axes.labelsize': 7, 'xtick.labelsize': 6.5,
    'ytick.labelsize': 6.5, 'legend.fontsize': 6.5, 'axes.linewidth': 0.6, 'axes.edgecolor': AXIS,
    'axes.labelcolor': INK2, 'xtick.color': INK2, 'ytick.color': INK2, 'text.color': INK, 'xtick.major.width': 0.6,
    'ytick.major.width': 0.6, 'xtick.major.size': 2.5, 'ytick.major.size': 2.5, 'axes.spines.top': False,
    'axes.spines.right': False, 'pdf.fonttype': 42, 'ps.fonttype': 42, 'figure.dpi': 200, 'savefig.bbox': 'tight',
    'savefig.pad_inches': 0.02, 'axes.axisbelow': True, 'legend.frameon': False, 'mathtext.fontset': 'custom',
    'mathtext.rm': 'Arimo', 'mathtext.it': 'Arimo:italic', 'mathtext.bf': 'Arimo:bold'})
W = 7.1  # full text width (inches)


def panel(ax, letter, title=None, dx=-0.02, dy=1.06):
    ax.text(dx, dy, letter, transform=ax.transAxes, fontsize=9.5, fontweight='bold', va='bottom', ha='right', color=INK)
    if title:
        ax.text(dx + 0.03, dy, title, transform=ax.transAxes, fontsize=7.5, fontweight='bold', va='bottom', ha='left', color=INK)


def grid(ax, axis='y'):
    ax.grid(axis=axis, color=GRID, lw=0.5)


# ------------------------------------------------------------------ Fig 2: research dynamics (Normandy)
def fig_dynamics():
    N = R['normandy']
    C = N['cycles']
    t0 = N['research_started']
    seed = N['seed_dev']['boards']
    fin = {c['id']: c for c in N['final']['candidates']}
    picks = {b: p['id'] for b, p in fin['composed']['parts'].items()}
    hold = {(r['id'], r['board']): r for r in T['normandy']}
    fig = plt.figure(figsize=(W, 4.35))
    gs = fig.add_gridspec(2, 12, height_ratios=[1.0, 0.8], hspace=0.5, wspace=1.4, left=0.06, right=0.995, top=0.93, bottom=0.085)
    for k, b in enumerate(['temporal', 'heart', 'embryo']):
        ax = fig.add_subplot(gs[0, 4 * k:4 * k + 4])
        rows = [c for c in C if c['board'] == b and c['dev_board'] is not None and c['finished']]
        rej = [c for c in rows if c['verdict'] != 'accepted']
        acc = sorted([c for c in rows if c['verdict'] == 'accepted'], key=lambda c: c['finished'])
        hx = lambda c: (c['finished'] - t0) / 3600  # noqa: E731
        ax.scatter([hx(c) for c in rej], [c['dev_board'] for c in rej], s=11, facecolor='white', edgecolor=NEUTRAL, lw=0.7, zorder=2)
        # best-so-far among accepted candidates
        xs, ys, best = [0.0], [seed[b]], seed[b]
        for c in acc:
            if c['dev_board'] > best:
                best = c['dev_board']
                xs.append(hx(c)); ys.append(best)
        xs.append(27.2); ys.append(best)
        ax.step(xs, ys, where='post', color=BOARD[b], lw=1.3, zorder=3, solid_capstyle='round')
        ax.scatter([hx(c) for c in acc], [c['dev_board'] for c in acc], s=15, color=BOARD[b], edgecolor='white', lw=0.5, zorder=4)
        ax.axhline(seed[b], color=MUTED, lw=0.6, ls=(0, (3, 2)), zorder=1)
        ax.text(27.0, seed[b] - 0.012 * 14, 'seed', ha='right', va='top', fontsize=6, color=MUTED)
        # annotate the Dev-best and the holdout-selected candidate
        dev_best = max(acc, key=lambda c: c['dev_board'])
        sel = next((c for c in acc if c['id'] == picks.get(b)), None)
        span = max(c['dev_board'] for c in rows) - min(min(c['dev_board'] for c in rows), seed[b])
        if sel is not None:
            ax.scatter([hx(sel)], [sel['dev_board']], s=58, facecolor='none', edgecolor=INK, lw=1.0, zorder=5)
        def note(c, text, fx, fy, bold=False):
            ax.annotate(text, (hx(c), c['dev_board']), xytext=(fx, fy), textcoords='axes fraction', fontsize=6, color=INK,
                        ha='right', va='center', fontweight='bold' if bold else 'normal', linespacing=1.25,
                        arrowprops=dict(arrowstyle='-', color=INK2, lw=0.5, shrinkA=1, shrinkB=4, relpos=(1.0, 0.5)
                                        if hx(c) > 14 else (0.0, 0.5)))
        hb = hold.get((dev_best['id'], b), {}).get('hold')
        if sel is not None and sel['id'] != dev_best['id']:
            h = hold[(sel['id'], b)]['hold']
            note(sel, f"selected: {sel['id']}\nholdout {h:+.1f}", 0.66, 0.30, bold=True)
            note(dev_best, f"Dev-best: {dev_best['id']}\nholdout {hb:+.1f}", 0.98, 0.50)
        elif sel is not None:
            h = hold[(sel['id'], b)]['hold']
            note(sel, f"Dev-best = selected:\n{sel['id']}, holdout {h:+.1f}", 0.98, 0.42, bold=True)
        else:
            note(dev_best, f"Dev-best: {dev_best['id']}\nholdout {hb:+.1f}; seed kept", 0.98, 0.42)
        ax.set_xlim(-0.6, 27.6); ax.set_xticks([0, 6, 12, 18, 24])
        ax.set_xlabel('Research wall-clock (h)')
        if k == 0:
            ax.set_ylabel('Dev board score')
        grid(ax)
        n_acc, n_all = len([c for c in C if c['board'] == b and c['verdict'] == 'accepted']), len([c for c in C if c['board'] == b])
        ax.set_title(f"{BNAME[b]}", color=INK, fontweight='bold', loc='left', pad=4)
        ax.text(1.0, 1.035, f"{n_acc} accepted / {n_all} cycles", transform=ax.transAxes, ha='right', va='bottom', fontsize=6, color=INK2)
        if k == 0:
            panel(ax, 'a', dx=-0.13, dy=1.03)
            ax.legend(handles=[Line2D([], [], marker='o', ls='', ms=4, color=BOARD[b], mec='white', mew=0.5, label='accepted'),
                               Line2D([], [], marker='o', ls='', ms=3.6, mfc='white', mec=NEUTRAL, mew=0.7, label='rejected'),
                               Line2D([], [], color=BOARD[b], lw=1.3, label='best so far')],
                      loc='upper left', handlelength=1.2, borderaxespad=0.2, labelspacing=0.25, handletextpad=0.5)

    # ---- b: decision funnel
    ax = fig.add_subplot(gs[1, 0:5])
    n_cyc = len(C)
    n_cand = sum(c['verdict'] != 'skipped' for c in C)
    rej = [c for c in C if c['verdict'] == 'rejected']
    race_words = ('Δproxy', 'clear loss', 'no effect', 'inconclusive', 'regressed', 'mean change', 'crashes', 'parent failed')
    n_gate = sum(not c['reason'].startswith(race_words) and 'promotion review veto' not in c['reason'] for c in rej)
    n_review = sum('promotion review veto' in c['reason'] for c in rej)
    n_acc = sum(c['verdict'] == 'accepted' for c in C)
    n_short = len([c for c in N['final']['candidates'] if c['id'] not in ('seed', 'composed')])
    n_sel = len(picks)
    stages = [('Research cycles started', n_cyc), ('Candidate program produced', n_cand), ('Passed plausibility gates', n_cand - n_gate),
              ('Won paired Dev race + review', n_acc), ('Shortlisted for holdout', n_short), ('Selected (holdout lower bound)', n_sel)]
    print('funnel', stages, 'gate rejects', n_gate, 'review vetoes', n_review)
    ramp = ['#b7d3f6', '#9ec5f4', '#6da7ec', '#3987e5', '#256abf', '#104281']
    for i, (lab, n) in enumerate(stages):
        y = len(stages) - 1 - i
        ax.barh(y, n, height=0.62, color=ramp[i], lw=0)
        ax.text(n + 2.5, y, f'{n}', va='center', ha='left', fontsize=7, fontweight='bold', color=INK)
        ax.text(-3, y, lab, va='center', ha='right', fontsize=6.5, color=INK)
    ax.set_xlim(0, 158); ax.set_ylim(-0.6, len(stages) - 0.4)
    ax.set_yticks([]); ax.spines['left'].set_visible(False)
    ax.set_xlabel('Candidates (Normandy run)')
    ax.set_xticks([0, 50, 100, 150])
    panel(ax, 'b', dx=-0.63, dy=1.02)

    # ---- c: outcome by researcher model
    ax = fig.add_subplot(gs[1, 7:12])
    short = {'claude:claude-opus-5-5': 'Claude Opus 5.5', 'claude:claude-fable-5-2': 'Claude Fable 5.2', 'agy:gemini-4-neon-high': 'Gemini 4 Neon',
             'codex:gpt-6.2-sol': 'GPT-6.2 Sol', 'codex:gpt-6-luna': 'GPT-6 Luna', 'agy:claude-opus-5-5-high': 'Claude Opus 5.5 (agy)',
             'opencode:opencode/deepseek-v4.1-flash-free': 'DeepSeek v4.1 Flash', 'commandcode:deepseek/deepseek-v4.1-flash': 'DeepSeek v4.1 Flash'}
    agg = collections.defaultdict(lambda: collections.Counter())
    for c in C:
        agg[short.get(c['researcher'], c['researcher'])][c['verdict']] += 1
    order = sorted(agg, key=lambda m: (-agg[m]['accepted'], -sum(agg[m].values())))
    cols = {'accepted': '#2a78d6', 'rejected': NEUTRAL, 'skipped': NEUTRAL_L}
    labs = {'accepted': 'accepted', 'rejected': 'rejected', 'skipped': 'no candidate'}
    for i, m in enumerate(order):
        y = len(order) - 1 - i
        left = 0
        for v in ('accepted', 'rejected', 'skipped'):
            n = agg[m][v]
            if n:
                ax.barh(y, n, left=left, height=0.62, color=cols[v], lw=0.8, edgecolor='white')
                if n >= 4:
                    ax.text(left + n / 2, y, str(n), ha='center', va='center', fontsize=6, color='white' if v != 'skipped' else INK2)
            left += n
        ax.text(-1.2, y, m, ha='right', va='center', fontsize=6.5, color=INK)
    ax.set_yticks([]); ax.spines['left'].set_visible(False)
    ax.set_xlim(0, 60); ax.set_ylim(-0.6, len(order) - 0.4)
    ax.set_xlabel('Research cycles by researcher model')
    ax.legend(handles=[Rectangle((0, 0), 1, 1, color=cols[v], label=labs[v]) for v in cols], loc='lower right', handlelength=0.9,
              handleheight=0.8, labelspacing=0.3, borderaxespad=0.1)
    panel(ax, 'c', dx=-0.47, dy=1.02)
    fig.savefig(F / 'fig_dynamics.pdf')
    plt.close(fig)


# ------------------------------------------------------------------ Fig 3: Dev -> holdout transfer and selection
def fig_transfer():
    runs = [('run1', 'Run 1', '^'), ('run2', 'Run 2', 's'), ('dday', 'D-Day', 'D'), ('normandy', 'Normandy', 'o')]
    fig = plt.figure(figsize=(W, 2.75))
    gs = fig.add_gridspec(1, 4, width_ratios=[1, 1, 1, 0.92], wspace=0.34, left=0.065, right=0.995, top=0.86, bottom=0.165)
    sel_ids = {}
    for rn, _, _ in runs:
        comp = next((c for c in R[rn]['final']['candidates'] if c['id'] == 'composed'), None)
        sel_ids[rn] = {b: p['id'] for b, p in ((comp or {}).get('parts') or {}).items()}
    for k, b in enumerate(['temporal', 'heart', 'embryo']):
        ax = fig.add_subplot(gs[0, k])
        pts = []
        for rn, lab, mk in runs:
            for r in T[rn]:
                if r['board'] != b or r['id'] == 'composed' or r['dev'] is None:
                    continue
                pts.append((r['dev'], r['hold'], r['se'] or 0, mk, sel_ids[rn].get(b) == r['id'], r['id'], rn))
        xs, ys = np.array([p[0] for p in pts]), np.array([p[1] for p in pts])
        lo, hi = min(ys.min(), -1) * 1.12, max(ys.max(), 1) * 1.25
        xmax = max(xs.max() * 1.1, 2.5)
        ax.axhspan(0.25, hi, color=BOARD[b], alpha=0.07, lw=0)
        ax.axhline(0, color=AXIS, lw=0.7)
        ax.plot([0, min(xmax, hi)], [0, min(xmax, hi)], color=MUTED, lw=0.6, ls=(0, (3, 2)))
        if b != 'embryo':
            ax.text(min(xmax, hi) * 0.97, min(xmax, hi) * 0.97, 'y = x', fontsize=5.5, color=MUTED, ha='right', va='bottom', rotation=0)
        for x, y, se, mk, sel, cid, rn in pts:
            ax.errorbar(x, y, yerr=1.0 * se, color=BOARD[b], lw=0.6, zorder=2)
            ax.scatter([x], [y], s=20 if mk != 'D' else 15, marker=mk, color=BOARD[b], edgecolor='white', lw=0.5, zorder=3)
            if sel:
                ax.scatter([x], [y], s=70, facecolor='none', edgecolor=INK, lw=1.0, zorder=4)
        r = np.corrcoef(xs, ys)[0, 1] if len(xs) > 2 else float('nan')
        n_pos = int((ys > 0.25).sum())
        ax.set_xlim(0, xmax); ax.set_ylim(lo, hi)
        ax.set_xlabel('Dev gain over seed')
        if k == 0:
            ax.set_ylabel('Paired holdout gain over seed')
        grid(ax)
        ax.set_title(BNAME[b], color=INK, fontweight='bold', loc='left', pad=4)
        ax.text(1.0, 1.035, f'n = {len(xs)},  r = {r:+.2f}', transform=ax.transAxes, ha='right', va='bottom', fontsize=6, color=INK2)
        tx, ty, ha = {'temporal': (0.97, 0.50, 'right'), 'heart': (0.97, 0.56, 'right'), 'embryo': (0.04, 0.05, 'left')}[b]
        ax.text(tx, ty, f'{n_pos} of {len(xs)} Dev winners\nimprove the holdout', transform=ax.transAxes, ha=ha, va='center' if b != 'embryo' else 'bottom',
                fontsize=6, color=INK2, linespacing=1.25)
        print('transfer', b, 'n', len(xs), 'r', round(float(r), 3), 'positive', n_pos)
        if k == 0:
            panel(ax, 'a', dx=-0.14, dy=1.03)
            ax.legend(handles=[Line2D([], [], marker=mk, ls='', ms=3.8, color=INK2, mec='white', mew=0.4, label=lab) for _, lab, mk in runs]
                      + [Line2D([], [], marker='o', ls='', ms=6.5, mfc='none', mec=INK, mew=1.0, label='selected')],
                      loc='lower left', bbox_to_anchor=(0.0, 0.02), handlelength=1.0, labelspacing=0.22, handletextpad=0.3, borderaxespad=0.2)
    # ---- waterfall: composed holdout score of the Normandy run
    ax = fig.add_subplot(gs[0, 3])
    cands = {c['id']: c for c in R['normandy']['final']['candidates']}
    seed_h, comp = cands['seed']['holdout'], cands['composed']
    parts = comp['parts']
    steps = [('Seed', seed_h, None), ('+ T1', parts['temporal']['mean'] * 1.0, 'temporal'),
             ('+ heart', parts['heart']['mean'] * 0.5, 'heart'), ('Final', comp['holdout'], None)]
    base = 128.0
    cur = seed_h
    ax.bar(0, seed_h - base, bottom=base, width=0.6, color=NEUTRAL, lw=0)
    ax.text(0, seed_h + 0.15, f'{seed_h:.1f}', ha='center', va='bottom', fontsize=6.5, color=INK)
    for i, (lab, v, b) in enumerate(steps[1:3], start=1):
        ax.bar(i, v, bottom=cur, width=0.6, color=BOARD[b], lw=0)
        ax.plot([i - 1 + 0.3, i - 0.3], [cur, cur], color=MUTED, lw=0.5)
        ax.text(i, cur + v + 0.15, f'{v:+.2f}', ha='center', va='bottom', fontsize=6.5, color=INK)
        ax.text(i, cur - 0.2, parts[b]['id'], ha='center', va='top', fontsize=5.8, color=INK2)
        cur += v
    ax.plot([2.3, 2.7], [cur, cur], color=MUTED, lw=0.5)
    ax.bar(3, comp['holdout'] - base, bottom=base, width=0.6, color=INK2, lw=0)
    ax.text(3, comp['holdout'] + 0.15, f"{comp['holdout']:.1f}", ha='center', va='bottom', fontsize=6.5, color=INK, fontweight='bold')
    ax.set_xticks(range(4)); ax.set_xticklabels([s[0] for s in steps], fontsize=6.5)
    ax.set_ylim(base, 138.4); ax.set_xlim(-0.5, 3.5)
    ax.set_ylabel('Holdout proxy (T1 + ½ heart + ½ embryo)')
    grid(ax)
    ax.set_title('Composed final program', color=INK, fontweight='bold', loc='left', pad=4)
    panel(ax, 'b', dx=-0.2, dy=1.03)
    print('waterfall', seed_h, parts['temporal']['mean'], parts['heart']['mean'] * .5, comp['holdout'])
    fig.savefig(F / 'fig_transfer.pdf')
    plt.close(fig)


# ------------------------------------------------------------------ Fig 4: hidden-test results
OURS_DDAY = {  # D-Day entry, public leaderboard (agent track)
    'temporal': dict(headline=71.1028, metrics=dict(de_score=68.0, de_direction=78.5, mmd_u=66.4, variogram=72.8)),
    'heart': dict(headline=65.2272, metrics=dict(de_score=61.3, de_direction=69.4, mmd_u=59.5, variogram=72.6, d2_shape=63.6,
                                                  occupancy_dice=49.6, scale_log_ratio=87.2, neighborhood_mmd=64.0)),
    'embryo': dict(headline=68.4319, metrics=dict(de_score=65.1, de_direction=73.4, mmd_u=79.2, variogram=59.0, d2_shape=63.3,
                                                   occupancy_dice=3.7, scale_log_ratio=99.8, neighborhood_mmd=77.8)),
    'perturbation': dict(headline=69.0162, metrics=dict(de_score=61.7, de_direction=68.0, severity_slope=88.7, mmd_u=56.5, variogram=56.9))}
KEY = {'temporal': 'T1_test_agent', 'heart': 'T2_heart_test_agent', 'embryo': 'T2_embryo_test_agent', 'perturbation': 'T3_bcatenin_test_agent'}
MNAME = dict(de_score='DE score', de_direction='DE direction', mmd_u='MMD', variogram='Variogram', d2_shape='D2 shape',
             occupancy_dice='Occupancy', scale_log_ratio='Scale', neighborhood_mmd='Neighbourhood', severity_slope='Severity slope')


def ours(board):
    rows = LB[KEY[board]]['rows']
    me = [r for r in rows if 'AgenticScientist' in (r['team'] or '')]
    return rows, (me[0] if me else None)


def fig_test():
    fig = plt.figure(figsize=(W, 4.2))
    gs = fig.add_gridspec(2, 12, height_ratios=[0.86, 1.0], hspace=0.55, wspace=1.0, left=0.085, right=0.995, top=0.94, bottom=0.085)
    # ---- a: board headline vs the agent-track field
    ax = fig.add_subplot(gs[0, 0:7])
    rng = np.random.default_rng(3)
    boards = ['temporal', 'heart', 'embryo', 'perturbation']
    summary = {}
    for i, b in enumerate(boards):
        y = len(boards) - 1 - i
        rows, me = ours(b)
        vals = np.array([r['headline'] for r in rows if 'AgenticScientist' not in (r['team'] or '')])
        ax.scatter(vals, y + rng.uniform(-0.2, 0.2, len(vals)), s=5, color=NEUTRAL, alpha=0.75, lw=0, zorder=2)
        d, n = OURS_DDAY[b]['headline'], me['headline']
        moved = me['model'] == 'Normandy' and abs(n - d) > 1e-6
        ax.scatter([d], [y], s=30, facecolor='white', edgecolor=BOARD[b], lw=1.3, zorder=4)
        if moved:
            ax.add_patch(FancyArrowPatch((d + 0.55, y), (n - 0.6, y), arrowstyle='-|>', mutation_scale=6, color=BOARD[b], lw=1.1, zorder=3))
            ax.scatter([n], [y], s=34, color=BOARD[b], edgecolor='white', lw=0.6, zorder=5)
            ax.text(n + 0.9, y + 0.33, f'{n:.1f}  ({n - d:+.1f})', fontsize=6.5, fontweight='bold', color=INK, va='center', ha='left', path_effects=HALO, zorder=6)
        else:
            ax.text(d + 0.9, y + 0.36, f'{d:.1f}  (D-Day entry stands)', fontsize=6.5, color=INK, va='center', ha='left', path_effects=HALO, zorder=6)
        ax.text(48.6, y, BNAME[b], ha='right', va='center', fontsize=6.8, color=INK, fontweight='bold')
        summary[b] = dict(dday=d, now=n, rank=me['rank'], teams=len(rows), top=float(vals.max()), median=float(np.median(vals)))
    print('test summary', json.dumps(summary))
    ax.axvline(50, color=MUTED, lw=0.6, ls=(0, (3, 2)))
    ax.text(50.3, -0.42, 'floor = 50', fontsize=5.8, color=MUTED, ha='left', va='center')
    ax.set_xlim(49, 86); ax.set_ylim(-0.55, 3.75)
    ax.set_yticks([]); ax.spines['left'].set_visible(False)
    ax.set_xlabel('Hidden-test board score')
    grid(ax, 'x')
    ax.legend(handles=[Line2D([], [], marker='o', ls='', ms=5, mfc='white', mec=INK2, mew=1.2, label='D-Day (run 3)'),
                       Line2D([], [], marker='o', ls='', ms=5.2, color=INK2, mec='white', mew=0.5, label='Normandy (run 4)'),
                       Line2D([], [], marker='o', ls='', ms=2.6, color=NEUTRAL, label='other agent-track teams')],
              loc='lower left', bbox_to_anchor=(0.0, 1.0), ncol=3, handletextpad=0.2, columnspacing=1.2, borderaxespad=0.1)
    panel(ax, 'a', dx=-0.2, dy=1.02)

    # ---- b: total score against the agent-track field
    ax = fig.add_subplot(gs[0, 8:12])
    ov = LB['overall_agent']['rows']
    tot = sorted([r['total'] for r in ov if 'AgenticScientist' not in (r['team'] or '') and r['total'] > 0], reverse=True)
    me = next(r for r in ov if 'AgenticScientist' in (r['team'] or ''))
    d_tot = sum(OURS_DDAY[b]['headline'] * w for b, w in zip(boards, (1, .5, .5, 1)))
    ranks = np.arange(1, len(tot) + 1)
    ax.plot(ranks, tot, color=NEUTRAL, lw=1.2, zorder=2)
    r_d = 1 + sum(t > d_tot for t in tot)
    r_n = 1 + sum(t > me['total'] for t in tot)
    ax.scatter([r_d], [d_tot], s=30, facecolor='white', edgecolor=INK, lw=1.2, zorder=4)
    ax.scatter([r_n], [me['total']], s=34, color=INK, edgecolor='white', lw=0.6, zorder=5)
    ax.annotate(f"Normandy {me['total']:.1f}\nrank {r_n} of {len(tot) + 1}", (r_n, me['total']), xytext=(r_n + 12, me['total'] + 14), fontsize=6.5, fontweight='bold',
                ha='left', va='center', arrowprops=dict(arrowstyle='-', color=INK2, lw=0.5, shrinkB=4))
    ax.annotate(f'D-Day {d_tot:.1f}', (r_d, d_tot), xytext=(r_d - 2, d_tot - 42), fontsize=6.5, ha='left', va='center',
                arrowprops=dict(arrowstyle='-', color=INK2, lw=0.5, shrinkB=4))
    ax.set_xlabel('Agent-track rank'); ax.set_ylabel('Total score')
    ax.set_xlim(0, len(tot) + 2); ax.set_ylim(60, 245)
    grid(ax)
    panel(ax, 'b', dx=-0.2, dy=1.02)
    print('overall', d_tot, r_d, me['total'], r_n, len(tot) + 1, 'top', tot[0])

    # ---- c: per-metric skill, D-Day -> Normandy, with the leading agent entry as reference
    spans = {'temporal': (0, 3), 'heart': (3, 8), 'perturbation': (8, 12)}
    for j, b in enumerate(['temporal', 'heart', 'perturbation']):
        a0, a1 = spans[b]
        ax = fig.add_subplot(gs[1, a0:a1])
        rows, me = ours(b)
        top = rows[0]['metrics']
        ms = list(me['metrics'])
        for i, m in enumerate(ms):
            d, n = OURS_DDAY[b]['metrics'][m], me['metrics'][m]
            ax.plot([d, n], [i, i], color=BOARD[b], lw=1.6, solid_capstyle='round', zorder=2)
            ax.scatter([d], [i], s=20, facecolor='white', edgecolor=BOARD[b], lw=1.1, zorder=3)
            ax.scatter([n], [i], s=24, color=BOARD[b], edgecolor='white', lw=0.5, zorder=4)
            ax.plot([top[m], top[m]], [i - 0.33, i + 0.33], color=INK2, lw=1.0, zorder=1)
            off = 1.6 if n >= d else -1.6
            ax.text(n + off, i - 0.36, f'{n - d:+.1f}', fontsize=5.8, color=INK, ha='left' if n >= d else 'right', va='center')
        ax.set_xticks(range(len(ms))); ax.set_xticklabels([MNAME[m] for m in ms], rotation=32, ha='right', rotation_mode='anchor')
        ax.set_xlim(-0.6, len(ms) - 0.25)
        ax.set_ylim(30, 104)
        # swap: we drew x=value,y=index above for clarity of code; redraw as vertical dumbbells
        ax.cla()
        for i, m in enumerate(ms):
            d, n = OURS_DDAY[b]['metrics'][m], me['metrics'][m]
            ax.plot([i, i], [d, n], color=BOARD[b], lw=1.8, solid_capstyle='round', zorder=2)
            ax.plot([i - 0.3, i + 0.3], [top[m], top[m]], color=INK2, lw=1.0, zorder=1)
            ax.scatter([i], [d], s=20, facecolor='white', edgecolor=BOARD[b], lw=1.1, zorder=3)
            ax.scatter([i], [n], s=24, color=BOARD[b], edgecolor='white', lw=0.5, zorder=4)
            up = n >= d
            yy = (max(d, n) + 3.4) if up else (min(d, n) - 3.4)
            if up and abs(top[m] - yy) < 2.6:
                yy = top[m] + 3.0
            ax.text(i, yy, f'{n - d:+.1f}', fontsize=5.8, color=INK, ha='center', va='center', path_effects=HALO, zorder=6)
        ax.set_xticks(range(len(ms))); ax.set_xticklabels([MNAME[m] for m in ms], rotation=32, ha='right', rotation_mode='anchor')
        ax.set_xlim(-0.6, len(ms) - 0.4)
        ax.set_ylim(30, 106); ax.set_yticks([40, 60, 80, 100])
        ax.axhline(50, color=MUTED, lw=0.6, ls=(0, (3, 2)), zorder=0)
        grid(ax)
        ax.set_title(BNAME[b], color=INK, fontweight='bold', loc='left', pad=4)
        if j == 0:
            ax.set_ylabel('Metric skill (hidden test)')
            panel(ax, 'c', dx=-0.33, dy=1.03)
        if j == 0:
            ax.legend(handles=[Line2D([], [], marker='o', ls='', ms=4.6, mfc='white', mec=INK2, mew=1.1, label='D-Day'),
                               Line2D([], [], marker='o', ls='', ms=4.8, color=INK2, mec='white', mew=0.5, label='Normandy'),
                               Line2D([], [], color=INK2, lw=1.0, label='leading agent entry')],
                      loc='lower left', bbox_to_anchor=(0.0, 0.0), handlelength=1.1, labelspacing=0.25, borderaxespad=0.2, ncol=1)
        print('metrics', b, {m: (OURS_DDAY[b]['metrics'][m], round(me['metrics'][m], 1), round(top[m], 1)) for m in ms})
    fig.savefig(F / 'fig_test.pdf')
    plt.close(fig)


# ------------------------------------------------------------------ Fig: run 3 (D-Day)
def fig_dday():
    N = R['dday']
    C = N['cycles']
    t0 = N['research_started']
    seed = N['seed_dev']['boards']
    hold = {(r['id'], r['board']): r for r in T['dday']}
    TEND = 15.0
    fig = plt.figure(figsize=(W, 4.45))
    gt = fig.add_gridspec(1, 4, wspace=0.27, left=0.06, right=0.995, top=0.93, bottom=0.585)
    gs = fig.add_gridspec(1, 24, wspace=1.6, left=0.06, right=0.995, top=0.44, bottom=0.085)
    hx = lambda c: (c['finished'] - t0) / 3600  # noqa: E731
    notes = {'temporal': 'Dev-best {id}: holdout {h:+.1f},\nlower bound {lb:+.2f} < 0.25; seed kept', 'heart': 'Dev-best {id}:\nholdout {h:+.1f}; seed kept',
             'embryo': 'Dev-best {id}:\nholdout {h:+.1f}; seed kept', 'perturbation': 'no holdout; {id} taken on Dev,\ntest file unchanged'}
    for k, b in enumerate(['temporal', 'heart', 'embryo', 'perturbation']):
        ax = fig.add_subplot(gt[0, k])
        rows = [c for c in C if c['board'] == b and c['dev_board'] is not None and c['finished']]
        veto = [c for c in rows if c['review'] == 'veto']
        rej = [c for c in rows if c['verdict'] != 'accepted' and c['review'] != 'veto']
        acc = sorted([c for c in rows if c['verdict'] == 'accepted'], key=lambda c: c['finished'])
        ax.scatter([hx(c) for c in rej], [c['dev_board'] for c in rej], s=11, facecolor='white', edgecolor=NEUTRAL, lw=0.7, zorder=2)
        ax.scatter([hx(c) for c in veto], [c['dev_board'] for c in veto], s=15, marker='x', color=INK, lw=0.9, zorder=4)
        xs, ys, best = [0.0], [seed[b]], seed[b]
        for c in acc:
            if c['dev_board'] > best:
                best = c['dev_board']
                xs.append(hx(c)); ys.append(best)
        xs.append(TEND - 0.2); ys.append(best)
        ax.step(xs, ys, where='post', color=BOARD[b], lw=1.3, zorder=3, solid_capstyle='round')
        ax.scatter([hx(c) for c in acc], [c['dev_board'] for c in acc], s=15, color=BOARD[b], edgecolor='white', lw=0.5, zorder=5)
        ax.axhline(seed[b], color=MUTED, lw=0.6, ls=(0, (3, 2)), zorder=1)
        lo = min(min(c['dev_board'] for c in rows), seed[b]); hi = max(c['dev_board'] for c in rows)
        pad = 0.1 * (hi - lo)
        ax.set_ylim(lo - 4.6 * pad, hi + pad)
        ax.text(7.4, seed[b] - 0.3 * pad, 'seed', ha='center', va='top', fontsize=6, color=MUTED)
        dev_best = max(acc, key=lambda c: c['dev_board'])
        if b == 'perturbation':
            dev_best = min(acc, key=lambda c: c['finished'])
        h = hold.get((dev_best['id'], b), {})
        txt = notes[b].format(id=dev_best['id'], h=h.get('hold', 0), lb=h.get('hold', 0) - 2.92 * h.get('se', 0))
        ax.text(0.98, 0.035, txt, transform=ax.transAxes, ha='right', va='bottom', fontsize=5.8, color=INK, linespacing=1.25)
        ax.set_xlim(-0.4, TEND + 0.2); ax.set_xticks([0, 4, 8, 12])
        ax.set_xlabel('Research wall-clock (h)')
        if k == 0:
            ax.set_ylabel('Dev board score')
        grid(ax)
        n_acc, n_all = len([c for c in C if c['board'] == b and c['verdict'] == 'accepted']), len([c for c in C if c['board'] == b])
        ax.set_title(f"{BNAME[b]}", color=INK, fontweight='bold', loc='left', pad=4)
        ax.text(1.0, 1.035, f"{n_acc} / {n_all} cycles", transform=ax.transAxes, ha='right', va='bottom', fontsize=6, color=INK2)
        if k == 0:
            panel(ax, 'a', dx=-0.2, dy=1.03)
    fig.legend(handles=[Line2D([], [], marker='o', ls='', ms=4, color=INK2, mec='white', mew=0.5, label='accepted'),
                        Line2D([], [], marker='o', ls='', ms=3.6, mfc='white', mec=NEUTRAL, mew=0.7, label='lost the Dev race'),
                        Line2D([], [], marker='x', ls='', ms=3.8, color=INK, mew=0.9, label='won the race, vetoed by the reviewer'),
                        Line2D([], [], color=INK2, lw=1.3, label='best accepted so far')],
               loc='upper right', bbox_to_anchor=(0.995, 1.012), ncol=4, handlelength=1.3, columnspacing=1.4, handletextpad=0.5, borderaxespad=0)

    # ---- b: decision funnel
    ax = fig.add_subplot(gs[0, 5:9])
    rej = [c for c in C if c['verdict'] == 'rejected']
    n_cyc, n_cand = len(C), sum(c['verdict'] != 'skipped' for c in C)
    n_veto = sum(c['review'] == 'veto' for c in rej)
    n_acc = sum(c['verdict'] == 'accepted' for c in C)
    n_won = n_acc + n_veto
    n_short = len(T['dday'])
    n_sel = sum((r['hold'] - 2.92 * r['se']) > 0.25 for r in T['dday'])
    stages = [('Research cycles finished', n_cyc), ('Candidate program produced', n_cand), ('Won the paired Dev race', n_won),
              ('Passed promotion review', n_acc), ('Re-scored on holdout', n_short), ('Cleared the holdout bound', n_sel)]
    print('dday funnel', stages)
    ramp = ['#b7d3f6', '#9ec5f4', '#6da7ec', '#3987e5', '#256abf', '#104281']
    for i, (lab, n) in enumerate(stages):
        y = len(stages) - 1 - i
        ax.barh(y, n, height=0.62, color=ramp[i], lw=0)
        ax.text(n + 2.0, y, f'{n}', va='center', ha='left', fontsize=7, fontweight='bold', color=INK)
        ax.text(-2, y, lab, va='center', ha='right', fontsize=6.5, color=INK)
    ax.set_xlim(0, 82); ax.set_ylim(-0.6, len(stages) - 0.4)
    ax.set_yticks([]); ax.spines['left'].set_visible(False)
    ax.set_xlabel('Candidates'); ax.set_xticks([0, 25, 50, 75])
    panel(ax, 'b', dx=-1.36, dy=1.02)

    # ---- c: paired holdout gain of the shortlisted programs
    ax = fig.add_subplot(gs[0, 11:16])
    order = []
    for b in ['temporal', 'heart', 'embryo']:
        order += sorted([r for r in T['dday'] if r['board'] == b], key=lambda r: -r['hold'])
    y, ys, prev = 0.0, [], None
    for r in order:
        if prev is not None and r['board'] != prev:
            y -= 0.7
        ys.append(y); prev = r['board']; y -= 1.0
    ax.axvspan(0.25, 4.0, color='#e9f1fb', lw=0, zorder=0)
    ax.axvline(0, color=AXIS, lw=0.7, zorder=1)
    ax.axvline(0.25, color=INK2, lw=0.6, ls=(0, (3, 2)), zorder=1)
    for r, yy in zip(order, ys):
        half = 2.92 * r['se']
        ax.plot([r['hold'] - half, r['hold'] + half], [yy, yy], color=BOARD[r['board']], lw=1.1, solid_capstyle='butt', zorder=2)
        ax.scatter([r['hold']], [yy], s=17, color=BOARD[r['board']], edgecolor='white', lw=0.5, zorder=3)
    ax.set_yticks(ys); ax.set_yticklabels([r['id'] for r in order], fontsize=5.8)
    ax.tick_params(axis='y', length=0)
    ax.set_xlim(-9.3, 4.0); ax.set_xticks([-8, -6, -4, -2, 0, 2, 4]); ax.set_ylim(min(ys) - 0.8, 1.1)
    ax.set_xlabel('Paired holdout gain over the seed')
    grid(ax, 'x'); ax.spines['left'].set_visible(False)
    for b, lab in (('temporal', 'T1'), ('heart', 'heart'), ('embryo', 'embryo')):
        yy = [v for r, v in zip(order, ys) if r['board'] == b]
        ax.text(3.8, (yy[0] + yy[-1]) / 2, lab, ha='right', va='center', fontsize=6.3, fontweight='bold', color=INK)
    ax.text(0.45, 0.55, 'selection region', ha='left', va='center', fontsize=5.8, color=INK2)
    panel(ax, 'c', dx=-0.2, dy=1.02)

    # ---- d: outcome by researcher model
    ax = fig.add_subplot(gs[0, 20:24])
    short = {'claude:claude-opus-5-5': 'Claude Opus 5.5', 'claude:claude-fable-5-2': 'Claude Fable 5.2', 'agy:gemini-4-neon-high': 'Gemini 4 Neon',
             'codex:gpt-6.2-sol': 'GPT-6.2 Sol', 'codex:gpt-6-luna': 'GPT-6 Luna', 'agy:claude-opus-5-5-high': 'Claude Opus 5.5 (agy)',
             'opencode:opencode/deepseek-v4.1-flash-free': 'DeepSeek v4.1 Flash', 'commandcode:deepseek/deepseek-v4.1-flash': 'DeepSeek v4.1 Flash'}
    agg = collections.defaultdict(lambda: collections.Counter())
    for c in C:
        v = 'vetoed' if c['review'] == 'veto' else c['verdict']
        agg[short.get(c['researcher'], c['researcher'])][v] += 1
    order = sorted(agg, key=lambda m: (-agg[m]['accepted'], -sum(agg[m].values())))
    print('dday models', {m: dict(agg[m]) for m in order})
    cols = {'accepted': '#2a78d6', 'vetoed': '#52514e', 'rejected': NEUTRAL, 'skipped': NEUTRAL_L}
    labs = {'accepted': 'accepted', 'vetoed': 'vetoed', 'rejected': 'lost race', 'skipped': 'no candidate'}
    for i, m in enumerate(order):
        yy = len(order) - 1 - i
        left = 0
        for v in cols:
            n = agg[m][v]
            if n:
                ax.barh(yy, n, left=left, height=0.62, color=cols[v], lw=0.8, edgecolor='white')
                if n >= 3:
                    ax.text(left + n / 2, yy, str(n), ha='center', va='center', fontsize=6, color='white' if v != 'skipped' else INK2)
            left += n
        ax.text(-0.8, yy, m, ha='right', va='center', fontsize=6.5, color=INK)
    ax.set_yticks([]); ax.spines['left'].set_visible(False)
    ax.set_xlim(0, 31); ax.set_ylim(-2.3, len(order) - 0.4); ax.set_xticks([0, 10, 20, 30])
    ax.set_xlabel('Research cycles')
    ax.legend(handles=[Rectangle((0, 0), 1, 1, color=cols[v], label=labs[v]) for v in cols], loc='lower right', ncol=2, handlelength=0.9,
              handleheight=0.8, labelspacing=0.3, columnspacing=0.9, borderaxespad=0.1)
    panel(ax, 'd', dx=-1.0, dy=1.02)
    fig.savefig(F / 'fig_dday.pdf')
    plt.close(fig)


if __name__ == '__main__':
    which = sys.argv[1:] or ['dynamics', 'dday', 'transfer', 'test']
    for w in which:
        globals()['fig_' + w]()
