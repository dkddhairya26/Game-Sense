"""Reusable native presentation of calculated, source-scoped performance.

The widget consumes the same pure functions as the unit tests. Keeping drawing
separate from calculation lets exported evidence be checked independently of Qt.
"""
from __future__ import annotations

import pandas as pd
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton
from .charts import AnalyticsChart
from .ratings import rating_history, rating_summary, rating_explanation
from .insights import statistical_insights


def rating_chart_data(data,sport):
    """Retain source grain when presenting calculated rating history.

    Undated research player rows are one season observation, never invented
    individual match dates. Names label points; stable IDs join the identities.
    """
    history=rating_history(data,sport)
    if history.empty:
        return history
    names=data.drop_duplicates('competitor_id').set_index('competitor_id')['competitor']
    history['competitor']=history['competitor_id'].map(names)
    history['record_kind']=history['rating_grain'].map({'game':'event','season':'season_rating'})
    history['date_precision']=history['rating_grain'].map({'game':'day','season':'season'})
    return history


class PerformancePanel(QWidget):
    """Explain an experimental score and show observations behind its trend."""
    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(14)
        row = QHBoxLayout()
        self.score = QLabel('— / 100')
        self.score.setObjectName('number')
        row.addWidget(self.score)
        self.scope = QLabel()
        self.scope.setWordWrap(True)
        row.addWidget(self.scope, 1)
        self.explain_button = QPushButton('How is this rating calculated?')
        self.explain_button.setCheckable(True)
        row.addWidget(self.explain_button)
        layout.addLayout(row)
        self.formula = QLabel()
        self.formula.setWordWrap(True)
        self.formula.setTextFormat(Qt.TextFormat.PlainText)
        self.formula.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self.formula.setObjectName('muted')
        self.formula.setVisible(False)
        self.explain_button.toggled.connect(self.formula.setVisible)
        layout.addWidget(self.formula)
        self.insights = QLabel()
        self.insights.setWordWrap(True)
        self.insights.setTextFormat(Qt.TextFormat.PlainText)
        self.insights.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        layout.addWidget(self.insights)
        self.chart = AnalyticsChart()
        layout.addWidget(self.chart)
        self.summary = {}
        self.observations = []

    def set_data(self, data, sport):
        self.summary = rating_summary(data, sport)
        value = self.summary.get('score')
        recent = self.summary.get('recent_score')
        self.score.setText(f'{value:.1f} / 100' if value is not None else 'Unavailable')
        self.scope.setText(
            'EXPERIMENTAL GAMESENSE RATING · not an official league statistic\n'
            + (f"Recent form {recent:.1f} / 100 · {self.summary.get('recent_label','')} · " if recent is not None else '')
            + f"{self.summary.get('eligible_records', 0):,} eligible of "
            + f"{self.summary.get('total_records', len(data)):,} records. "
            + str(self.summary.get('limitation', '')))
        entity = 'team' if not data.empty and data.get('entity_type', pd.Series(dtype=str)).eq('team').all() else 'athlete'
        self.formula.setText(rating_explanation(sport, entity))
        self.observations = statistical_insights(data, sport)
        self.insights.setText('\n\n'.join(
            str(item['text']) + '\n' + str(item.get('period', ''))
            + ' · ' + str(item.get('source', ''))
            for item in self.observations) or
            'No statistical insight can be calculated from this selection. '
            'Choose a competitor with recorded results; missing observations stay unknown.')
        rated = rating_chart_data(data, sport)
        self.chart.plot(rated, sport, metric='experimental_rating', mode='Event timeline')
