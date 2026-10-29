"""Interactive Qt/Matplotlib charts using observed records and explicit aggregation.

No coordinates, events, missing values or athlete performance are synthesized.
All displayed aggregates can be exported through ``export_csv``.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
from PySide6.QtCore import Signal
from PySide6.QtGui import QColor, QIcon, QPainter
from PySide6.QtWidgets import QWidget, QVBoxLayout, QLabel
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg, NavigationToolbar2QT
from matplotlib.figure import Figure
from matplotlib import dates as mdates
from matplotlib.patches import Arc, Circle, Ellipse, Rectangle
from .analytics import is_rate, lower_is_better, metric_summary

MODES = ['Season trend', 'Event timeline', 'Rolling average', 'Ranking',
         'Distribution', 'Scatter', 'Radar', 'Heatmap', 'Box plot', 'Cumulative total',
         'Shot map', 'Shot density', 'Passing network', 'Grid vs finish',
         'Championship evolution', 'Lap duration', 'Pit-stop timeline', 'Court shot map', 'Oval events']
THEMES = {
    'Soccer': {'accent': '#4ae3ab', 'secondary': '#92baff', 'background': '#111f22', 'name': 'PITCH INTELLIGENCE'},
    'NBA': {'accent': '#ffac66', 'secondary': '#9faaff', 'background': '#231c1b', 'name': 'COURT INTELLIGENCE'},
    'AFL': {'accent': '#f5d078', 'secondary': '#8dbbff', 'background': '#151e30', 'name': 'OVAL INTELLIGENCE'},
    'F1': {'accent': '#ff667b', 'secondary': '#83d9e6', 'background': '#241c24', 'name': 'RACE INTELLIGENCE'},
}
_EXCLUDE = {'season', 'round', 'year', 'competitor_id', 'team_id', 'match_id', 'event_id',
            'provider_id', 'id', 'is_demo', 'latitude', 'longitude', 'rating'}


def available_metrics(df: pd.DataFrame) -> list[str]:
    return [str(column) for column in df.columns
            if column not in _EXCLUDE and not str(column).endswith('_id')
            and pd.api.types.is_numeric_dtype(df[column])
            and not pd.api.types.is_bool_dtype(df[column])
            and df[column].notna().any()]


def numeric_values(df, metric):
    return pd.to_numeric(df[metric], errors='coerce').replace([np.inf, -np.inf], np.nan)


def title(metric):
    return str(metric).replace('_', ' ').title()


def _record_average(frame, metric):
    """Use source denominators for rates when provided; never add percentages."""
    if is_rate(metric):
        value = metric_summary(frame, metric)['average']
        return float(value) if value is not None else np.nan
    return numeric_values(frame, metric).mean()


def _grouped_average(frame, keys, metric):
    if not is_rate(metric):
        return frame.groupby(keys, sort=True)['_value'].mean()
    return frame.groupby(keys, sort=True).apply(
        lambda group: _record_average(group, metric), include_groups=False)


class AnalyticsChart(QWidget):
    pointSelected = Signal(str)
    explanationChanged = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        self.figure = Figure(figsize=(8, 3.4), facecolor='#111f22', constrained_layout=True)
        self.canvas = FigureCanvasQTAgg(self.figure)
        self.canvas.setMinimumHeight(210)
        self.toolbar = NavigationToolbar2QT(self.canvas, self)
        self.toolbar.setStyleSheet('QToolBar {background: transparent; border:0;} QToolButton {padding:3px;} QToolButton:hover {background:#28423c;} QToolButton:checked {background:#36534c; border-radius:4px;}')
        for action in self.toolbar.actions():
            if not action.icon().isNull():
                icon=action.icon().pixmap(22,22)
                painter=QPainter(icon)
                painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceIn)
                painter.fillRect(icon.rect(),QColor('#b5cfc5'))
                painter.end()
                action.setIcon(QIcon(icon))
        layout.addWidget(self.toolbar)
        layout.addWidget(self.canvas, 1)
        self.explanation = QLabel('Choose a metric and downloaded records to explore.')
        self.explanation.setWordWrap(True)
        self.explanation.setStyleSheet('color:#9aafad; font-size:11px; padding:8px 12px;')
        layout.addWidget(self.explanation)
        self.plotted_data = pd.DataFrame()
        self._hover_items = []
        self._annotation = None
        self._axes = None
        self.canvas.mpl_connect('motion_notify_event', self._hover)
        self.canvas.mpl_connect('pick_event', self._pick)

    @staticmethod
    def available_metrics(df):
        return available_metrics(df)

    def export_png(self, path):
        self.figure.savefig(path, dpi=180, facecolor=self.figure.get_facecolor(), bbox_inches='tight')

    def export_csv(self, path):
        self.plotted_data.to_csv(path, index=False)

    def _message(self, text):
        self.explanation.setText(text)
        self.explanationChanged.emit(text)

    def _style_axis(self, ax, theme):
        ax.set_facecolor(theme['background'])
        ax.tick_params(colors='#a5b6ba', labelsize=9, length=0, pad=8)
        ax.xaxis.label.set_color('#b9c9cc')
        ax.yaxis.label.set_color('#b9c9cc')
        ax.title.set_color('#edf7f3')
        ax.grid(axis='y', color='#8aa9aa', linewidth=.55, alpha=.15)
        ax.set_axisbelow(True)
        for spine in ax.spines.values():
            spine.set_visible(False)

    def _empty(self, ax, message):
        ax.text(.5, .54, 'NO OBSERVED DATA', color='#d0e1dc', fontsize=13,
                weight='bold', ha='center', va='center', transform=ax.transAxes)
        ax.text(.5, .41, message, color='#8caba3', fontsize=10,
                ha='center', va='center', transform=ax.transAxes, wrap=True)
        ax.set_xticks([])
        ax.set_yticks([])
        self._message(message)
        self.canvas.draw_idle()

    def _remember(self, artist, xvalues, yvalues, labels, identities):
        self._hover_items.append((artist, list(xvalues), list(yvalues), list(labels), list(identities)))

    def plot(self, df, sport, people=None, metric=None, mode='Season trend', secondary_metric=None):
        theme = THEMES.get(sport, THEMES['Soccer'])
        self.figure.clear()
        self.figure.set_facecolor(theme['background'])
        ax = self.figure.add_subplot(111, projection='polar' if mode == 'Radar' else None)
        self._axes = ax
        self._hover_items = []
        self._annotation = None
        self.plotted_data = pd.DataFrame()
        self._style_axis(ax, theme)
        if df is None or df.empty:
            self._empty(ax, 'Download an archive or import real records to begin.')
            return
        if mode in MODES[10:]:
            self._plot_sport_mode(df, sport, people, mode, theme, ax)
            return
        metrics = available_metrics(df)
        if not metric or metric not in metrics:
            metric = metrics[0] if metrics else None
        if metric is None:
            self._empty(ax, 'This selection has no numeric observations. Missing statistics remain unknown.')
            return
        work = df.copy()
        work['_value'] = numeric_values(work, metric)
        work = work.loc[work['_value'].notna()]
        if 'competitor' not in work:
            self._empty(ax, 'These records do not contain competitor identities.')
            return
        work['_identity'] = work['competitor_id'].fillna(work['competitor']).astype(str) if 'competitor_id' in work else work['competitor'].astype(str)
        names = work.drop_duplicates('_identity').set_index('_identity')['competitor'].to_dict()
        name_counts = pd.Series(list(names.values())).value_counts()
        display_names = {identity: (f'{name} · {identity}' if name_counts.get(name, 0) > 1 else name)
                         for identity, name in names.items()}
        if people:
            # Prefer stable IDs. Labels are accepted for the legacy import interface.
            selected = work['_identity'].isin([str(p) for p in people]) | work['competitor'].isin(people)
            selection = work.loc[selected].copy()
        else:
            selection = work.copy()
        if selection.empty:
            self._empty(ax, 'No observed values for the selected athlete and metric.')
            return
        palette = [theme['accent'], theme['secondary'], '#e1c383', '#bc9ce8', '#74c7c2', '#e795aa']
        chart_title = f'{title(metric)}  /  {mode}'
        ax.set_title(chart_title, loc='left', fontsize=12, fontweight='bold', pad=19, color='#edf7f3')
        explanation = 'Values are from the selected source records; missing observations are excluded.'

        if mode in ('Season trend', 'Event timeline', 'Rolling average', 'Cumulative total'):
            pieces = []
            identities = selection['_identity'].drop_duplicates().head(6)
            seasons = sorted(selection['season'].dropna().astype(str).unique()) if 'season' in selection else []
            for idx, identity in enumerate(identities):
                rows = selection.loc[selection['_identity'] == identity].copy()
                if mode == 'Season trend':
                    if 'season' not in rows:
                        continue
                    rows['_season'] = rows['season'].astype(str)
                    values = _grouped_average(rows, '_season', metric).reindex(seasons)
                    x = list(range(len(values)))
                    y = values.to_numpy()
                    labels = [str(s) for s in values.index]
                    stride = max(1, int(np.ceil(len(labels)/10)))
                    ax.set_xticks(x[::stride], labels[::stride], rotation=25 if len(labels) > 10 else 0)
                    pieces.append(pd.DataFrame({'competitor_id': identity, 'competitor': names[identity],
                                                'season': labels, 'mean_' + metric: y}))
                    explanation = 'Mean per source record in each season; rates use source denominators where available. Gaps mean no observation, rather than zero.'
                else:
                    if 'date' not in rows:
                        continue
                    kinds = rows.get('record_type', rows.get('record_kind', pd.Series('event', index=rows.index))).fillna('event').astype(str)
                    seasonal = kinds.str.contains('season|career', case=False, regex=True)
                    if seasonal.any() and not seasonal.all():
                        self._fallback(df, sport, people, 'This selection mixes event and season records; they cannot form one event timeline.')
                        return
                    if mode == 'Cumulative total' and kinds.str.contains('career', case=False).any():
                        self._empty(ax, 'Career snapshots cannot be added together. Choose season trend or an event archive.')
                        return
                    rows['_date'] = pd.to_datetime(rows['date'], errors='coerce', utc=True).dt.tz_localize(None)
                    rows = rows.dropna(subset=['_date']).sort_values('_date')
                    x = rows['_date'].tolist()
                    y = rows['_value'].to_numpy()
                    labels = rows['season'].astype(str).tolist() if seasonal.all() and 'season' in rows else [str(d.date()) for d in x]
                    if mode == 'Rolling average':
                        y = (np.array([_record_average(rows.iloc[max(0,i-4):i+1], metric) for i in range(len(rows))])
                             if is_rate(metric) else pd.Series(y).rolling(5, min_periods=1).mean().to_numpy())
                        explanation = 'Trailing mean of up to five observed records per athlete, in date order; rates use source denominators where available.'
                    elif mode == 'Cumulative total':
                        if is_rate(metric):
                            self._empty(ax, 'Cumulative totals are unavailable for percentages, rates and positions. Choose an additive metric.')
                            return
                        y = np.cumsum(y)
                        explanation = 'Running sum of observed source values. Interpret only additive totals, with consistent record units.'
                    export = pd.DataFrame({'competitor_id': identity, 'competitor': names[identity],
                                           'date': rows['_date'].to_numpy(), metric: y})
                    for provenance in ('season', 'date_precision', 'record_kind', 'record_type'):
                        if provenance in rows:
                            export[provenance] = rows[provenance].to_numpy()
                    pieces.append(export)
                    if seasonal.all() and 'season' in rows:
                        x = [seasons.index(s) for s in labels]
                        stride = max(1, int(np.ceil(len(seasons)/10)))
                        ax.set_xticks(list(range(len(seasons)))[::stride], seasons[::stride], rotation=25 if len(seasons)>10 else 0)
                        explanation += ' Each observation is a season aggregate; supplied date keys do not represent individual game dates.'
                    else:
                        ax.xaxis.set_major_locator(mdates.AutoDateLocator(minticks=3, maxticks=7))
                        ax.xaxis.set_major_formatter(mdates.ConciseDateFormatter(ax.xaxis.get_major_locator()))
                if not len(y):
                    continue
                artist, = ax.plot(x, y, color=palette[idx % len(palette)], linewidth=2.5,
                                  marker='o' if len(y) < 45 else None, markersize=4,
                                  label=display_names[identity], picker=7)
                if len(identities) == 1 and len(y) > 1:
                    ax.fill_between(x, y, alpha=.07, color=palette[idx % len(palette)])
                self._remember(artist, x, y, [f'{names[identity]} · {label}\n{title(metric)}: {value:,.3g}' for label, value in zip(labels, y)], [identity]*len(y))
            self.plotted_data = pd.concat(pieces, ignore_index=True) if pieces else pd.DataFrame()
            ax.set_ylabel(title(metric))
            kinds = selection.get('record_type', selection.get('record_kind', pd.Series('event', index=selection.index))).fillna('event').astype(str)
            season_axis = mode == 'Season trend' or kinds.str.contains('season|career', case=False, regex=True).all()
            ax.set_xlabel('Season' if season_axis else 'Date of source record')

        elif mode == 'Ranking':
            means = _grouped_average(selection, '_identity', metric)
            means = means.sort_values(ascending=lower_is_better(metric)).head(12).iloc[::-1]
            positions = list(range(len(means)))
            bars = ax.barh(positions, means, color=theme['accent'], height=.59)
            ax.set_yticks(positions, [display_names[k] for k in means.index])
            ax.set_xlabel(title(metric) + ' · mean per source record')
            for bar, identity, value in zip(bars, means.index, means):
                ax.annotate(f'{value:,.2f}', (bar.get_width(), bar.get_y()+bar.get_height()/2),
                            xytext=(7, 0), textcoords='offset points', va='center', color='#d9ebe5', fontsize=9)
                bar.set_picker(True)
                self._remember(bar, [bar.get_width()], [bar.get_y()+bar.get_height()/2],
                               [f'{names[identity]}\nMean {title(metric)}: {value:,.3g}'], [identity])
            ax.margins(x=.2)
            self.plotted_data = pd.DataFrame({'competitor_id': means.index, 'competitor': [names[k] for k in means.index], 'mean_' + metric: means.values})
            explanation = 'Ranked source-record means; rates use source denominators where available. Lower-is-better metrics rank the lowest observed average first.'

        elif mode == 'Distribution':
            for idx, (identity, rows) in enumerate(selection.groupby('_identity', sort=False)):
                if idx >= 6:
                    break
                ax.hist(rows['_value'], bins='auto', color=palette[idx], alpha=.5, label=names[identity], edgecolor=theme['background'])
            ax.set_xlabel(title(metric))
            ax.set_ylabel('Observed records')
            shown = selection['_identity'].drop_duplicates().head(6)
            self.plotted_data = selection.loc[selection['_identity'].isin(shown)].drop(columns=['_value', '_identity'])
            explanation = 'Distribution of actual metric values for up to six athletes, with automatic histogram bins. No missing records are filled.'

        elif mode == 'Scatter':
            others = [m for m in metrics if m != metric]
            secondary_metric = secondary_metric if secondary_metric in others else (others[0] if others else None)
            if not secondary_metric:
                self._empty(ax, 'A scatter plot needs two observed numeric metrics.')
                return
            selection['_other'] = numeric_values(selection, secondary_metric)
            selection = selection.dropna(subset=['_other'])
            for idx, (identity, rows) in enumerate(selection.groupby('_identity', sort=False)):
                if idx >= 6:
                    break
                artist = ax.scatter(rows['_value'], rows['_other'], s=34, alpha=.78,
                                    color=palette[idx], label=names[identity], picker=7, edgecolors='none')
                self._remember(artist, rows['_value'], rows['_other'],
                               [f'{names[identity]}\n{title(metric)}: {a:,.3g}\n{title(secondary_metric)}: {b:,.3g}' for a, b in zip(rows['_value'], rows['_other'])], [identity]*len(rows))
            ax.set_xlabel(title(metric))
            ax.set_ylabel(title(secondary_metric))
            shown = selection['_identity'].drop_duplicates().head(6)
            self.plotted_data = selection.loc[selection['_identity'].isin(shown)].drop(columns=['_value', '_identity', '_other'])
            explanation = 'Each point is one source record with both metrics observed; correlation does not establish causation.'

        elif mode == 'Radar':
            radar_metrics = metrics[:6]
            means = pd.DataFrame({m: work.groupby('_identity').apply(lambda group: _record_average(group, m), include_groups=False) for m in radar_metrics})
            radar_metrics = [m for m in radar_metrics if means[m].notna().sum() >= 2]
            if len(radar_metrics) < 3:
                self._empty(ax, 'Radar comparison needs at least three shared metrics and two athletes.')
                return
            percentile = means[radar_metrics].rank(pct=True, ascending=True) * 100
            for m in radar_metrics:
                if lower_is_better(m):
                    percentile[m] = means[m].rank(pct=True, ascending=False) * 100
            angles = np.linspace(0, 2*np.pi, len(radar_metrics), endpoint=False).tolist()
            chosen = selection['_identity'].drop_duplicates().head(4)
            for idx, identity in enumerate(chosen):
                if identity not in percentile.index or percentile.loc[identity].isna().any():
                    continue
                values = percentile.loc[identity].tolist()
                ax.plot(angles+[angles[0]], values+[values[0]], color=palette[idx], linewidth=2, label=names[identity])
                ax.fill(angles+[angles[0]], values+[values[0]], color=palette[idx], alpha=.08)
            ax.set_xticks(angles, [title(m) for m in radar_metrics], color='#c4d2cf', fontsize=9)
            ax.set_ylim(0, 100)
            ax.set_yticks([25, 50, 75, 100])
            ax.grid(color='#8aa9aa', alpha=.2)
            self.plotted_data = percentile.loc[percentile.index.intersection(chosen)].reset_index().rename(columns={'_identity': 'competitor_id'})
            explanation = 'Percentile of each athlete’s source-record mean within this downloaded cohort; average ties. Selected lower-is-better metrics are reversed. These are GameSense percentiles, not official ratings.'

        elif mode == 'Heatmap':
            if 'season' not in selection:
                self._empty(ax, 'Season observations are required for the heatmap.')
                return
            pivot = _grouped_average(selection, ['_identity', 'season'], metric).unstack('season')
            pivot = pivot.iloc[:12, -24:]
            image = ax.imshow(np.ma.masked_invalid(pivot.to_numpy()), aspect='auto', cmap='YlGnBu', interpolation='nearest')
            ax.set_xticks(range(len(pivot.columns)), [str(s) for s in pivot.columns], rotation=40, ha='right')
            ax.set_yticks(range(len(pivot.index)), [names[k] for k in pivot.index])
            ax.grid(False)
            colorbar = self.figure.colorbar(image, ax=ax, shrink=.8, pad=.025)
            colorbar.ax.tick_params(colors='#a5b6ba', labelsize=8)
            colorbar.outline.set_visible(False)
            self.plotted_data = pivot.reset_index().rename(columns={'_identity': 'competitor_id'})
            self.plotted_data.insert(1, 'competitor', self.plotted_data['competitor_id'].map(names))
            explanation = 'Colour represents mean observed values per athlete and season; rates use source denominators where available. Blank cells have no observation. Limited to 12 athletes and the latest 24 downloaded seasons.'

        elif mode == 'Box plot':
            groups = list(selection.groupby('_identity', sort=False))[:8]
            box = ax.boxplot([rows['_value'].to_numpy() for _, rows in groups], patch_artist=True,
                             tick_labels=[names[k] for k, _ in groups], widths=.45,
                             medianprops={'color': '#ffffff', 'linewidth': 1.8},
                             whiskerprops={'color': '#94a9ad'}, capprops={'color': '#94a9ad'},
                             flierprops={'markeredgecolor': theme['accent'], 'markersize': 4})
            for idx, patch in enumerate(box['boxes']):
                patch.set_facecolor(palette[idx % len(palette)])
                patch.set_alpha(.55)
            ax.set_ylabel(title(metric))
            ax.tick_params(axis='x', labelrotation=20)
            self.plotted_data = selection.loc[selection['_identity'].isin([identity for identity,_ in groups])].drop(columns=['_value', '_identity'])
            explanation = 'Median, quartiles and 1.5×IQR whiskers of observed source values. Dots mark outliers; sparse samples can be misleading.'
        else:
            self._empty(ax, 'Select a supported chart mode.')
            return

        handles, labels = ax.get_legend_handles_labels()
        if handles:
            ax.legend(handles, labels, loc='upper left', facecolor=theme['background'],
                      edgecolor='none', labelcolor='#cfddda', fontsize=8, framealpha=.85)
        if self.plotted_data.empty:
            self._empty(ax, 'No plottable observations for this chart and selection.')
            return
        self._message(explanation)
        if mode != 'Radar':
            self._annotation = ax.annotate('', xy=(0, 0), xytext=(14, 14), textcoords='offset points',
                                          bbox={'boxstyle': 'round,pad=.6', 'fc': '#223635', 'ec': '#5e8177'},
                                          color='#f0faf7', fontsize=9, zorder=99)
            self._annotation.set_visible(False)
        self.canvas.draw_idle()

    def _hover(self, event):
        if self._annotation is None or event.inaxes != self._axes:
            if self._annotation is not None and self._annotation.get_visible():
                self._annotation.set_visible(False)
                self.canvas.draw_idle()
            return
        for artist, xs, ys, labels, identities in self._hover_items:
            hit, info = artist.contains(event)
            if hit:
                index = min(int(info.get('ind', [0])[0]), len(xs)-1)
                x = self._axes.convert_xunits(xs[index])
                self._annotation.xy = (x, ys[index])
                self._annotation.set_text(labels[index])
                self._annotation.set_visible(True)
                self.canvas.draw_idle()
                return
        if self._annotation.get_visible():
            self._annotation.set_visible(False)
            self.canvas.draw_idle()

    def _pick(self, event):
        for artist, xs, ys, labels, identities in self._hover_items:
            if event.artist is artist and identities:
                indices = getattr(event, 'ind', [0])
                self.pointSelected.emit(str(identities[min(int(indices[0]), len(identities)-1)]))
                return

    def _fallback(self, df, sport, people, reason):
        self.plot(df, sport, people, mode='Season trend')
        self._message(reason + ' Showing observed season trends instead. ' + self.explanation.text())

    def _plot_sport_mode(self, df, sport, people, mode, theme, ax):
        work = df.copy()
        if 'competitor' not in work:
            self._empty(ax, 'Competitor identities are required.')
            return
        work['_identity'] = work['competitor_id'].fillna(work['competitor']).astype(str) if 'competitor_id' in work else work['competitor'].astype(str)
        if people:
            work = work.loc[work['_identity'].isin([str(p) for p in people]) | work['competitor'].isin(people)]
        if work.empty:
            self._empty(ax, 'No source records for this athlete selection.')
            return
        palette = [theme['accent'], theme['secondary'], '#e1c383', '#bc9ce8', '#74c7c2', '#e795aa']
        ax.set_title(mode.upper(), loc='left', fontsize=12, fontweight='bold', pad=18, color='#edf7f3')
        reason = ''

        if mode in ('Shot map', 'Shot density', 'Court shot map', 'Oval events'):
            expected = {'Shot map': ('Soccer', 'StatsBomb 120x80 event coordinates', 'shot_events'),
                        'Shot density': ('Soccer', 'StatsBomb 120x80 event coordinates', 'shot_events'),
                        'Court shot map': ('NBA', 'NBA feet, basket origin', 'shot_events'),
                        'Oval events': ('AFL', 'AFL normalized 0-100', 'field_events')}
            wanted_sport, schema, event_key = expected[mode]
            if sport != wanted_sport or event_key not in work or 'spatial_source' not in work:
                self._fallback(df, sport, people, f'{mode} requires verified {wanted_sport} event coordinates; this source does not provide them.')
                return
            events = []
            for _, row in work.loc[work['spatial_source'] == schema].iterrows():
                collection = row.get(event_key)
                if not isinstance(collection, list):
                    continue
                for event in collection:
                    if not isinstance(event, dict):
                        continue
                    try:
                        x, y = float(event['x']), float(event['y'])
                    except (KeyError, ValueError, TypeError):
                        continue
                    if not np.isfinite(x) or not np.isfinite(y):
                        continue
                    limits = {'Soccer': (0,120,0,80), 'NBA': (-25,25,-5.25,88.75), 'AFL': (0,100,0,100)}[sport]
                    if not (limits[0] <= x <= limits[1] and limits[2] <= y <= limits[3]):
                        continue
                    events.append({**event, 'x':x, 'y':y, 'competitor_id': row['_identity'],
                                   'competitor':row['competitor'], 'date':row.get('date'), 'season':row.get('season')})
            if not events:
                self._fallback(df, sport, people, f'No recorded events with the supported coordinate schema ({schema}).')
                return
            self.plotted_data = pd.DataFrame(events)
            if sport == 'Soccer':
                self._pitch(ax)
                reason = 'Actual StatsBomb shot locations on a 120×80 pitch. Attacking direction is as supplied by the provider.'
            elif sport == 'NBA':
                self._court(ax)
                reason = 'Imported NBA shot coordinates in feet, with the near basket at (0, 0). Only records explicitly declaring this coordinate schema are shown.'
            else:
                self._oval(ax)
                reason = 'Imported AFL event coordinates normalized to a 0–100 field. Only records explicitly declaring this coordinate schema are shown.'
            if mode == 'Shot density':
                artist = ax.hexbin(self.plotted_data['x'], self.plotted_data['y'], gridsize=(20,13),
                                   extent=(0,120,0,80), mincnt=1, cmap='YlOrRd', alpha=.85, linewidths=.2)
                bar = self.figure.colorbar(artist, ax=ax, shrink=.65, pad=.02)
                bar.ax.tick_params(colors='#a5b6ba', labelsize=8)
                bar.set_label('Observed shots', color='#c6d7d0')
                reason += ' Hexagons count observed shots; empty space is not inferred player coverage.'
            else:
                goals = self.plotted_data.get('outcome', pd.Series('', index=self.plotted_data.index)).eq('Goal')
                colors = np.where(goals, '#fff0aa', theme['accent'])
                xg = pd.to_numeric(self.plotted_data.get('xg', pd.Series(np.nan, index=self.plotted_data.index)), errors='coerce')
                sizes = 28 + xg.fillna(0).clip(0,1).to_numpy()*260
                artist = ax.scatter(self.plotted_data['x'],self.plotted_data['y'],s=sizes,
                                    c=colors,alpha=.83,edgecolors='#edf3df',linewidths=.55,picker=7,zorder=5)
                labels = []
                for _, event in self.plotted_data.iterrows():
                    suffix = f" · xG {event['xg']:.3f}" if pd.notna(event.get('xg')) else ''
                    labels.append(f"{event['competitor']} · {event.get('outcome', event.get('type', 'Observed event'))}{suffix}\n({event['x']:.1f}, {event['y']:.1f})")
                self._remember(artist,self.plotted_data['x'],self.plotted_data['y'],labels,self.plotted_data['competitor_id'])
                if sport == 'Soccer':
                    reason += ' Gold marks goals; marker area scales with recorded xG. Missing xG uses the base marker size.'

        elif mode == 'Passing network':
            if sport != 'Soccer' or 'pass_links' not in work:
                self._fallback(df, sport, people, 'Passing networks require actual completed-pass recipient records.')
                return
            links = []
            for _, row in work.iterrows():
                if isinstance(row.get('pass_links'),dict):
                    links.extend({'from':row['competitor'],'to':recipient,'passes':count}
                                 for recipient,count in row['pass_links'].items()
                                 if isinstance(count,(int,float)) and count>0)
            if not links:
                self._fallback(df, sport, people, 'No observed completed-pass links for this selection.')
                return
            links = pd.DataFrame(links).groupby(['from','to'],as_index=False)['passes'].sum().nlargest(18,'passes')
            nodes = list(dict.fromkeys(links['from'].tolist()+links['to'].tolist()))
            angles = np.linspace(0,2*np.pi,len(nodes),endpoint=False)
            coords = dict(zip(nodes,zip(np.cos(angles),np.sin(angles))))
            for _, row in links.iterrows():
                x0,y0 = coords[row['from']]; x1,y1 = coords[row['to']]
                ax.annotate('',xy=(x1*.9,y1*.9),xytext=(x0*.9,y0*.9),
                            arrowprops={'arrowstyle':'->','color':theme['accent'],'alpha':.3+min(.5,row['passes']/links['passes'].max()*.5),'lw':.6+row['passes']/links['passes'].max()*3})
            for name,(x,y) in coords.items():
                ax.scatter([x],[y],s=75,color=theme['accent'],zorder=4)
                ax.text(x*1.13,y*1.13,name,color='#d9ece2',fontsize=8,ha='center',va='center')
            ax.set(xlim=(-1.55,1.55),ylim=(-1.3,1.3),aspect='equal')
            ax.axis('off')
            self.plotted_data = links
            reason = 'Directed links show the strongest 18 observed completed-pass connections. Circular node placement is an abstract network layout, not player positions on a pitch.'

        elif mode in ('Grid vs finish','Championship evolution','Lap duration','Pit-stop timeline'):
            if sport != 'F1':
                self._fallback(df, sport, people, mode + ' requires real Formula 1 race records.')
                return
            selected = work['_identity'].drop_duplicates().head(6)
            work = work.loc[work['_identity'].isin(selected)].copy()
            if mode == 'Grid vs finish':
                if not {'grid_position','finish_position'}.issubset(work.columns):
                    self._fallback(df,sport,people,'The selected source lacks recorded grid or finish positions.')
                    return
                work['_x'] = pd.to_numeric(work['grid_position'],errors='coerce')
                work['_y'] = pd.to_numeric(work['finish_position'],errors='coerce')
                work = work.loc[(work['_x']>0)&(work['_y']>0)]
                for idx,(identity,rows) in enumerate(work.groupby('_identity',sort=False)):
                    artist=ax.scatter(rows['_x'],rows['_y'],s=40,alpha=.7,color=palette[idx],label=rows['competitor'].iloc[0],picker=7)
                    self._remember(artist,rows['_x'],rows['_y'],[f"{r['competitor']} · {r.get('event',r.get('date',''))}\nGrid {r['_x']:g} → Finish {r['_y']:g}" for _,r in rows.iterrows()],rows['_identity'])
                if not work.empty:
                    maximum=max(work['_x'].max(),work['_y'].max())+1
                    ax.plot([1,maximum],[1,maximum],color='#819e9a',linestyle='--',linewidth=1,alpha=.5)
                    ax.set_xlim(.5,maximum);ax.set_ylim(maximum,.5)
                ax.set_xlabel('Starting grid position');ax.set_ylabel('Finishing position · lower is better')
                reason='Actual grid and finish positions. Points above the diagonal gained places. Pit-lane starts without a numeric grid are excluded.'
            elif mode in ('Championship evolution','Lap duration'):
                observed_durations=[key for key in ('fastest_lap_time_ms','qualifying_time_ms') if key in work and pd.to_numeric(work[key],errors='coerce').notna().any()]
                ykey='championship_points' if mode=='Championship evolution' else (observed_durations[0] if observed_durations else 'fastest_lap_time_ms')
                if ykey not in work or 'round' not in work:
                    self._fallback(df,sport,people,'The source does not contain the recorded '+title(ykey)+'.')
                    return
                work['_x']=pd.to_numeric(work['round'],errors='coerce')
                work['_y']=pd.to_numeric(work[ykey],errors='coerce')/(1000 if mode=='Lap duration' else 1)
                work=work.dropna(subset=['_x','_y'])
                pieces=[]
                for idx,((identity,season),rows) in enumerate(work.groupby(['_identity','season'],sort=True)):
                    if idx>=8:break
                    rows=rows.sort_values('_x');pieces.append(rows)
                    name=rows['competitor'].iloc[0]
                    artist,=ax.plot(rows['_x'],rows['_y'],color=palette[idx%len(palette)],linewidth=2,marker='o',markersize=3,label=f'{name} · {season}',picker=7)
                    self._remember(artist,rows['_x'],rows['_y'],[f"{name} · {season} · Round {r['_x']:g}\n{title(ykey)}: {r['_y']:,.3f}" for _,r in rows.iterrows()],rows['_identity'])
                work=pd.concat(pieces) if pieces else work.iloc[:0]
                ax.set_xlabel('Championship round')
                ax.set_ylabel('Championship points' if mode=='Championship evolution' else 'Lap duration · seconds')
                reason=('Provider-recorded championship standings after each round; historical dropped-score rules are preserved. Up to eight athlete-season series.' if mode=='Championship evolution' else 'Actual recorded fastest-lap or qualifying durations converted from milliseconds to seconds. Circuits differ, so this chart is not a normalized pace comparison.')
            else:
                if 'pit_stop_events' not in work:
                    self._fallback(df,sport,people,'No recorded pit-stop events in this source or historical era.')
                    return
                stops=[]
                for _,row in work.iterrows():
                    events=row.get('pit_stop_events')
                    if not isinstance(events,list):continue
                    for event in events:
                        if not isinstance(event,dict) or event.get('lap') is None:continue
                        stops.append({**event,'competitor':row['competitor'],'competitor_id':row['_identity'],
                                      'race':str(row.get('event',row.get('event_id',''))),'season':row.get('season')})
                if not stops:
                    self._fallback(df,sport,people,'This selection has no recorded pit stops; older races may have no pit-stop timing archive.')
                    return
                stopdata=pd.DataFrame(stops)
                stopdata['race_driver']=stopdata['competitor']+' · '+stopdata['season'].astype(str)+' · '+stopdata['race']
                labels=stopdata['race_driver'].drop_duplicates().head(10).tolist()
                stopdata=stopdata.loc[stopdata['race_driver'].isin(labels)].copy()
                y=stopdata['race_driver'].map({name:i for i,name in enumerate(labels)})
                x=pd.to_numeric(stopdata['lap'],errors='coerce')
                artist=ax.scatter(x,y,s=70,marker='D',color=theme['accent'],edgecolor='#ffe0cc',linewidth=.7,picker=7)
                self._remember(artist,x,y,[f"{r['competitor']} · Stop {r.get('stop','?')}\nLap {r['lap']} · Duration {r.get('duration_ms','unknown')} ms" for _,r in stopdata.iterrows()],stopdata['competitor_id'])
                ax.set_yticks(range(len(labels)),[name if len(name)<56 else name[:53]+'…' for name in labels],fontsize=8)
                ax.set_xlabel('Recorded race lap');ax.set_ylabel('Driver / race')
                work=stopdata
                reason='Each diamond is a recorded pit stop, placed at its actual race lap. Up to ten driver-race rows. Historical records without pit-stop timing are omitted.'
            self.plotted_data=work.drop(columns=['_identity','_x','_y'],errors='ignore')
            if self.plotted_data.empty:
                self._fallback(df,sport,people,'No valid observations for this racing chart in the selection.')
                return
        else:
            self._empty(ax,'This chart mode is unavailable.')
            return
        handles,labels=ax.get_legend_handles_labels()
        if handles:
            ax.legend(handles,labels,loc='upper left',facecolor=theme['background'],edgecolor='none',labelcolor='#cfddda',fontsize=8,framealpha=.85)
        self._message(reason)
        self._annotation=ax.annotate('',xy=(0,0),xytext=(14,14),textcoords='offset points',
                                     bbox={'boxstyle':'round,pad=.6','fc':'#223635','ec':'#5e8177'},color='#f0faf7',fontsize=9,zorder=99)
        self._annotation.set_visible(False)
        self.canvas.draw_idle()

    @staticmethod
    def _pitch(ax):
        line='#90bda5'
        ax.set_facecolor('#163629')
        for x in range(0,120,20):
            ax.add_patch(Rectangle((x,0),10,80,facecolor='#1a3c2d',edgecolor='none',zorder=0))
        for patch in [Rectangle((0,0),120,80,fill=False),Rectangle((0,18),18,44,fill=False),
                      Rectangle((102,18),18,44,fill=False),Rectangle((0,30),6,20,fill=False),
                      Rectangle((114,30),6,20,fill=False),Circle((60,40),10,fill=False)]:
            patch.set_edgecolor(line);patch.set_linewidth(1);ax.add_patch(patch)
        ax.axvline(60,color=line,linewidth=1)
        ax.scatter([12,108,60],[40,40,40],s=6,color=line)
        ax.set(xlim=(-2,122),ylim=(82,-2),aspect='equal')
        ax.set_xlabel('Pitch length · StatsBomb units');ax.set_ylabel('Pitch width · StatsBomb units')
        ax.grid(False)

    @staticmethod
    def _court(ax):
        line='#c4a488';ax.set_facecolor('#34281f')
        for patch in [Rectangle((-25,-5.25),50,94,fill=False),Rectangle((-8,-5.25),16,19,fill=False),
                      Rectangle((-8,69.75),16,19,fill=False),Circle((0,41.75),6,fill=False),
                      Circle((0,0),.75,fill=False),Circle((0,83.5),.75,fill=False),
                      Arc((0,0),47.5,47.5,theta1=22,theta2=158),Arc((0,83.5),47.5,47.5,theta1=202,theta2=338)]:
            patch.set_edgecolor(line);patch.set_linewidth(1);ax.add_patch(patch)
        ax.axhline(41.75,color=line,linewidth=1)
        ax.set(xlim=(-27,27),ylim=(-7.25,90.75),aspect='equal')
        ax.set_xlabel('Feet across court');ax.set_ylabel('Feet from near basket')
        ax.grid(False)

    @staticmethod
    def _oval(ax):
        line='#d0b56d';ax.set_facecolor('#182b31')
        for patch in [Ellipse((50,50),100,100,fill=False),Circle((50,50),10,fill=False),
                      Rectangle((45,45),10,10,fill=False)]:
            patch.set_edgecolor(line);patch.set_linewidth(1);ax.add_patch(patch)
        ax.plot([0,0],[44,56],color=line);ax.plot([100,100],[44,56],color=line)
        ax.set(xlim=(-3,103),ylim=(-3,103),aspect=.6)
        ax.set_xlabel('Normalized field length');ax.set_ylabel('Normalized field width')
        ax.grid(False)
