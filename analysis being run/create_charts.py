#!/usr/bin/env python3
"""Render saved analysis tables using the matplotlib-research-charts skill.

Run with the project's Python environment. No models are fitted and no network
requests are made. Source tables remain unchanged. See CHARTS.md for methods.
"""
from __future__ import annotations
import argparse
import csv
import hashlib
import json
import os
from pathlib import Path
import sys
import tempfile
import textwrap
import warnings
from collections import Counter

# Keep Matplotlib/fontconfig caches in a writable temporary directory.
CACHE = Path(tempfile.gettempdir()) / 'midterm464-research-charts'
CACHE.mkdir(exist_ok=True)
os.environ.setdefault('MPLCONFIGDIR', str(CACHE / 'matplotlib'))
os.environ.setdefault('XDG_CACHE_HOME', str(CACHE))
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib import font_manager, ticker
from matplotlib.colors import LinearSegmentedColormap
from matplotlib.patches import Patch, Rectangle
from matplotlib.lines import Line2D
import numpy as np

BASE = Path(__file__).resolve().parent
MAJORS = ['ACCT', 'BMGT', 'BNAD', 'ECON', 'ENTR', 'FIN', 'MIS', 'MKTG', 'OSCM']
SECTIONS = {1: '01_curriculum_alignment', 2: '02_career_archetypes',
            3: '03_transition_dynamics', 4: '04_hedonic_salary'}
QUADRANTS = ['High Alignment', 'Market Gap', 'Over-Supply', 'Low Priority']
QUAD_FAMILIES = dict(zip(QUADRANTS, ['teal', 'amber', 'violet', 'neutral']))
STATES = ['Individual Contributor', 'Client-Facing Operator', 'Functional Lead']
STATE_LABELS = ['Individual\nContributor', 'Client-Facing\nOperator', 'Functional\nLead']
STATE_FAMILIES = ['blue', 'amber', 'teal']
SYNTHETIC = 'Synthetic alumni · testing results'
MANIFEST = []
FONTS = {}


def setup_style(skill_root: Path, font_dir: Path | None):
    global color, bars, clean_axes, export, FONTS
    helper = skill_root / 'scripts' / 'chart_style.py'
    if not helper.is_file():
        raise FileNotFoundError(f'Skill helper not found: {helper}; supply --skill-root.')
    sys.path.insert(0, str(helper.parent))
    from chart_style import configure, color, bars, clean_axes, export
    # Register locally supplied fonts; the helper also registers bundled B612 Mono.
    supplied = font_dir or Path.home() / 'Library' / 'Fonts'
    available = {f.name for f in font_manager.fontManager.ttflist}
    if 'Graphik' in available:
        FONTS = configure(font_dir=supplied, strict=True)
    else:
        with warnings.catch_warnings():
            warnings.filterwarnings('ignore', message='Graphik unavailable.*')
            FONTS = configure(font_dir=supplied, strict=False)
        available = {f.name for f in font_manager.fontManager.ttflist}
        if 'Graphik' in available:
            FONTS['sans'] = 'Graphik'
        elif 'IBM Plex Sans' in available:
            FONTS['sans'] = 'IBM Plex Sans'
        else:
            raise RuntimeError('Neither Graphik nor IBM Plex Sans is available; provide --font-dir.')
        matplotlib.rcParams['font.sans-serif'] = [FONTS['sans']]
    FONTS['sans_file'] = str(font_manager.findfont(font_manager.FontProperties(family=FONTS['sans']), fallback_to_default=False))
    FONTS['mono_file'] = str(font_manager.findfont(font_manager.FontProperties(family=FONTS['mono']), fallback_to_default=False))
    matplotlib.rcParams.update({'axes.titlelocation': 'left', 'figure.max_open_warning': 30})
    print('Fonts:', FONTS, flush=True)


def read(section, filename):
    with (BASE / SECTIONS[section] / 'outputs' / filename).open(newline='', encoding='utf-8') as f:
        return list(csv.DictReader(f))


def num(row, key):
    return float(row[key])


def wrapped(s, width=32):
    return '\n'.join(textwrap.wrap(s.replace(' -> ', ' to '), width, break_long_words=False))


def canvas(title, subtitle, size=(11, 7), footnote='', left=.10, bottom=.17, top=.79, right=.95):
    fig = plt.figure(figsize=size)
    if size[1] <= 9:
        bottom = max(bottom, .23)
    fig.subplots_adjust(left=left, right=right, bottom=bottom, top=top)
    fig.text(.055, .955, title, fontsize=22, va='top', weight='normal')
    fig.text(.055, .892, subtitle, fontsize=10, color=color('slate-600'), va='top')
    fig.text(.055, .044, SYNTHETIC, fontsize=8.5, color=color('slate-700'))
    if footnote:
        fig.text(.055, .074, footnote, fontsize=8.3, color=color('slate-600'), linespacing=1.55)
    return fig


def numeric(ax, axis='x', percent=False):
    clean_axes(ax, dots=True)
    if percent:
        getattr(ax, axis+'axis').set_major_formatter(ticker.PercentFormatter(1, decimals=0))
    ax.tick_params(axis='both', labelsize=10)


def save(fig, section, stem, title, sources, data, note):
    folder = BASE / SECTIONS[section] / 'outputs' / 'charts'
    folder.mkdir(parents=True, exist_ok=True)
    fig.canvas.draw()
    # The skill helper exports 300 dpi PNG and embedded/path vector PDF and SVG.
    export(fig, folder / stem)
    plt.close(fig)
    fields = list(dict.fromkeys(k for r in data for k in r))
    with (folder / f'{stem}.data.csv').open('w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        writer.writerows(data)
    source_info = {}
    for source in sources:
        path = BASE / SECTIONS[section] / 'outputs' / source
        source_info[source] = hashlib.sha256(path.read_bytes()).hexdigest()
    MANIFEST.append(dict(section=SECTIONS[section], stem=stem, title=title,
                         sources_sha256=source_info, plotting_rows=len(data), notes=note))
    print(f'Exported {SECTIONS[section]}/outputs/charts/{stem} [PNG, PDF, SVG, data]', flush=True)


def hbars(ax, labels, values, family='blue', fmt=None, xmax=None):
    yy = np.arange(len(labels))
    ax.barh(yy, values, height=.62, color=color(family+'-400'),
            edgecolor=color(family+'-600'), linewidth=1.3, zorder=3)
    ax.set_yticks(yy, labels)
    ax.invert_yaxis()
    limit = xmax or max(max(values), .01)*1.22
    ax.set_xlim(0, limit)
    numeric(ax)
    if fmt:
        for y, v in zip(yy, values):
            ax.text(v + limit*.018, y, fmt(v), va='center', fontsize=10, color=color(family+'-700'))


def heatmap(ax, matrix, row_labels, col_labels, *, vmin=0, vmax=1, diverging=False, fmt=None):
    cmap = (LinearSegmentedColormap.from_list('signed', [color('violet-500'), 'white', color('amber-500')])
            if diverging else LinearSegmentedColormap.from_list('sequential', ['white', color('blue-100'), color('blue-700')]))
    image = ax.imshow(np.asarray(matrix), aspect='auto', cmap=cmap, vmin=vmin, vmax=vmax)
    ax.set_yticks(range(len(row_labels)), row_labels)
    ax.set_xticks(range(len(col_labels)), col_labels)
    ax.tick_params(length=0, pad=9)
    for spine in ax.spines.values(): spine.set_visible(False)
    ax.set_xticks(np.arange(len(col_labels)+1)-.5, minor=True)
    ax.set_yticks(np.arange(len(row_labels)+1)-.5, minor=True)
    ax.grid(which='minor', color='white', linewidth=2)
    ax.tick_params(which='minor', length=0)
    if fmt:
        for i in range(len(row_labels)):
            for j in range(len(col_labels)):
                value = matrix[i][j]
                if not np.isfinite(value):continue
                rgb = np.asarray(cmap(np.clip((value-vmin)/(vmax-vmin), 0, 1)))[:3]
                linear = np.where(rgb <= .04045, rgb/12.92, ((rgb+.055)/1.055)**2.4)
                dark = float(linear @ np.array([.2126, .7152, .0722])) < .18
                ax.text(j, i, fmt(value), ha='center', va='center', fontsize=9,
                        color='white' if dark else color('slate-800'))
    return image


def curriculum():
    rows = read(1, 'gap_matrix.csv')
    counts = Counter(r['quadrant'] for r in rows)
    fig = canvas('Curriculum supply meets occupational demand',
                 f'{len(rows):,} terms · percentile-rank scores · split at 0.50 on both axes', size=(11, 8),
                 footnote='Source: gap_matrix.csv · Course skills and Hot Technologies are separate records.\nDemand combines O*NET task relevance and occupation-weighted posting shares; it is not a posting count.', bottom=.19)
    ax = fig.add_subplot(111)
    for quadrant in QUADRANTS:
        part = [r for r in rows if r['quadrant']==quadrant]
        family = QUAD_FAMILIES[quadrant]
        ax.scatter([num(r,'supply_score') for r in part], [num(r,'demand_score') for r in part],
                   s=24, facecolor=color(family+'-400'), edgecolor=color(family+'-700'),
                   lw=.45, alpha=.72, label=f'{quadrant}  ·  {counts[quadrant]}', zorder=3)
    ax.axhline(.5, color=color('slate-500'), lw=1, ls=(0,(4,4)))
    ax.axvline(.5, color=color('slate-500'), lw=1, ls=(0,(4,4)))
    ax.set(xlim=(0,1.03), ylim=(0,1.04), xlabel='Curriculum supply score (percentile rank)', ylabel='Occupational demand score (percentile rank)')
    clean_axes(ax, dots=False)
    ax.legend(loc='upper center', bbox_to_anchor=(.5,1.13), ncol=2, fontsize=9)
    # Label a small fixed set of recognizable course-skill records without moving marks.
    offsets = {'SQL':(-15,-20), 'Microsoft Excel':(45,-10), 'Tableau':(-70,-45), 'SAS':(40,-40)}
    for term, xy in offsets.items():
        match = [r for r in rows if r['term']==term and r['term_source']=='course_skill']
        if match:
            r = match[0]
            ax.annotate(term, (num(r,'supply_score'),num(r,'demand_score')), xytext=xy,
                        textcoords='offset points', fontsize=9, bbox=dict(fc='white',ec='none',pad=1.5),
                        arrowprops=dict(arrowstyle='-', color=color('slate-500'), lw=.7), zorder=5)
    save(fig,1,'01_supply_demand_quadrants','Supply and demand quadrants',['gap_matrix.csv'],rows,
         'Both axes are ranks, not percentages of postings. Duplicate display names retain separate source records. No jitter.')

    bymajor = read(1,'gap_matrix_by_major.csv')
    data = []
    for major in MAJORS:
        part=[r for r in bymajor if r['major']==major]
        for q in QUADRANTS:
            n=sum(r['quadrant']==q for r in part)
            data.append(dict(major=major,quadrant=q,n_terms=n,total_terms=len(part),share=n/len(part)))
    fig=canvas('Alignment mix across majors','Each bar contains the same term universe, rescored for that major',size=(11,7),
               footnote='Source: gap_matrix_by_major.csv · Within-major term shares; percentages sum to 100%.\nQuadrant membership uses supply and demand percentile ranks, each split at 0.50.',left=.12,bottom=.20)
    ax=fig.add_subplot(111); left=np.zeros(len(MAJORS))
    for q in QUADRANTS:
        vals=np.array([next(r['share'] for r in data if r['major']==m and r['quadrant']==q) for m in MAJORS])
        fam=QUAD_FAMILIES[q]
        ax.barh(MAJORS, vals, left=left,color=color(fam+'-400'),edgecolor='white',lw=1.3,label=q,height=.7,zorder=3)
        for y,(v,l) in enumerate(zip(vals,left)):
            if v>.09:ax.text(l+v/2,y,f'{v:.0%}',ha='center',va='center',fontsize=10,color=color('slate-900'))
        left+=vals
    assert np.allclose(left,1)
    numeric(ax,percent=True);ax.set_xlim(0,1);ax.invert_yaxis();ax.set_xlabel('Share of terms within major')
    ax.legend(ncol=4,loc='upper center',bbox_to_anchor=(.5,1.15),fontsize=9)
    save(fig,1,'02_alignment_mix_by_major','Alignment mix across majors',['gap_matrix_by_major.csv'],data,'100% stacked shares, not counts of students.')

    top=sorted((r for r in rows if r['quadrant']=='Market Gap'),key=lambda r:num(r,'alignment_gap'),reverse=True)[:12]
    labels=[wrapped(r['term'],35)+('  [course]' if r['term_source']=='course_skill' else '  [tech]') for r in top]
    fig=canvas('Largest demand–supply gaps','Top 12 Market Gap records ranked by demand score minus supply score',size=(12,8.2),
               footnote='Source: gap_matrix.csv · [course] = course skill; [tech] = O*NET Hot Technology.\nRank differences are descriptive gaps, not percentage-point gaps in enrollment or job postings.',left=.39,bottom=.19)
    ax=fig.add_subplot(111);hbars(ax,labels,[num(r,'alignment_gap') for r in top],family='amber',fmt=lambda v:f'{v:.2f}',xmax=1)
    ax.set_xlabel('Demand percentile rank − supply percentile rank')
    save(fig,1,'03_largest_market_gaps','Largest market gaps',['gap_matrix.csv'],top,'Top 12 rows, retaining source identity; zero-based bar axis.')

    ids=[r['term_id'] for r in top]
    lookup={(r['term_id'],r['major']):num(r,'alignment_gap') for r in bymajor}
    matrix=[[lookup[(key,m)] for m in MAJORS] for key in ids]
    fig=canvas('How pooled market gaps vary by major','Same 12 pooled gap records · signed rank difference within each major',size=(12,8.6),
               footnote='Sources: gap_matrix.csv, gap_matrix_by_major.csv · Amber: demand exceeds supply; violet: reverse.\nSelection uses pooled gaps; each displayed cell uses the corresponding major-specific score.',left=.39,bottom=.18)
    ax=fig.add_subplot(111);image=heatmap(ax,matrix,labels,MAJORS,vmin=-1,vmax=1,diverging=True,fmt=lambda v:f'{v:+.2f}')
    fig.colorbar(image,ax=ax,pad=.035,fraction=.04,label='Demand rank − supply rank')
    derived=[dict(term_id=r['term_id'],term=r['term'],term_source=r['term_source'],major=m,alignment_gap=lookup[(r['term_id'],m)]) for r in top for m in MAJORS]
    save(fig,1,'04_market_gaps_by_major','Market gaps by major',['gap_matrix.csv','gap_matrix_by_major.csv'],derived,'Diverging colors share the fixed −1 to +1 rank-gap scale.')


def archetypes():
    selection=read(2,'cluster_selection.csv')
    groups=MAJORS+['ALL']
    fig=canvas('Selecting the number of career archetypes','Highest mean silhouette selects k · scores estimated from the analysis sample',size=(15,8.5),
               footnote='Source: cluster_selection.csv · No fold or bootstrap uncertainty is available.\nGold ring marks the selected k; shared y-axis is the silhouette score (possible range −1 to 1).',bottom=.18,top=.79,left=.07)
    axes=fig.subplots(2,5,sharey=True)
    upper=max(num(r,'silhouette') for r in selection)*1.18
    data=[]
    for ax,group in zip(axes.flat,groups):
        part=sorted([r for r in selection if r['group']==group],key=lambda r:int(r['k']))
        xx=[int(r['k']) for r in part];yy=[num(r,'silhouette') for r in part];best=int(np.argmax(yy))
        ax.plot(xx,yy,'o-',color=color('blue-500'),markeredgecolor='white',zorder=3)
        ax.scatter([xx[best]],[yy[best]],s=130,facecolor='none',edgecolor=color('amber-600'),lw=2,zorder=4)
        ax.set_title(f'{"Pooled" if group=="ALL" else group} · k = {xx[best]}',fontsize=12,pad=10)
        ax.set(ylim=(0,upper),xlabel='Number of clusters');ax.xaxis.set_major_locator(ticker.MaxNLocator(integer=True,nbins=4));numeric(ax)
        data.extend([{**r,'selected':i==best} for i,r in enumerate(part)])
    for ax in axes[:,0]:ax.set_ylabel('Mean silhouette')
    fig.subplots_adjust(wspace=.30,hspace=.8)
    save(fig,2,'01_cluster_selection','Archetype cluster selection',['cluster_selection.csv'],data,'Shared score scale; points represent tried k values, not a learning curve.')

    profiles=[r for r in read(2,'archetype_profiles.csv') if r['group']=='ALL']
    profiles.sort(key=lambda r:-int(r['n_alumni']))
    ids=[r['archetype_id'] for r in profiles]
    labels=[r['archetype_id']+' · '+wrapped(r['archetype_label'].split(' -> ')[0],30) for r in profiles]
    fig=canvas('Ten pooled career archetypes','Archetypes use entry and year-three trajectories, including promotion-related title features',size=(13,9),
               footnote='Source: archetype_profiles.csv · All alumni appear once in the pooled solution.\nPromotion rates profile a trajectory-based clustering and are not independent predictions.',left=.34,bottom=.18)
    gs=fig.add_gridspec(1,2,width_ratios=[1,1],wspace=.35)
    ax=fig.add_subplot(gs[0,0]);hbars(ax,labels,[int(r['n_alumni']) for r in profiles],fmt=lambda v:f'{int(v):,}')
    ax.set_xlabel('Alumni (count)');ax.set_title('Group size',fontsize=14)
    ax2=fig.add_subplot(gs[0,1]); yy=np.arange(len(profiles))
    ax2.scatter([num(r,'promotion_rate_3yr') for r in profiles],yy,s=55,color=color('teal-500'),edgecolor=color('teal-700'),zorder=3)
    ax2.set(ylim=ax.get_ylim(),xlim=(0,1.18),yticks=yy,yticklabels=[],xlabel='Promoted within three years')
    numeric(ax2,percent=True);ax2.set_xticks([0,.25,.5,.75,1]);ax2.set_title('Promotion rate',fontsize=14)
    for y,r in enumerate(profiles):ax2.text(num(r,'promotion_rate_3yr')+.035,y,f"{num(r,'promotion_rate_3yr'):.1%}",va='center',fontsize=10)
    save(fig,2,'02_pooled_archetype_profiles','Pooled archetype sizes and promotion rates',['archetype_profiles.csv'],profiles,'Point rates have no invented intervals. Full labels and counts remain in plotting data.')

    assignments=[r for r in read(2,'archetype_assignments.csv') if r['group']=='ALL']
    counts=Counter((r['archetype_id'],r['major']) for r in assignments)
    matrix=[[counts[(a,m)]/int(next(r['n_alumni'] for r in profiles if r['archetype_id']==a)) for m in MAJORS] for a in ids]
    assert np.allclose(np.sum(matrix,axis=1),1)
    fig=canvas('Career archetypes cross major boundaries','Major composition within each pooled archetype · rows sum to 100%',size=(11.5,8),
               footnote='Sources: archetype_assignments.csv, archetype_profiles.csv · Pooled assignments only.\nALL-A1 through ALL-A10 use the pooled profile numbering; identities are consistent across figures.',left=.15,bottom=.18)
    ax=fig.add_subplot(111);image=heatmap(ax,matrix,ids,MAJORS,fmt=lambda v:f'{v:.0%}' if v else '·')
    fig.colorbar(image,ax=ax,pad=.03,fraction=.04,format=ticker.PercentFormatter(1),label='Share of archetype')
    data=[dict(archetype_id=a,major=m,n_alumni=counts[(a,m)],share=matrix[i][j]) for i,a in enumerate(ids) for j,m in enumerate(MAJORS)]
    save(fig,2,'03_archetype_major_composition','Archetype major composition',['archetype_assignments.csv','archetype_profiles.csv'],data,'Counts computed from saved pooled assignments, avoiding rounding in the major_mix display field.')

    industry=[r for r in read(2,'archetype_industry_distribution.csv') if r['group']=='ALL']
    sectors=sorted({r['industry_sector'] for r in industry}); lookup={(r['archetype_id'],r['industry_sector']):num(r,'share') for r in industry}
    matrix=[[lookup.get((a,s),0) for s in sectors] for a in ids]
    assert np.allclose(np.sum(matrix,axis=1),1,atol=.001)
    fig=canvas('Industry mix within career archetypes','Pooled archetypes · industry is also an input to the clustering',size=(12,9),
               footnote='Source: archetype_industry_distribution.csv · Each row sums to approximately 100% (rounded).\nIndustry separation partly reflects the clustering feature definition, rather than external validation.',left=.15,bottom=.25)
    ax=fig.add_subplot(111);image=heatmap(ax,matrix,ids,[wrapped(s,15) for s in sectors],fmt=lambda v:f'{v:.0%}' if v else '·')
    ax.tick_params(axis='x',labelsize=9);fig.colorbar(image,ax=ax,pad=.03,fraction=.04,format=ticker.PercentFormatter(1),label='Share of archetype')
    save(fig,2,'04_archetype_industry_mix','Archetype industry mix',['archetype_industry_distribution.csv'],industry,'Shared 0–100% sequential color scale; absent combinations have zero count.')

    geo=[r for r in read(2,'archetype_geo_hubs.csv') if r['group']=='ALL']
    metros=sorted({r['location_metro'] for r in geo}); lookup={(r['archetype_id'],r['location_metro']):r for r in geo}
    matrix=[[num(lookup[(a,m)],'location_quotient') for m in metros] for a in ids]
    tests=[r for r in read(2,'archetype_independence_tests.csv') if r['group']=='ALL' and r['variable']=='location_metro']
    p=num(tests[0],'p_value')
    fig=canvas('Geographic concentration is weak in this sample',f'Pooled archetypes · location quotient = archetype metro share / all-alumni metro share · pooled chi-square p = {p:.3f}',size=(13,9),
               footnote='Sources: archetype_geo_hubs.csv, archetype_independence_tests.csv · LQ = 1 means no concentration.\nOutlined cells meet the descriptive hub rule (LQ ≥ 1.2 and n ≥ 30); the pooled association test is not significant.',left=.13,bottom=.27)
    ax=fig.add_subplot(111);image=heatmap(ax,matrix,ids,[wrapped(m.split(',')[0],14) for m in metros],vmin=.5,vmax=1.5,diverging=True,fmt=lambda v:f'{v:.2f}')
    # The diverging palette is centered at LQ = 1 by symmetric limits.
    for i,a in enumerate(ids):
        for j,m in enumerate(metros):
            if lookup[(a,m)]['is_hub'].lower()=='true':ax.add_patch(Rectangle((j-.46,i-.46),.92,.92,fill=False,ec=color('slate-900'),lw=1.5))
    ax.tick_params(axis='x',labelsize=9);fig.colorbar(image,ax=ax,pad=.03,fraction=.04,label='Location quotient (center = 1)')
    save(fig,2,'05_archetype_geographic_concentration','Archetype geographic concentration',['archetype_geo_hubs.csv','archetype_independence_tests.csv'],geo,'Fixed LQ color limits 0.5–1.5, midpoint 1; hub outlines are descriptive, not significance marks.')


def transitions():
    raw=read(3,'role_state_transition_matrices.csv')
    rows=[r for r in raw if r['major']=='ALL' and r['step']=='t1 entry -> t2 year 3']
    origins=STATES[:2]; lookup={(r['from_state'],r['to_state']):r for r in rows}
    totals={s:int(next(r['n_from'] for r in rows if r['from_state']==s)) for s in origins}
    matrix=[[num(lookup[(a,b)],'p') if (a,b) in lookup else 0 for b in STATES] for a in origins]
    assert np.allclose(np.sum(matrix,axis=1),1,atol=.001)
    fig=canvas('Observed three-year role transitions','Pooled entry to year-three transition probabilities · two observed entry states',size=(12.5,7.5),
               footnote='Source: role_state_transition_matrices.csv · Probabilities condition on the entry-state denominator.\nRight panel: saved 95% Wilson score intervals; missing zero-count destinations are displayed as 0%.',left=.20,bottom=.20)
    gs=fig.add_gridspec(1,2,width_ratios=[1.15,1],wspace=.65)
    ax=fig.add_subplot(gs[0,0]);heatmap(ax,matrix,[f'{wrapped(s,19)}\nn = {totals[s]:,}' for s in origins],STATE_LABELS,fmt=lambda v:f'{v:.1%}')
    ax.set_title('Full conditional distribution',fontsize=13);ax.tick_params(axis='x',labelsize=9)
    ax2=fig.add_subplot(gs[0,1]);lead=[lookup[(s,'Functional Lead')] for s in origins]
    vals=np.array([num(r,'p') for r in lead]);lo=np.array([num(r,'p_ci_low') for r in lead]);hi=np.array([num(r,'p_ci_high') for r in lead])
    ax2.errorbar(vals,range(2),xerr=np.array([vals-lo,hi-vals]),fmt='o',color=color('teal-600'),ecolor=color('slate-900'),capsize=3,markersize=7,zorder=3)
    ax2.set(yticks=range(2),yticklabels=['IC','Client-facing'],xlim=(0,1),ylim=(1.5,-.5),xlabel='P(Functional Lead | entry state)')
    ax2.set_title('Transition to Functional Lead',fontsize=13);numeric(ax2,percent=True)
    for i,v in enumerate(vals):ax2.text(v+.05,i,f'{v:.1%}',va='center',fontsize=10)
    save(fig,3,'01_observed_role_transitions','Observed role transition probabilities',['role_state_transition_matrices.csv'],rows,'Zero destinations are inferred only for observed origin rows. No unobserved Functional Lead origin row is manufactured.')

    edges=read(3,'title_transition_edges.csv'); top=[]
    for m in MAJORS:top+=sorted([r for r in edges if r['major']==m],key=lambda r:-int(r['n']))[:2]
    labels=[f"{r['major']} · "+wrapped(f"{r['from_state']} to {r['to_state']}",52) for r in top]
    fig=canvas('Most common title paths within each major','Two largest observed transition counts per major · probability conditions on each entry title',size=(14.5,11.5),
               footnote='Source: title_transition_edges.csv · Points and whiskers are probabilities and saved 95% Wilson intervals.\nPaths have different entry-title denominators; they are not shares of all graduates or a conserved flow.',left=.48,bottom=.15,top=.82)
    ax=fig.add_subplot(111);yy=np.arange(len(top));v=np.array([num(r,'p') for r in top]);lo=np.array([num(r,'p_ci_low') for r in top]);hi=np.array([num(r,'p_ci_high') for r in top])
    ax.errorbar(v,yy,xerr=np.array([v-lo,hi-v]),fmt='o',color=color('blue-600'),ecolor=color('slate-900'),capsize=3,zorder=3)
    ax.set(yticks=yy,yticklabels=labels,xlim=(0,1.18),ylim=(len(top)-.3,-.7),xlabel='P(year-three title | entry title)');numeric(ax,percent=True);ax.set_xticks([0,.25,.5,.75,1]);ax.tick_params(axis='y',labelsize=9)
    for y,r in enumerate(top):ax.text(num(r,'p')+.055,y,f"{num(r,'p'):.0%} · n={int(r['n']):,}",va='center',fontsize=9)
    save(fig,3,'02_common_title_paths','Most common title paths',['title_transition_edges.csv'],top,'Two highest-count edges per major, not two highest conditional probabilities. Full denominators are in source/plotting data.')

    classified=read(3,'entry_role_springboard_classification.csv')
    classified.sort(key=lambda r:(MAJORS.index(r['major']),-num(r,'promo_rate')))
    labels=[f"{r['major']} · {r['first_title']}" for r in classified]
    fig=canvas('Entry-role promotion rates versus their major','Every observed entry title · colored points use the analysis classification',size=(13,14),
               footnote='Source: entry_role_springboard_classification.csv · Diamonds mark the full-major promotion rate.\nClassifications compare each title with the rest of its major using unadjusted two-sided p < 0.05; exploratory, not causal.',left=.41,bottom=.12,top=.85)
    ax=fig.add_subplot(111)
    for y,r in enumerate(classified):
        label=r['classification'];fam='teal' if label=='Springboard' else 'rose' if label!='Typical' else 'neutral'
        a=num(r,'major_promo_rate');b=num(r,'promo_rate')
        ax.plot([a,b],[y,y],color=color(fam+'-300'),lw=2,zorder=2)
        ax.scatter(a,y,marker='D',s=25,facecolor='white',edgecolor=color('slate-500'),zorder=3)
        ax.scatter(b,y,s=35,color=color(fam+'-500'),edgecolor=color(fam+'-700'),lw=.7,zorder=4)
        ax.text(b+.025,y,f'{b:.0%}',fontsize=8,va='center')
    ax.set(yticks=range(len(labels)),yticklabels=labels,ylim=(len(labels)-.3,-.7),xlim=(0,1),xlabel='Promoted within three years');numeric(ax,percent=True);ax.tick_params(axis='y',labelsize=9)
    handles=[Line2D([],[],marker='o',ls='',color=color(f+'-500'),label=l) for f,l in [('teal','Springboard'),('neutral','Typical'),('rose','Lower promotion')]]
    ax.legend(handles=handles,loc='upper center',bbox_to_anchor=(.5,1.055),ncol=3)
    save(fig,3,'03_entry_role_promotion_comparison','Entry-role promotion comparison',['entry_role_springboard_classification.csv'],classified,'Classification flags use existing unadjusted tests. No invented uncertainty on promotion-rate points.')

    seq=read(3,'top_title_sequences_by_major.csv')
    chosen=[max((r for r in seq if r['major']==m),key=lambda r:num(r,'support_pct')) for m in MAJORS]
    labels=[r['major']+' · '+wrapped(r['pattern'],62) for r in chosen]
    fig=canvas('Most frequent closed title sequence by major','One highest-support pattern per major · PrefixSpan output',size=(14,9.5),
               footnote='Source: top_title_sequences_by_major.csv · Support is the share of alumni in that major containing the pattern.\nConfidence is conditional on the earlier items; patterns can overlap, so their supports need not sum to 100%.',left=.53,bottom=.19)
    ax=fig.add_subplot(111);hbars(ax,labels,[num(r,'support_pct') for r in chosen],family='violet',xmax=max(num(r,'support_pct') for r in chosen)*1.55)
    ax.xaxis.set_major_formatter(ticker.PercentFormatter(1));ax.set_xlabel('Sequence support (% of alumni within major)');ax.tick_params(axis='y',labelsize=9)
    for y,r in enumerate(chosen):
        ax.text(num(r,'support_pct')+.008,y,f"{num(r,'support_pct'):.1%}  ·  conf. {num(r,'confidence'):.0%}",va='center',fontsize=9)
    save(fig,3,'04_frequent_title_sequences','Frequent title sequences',['top_title_sequences_by_major.csv'],chosen,'One most-supported closed pattern per major; support_pct source values are fractions, formatted as percentages.')

    project=read(3,'absorbing_chain_projection.csv')
    tests=read(3,'markov_property_tests.csv')
    part=[r for r in project if r['group']=='ALL' and r['metric'].startswith('projected_share')]
    fig=canvas('Beyond year three is a model extrapolation','Absorbing-chain scenario · first-order Markov assumption is rejected in the saved analysis',size=(11.5,7.5),
               footnote='Sources: absorbing_chain_projection.csv, role_state_transition_matrices.csv, markov_property_tests.csv.\nDashed paths assume an unchanged 3-year matrix and absorbing Functional Lead; only the year-three points are observed.',left=.11,bottom=.19)
    ax=fig.add_subplot(111);ax.axvspan(3,9.5,color=color('slate-100'),zorder=0)
    data=[]
    for state,fam in zip(STATES,STATE_FAMILIES):
        vals=[next(num(r,'value') for r in part if r['metric']==f'projected_share_year_{year}' and r['state']==state) for year in [3,6,9]]
        observed=sum(int(r['n']) for r in rows if r['to_state']==state)/sum(totals.values())
        assert abs(vals[0]-observed)<.0002
        ax.plot([3,6,9],vals,ls=(0,(5,4)),marker='o',markerfacecolor='white',markeredgewidth=1.5,color=color(fam+'-600'),zorder=3)
        ax.scatter(3,observed,s=70,color=color(fam+'-600'),edgecolor='white',zorder=4)
        label_y = {'Individual Contributor': .16, 'Client-Facing Operator': .065, 'Functional Lead': vals[-1]}[state]
        ax.annotate(state+'\n'+f'{vals[-1]:.1%}', xy=(9, vals[-1]), xytext=(9.45, label_y),
                    va='center', fontsize=10, color=color(fam+'-700'),
                    arrowprops=dict(arrowstyle='-', lw=.8, color=color(fam+'-500')))
        data.extend([dict(state=state,year=y,share=v,observation_status='observed endpoint' if y==3 else 'model projection') for y,v in zip([3,6,9],vals)])
    ax.set(xlim=(2.5,12.5),ylim=(0,1),xticks=[3,6,9],xlabel='Years after entry',ylabel='Share of pooled alumni');numeric(ax,axis='y',percent=True)
    save(fig,3,'05_absorbing_chain_projection','Absorbing-chain extrapolation',['absorbing_chain_projection.csv','role_state_transition_matrices.csv','markov_property_tests.csv'],data,'Dashed paths are scenario projections, not forecasts validated by additional observations. No uncertainty is supplied.')


def dollar_axis(ax, axis='x'):
    getattr(ax,axis+'axis').set_major_formatter(ticker.FuncFormatter(lambda x,pos:f'−${abs(x)/1000:g}k' if x<0 else f'${x/1000:g}k'))


def salary():
    performance=read(4,'model_cv_performance.csv')
    labelmap={'linear_regression':'Linear\nregression','random_forest':'Random\nForest','xgboost':'XGBoost'}
    fig=canvas('Linear and tree models perform similarly','Starting salary prediction · five-fold cross-validation',size=(11.5,7.5),
               footnote='Source: model_cv_performance.csv · Left error bars: ±1 standard deviation of fold R², not confidence intervals.\nRight: mean fold RMSE in dollars; no RMSE uncertainty is supplied. All models use the same feature design.',left=.10,bottom=.20)
    axes=fig.subplots(1,2); labels=[labelmap[r['model']] for r in performance];tokens=['neutral-400','blue-400','amber-400']
    numeric(axes[0]);bars(axes[0],labels,[num(r,'cv_r2_mean') for r in performance],errors=[num(r,'cv_r2_std') for r in performance],tokens=tokens,fmt='.3f')
    axes[0].set(ylabel='Cross-validated R²',ylim=(0,.5));axes[0].set_title('Explained variance',fontsize=14)
    numeric(axes[1]);rmse_bars=bars(axes[1],labels,[num(r,'cv_rmse_mean') for r in performance],tokens=tokens,fmt=',.0f')
    rmse_bars.errorbar.remove()
    axes[1].set_ylabel('Root mean squared error (USD)');axes[1].set_title('Prediction error · lower is better',fontsize=14);dollar_axis(axes[1],axis='y')
    fig.subplots_adjust(wspace=.38)
    save(fig,4,'01_model_cross_validation','Salary model cross-validation',['model_cv_performance.csv'],performance,'Symmetric bars are SD across folds for R² only. Both bar axes begin at zero.')

    source='hedonic_skill_premiums_metro_fixed_effects.csv'
    premiums=read(4,source)
    summary=json.loads((BASE/SECTIONS[4]/'outputs/hedonic_model_summary.json').read_text())[0]
    mean=float(summary['mean_starting_salary'])
    part=sorted(premiums,key=lambda r:-abs(num(r,'dollar_premium')))[:12]
    count=sum(num(r,'q_value_fdr')<.05 for r in premiums)
    data=[{**r,'ci_low_usd':float(np.expm1(num(r,'ci_low'))*mean),'ci_high_usd':float(np.expm1(num(r,'ci_high'))*mean)} for r in part]
    fig=canvas('Estimated skill premiums remain uncertain',f'{count} of {len(premiums)} estimated bundles pass FDR q < 0.05 · 12 largest absolute point estimates shown',size=(13,8.8),
               footnote='Sources: hedonic_skill_premiums_metro_fixed_effects.csv, hedonic_model_summary.json.\nWhiskers: pointwise 95% HC1-robust intervals transformed from log salary. Selected estimates; associations, not causal returns.',left=.43,bottom=.18)
    ax=fig.add_subplot(111); yy=np.arange(len(part));v=np.array([num(r,'dollar_premium') for r in part]);lo=np.array([r['ci_low_usd'] for r in data]);hi=np.array([r['ci_high_usd'] for r in data])
    ax.errorbar(v,yy,xerr=np.array([v-lo,hi-v]),fmt='o',color=color('violet-600'),ecolor=color('slate-900'),elinewidth=1.2,capsize=3,zorder=3)
    ax.axvline(0,color=color('slate-500'),lw=1)
    ax.set(yticks=yy,yticklabels=[wrapped(r['bundle_label'],42) for r in part],ylim=(len(part)-.3,-.7),xlabel='Model-implied dollar difference at mean salary (USD)')
    numeric(ax);dollar_axis(ax);ax.tick_params(axis='y',labelsize=9)
    save(fig,4,'02_skill_premiums_robust_intervals','Skill salary premiums with robust intervals',[source,'hedonic_model_summary.json'],data,'Dollar CI endpoints = (exp(saved log-coefficient CI) − 1) × mean starting salary. Intervals are pointwise, not FDR-adjusted.')

    control=read(4,'hedonic_controls_metro_fixed_effects.csv')
    chosen=[r for r in control if r['term']=='had_internship' or r['term'].startswith('grad_year_') or r['term'].startswith('location_metro_')]
    labels=[]
    for r in chosen:
        term=r['term']
        labels.append('Had internship' if term=='had_internship' else 'Cohort '+term.removeprefix('grad_year_') if term.startswith('grad_year_') else wrapped(term.removeprefix('location_metro_'),37))
    data=[{**r,'ci_low_usd':float(np.expm1(num(r,'ci_low'))*mean),'ci_high_usd':float(np.expm1(num(r,'ci_high'))*mean)} for r in chosen]
    fig=canvas('Salary controls recover the planted differences','Metro and graduation-year indicators plus internship · each indicator is relative to its omitted reference',size=(13,9.2),
               footnote='Sources: hedonic_controls_metro_fixed_effects.csv, hedonic_model_summary.json · 95% HC1-robust intervals.\nOmitted references: read from the local feature design; indicator contrasts are not city-level mean salaries.',left=.39,bottom=.19)
    # infer omitted references from the same local feature design and observed levels
    # Infer the actual omitted levels, avoiding assumptions about baseline coding.
    alumni_path=BASE.parent/'data/alumni/synthetic_alumni.csv'
    with alumni_path.open(newline='') as f:alumni=list(csv.DictReader(f))
    observed_metros={r['location_metro'] for r in alumni};observed_years={r['grad_year'] for r in alumni}
    present_metros={r['term'].removeprefix('location_metro_') for r in control if r['term'].startswith('location_metro_')}
    present_years={r['term'].removeprefix('grad_year_') for r in control if r['term'].startswith('grad_year_')}
    reference_metros=sorted(observed_metros-present_metros);reference_years=sorted(observed_years-present_years)
    fig.text(.055,.12,'Metro reference: '+', '.join(reference_metros)+'   ·   Cohort reference: '+', '.join(reference_years),fontsize=8.5,color=color('slate-600'))
    ax=fig.add_subplot(111);v=np.array([num(r,'dollar_premium') for r in chosen]);lo=np.array([r['ci_low_usd'] for r in data]);hi=np.array([r['ci_high_usd'] for r in data]); yy=np.arange(len(chosen))
    ax.errorbar(v,yy,xerr=np.array([v-lo,hi-v]),fmt='o',color=color('blue-600'),ecolor=color('slate-900'),capsize=3,zorder=3)
    ax.axvline(0,color=color('slate-500'),lw=1);ax.set(yticks=yy,yticklabels=labels,ylim=(len(chosen)-.3,-.7),xlabel='Model-implied dollar difference at mean salary (USD)');numeric(ax);dollar_axis(ax);ax.tick_params(axis='y',labelsize=9)
    for r in data:r.update(metro_reference='; '.join(reference_metros),cohort_reference='; '.join(reference_years))
    save(fig,4,'03_salary_control_estimates','Salary control estimates',['hedonic_controls_metro_fixed_effects.csv','hedonic_model_summary.json'],data,'References inferred from observed levels absent from model coefficient table; source alumni fingerprint recorded in run manifest.')

    importance=read(4,'shap_feature_importance.csv')
    top=sorted(importance,key=lambda r:-num(r,'mean_abs_shap'))[:15]
    fig=canvas('What drives the fitted salary model?','Top 15 XGBoost features by mean absolute TreeSHAP contribution',size=(13,9.5),
               footnote='Source: shap_feature_importance.csv · Blue: control; gold: skill bundle.\nMean absolute SHAP is model attribution magnitude, not a causal salary premium or held-out feature value.',left=.43,bottom=.17)
    ax=fig.add_subplot(111); yy=np.arange(len(top));vals=[num(r,'mean_abs_shap') for r in top]
    def feature_label(r):
        label=r['label'].replace('location_metro_','Metro: ').replace('major_','Major: ').replace('grad_year_','Cohort: ').replace('had_internship','Had internship').replace('gpa_final','Final GPA')
        return wrapped(label,42)
    for y,r in enumerate(top):
        fam='amber' if r['feature_type']=='skill_bundle' else 'blue'
        ax.barh(y,num(r,'mean_abs_shap'),height=.62,facecolor=color(fam+'-400'),edgecolor=color(fam+'-600'),lw=1.3,zorder=3)
        ax.text(num(r,'mean_abs_shap')+max(vals)*.025,y,f"${num(r,'mean_abs_shap'):,.0f}",va='center',fontsize=10)
    ax.set(yticks=yy,yticklabels=[feature_label(r) for r in top],xlim=(0,max(vals)*1.23),ylim=(len(top)-.3,-.7),xlabel='Mean |TreeSHAP contribution| (USD)');numeric(ax);dollar_axis(ax);ax.tick_params(axis='y',labelsize=9)
    present_types={r['feature_type'] for r in top}
    ax.legend(handles=[Patch(fc=color(f+'-400'),ec=color(f+'-600'),label=l) for f,l,t in [('blue','Control','control'),('amber','Skill bundle','skill_bundle')] if t in present_types],loc='upper right',bbox_to_anchor=(1,1.08))
    save(fig,4,'04_shap_feature_importance','TreeSHAP feature importance',['shap_feature_importance.csv'],top,'Magnitude is unsigned and does not imply a positive effect. Saved attribution values, not a reconstructed SHAP beeswarm.')

    interactions=read(4,'shap_top_interactions.csv')[:10]
    fig=canvas('Largest fitted pairwise interactions','Top 10 saved mean absolute XGBoost interaction values · 1,500-row sample',size=(13,9),
               footnote='Source: shap_top_interactions.csv · Mean |interaction| is an unsigned model attribution in USD.\nThis table contains off-diagonal TreeSHAP entries Phi(a,b); it does not double them or identify causal complementarities.',left=.51,bottom=.19)
    ax=fig.add_subplot(111)
    labels=[wrapped(r['feature_a'].replace('location_metro_','Metro: ').replace('major_','Major: ').replace('grad_year_','Cohort: ')+' × '+r['feature_b'].replace('location_metro_','Metro: ').replace('major_','Major: ').replace('grad_year_','Cohort: '),52) for r in interactions]
    hbars(ax,labels,[num(r,'mean_abs_interaction') for r in interactions],family='amber',fmt=lambda v:f'${v:,.0f}')
    ax.set_xlabel('Mean |TreeSHAP interaction entry| (USD)');dollar_axis(ax);ax.tick_params(axis='y',labelsize=9)
    save(fig,4,'05_shap_top_interactions','Largest TreeSHAP interactions',['shap_top_interactions.csv'],interactions,'Uses the saved upper-triangle entry scale; not doubled into a joint contribution.')

    pairs=read(4,'skill_pair_interactions.csv')
    fig=canvas('Requested skill-pair interactions','Unavailable estimates remain missing; zero is shown only when the pair was estimated',size=(12.5,7),
               footnote='Source: skill_pair_interactions.csv · Estimated points are mean 2Phi(a,b) among alumni holding both bundles.\nExcel and Tableau have no usable variation here. No error intervals were computed for these pair estimates.',left=.40,bottom=.20)
    ax=fig.add_subplot(111); labels=[wrapped(r['skill_a']+' × '+r['skill_b'],38) for r in pairs]
    estimated=[r for r in pairs if r['status']=='estimated'];maxval=max([abs(num(r,'mean_interaction_when_both')) for r in estimated] or [0]);extent=max(1,maxval*1.5)
    ax.axvline(0,color=color('slate-400'),lw=1)
    for y,r in enumerate(pairs):
        if r['status']=='estimated':
            v=num(r,'mean_interaction_when_both');ax.scatter(v,y,s=55,facecolor=color('teal-400'),edgecolor=color('teal-700'),zorder=3)
            ax.text(.04,y,f"${v:,.2f} · both n={int(r['n_with_both'])}",transform=ax.get_yaxis_transform(),va='center',fontsize=10)
        else:
            ax.text(.5,y,'Not estimable · no usable variation',transform=ax.get_yaxis_transform(),ha='center',va='center',color=color('slate-500'),fontsize=10,bbox=dict(fc='white',ec='none',pad=3))
    ax.set(yticks=range(len(labels)),yticklabels=labels,ylim=(len(labels)-.4,-.6),xlim=(-extent,extent),xlabel='Mean joint interaction among co-holders (USD)');numeric(ax);ax.xaxis.set_major_formatter(ticker.FuncFormatter(lambda x,pos:f'${x:g}'));ax.tick_params(axis='y',labelsize=10)
    save(fig,4,'06_requested_skill_pair_interactions','Requested skill-pair estimability',['skill_pair_interactions.csv'],pairs,'All-zero estimates retain a symmetric ±$1 display window. Missing pair estimates are text only, never fabricated zeros.')


def write_indexes(sections):
    for section in sections:
        name=SECTIONS[section];folder=BASE/name/'outputs/charts'
        items=[r for r in MANIFEST if r['section']==name]
        manifest=dict(fonts=FONTS,formats=['PNG (300 dpi)','PDF (font subsets)','SVG (font paths)'],synthetic_alumni=True,charts=items)
        (folder/'charts_manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
        lines=[f'# {name} charts','',f'Font: **{FONTS["sans"]}**; code typography: **{FONTS["mono"]}**.',
               '', 'All alumni-dependent results use synthetic testing data. Each figure includes a source caption. Original output tables are unchanged.',
               '', '| Figure | PNG | PDF | SVG | Plotting data |', '|---|---|---|---|---|']
        for r in items:
            s=r['stem'];lines.append(f'| {r["title"]} | [PNG]({s}.png) | [PDF]({s}.pdf) | [SVG]({s}.svg) | [CSV]({s}.data.csv) |')
        lines+=['','## Reading the charts','']
        lines += [f'- **{r["title"]}:** {r["notes"]}' for r in items]
        lines += ['','Regenerate with the project virtual environment:', '', '```sh', f'.venv/bin/python "analysis being run/create_charts.py" --section {section}', '```','']
        (folder/'README.md').write_text('\n'.join(lines))
    source=BASE.parent/'data/alumni/synthetic_alumni.csv'
    summary=dict(fonts=FONTS,chart_count=len(MANIFEST),alumni_sha256=hashlib.sha256(source.read_bytes()).hexdigest(),charts=MANIFEST)
    (BASE/'charts_manifest.json').write_text(json.dumps(summary,indent=2)+'\n')


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--section',type=int,choices=list(SECTIONS),action='append',help='Section to render; repeat for multiple. Default: all.')
    parser.add_argument('--skill-root',type=Path,default=Path(os.environ.get('MATPLOTLIB_RESEARCH_CHARTS_SKILL',str(Path.home()/'.agents/skills/matplotlib-research-charts'))))
    parser.add_argument('--font-dir',type=Path,help='Optional directory containing licensed Graphik or IBM Plex Sans fonts.')
    args=parser.parse_args();setup_style(args.skill_root,args.font_dir)
    sections=sorted(set(args.section or SECTIONS))
    for section in sections:{1:curriculum,2:archetypes,3:transitions,4:salary}[section]()
    write_indexes(sections)
    print(f'Completed {len(MANIFEST)} charts.',flush=True)


if __name__=='__main__':
    main()
