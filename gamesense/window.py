"""Native Qt workspace for exploring a persistent, source-attributed sports archive.

Network jobs run in Qt's thread pool; only queued signals touch widgets. Tables
use a Qt model over a bounded query, so navigation never loads an entire archive.
"""
from __future__ import annotations
import json
import threading
from pathlib import Path
from html import escape
import pandas as pd
from PySide6.QtCore import Qt, QObject, Signal, QRunnable, QThreadPool, QTimer, QSettings, QAbstractTableModel, QModelIndex, QRectF
from PySide6.QtGui import QColor, QPainter, QPen, QFont, QPainterPath, QLinearGradient, QIcon
from PySide6.QtWidgets import (QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QGridLayout, QLabel,
    QPushButton, QComboBox, QLineEdit, QFileDialog, QMessageBox, QTableView, QFrame, QLayout,
    QStackedWidget, QScrollArea, QHeaderView, QProgressBar, QCheckBox, QTabWidget, QSpinBox)
from .analytics import SPORTS, clean_data, metric_summary, season_history, leaderboard, is_rate
from .importers import prepare_import
from .archive import Archive
from .providers import PROVIDERS
from .http import HttpClient
from .charts import AnalyticsChart, MODES, available_metrics
from .images import PortraitWidget

SPORT_STYLES = {
    'Soccer': ('#51e2a3', 'PITCH MODE', 'Football intelligence', 'Read the game beyond the scoreline.'),
    'NBA': ('#ffae73', 'COURT MODE', 'Basketball intelligence', 'Every possession tells a bigger story.'),
    'AFL': ('#e8c977', 'OVAL MODE', 'Australian football intelligence', 'Find the patterns across the oval.'),
    'F1': ('#ff6c76', 'RACE MODE', 'Race intelligence', 'Decades of racing. A clearer racing line.'),
}
BASE_STYLE = """
QWidget { background:#0e1116; color:#e9edf3; font-family:'Segoe UI'; font-size:12px; }
QMainWindow { background:#0e1116; }
QFrame#sidebar { background:#10151c; border-right:1px solid #242b34; }
QLabel { background:transparent; }
QLabel#brand { font-size:21px; font-weight:800; letter-spacing:1px; }
QLabel#muted { color:#96a2b3; }
QLabel#eyebrow { color:ACCENT; font-size:10px; font-weight:700; letter-spacing:2px; }
QLabel#heading { font-size:27px; font-weight:700; }
QLabel#section { font-size:17px; font-weight:650; }
QLabel#number { font-size:29px; font-weight:700; }
QFrame#panel { background:#151b23; border:1px solid #28313d; border-radius:12px; }
QPushButton { background:#202935; border:1px solid #303c4b; padding:9px 14px; border-radius:7px; font-weight:600; }
QPushButton:hover { background:#2b3848; border-color:ACCENT; }
QPushButton:disabled { color:#606e7d; border-color:#28313d; }
QPushButton#primary { background:ACCENT; color:#10171a; border:0; }
QPushButton#nav { background:transparent; text-align:left; border:0; padding:11px 14px; color:#a3afbe; }
QPushButton#nav:checked { background:#24313a; color:ACCENT; border-left:3px solid ACCENT; }
QLineEdit,QComboBox,QSpinBox { background:#141c25; border:1px solid #303b49; border-radius:6px; padding:8px; selection-background-color:#375a60; }
QLineEdit:focus,QComboBox:focus { border-color:ACCENT; }
QComboBox::drop-down { border:0; width:22px; }
QComboBox QAbstractItemView { background:#1b2633; selection-background-color:#36545c; }
QScrollArea,QStackedWidget { border:0; }
QScrollBar:vertical { background:#11171f; width:9px; margin:0; }
QScrollBar::handle:vertical { background:#344354; min-height:32px; border-radius:4px; }
QScrollBar::add-line:vertical,QScrollBar::sub-line:vertical { height:0; }
QTableView { background:#151b23; alternate-background-color:#19212b; border:1px solid #293440; border-radius:8px; gridline-color:#27313b; selection-background-color:#2a4753; }
QHeaderView::section { background:#202a36; color:#acbacb; padding:9px; border:0; font-weight:600; }
QTableView::item { padding:6px; }
QProgressBar { border:1px solid #303c49; border-radius:5px; text-align:center; min-height:18px; }
QProgressBar::chunk { background:ACCENT; border-radius:4px; }
QTabWidget::pane { border:0; }
QTabBar::tab { background:#1b2530; padding:10px 18px; margin-right:4px; border-radius:5px; color:#a2afc0; }
QTabBar::tab:selected { background:#2b3d45; color:ACCENT; }
QToolTip { color:#e9edf3; background:#243341; border:1px solid #567184; padding:7px; }
QCheckBox { spacing:8px; }
"""


def label(text='', kind=None, wrap=False):
    widget = QLabel(text)
    widget.setTextFormat(Qt.TextFormat.PlainText)
    if kind:
        widget.setObjectName(kind)
    widget.setWordWrap(wrap)
    return widget


def button(text, slot, primary=False):
    widget = QPushButton(text)
    if primary:
        widget.setObjectName('primary')
    widget.clicked.connect(slot)
    return widget


def panel():
    frame = QFrame()
    frame.setObjectName('panel')
    layout = QVBoxLayout(frame)
    layout.setContentsMargins(20, 18, 20, 18)
    layout.setSpacing(12)
    return frame, layout


def fmt(value):
    if isinstance(value, (list, dict)):
        return json.dumps(value, ensure_ascii=False, default=str)
    if value is None or pd.isna(value):
        return '—'
    if isinstance(value, (int, float)):
        return f'{value:,.0f}' if float(value).is_integer() else f'{value:,.2f}'
    return str(value)


class DataModel(QAbstractTableModel):
    """Missing numeric values stay missing and sorting uses their numeric values."""
    def __init__(self, frame=None, parent=None):
        super().__init__(parent)
        self.frame = frame if frame is not None else pd.DataFrame()

    def rowCount(self, parent=QModelIndex()):
        return 0 if parent.isValid() else len(self.frame)

    def columnCount(self, parent=QModelIndex()):
        return 0 if parent.isValid() else len(self.frame.columns)

    def data(self, index, role=Qt.ItemDataRole.DisplayRole):
        if not index.isValid() or index.row() >= len(self.frame) or index.column() >= len(self.frame.columns):
            return None
        value = self.frame.iat[index.row(), index.column()]
        if role == Qt.ItemDataRole.DisplayRole:
            return fmt(value)
        if role == Qt.ItemDataRole.ToolTipRole:
            return str(self.frame.columns[index.column()]) + ': ' + fmt(value)
        if role == Qt.ItemDataRole.TextAlignmentRole:
            return int(Qt.AlignmentFlag.AlignVCenter | (Qt.AlignmentFlag.AlignRight if isinstance(value, (int, float)) else Qt.AlignmentFlag.AlignLeft))
        return None

    def headerData(self, section, orientation, role=Qt.ItemDataRole.DisplayRole):
        if role == Qt.ItemDataRole.DisplayRole:
            if orientation == Qt.Orientation.Horizontal and (section < 0 or section >= len(self.frame.columns)):
                return None
            return str(self.frame.columns[section]).replace('_', ' ').title() if orientation == Qt.Orientation.Horizontal else str(section + 1)
        return None

    def sort(self, column, order):
        if column < 0 or column >= len(self.frame.columns):
            return
        self.layoutAboutToBeChanged.emit()
        self.frame = self.frame.sort_values(self.frame.columns[column], ascending=order == Qt.SortOrder.AscendingOrder, na_position='last').reset_index(drop=True)
        self.layoutChanged.emit()


class Signals(QObject):
    done = Signal(object)
    failed = Signal(str)
    progress = Signal(str)


class Job(QRunnable):
    def __init__(self, fn):
        super().__init__()
        self.fn = fn
        self.signals = Signals()

    def run(self):
        try:
            self.signals.done.emit(self.fn(self.signals.progress.emit))
        except Exception as exc:
            self.signals.failed.emit(f'{type(exc).__name__}: {exc}')


class SportBanner(QWidget):
    """Original vector artwork is decorative, never presented as measured tracking."""
    def __init__(self, sport='Soccer'):
        super().__init__()
        self.sport = sport
        self.setMinimumHeight(176)

    def set_sport(self, sport):
        self.sport = sport
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        accent, mode, title, subtitle = SPORT_STYLES[self.sport]
        rect = QRectF(self.rect().adjusted(0, 0, -1, -1))
        gradient = QLinearGradient(rect.topLeft(), rect.bottomRight())
        gradient.setColorAt(0, QColor('#1c2930' if self.sport == 'Soccer' else '#242029' if self.sport == 'F1' else '#23242b'))
        gradient.setColorAt(1, QColor('#121a21'))
        painter.setBrush(gradient)
        painter.setPen(QPen(QColor('#31404b'), 1))
        painter.drawRoundedRect(rect, 12, 12)
        x, y, w, h = rect.width() * .70, 27, rect.width() * .26, 120
        color = QColor(accent)
        color.setAlpha(135)
        painter.setPen(QPen(color, 1.6))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        if self.sport == 'Soccer':
            painter.drawRect(QRectF(x, y, w, h))
            painter.drawLine(int(x+w/2), y, int(x+w/2), int(y+h))
            painter.drawEllipse(QRectF(x+w*.35, y+h*.27, w*.3, h*.46))
            for left in (x, x+w*.82):
                painter.drawRect(QRectF(left, y+h*.24, w*.18, h*.52))
        elif self.sport == 'NBA':
            painter.drawRect(QRectF(x, y, w, h))
            painter.drawLine(int(x+w/2), y, int(x+w/2), int(y+h))
            painter.drawEllipse(QRectF(x+w*.39, y+h*.31, w*.22, h*.38))
            for left in (x, x+w*.78):
                painter.drawRect(QRectF(left, y+h*.30, w*.22, h*.40))
                painter.drawEllipse(QRectF(left, y+h*.12, w*.22, h*.76))
        elif self.sport == 'AFL':
            painter.drawEllipse(QRectF(x, y, w, h))
            painter.drawEllipse(QRectF(x+w*.35, y+h*.28, w*.30, h*.44))
            painter.drawRect(QRectF(x+w*.28, y+h*.20, w*.44, h*.60))
            for left in (x, x+w):
                for offset in (-14, -5, 5, 14):
                    painter.drawLine(int(left), int(y+h/2+offset), int(left+(9 if left == x else -9)), int(y+h/2+offset))
        else:
            path = QPainterPath()
            points = [(0,.7),(.15,.83),(.30,.69),(.31,.35),(.53,.32),(.60,.65),(.77,.61),(.91,.20),(1,.13),(.82,.12),(.71,.38),(.47,.1),(.15,.16),(0,.7)]
            path.moveTo(x+points[0][0]*w, y+points[0][1]*h)
            for a, b in points[1:]:
                path.lineTo(x+a*w, y+b*h)
            painter.drawPath(path)
            painter.setPen(QColor('#97a3b2'))
            painter.setFont(QFont('Segoe UI', 7))
            painter.drawText(int(x), int(y+h+14), 'ILLUSTRATIVE CIRCUIT · NO TELEMETRY')
        painter.setPen(QColor(accent))
        painter.setFont(QFont('Segoe UI', 9, QFont.Weight.Bold))
        painter.drawText(28, 36, mode + '   /   GAMESENSE ARCHIVE')
        painter.setPen(QColor('#f3f5f8'))
        painter.setFont(QFont('Segoe UI', 23, QFont.Weight.Bold))
        painter.drawText(QRectF(28, 49, rect.width()*.66, 48), Qt.AlignmentFlag.AlignVCenter, title)
        painter.setPen(QColor('#a8b5c4'))
        painter.setFont(QFont('Segoe UI', 10))
        painter.drawText(29, 125, subtitle)
        painter.end()


class GameSenseWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle('GameSense — Sports Intelligence')
        self.resize(1440, 960)
        self.setMinimumSize(1040, 720)
        icon = Path(__file__).resolve().parents[1] / 'assets' / 'gamesense.png'
        if icon.exists():
            self.setWindowIcon(QIcon(str(icon)))
        self.archive = Archive()
        self.initializing = True
        self.settings = QSettings(str(Path(self.archive.path).parent / 'preferences.ini'), QSettings.Format.IniFormat)
        if __import__('os').environ.get('GAMESENSE_OFFLINE') == '1':
            self.settings.setValue('offline', True)
        self.pool = QThreadPool(self)
        self.jobs = {}
        self.cancel_event = threading.Event()
        self.download_running = False
        self.download_seasons = []
        self.frame = pd.DataFrame()
        self.profile_frame = pd.DataFrame()
        self.identities = pd.DataFrame()
        self.demo = False
        self.route = 'home'
        self.page_offset = 0
        self._build()
        self._change_sport()
        self.navigate('home')
        self.status.setText('Preparing the bundled real historical archive in the background…')
        self._job('bootstrap', lambda progress: self.archive.seed_bundled(), self._bootstrap_done, self._bootstrap_failed)

    def _bootstrap_done(self, count):
        self.initializing = False
        self.status.setText(f'Local archive ready · {count:,} bundled records processed. Downloaded history works offline.')
        self._change_sport()

    def _bootstrap_failed(self, message):
        self.initializing = False
        self.status.setText('Archive preparation failed: ' + message)

    @property
    def sport_name(self):
        return self.sport.currentText()

    def _build(self):
        root = QWidget()
        self.setCentralWidget(root)
        shell = QHBoxLayout(root)
        shell.setContentsMargins(0, 0, 0, 0)
        shell.setSpacing(0)
        sidebar = QFrame()
        sidebar.setObjectName('sidebar')
        sidebar.setFixedWidth(206)
        nav = QVBoxLayout(sidebar)
        nav.setContentsMargins(16, 27, 16, 22)
        nav.addWidget(label('GAMESENSE', 'brand'))
        nav.addWidget(label('SPORTS INTELLIGENCE', 'eyebrow'))
        nav.addSpacing(30)
        self.nav_buttons = {}
        for key, title in [('home','Overview'), ('dashboard','Sport dashboard'), ('profiles','Players & clubs'), ('teams','Teams and rosters'), ('compare','Head to head'), ('leaders','Leaderboards'), ('explorer','Historical records')]:
            btn = button(title, lambda checked=False, k=key: self.navigate(k))
            btn.setObjectName('nav')
            btn.setCheckable(True)
            self.nav_buttons[key] = btn
            nav.addWidget(btn)
        nav.addStretch()
        nav.addWidget(label('YOUR LIBRARY', 'eyebrow'))
        for key, title in [('downloads', 'Data manager'), ('settings','Preferences'), ('about','Sources and about')]:
            btn = button(title, lambda checked=False, k=key: self.navigate(k))
            btn.setObjectName('nav')
            btn.setCheckable(True)
            self.nav_buttons[key] = btn
            nav.addWidget(btn)
        nav.addSpacing(14)
        nav.addWidget(label('DESKTOP  /  0.8.0 · MULTI-LEAGUE EDITION', 'muted'))
        shell.addWidget(sidebar)
        body = QWidget()
        layout = QVBoxLayout(body)
        layout.setContentsMargins(28, 22, 28, 16)
        layout.setSpacing(17)
        header = QHBoxLayout()
        self.breadcrumb = label('WORKSPACE / OVERVIEW', 'eyebrow')
        header.addWidget(self.breadcrumb)
        header.addStretch()
        self.search = QLineEdit()
        self.search.setPlaceholderText('Search your archive…')
        self.search.setClearButtonEnabled(True)
        self.search.setMinimumWidth(210)
        self.search_timer = QTimer(self)
        self.search_timer.setSingleShot(True)
        self.search_timer.setInterval(220)
        self.search.textChanged.connect(lambda: self.search_timer.start())
        self.search_timer.timeout.connect(self._search_changed)
        self.search.returnPressed.connect(lambda: self.navigate('profiles'))
        header.addWidget(self.search)
        self.sport = QComboBox()
        self.sport.addItems(SPORTS)
        self.sport.setMinimumWidth(118)
        self.sport.currentTextChanged.connect(self._change_sport)
        header.addWidget(self.sport)
        self.season = QComboBox()
        self.season.setMinimumWidth(128)
        self.season.currentTextChanged.connect(self._season_changed)
        header.addWidget(self.season)
        self.competition_filter = QComboBox()
        self.competition_filter.setMinimumWidth(170)
        self.competition_filter.setToolTip(
            'Filter to a real league or competition present in your downloaded archive.')
        self.competition_filter.addItem('All competitions')
        self.competition_filter.currentTextChanged.connect(self._competition_changed)
        header.addWidget(self.competition_filter)
        layout.addLayout(header)
        self.stack = QStackedWidget()
        layout.addWidget(self.stack, 1)
        self.pages = {}
        self.page_layouts = {}
        for key in self.nav_buttons:
            page = QWidget()
            page_layout = QVBoxLayout(page)
            page_layout.setContentsMargins(0, 0, 0, 0)
            page_layout.setSpacing(16)
            page_layout.setSizeConstraint(QLayout.SizeConstraint.SetMinimumSize)
            scroll = QScrollArea()
            scroll.setWidgetResizable(True)
            scroll.setWidget(page)
            self.pages[key] = scroll
            self.page_layouts[key] = page_layout
            self.stack.addWidget(scroll)
        self._build_home()
        self._build_dashboard()
        self._build_profiles()
        self._build_compare()
        self._build_teams()
        self._build_leaders()
        self._build_explorer()
        self._build_downloads()
        self._build_settings()
        self._build_about()
        self.status = label('Local archive ready. Downloaded records remain available offline.', 'muted', True)
        layout.addWidget(self.status)
        shell.addWidget(body, 1)

    def _table(self, minimum=230):
        table = QTableView()
        table.setMinimumHeight(minimum)
        table.setAlternatingRowColors(True)
        table.setSelectionBehavior(QTableView.SelectionBehavior.SelectRows)
        table.setSelectionMode(QTableView.SelectionMode.SingleSelection)
        table.setEditTriggers(QTableView.EditTrigger.NoEditTriggers)
        table.setSortingEnabled(True)
        table.verticalHeader().hide()
        table.horizontalHeader().setStretchLastSection(True)
        return table

    def _fill(self, table, frame):
        table.setSortingEnabled(False)
        old = table.model()
        table.setModel(DataModel(frame.reset_index(drop=True), table))
        if old is not None:
            old.deleteLater()
        table.resizeColumnsToContents()
        for i in range(len(frame.columns)):
            table.setColumnWidth(i, min(280, max(95, table.columnWidth(i))))
        table.horizontalHeader().setStretchLastSection(True)
        # Keep the query's meaningful initial order. Qt otherwise sorts a fresh
        # model by its first (often technical identifier) column automatically.
        table.horizontalHeader().setSortIndicator(-1, Qt.SortOrder.AscendingOrder)
        table.setSortingEnabled(True)

    def _heading(self, layout, eyebrow, title, subtitle):
        layout.addWidget(label(eyebrow, 'eyebrow'))
        layout.addWidget(label(title, 'heading', True))
        layout.addWidget(label(subtitle, 'muted', True))

    def _build_home(self):
        layout = self.page_layouts['home']
        self._heading(layout, 'FOUR SPORTS. ONE PERSPECTIVE.', 'The game. In greater detail.', 'Explore real sporting history, trace a career, and turn records into a clearer picture.')
        self.home_grid = QGridLayout()
        self.home_counts = {}
        for index, sport in enumerate(SPORTS):
            frame, inner = panel()
            inner.addWidget(label(SPORT_STYLES[sport][1], 'eyebrow'))
            inner.addWidget(label({'Soccer':'Football', 'NBA':'Basketball', 'AFL':'Australian football', 'F1':'Formula 1'}[sport], 'section'))
            count = label('', 'muted', True)
            self.home_counts[sport] = count
            inner.addWidget(count)
            inner.addWidget(button('Explore archive  →', lambda checked=False, s=sport: self.open_sport(s), True))
            self.home_grid.addWidget(frame, index//2, index%2)
        layout.addLayout(self.home_grid)
        frame, inner = panel()
        inner.addWidget(label('Your archive, with the context intact.', 'section'))
        inner.addWidget(label('Each record keeps its provider and identity. Empty statistics stay empty. Historical coverage varies by competition and era; the Data Manager shows what is actually stored.', 'muted', True))
        inner.addWidget(button('Manage historical downloads', lambda: self.navigate('downloads')))
        layout.addWidget(frame)
        layout.addStretch()

    def _chart_controls(self, chart, parent_layout, callback):
        controls = QHBoxLayout()
        metric = QComboBox()
        metric.setMinimumWidth(160)
        mode = QComboBox()
        mode.addItems(MODES)
        controls.addWidget(label('METRIC', 'muted'))
        controls.addWidget(metric)
        controls.addWidget(mode)
        controls.addStretch()
        controls.addWidget(button('Save chart', lambda: self._export_chart(chart)))
        controls.addWidget(button('Export chart data', lambda: self._export_chart_data(chart)))
        metric.currentTextChanged.connect(callback)
        mode.currentTextChanged.connect(callback)
        chart.pointSelected.connect(self._open_identity)
        parent_layout.addLayout(controls)
        parent_layout.addWidget(chart)
        return metric, mode

    def _build_dashboard(self):
        layout = self.page_layouts['dashboard']
        self.banner = SportBanner()
        layout.addWidget(self.banner)
        self.coverage_note = label('', 'muted', True)
        layout.addWidget(self.coverage_note)
        self.history_action = button(
            'DISCOVER REAL PLAYER HISTORY', self._dashboard_history_action, True)
        layout.addWidget(self.history_action, alignment=Qt.AlignmentFlag.AlignLeft)
        cards = QHBoxLayout()
        self.stat_values = []
        for title in ['LOCAL RECORDS', 'IDENTITIES', 'TEAMS', 'SEASONS']:
            frame, inner = panel()
            inner.addWidget(label(title, 'muted'))
            value = label('—', 'number')
            inner.addWidget(value)
            self.stat_values.append(value)
            cards.addWidget(frame)
        layout.addLayout(cards)
        # A real analytics dashboard needs simultaneous, different explanations of
        # the data — not a single chart with nineteen options in a dropdown.
        layout.addWidget(label('THE ANALYTICS STUDIO', 'section'))
        layout.addWidget(label(
            'Six independent interactive charts. Every panel is generated from recorded '
            'statistics; unavailable data stays visibly unavailable.', 'muted', True))
        frame, inner = panel()
        inner.addWidget(label('YOUR DEEP DIVE', 'eyebrow'))
        self.dash_chart = AnalyticsChart()
        self.dash_metric, self.dash_mode = self._chart_controls(
            self.dash_chart, inner, self._plot_dashboard)
        self.dash_grid = QGridLayout()
        self.dash_grid.setHorizontalSpacing(14)
        self.dash_grid.setVerticalSpacing(14)
        self.dash_visuals = []
        for index in range(6):
            card, content = panel()
            caption = label('SPORT INTELLIGENCE', 'eyebrow')
            content.addWidget(caption)
            chart = AnalyticsChart()
            chart.setMinimumHeight(290)
            # Each dashboard tile is a clean read-only visual, with hover and
            # point selection. The separate Deep Dive retains full pan/zoom/export
            # tools, rather than repeating a toolbar in every mini-panel.
            chart.toolbar.setVisible(False)
            chart.pointSelected.connect(self._open_identity)
            content.addWidget(chart)
            self.dash_visuals.append((caption, chart))
            self.dash_grid.addWidget(card, index // 2, index % 2)
        layout.addLayout(self.dash_grid)
        layout.addWidget(label('BUILD YOUR OWN COMPARISON', 'section'))
        layout.addWidget(frame)
        self.featured = QHBoxLayout()
        layout.addWidget(label('FROM YOUR ARCHIVE', 'eyebrow'))
        layout.addLayout(self.featured)
        layout.addStretch()

    def _build_profiles(self):
        layout = self.page_layouts['profiles']
        self._heading(layout, 'PLAYERS & CLUBS', 'A complete picture of the game.', 'Explore real athlete performance and verified club results across recorded seasons and leagues. Club goals are not player goals.')
        self.athlete = QComboBox()
        self.athlete.setEditable(True)
        self.athlete.completer().setFilterMode(Qt.MatchFlag.MatchContains)
        self.athlete.completer().setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        self.athlete.setMinimumWidth(270)
        self.athlete.currentIndexChanged.connect(self._load_profile)
        row = QHBoxLayout()
        row.addWidget(self.athlete, 1)
        self.fav_button = button('Save favourite', self._toggle_favourite)
        row.addWidget(self.fav_button)
        row.addWidget(button('Explore verified data sources', self._open_data_finder))
        layout.addLayout(row)
        self.profile_full_history = QCheckBox(
            'Show full downloaded club history · all seasons & competitions')
        self.profile_full_history.setChecked(True)
        self.profile_full_history.toggled.connect(self._load_profile)
        layout.addWidget(self.profile_full_history)
        filters = QHBoxLayout()
        self.era_start, self.era_end = QSpinBox(), QSpinBox()
        for spin in (self.era_start, self.era_end):
            spin.setRange(0, 2100)
            spin.setSpecialValueText('Any year')
            spin.setSingleStep(1)
            spin.valueChanged.connect(self._identity_filters_changed)
        filters.addWidget(label('Recorded seasons from', 'muted'))
        filters.addWidget(self.era_start)
        filters.addWidget(label('through', 'muted'))
        filters.addWidget(self.era_end)
        self.favourites_only = QCheckBox('Favourites only')
        self.favourites_only.toggled.connect(self._identity_filters_changed)
        filters.addWidget(self.favourites_only)
        filters.addStretch()
        layout.addLayout(filters)
        frame, inner = panel()
        hero = QHBoxLayout()
        self.portrait = PortraitWidget(size=168)
        hero.addWidget(self.portrait)
        text = QVBoxLayout()
        self.profile_name = label('Choose an athlete', 'heading', True)
        self.profile_meta = label('', 'muted', True)
        self.profile_summary = label('', 'muted', True)
        self.profile_eyebrow = label('CAREER PROFILE', 'eyebrow')
        text.addWidget(self.profile_eyebrow)
        text.addWidget(self.profile_name)
        text.addWidget(self.profile_meta)
        text.addWidget(self.profile_summary)
        numbers = QHBoxLayout()
        self.hero_metrics = []
        for _ in range(3):
            stat = QVBoxLayout()
            value, caption = label('—', 'section'), label('', 'muted')
            stat.addWidget(value)
            stat.addWidget(caption)
            numbers.addLayout(stat)
            self.hero_metrics.append((value, caption))
        text.addLayout(numbers)
        self.profile_breakdown = label('', 'muted', True)
        text.addWidget(self.profile_breakdown)
        text.addStretch()
        hero.addLayout(text, 1)
        inner.addLayout(hero)
        self.image_credit = label('Portraits are licensed individually. A silhouette means no verified photograph is cached.', 'muted', True)
        self.image_credit.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self.portrait.attributionChanged.connect(self.image_credit.setText)
        inner.addWidget(self.image_credit)
        layout.addWidget(frame)
        tabs = QTabWidget()
        overview = QWidget()
        ov = QVBoxLayout(overview)
        self.profile_chart = AnalyticsChart()
        self.profile_metric, self.profile_mode = self._chart_controls(self.profile_chart, ov, self._plot_profile)
        self.profile_detail = label('', 'muted', True)
        ov.addWidget(self.profile_detail)
        tabs.addTab(overview, 'Performance evolution')
        history = QWidget()
        hl = QVBoxLayout(history)
        self.history_table = self._table(270)
        hl.addWidget(self.history_table)
        tabs.addTab(history, 'Season history')
        match_screen = QWidget()
        match_layout = QVBoxLayout(match_screen)
        self.profile_match_note = label(
            'Actual final match results, with source attribution and opponent. '
            'This is club history, not athlete appearances.', 'muted', True)
        match_layout.addWidget(self.profile_match_note)
        self.profile_match_table = self._table(290)
        match_layout.addWidget(self.profile_match_table)
        self.profile_match_index = tabs.addTab(match_screen, 'Match results')
        self.profile_tabs = tabs
        advanced = QWidget()
        al = QVBoxLayout(advanced)
        self.advanced_table = self._table(270)
        al.addWidget(self.advanced_table)
        tabs.addTab(advanced, 'Available statistics')
        sources = QWidget()
        sl = QVBoxLayout(sources)
        self.profile_sources = label('', 'muted', True)
        self.profile_sources.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        sl.addWidget(self.profile_sources)
        sl.addStretch()
        tabs.addTab(sources, 'Sources & coverage')
        layout.addWidget(tabs)
        layout.addStretch()

    def _build_compare(self):
        layout = self.page_layouts['compare']
        self._heading(layout, 'HEAD TO HEAD', 'Two careers. A clearer comparison.', 'Compare the same statistic within the selected sport and season. Missing values are never substituted with zero.')
        row = QHBoxLayout()
        self.compare_a, self.compare_b = QComboBox(), QComboBox()
        self.compare_portraits = []
        for combo in (self.compare_a, self.compare_b):
            frame, inner = panel()
            portrait = PortraitWidget(size=120)
            inner.addWidget(portrait, alignment=Qt.AlignmentFlag.AlignHCenter)
            inner.addWidget(combo)
            combo.currentIndexChanged.connect(self._load_comparison)
            self.compare_portraits.append(portrait)
            row.addWidget(frame)
        layout.addLayout(row)
        self.compare_chart = AnalyticsChart()
        self.compare_metric, self.compare_mode = self._chart_controls(self.compare_chart, layout, self._plot_comparison)
        self.compare_table = self._table(170)
        layout.addWidget(self.compare_table)
        layout.addStretch()

    def _build_teams(self):
        layout = self.page_layouts['teams']
        self._heading(layout, 'CLUB PERFORMANCE & ROSTERS', 'Results and the people behind them.', 'Explore real team scores, league-season performance and match logs. Rosters only appear when an actual athlete-level provider supplies them.')
        self.team_select = QComboBox()
        self.team_select.currentTextChanged.connect(self._load_team)
        layout.addWidget(self.team_select)
        self.team_note = label('', 'muted', True)
        layout.addWidget(self.team_note)
        self.open_club_button = button(
            'VIEW FULL VERIFIED CLUB PROFILE  →',self._open_selected_club_profile,True)
        layout.addWidget(self.open_club_button)
        self.roster_grid = QGridLayout()
        layout.addLayout(self.roster_grid)
        layout.addWidget(label('PERFORMANCE BY LEAGUE & SEASON','section'))
        self.team_table = self._table()
        layout.addWidget(self.team_table)
        layout.addWidget(label('RECORDED CLUB MATCHES','section'))
        self.team_matches = self._table(260)
        layout.addWidget(self.team_matches)
        layout.addStretch()

    def _build_leaders(self):
        layout = self.page_layouts['leaders']
        self._heading(layout, 'LEADERBOARDS', 'Standouts, with the evidence.', 'Rankings below use the current bounded query. Download more history or narrow the season for a meaningful cohort.')
        controls = QHBoxLayout()
        self.leader_metric = QComboBox()
        self.leader_metric.currentTextChanged.connect(self._load_leaders)
        self.leader_total = QCheckBox('Compare totals (rates use averages)')
        self.leader_total.setChecked(True)
        self.leader_total.toggled.connect(self._load_leaders)
        controls.addWidget(self.leader_metric)
        controls.addWidget(self.leader_total)
        controls.addStretch()
        controls.addWidget(button('Export standings', self._export_leaders))
        layout.addLayout(controls)
        self.leaders_featured = QHBoxLayout()
        layout.addLayout(self.leaders_featured)
        self.leader_table = self._table(380)
        self.leader_table.doubleClicked.connect(lambda index: self._open_table_identity(self.leader_table, index))
        layout.addWidget(self.leader_table)
        layout.addStretch()

    def _build_explorer(self):
        layout = self.page_layouts['explorer']
        self._heading(layout, 'HISTORICAL RECORDS', 'The source of every insight.', 'Browse a page of the archive. Every row retains its source, identity, record type and season.')
        controls = QHBoxLayout()
        controls.addWidget(button('Import CSV / Excel', self._import_file, True))
        controls.addWidget(button('Export visible records', self._export_records))
        controls.addStretch()
        self.previous = button('← Previous', lambda: self._turn_page(-1))
        self.next_page = button('Next →', lambda: self._turn_page(1))
        controls.addWidget(self.previous)
        controls.addWidget(self.next_page)
        layout.addLayout(controls)
        self.explorer_note = label('', 'muted', True)
        layout.addWidget(self.explorer_note)
        self.raw_table = self._table(470)
        self.raw_table.doubleClicked.connect(lambda index: self._open_table_identity(self.raw_table, index))
        layout.addWidget(self.raw_table)
        layout.addStretch()

    def _build_downloads(self):
        layout = self.page_layouts['downloads']
        self._heading(layout, 'DATA MANAGER', 'Build your sporting library.', 'Downloads save completed chunks immediately. Resume skips completed seasons; update latest refreshes the newest available season.')
        self.provider = QComboBox()
        for key, provider in PROVIDERS.items():
            self.provider.addItem(provider.meta.name, key)
        self.provider.currentIndexChanged.connect(self._provider_changed)
        layout.addWidget(self.provider)
        self.provider_note = label('', 'muted', True)
        self.provider_note.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        layout.addWidget(self.provider_note)
        self.free_player_card, free_player_layout = panel()
        free_player_layout.addWidget(
            label('START WITH A REAL FOOTBALL LEGEND', 'section'))
        free_player_layout.addWidget(label(
            'Cristiano Ronaldo · Portugal · FIFA World Cup 2022. Fetch verified '
            'match statistics from StatsBomb Open Data without an API key. '
            'This is World Cup coverage, NOT his full club career.',
            'muted', True))
        free_player_layout.addWidget(button(
            'GET REAL CRISTIANO RONALDO · WORLD CUP 2022',
            self._download_ronaldo_sample, True))
        layout.addWidget(self.free_player_card)
        # Freely reusable CC0 European domestic club history, requiring no key.
        self.free_leagues_card, cc0 = panel()
        cc0.addWidget(label('ALL THE CLUBS · MORE REAL EUROPEAN LEAGUES', 'section'))
        cc0.addWidget(label(
            'Premier League, La Liga, Bundesliga, Serie A, Ligue 1, '
            'Eredivisie, Primeira Liga and selected lower divisions. '
            'OpenFootball CC0 supplies actual club match scores from multiple '
            'historical seasons, with no account required. These are CLUB '
            'records, not player goals/assists. Current seasons depend on '
            'the upstream files being published.',
            'muted', True))
        cc0.addWidget(button(
            'DOWNLOAD HISTORICAL EUROPEAN CLUB RESULTS (NO API KEY)',
            self._download_free_club_results, True))
        layout.addWidget(self.free_leagues_card)
        # Optional individual AFL player box scores, distinct from Squiggle
        # team fixtures. This is user-initiated third-party research data only.
        self.afl_research_card, afr = panel()
        afr.addWidget(label('ACTUAL AFL PLAYER STATISTICS · OPT IN', 'section'))
        afr.addWidget(label(
            'Research archive contains recorded player-game kicks, disposals, '
            'handballs, marks, goals, tackles, clearances and more across '
            'historical VFL/AFL seasons. The publisher uses MIT for its '
            'project but cites AFL Tables as the original statistical source. '
            'Its underlying data redistribution rights require independent '
            'verification. Large personal/local download; NOT bundled.',
            'muted', True))
        afr.addWidget(button(
            'IMPORT HISTORICAL AFL PLAYER BOX SCORES',
            self._download_afl_player_archive, True))
        layout.addWidget(self.afl_research_card)
        # Optional authenticated football data: no key is bundled or saved.
        self.api_finder, api = panel()
        api.addWidget(label('GLOBAL FOOTBALL PLAYER FINDER', 'section'))
        api.addWidget(label(
            'Use your own API-Football key to search genuine players by provider ID. '
            'Search Ronaldo, confirm his identity, then retrieve only seasons '
            'covered by your provider subscription. The key stays in memory.',
            'muted', True))
        self.api_key_input = QLineEdit()
        self.api_key_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.api_key_input.setPlaceholderText('Your API-Football key — session only; not stored')
        api.addWidget(self.api_key_input)
        lookup = QHBoxLayout()
        self.api_player_search = QLineEdit()
        self.api_player_search.setPlaceholderText('Search surname, e.g. Ronaldo')
        self.api_player_search.returnPressed.connect(self._find_api_player)
        lookup.addWidget(self.api_player_search, 1)
        lookup.addWidget(button('Find real player', self._find_api_player))
        api.addLayout(lookup)
        self.api_player_results = QComboBox()
        self.api_player_results.setMinimumHeight(34)
        api.addWidget(self.api_player_results)
        api.addWidget(button('DOWNLOAD SELECTED PLAYER CAREER', self._download_api_player, True))
        self.api_search_status = label(
            'Requires an API-Sports account. Availability, costs and redistribution '
            'rights depend on your plan. No complete Ronaldo history is promised.',
            'muted', True)
        api.addWidget(self.api_search_status)
        layout.addWidget(self.api_finder)
        row = QHBoxLayout()
        row.addWidget(button('Discover available seasons', self._discover_seasons))
        self.range_start, self.range_end = QComboBox(), QComboBox()
        row.addWidget(self.range_start, 1)
        row.addWidget(label('to', 'muted'))
        row.addWidget(self.range_end, 1)
        layout.addLayout(row)
        self.competition = QComboBox()
        self.competition.setEditable(True)
        self.competition.setInsertPolicy(QComboBox.InsertPolicy.NoInsert)
        self.competition.setPlaceholderText('Discover and type to filter available competitions')
        competition_row = QHBoxLayout()
        competition_row.addWidget(self.competition, 1)
        self.competition_button = button('Download competition', lambda: self._start_download('competition'))
        competition_row.addWidget(self.competition_button)
        layout.addLayout(competition_row)
        row = QHBoxLayout()
        self.download_all = button('Load all available years', lambda: self._start_download('all'), True)
        self.download_range = button('Download selected range', lambda: self._start_download('range'))
        self.download_latest = button('Update latest', lambda: self._start_download('latest'))
        row.addWidget(self.download_all)
        row.addWidget(self.download_range)
        row.addWidget(self.download_latest)
        layout.addLayout(row)
        row = QHBoxLayout()
        row.addWidget(button('Resume interrupted download', lambda: self._start_download('all')))
        self.cancel_button = button('Cancel download', self._cancel_download)
        self.cancel_button.setEnabled(False)
        row.addWidget(self.cancel_button)
        row.addStretch()
        layout.addLayout(row)
        self.progress = QProgressBar()
        self.progress.setRange(0, 100)
        self.progress.setValue(0)
        layout.addWidget(self.progress)
        self.progress_text = label('Select a source, review its terms, then discover seasons.', 'muted', True)
        layout.addWidget(self.progress_text)
        layout.addWidget(label('Downloaded coverage', 'section'))
        self.coverage_table = self._table(220)
        layout.addWidget(self.coverage_table)
        layout.addWidget(button('Remove selected downloaded season…', self._remove_season))
        self.storage_note = label('', 'muted', True)
        layout.addWidget(self.storage_note)
        layout.addStretch()
        self._provider_changed()

    def _build_settings(self):
        layout = self.page_layouts['settings']
        self._heading(layout, 'PREFERENCES', 'A workspace that works for you.', 'Data lives on this computer. Network access is used for downloads and permitted portraits.')
        frame, inner = panel()
        self.offline = QCheckBox('Offline mode — use only downloaded records and cached portraits')
        self.offline.setChecked(self.settings.value('offline', False, type=bool))
        self.offline.toggled.connect(self._offline_changed)
        inner.addWidget(self.offline)
        self.demo_check = QCheckBox('Demonstration mode — clearly labelled fictional data, separate from archive')
        self.demo_check.toggled.connect(self._demo_changed)
        inner.addWidget(self.demo_check)
        inner.addWidget(label('Demonstration records are never added to your historical database or labelled as real players.', 'muted', True))
        inner.addWidget(label('Squiggle contact email', 'section'))
        self.contact_email = QLineEdit(str(self.archive.setting('contact_email', '')))
        self.contact_email.setPlaceholderText('Email required by the AFL team-results provider')
        inner.addWidget(self.contact_email)
        inner.addWidget(button('Save provider contact', self._save_contact))
        inner.addWidget(label('This address is stored in your local archive and sent to Squiggle in API request headers.', 'muted', True))
        layout.addWidget(frame)
        frame, inner = panel()
        inner.addWidget(label('Archive storage', 'section'))
        self.storage_path_label = label(str(getattr(self.archive, 'path', 'Local user data')), 'muted', True)
        self.storage_path_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        inner.addWidget(self.storage_path_label)
        inner.addWidget(button('Export coverage manifest', self._export_manifest))
        inner.addWidget(label('To reclaim space, back up the archive and remove unwanted data using a SQLite tool while GameSense is closed. No record deletion occurs automatically.', 'muted', True))
        layout.addWidget(frame)
        layout.addStretch()

    def _build_about(self):
        layout = self.page_layouts['about']
        self._heading(layout, 'GAMESENSE / 0.7.0 DEVELOPMENT', 'Statistics deserve context.', 'An independent native desktop application for football, basketball, Australian football and Formula 1.')
        for provider in PROVIDERS.values():
            frame, inner = panel()
            inner.addWidget(label(provider.meta.name, 'section'))
            inner.addWidget(label(self._provider_description(provider), 'muted', True))
            layout.addWidget(frame)
        frame, inner = panel()
        inner.addWidget(label('Images, calculations and acknowledgements', 'section'))
        inner.addWidget(label('Photographs: Wikimedia Commons, with the individual author, licence and source stored alongside each cached image. Unverified images use original silhouette artwork. Team logos are not bundled. Charts use Matplotlib and native Qt. Statistics use Pandas and NumPy; storage uses SQLite. Rate metrics are not summed. Full technical notes and AI assistance disclosure are included in the project documentation.', 'muted', True))
        layout.addWidget(frame)
        layout.addStretch()

    def navigate(self, route):
        self.route = route
        self.stack.setCurrentWidget(self.pages[route])
        for key, btn in self.nav_buttons.items():
            btn.setChecked(key == route)
        self.breadcrumb.setText('WORKSPACE / ' + self.nav_buttons[route].text().upper())
        self.refresh()

    def _dashboard_history_action(self):
        sport = self.sport_name
        if sport == 'Soccer':
            self._download_free_club_results()
            return
        if sport == 'AFL':
            self._download_afl_player_archive()
            return
        self.navigate('downloads')
        provider = {'NBA':'nba_stats', 'AFL':'squiggle', 'F1':'f1db'}.get(sport)
        if provider:
            idx=self.provider.findData(provider)
            if idx >= 0:
                self.provider.setCurrentIndex(idx)
        self.progress_text.setText(
            'This provider is optional and has specific data coverage. '
            'Click Discover available seasons, review the terms, '
            'then download the years it can actually supply.')

    def _open_data_finder(self):
        self.navigate('downloads')
        if self.sport_name == 'Soccer':
            self.provider.setCurrentIndex(self.provider.findData('api_football'))
            term = self.search.text().strip()
            if term:
                self.api_player_search.setText(term)

    def open_sport(self, sport):
        self.sport.setCurrentText(sport)
        self.navigate('dashboard')

    def _change_sport(self, *_):
        if not hasattr(self, 'season'):
            return
        sport = self.sport_name
        accent = SPORT_STYLES[sport][0]
        self.setStyleSheet(BASE_STYLE.replace('ACCENT', accent))
        self.banner.set_sport(sport)
        if hasattr(self, 'free_player_card'):
            self.free_player_card.setVisible(sport == 'Soccer')
        if hasattr(self, 'free_leagues_card'):
            self.free_leagues_card.setVisible(sport == 'Soccer')
        if hasattr(self, 'afl_research_card'):
            self.afl_research_card.setVisible(sport == 'AFL')
        seasons = self.archive.seasons(sport)
        if self.demo:
            from .demo import demo_data
            seasons = sorted(demo_data(sport)['season'].astype(str).unique(), reverse=True)
        self.season.blockSignals(True)
        self.season.clear()
        self.season.addItems(['All downloaded seasons'] + list(map(str, seasons)))
        self.season.blockSignals(False)
        self.competition_filter.blockSignals(True)
        self.competition_filter.clear()
        available = self.archive.competitions(sport) if not self.demo else []
        self.competition_filter.addItems(['All competitions'] + available)
        self.competition_filter.blockSignals(False)
        self.page_offset = 0
        self.search.clear()
        self._update_identities()
        self.refresh()

    def _selected_season(self):
        return None if self.season.currentIndex() <= 0 else self.season.currentText()

    def _selected_competition(self):
        if not hasattr(self, 'competition_filter') or self.competition_filter.currentIndex() <= 0:
            return None
        return self.competition_filter.currentText()

    def _competition_changed(self, *_):
        self.page_offset = 0
        self._update_identities()
        self.refresh()

    def _season_changed(self, *_):
        self.page_offset = 0
        self.refresh()

    def _query(self, competitor_id=None, team=None, limit=5000, offset=0):
        if self.demo:
            from .demo import demo_data
            data, _ = clean_data(demo_data(self.sport_name), self.sport_name)
            data['competitor_id'] = 'demo:' + data['competitor']
            data['source'] = 'FICTIONAL DEMONSTRATION'
            data['record_type'] = 'demo_event'
            if self._selected_season():
                data = data[data['season'].astype(str) == self._selected_season()]
            if self._selected_competition() and 'competition' in data:
                data = data[data['competition'] == self._selected_competition()]
            if competitor_id:
                data = data[data['competitor_id'] == competitor_id]
            if team:
                data = data[data['team'] == team]
            return data.iloc[offset:offset+limit].copy()
        return self.archive.query(
            self.sport_name, season=self._selected_season(),
            competition=self._selected_competition(),
            competitor_id=competitor_id, team=team, limit=limit, offset=offset)

    def _update_identities(self):
        text = self.search.text().strip()
        if self.demo:
            data = self._query(limit=1000)
            ids = data[['competitor_id', 'competitor', 'team']].drop_duplicates('competitor_id')
            if text:
                ids = ids[ids['competitor'].str.contains(text, case=False, regex=False)]
        else:
            first = str(self.era_start.value()) if hasattr(self, 'era_start') and self.era_start.value() else None
            last = str(self.era_end.value()) + '\uffff' if hasattr(self, 'era_end') and self.era_end.value() else None
            ids = self.archive.search(
                self.sport_name, text=text, limit=1000,
                first_season=first, last_season=last,
                competition=self._selected_competition(),
                season=self._selected_season())
        if hasattr(self, 'favourites_only') and self.favourites_only.isChecked() and not ids.empty:
            ids = ids[ids['competitor_id'].astype(str).isin(self._favourites())]
        self.identities = ids
        for combo, fallback in [(self.athlete, 0), (self.compare_a, 0), (self.compare_b, 1)]:
            old = combo.currentData()
            combo.blockSignals(True)
            combo.clear()
            for _, row in ids.iterrows():
                kind = ' [team]' if row.get('entity_type') == 'team' else ''
                combo.addItem(str(row['competitor']) + kind + ' · ' + str(row.get('team', '')), str(row['competitor_id']))
            index = combo.findData(old)
            combo.setCurrentIndex(index if index >= 0 else min(fallback, len(ids)-1))
            combo.blockSignals(False)

    def _search_changed(self):
        self._update_identities()
        if self.search.text().strip() and self.route != 'profiles':
            self.navigate('profiles')
        elif self.route == 'profiles':
            self._load_profile()

    def _identity_filters_changed(self, *_):
        if not hasattr(self, 'favourites_only') or not hasattr(self, 'compare_b'):
            return
        self._update_identities()
        if self.route == 'profiles':
            self._load_profile()

    def refresh(self, *_):
        if not hasattr(self, 'raw_table'):
            return
        sport = self.sport_name
        route = self.route
        if route == 'home':
            for name, widget in self.home_counts.items():
                stats = self.archive.stats(name)
                widget.setText(f"{stats.get('records', 0):,} records · {stats.get('competitors', stats.get('identities', 0)):,} identities · {stats.get('seasons', 0)} seasons\nStored locally. Source coverage varies.")
        elif route in {'dashboard', 'leaders', 'teams'}:
            self.frame = self._query(limit=10000)
            if route == 'dashboard':
                stats = self.archive.stats(sport) if not self.demo else {'records':len(self.frame), 'competitors':self.frame['competitor'].nunique(), 'teams':self.frame['team'].nunique(), 'seasons':self.frame['season'].nunique()}
                for widget, key in zip(self.stat_values, ['records','competitors','teams','seasons']):
                    widget.setText(fmt(stats.get(key, stats.get('identities', 0) if key == 'competitors' else 0)))
                sources = ', '.join(self.frame.get('source', self.frame.get('provider', pd.Series(dtype=str))).dropna().astype(str).unique())
                scope = ''
                if not self.frame.empty and 'entity_type' in self.frame:
                    kinds = self.frame['entity_type'].astype(str).value_counts()
                    team_records = int(kinds.get('team', 0))
                    athlete_records = int(kinds.get('athlete', 0))
                    scope = (
                        f"\nThis selection: {team_records:,} TEAM match rows and "
                        f"{athlete_records:,} ATHLETE rows. "
                    )
                    if sport=='AFL' and not athlete_records:
                        scope += ('Squiggle records include real goals, behinds, scores, '
                                  'margins and results. For individual disposals, kicks, '
                                  'marks or tackles, use the opt-in historical player '
                                  'archive in Data Manager.')
                    if sport=='Soccer' and not athlete_records:
                        scope += ('OpenFootball supplies club matches across leagues, '
                                  'not individual players. For Ronaldo or player career '
                                  'stats, use a supported player-level source.')
                self.coverage_note.setText(
                    ('FICTIONAL DEMONSTRATION MODE · ' if self.demo else 'REAL LOCAL ARCHIVE · ')
                    + (sources or 'No records for this selection. Open Data Manager to download history.')
                    + scope + '\nCharts show up to 10,000 selected records; '
                    'filter a season for a complete local cohort.')
                self.history_action.setText(
                    'GET MORE FOOTBALL CLUB HISTORY & PLAYER SOURCES'
                    if sport=='Soccer' else
                    'EXPLORE HISTORICAL NBA PLAYERS (1946–PRESENT)'
                    if sport=='NBA' else
                    'LOAD VERIFIED HISTORICAL '+sport+' DATA')
                self._set_metrics(self.dash_metric, self.frame)
                self._plot_dashboard()
                self._feature_cards(self.featured, self.identities.head(3))
            elif route == 'leaders':
                self._set_metrics(self.leader_metric, self.frame)
                self._load_leaders()
            else:
                old = self.team_select.currentText()
                teams = sorted(self.frame.get('team', pd.Series(dtype=str)).dropna().astype(str).unique())
                self.team_select.blockSignals(True)
                self.team_select.clear()
                self.team_select.addItems(teams)
                if old in teams:
                    self.team_select.setCurrentText(old)
                self.team_select.blockSignals(False)
                self._load_team()
        elif route == 'profiles':
            self._load_profile()
        elif route == 'compare':
            self._load_comparison()
        elif route == 'explorer':
            frame = self._query(limit=300, offset=self.page_offset)
            front = [c for c in ['date','season','competitor','team','competition','event','record_kind'] + available_metrics(frame) if c in frame]
            frame = frame[list(dict.fromkeys(front + list(frame.columns)))]
            self._fill(self.raw_table, frame)
            self.previous.setEnabled(self.page_offset > 0)
            self.next_page.setEnabled(len(frame) == 300)
            self.explorer_note.setText(f"Showing {len(frame):,} rows at offset {self.page_offset:,}. Double-click a row to open its identity. " + ('FICTIONAL DEMONSTRATION.' if self.demo else 'Only actual downloaded records are shown.'))
        elif route == 'downloads':
            coverage = self.archive.coverage(sport)
            self._fill(self.coverage_table, pd.DataFrame(coverage))
            path = Path(self.archive.path)
            size = path.stat().st_size / (1024*1024) if path.exists() else 0
            self.storage_note.setText(f'Archive: {path}\nDatabase: {size:,.1f} MB. Completed records are available without internet.')

    def _set_metrics(self, combo, frame):
        previous = combo.currentText()
        metrics = available_metrics(frame)
        combo.blockSignals(True)
        combo.clear()
        combo.addItems(metrics)
        preferred = {'F1':'points','NBA':'points','Soccer':'goals','AFL':'goals'}[self.sport_name]
        if previous in metrics:
            combo.setCurrentText(previous)
        elif preferred in metrics:
            combo.setCurrentText(preferred)
        combo.blockSignals(False)

    def _plot_dashboard(self, *_):
        frame = getattr(self, 'frame', pd.DataFrame())
        sport = self.sport_name
        self.dash_chart.plot(
            frame, sport, metric=self.dash_metric.currentText() or None,
            mode=self.dash_mode.currentText())
        if not hasattr(self, 'dash_visuals'):
            return
        # Each sporting discipline has a distinct analytical story. The chart
        # engine displays an explicit missing-data state for unsupported modes.
        layouts = {
            'Soccer': [
                ('GOALS ACROSS SEASONS', 'Season trend', 'goals'),
                ('GOALSCORING LEADERS', 'Ranking', 'goals'),
                ('SHOT MAP / VERIFIED COORDINATES', 'Shot map', 'shots'),
                ('ATTACKING EFFICIENCY', 'Scatter', 'shots'),
                ('CHANCE DISTRIBUTION', 'Distribution', 'goals'),
                ('PLAYER PROFILE COMPARISON', 'Radar', 'goals')],
            'NBA': [
                ('SCORING THROUGH THE YEARS', 'Season trend', 'points'),
                ('SCORING LEADERS', 'Ranking', 'points'),
                ('POINTS DISTRIBUTION', 'Distribution', 'points'),
                ('MULTI-STAT PLAYER PROFILE', 'Radar', 'points'),
                ('SCORING VS PLAYMAKING', 'Scatter', 'assists'),
                ('SCORING CONSISTENCY', 'Box plot', 'points')],
            'AFL': [
                ('BALL-WINNING EVOLUTION', 'Season trend', 'disposals'),
                ('DISPOSALS LEADERS', 'Ranking', 'disposals'),
                ('GOAL DISTRIBUTION', 'Distribution', 'goals'),
                ('PLAYER STAT PROFILE', 'Radar', 'disposals'),
                ('TACKLES VS POSSESSIONS', 'Scatter', 'tackles'),
                ('CONTESTED CONSISTENCY', 'Box plot', 'marks')],
            'F1': [
                ('CHAMPIONSHIP PROGRESSION', 'Season trend', 'points'),
                ('POINTS LEADERS', 'Ranking', 'points'),
                ('QUALIFYING VS RACE', 'Grid vs finish', 'grid_position'),
                ('FINISHING POSITION SPREAD', 'Distribution', 'finish_position'),
                ('DRIVER STRENGTHS', 'Radar', 'points'),
                ('CHAMPIONSHIP EVOLUTION', 'Championship evolution', 'championship_points')],
        }
        metrics = available_metrics(frame) if isinstance(frame, pd.DataFrame) else []
        # Team match scores contain useful stats, but NEVER disposals/assists.
        # The previous app showed six empty AFL panels by asking for player
        # fields in a Squiggle club-score archive. Choose accurate charts
        # based on the actual observational grain, not the name of the sport.
        team_data = bool(
            isinstance(frame, pd.DataFrame) and not frame.empty and
            'entity_type' in frame and
            frame['entity_type'].astype(str).eq('team').mean() >= .5)
        if sport == 'AFL' and team_data:
            layouts[sport] = [
                ('CLUB SCORING THROUGH THE SEASONS', 'Season trend', 'points'),
                ('HIGHEST-SCORING AFL CLUBS', 'Ranking', 'points'),
                ('GOALS PER MATCH · ACTUAL RESULTS', 'Distribution', 'goals'),
                ('DEFENSIVE POINTS CONCEDED', 'Box plot', 'points_against'),
                ('OFFENCE VS DEFENCE · CLUBS', 'Scatter', 'points'),
                ('CLUB PERFORMANCE PROFILE', 'Radar', 'margin'),
            ]
        elif sport == 'Soccer' and team_data:
            layouts[sport] = [
                ('CLUB GOALS BY SEASON', 'Season trend', 'goals'),
                ('TOP SCORING CLUBS', 'Ranking', 'goals'),
                ('GOALS CONCEDED DISTRIBUTION', 'Distribution', 'goals_against'),
                ('ATTACK VS DEFENCE · CLUBS', 'Scatter', 'goals'),
                ('LEAGUE TEAM PERFORMANCE', 'Radar', 'table_points'),
                ('GOAL DIFFERENCE BY MATCH', 'Box plot', 'goal_difference'),
            ]
        for (caption, chart), (heading, mode, preferred) in zip(
                self.dash_visuals, layouts[sport]):
            caption.setText(heading)
            # Do not quietly plot a different metric on a chart whose heading
            # promises something specific: say the source doesn't have it.
            if preferred not in metrics and mode not in (
                    'Shot map', 'Grid vs finish', 'Championship evolution'):
                chart.plot(pd.DataFrame(), sport, mode=mode)
                chart.explanation.setText(
                    f'{preferred.replace("_", " ").title()} is not provided by '
                    'the selected source. Load suitable real player statistics.')
            else:
                second = (
                    'points_against' if sport=='AFL' and team_data else
                    'goals_against' if sport=='Soccer' and team_data else None)
                chart.plot(
                    frame, sport,
                    metric=preferred if preferred in metrics
                           else (metrics[0] if metrics else None),
                    mode=mode,
                    secondary_metric=second if mode=='Scatter' else None)

    def _clear_layout(self, layout):
        while layout.count():
            item = layout.takeAt(0)
            if item.widget():
                item.widget().hide()
                item.widget().deleteLater()
            elif item.layout():
                self._clear_layout(item.layout())

    def _feature_cards(self, layout, identities, grid=False):
        self._clear_layout(layout)
        for index, (_, identity) in enumerate(identities.iterrows()):
            frame, inner = panel()
            frame.setMinimumHeight(154)
            row = QHBoxLayout()
            portrait = PortraitWidget(size=58)
            is_team = identity.get('entity_type') == 'team'
            if not is_team:
                portrait.set_athlete(str(identity['competitor_id']), str(identity['competitor']), self.sport_name, online=self._online() and not self.demo)
            row.addWidget(portrait)
            names = QVBoxLayout()
            names.addWidget(label(str(identity['competitor']), 'section', True))
            names.addWidget(label(str(identity.get('team', '')), 'muted', True))
            row.addLayout(names, 1)
            inner.addLayout(row)
            inner.addWidget(button('View team records' if is_team else 'Explore career  →', lambda checked=False, cid=str(identity['competitor_id']): self._open_identity(cid)))
            if grid:
                layout.addWidget(frame, index//3, index%3)
            else:
                layout.addWidget(frame)

    def _open_identity(self, identity):
        index = self.athlete.findData(identity)
        if index < 0:
            self.search.clear()
            self._update_identities()
            index = self.athlete.findData(identity)
        if index >= 0:
            self.athlete.setCurrentIndex(index)
        self.navigate('profiles')

    def _open_table_identity(self, table, index):
        frame = table.model().frame
        if index.row() < len(frame) and 'competitor_id' in frame:
            self._open_identity(str(frame.iloc[index.row()]['competitor_id']))

    def _online(self):
        return not self.offline.isChecked() if hasattr(self, 'offline') else not self.settings.value('offline', False, type=bool)

    def _load_profile(self, *_):
        if not hasattr(self, 'profile_chart'):
            return
        cid = self.athlete.currentData()
        identity = (
            self.identities[self.identities['competitor_id'].astype(str) == str(cid)]
            if cid and not self.identities.empty else pd.DataFrame())
        name = (
            str(identity.iloc[0]['competitor']) if not identity.empty
            else 'Select a club, player or driver')
        is_team = bool(
            not identity.empty and identity.iloc[0].get('entity_type') == 'team')
        self.profile_full_history.setVisible(is_team)
        self.profile_tabs.setTabVisible(self.profile_match_index, is_team)
        self.profile_eyebrow.setText(
            'VERIFIED CLUB RESULTS' if is_team else 'ATHLETE / DRIVER PROFILE')
        full_history = is_team and self.profile_full_history.isChecked()
        if not cid:
            data = pd.DataFrame()
        elif full_history and not self.demo:
            # Team profiles are a club's REAL complete local history, even
            # when the global archive picker is set to one league/season.
            data = self.archive.query(
                self.sport_name, competitor_id=cid, limit=75000)
        else:
            data = self._query(competitor_id=cid, limit=75000)
        self.profile_frame = data
        self.profile_name.setText(name)
        self.image_credit.setText(
            'Neutral team silhouette · no official club badge has been licensed.'
            if is_team else
            'Licensed athlete images are shown only when verified and available.')
        self.portrait.set_athlete(
            str(cid or 'empty'), name if cid else '', self.sport_name,
            online=self._online() and bool(cid) and not self.demo and not is_team)
        years = sorted(data.get('season', pd.Series(dtype=str)).dropna().astype(str).unique())
        leagues = sorted(data.get('competition', pd.Series(dtype=str)).dropna().astype(str).unique())
        if is_team:
            from .team_analytics import (
                club_summary, club_season_table, club_match_table)
            team_stats = club_summary(data, self.sport_name)
            self.profile_meta.setText(
                f'{self.sport_name} · CLUB / TEAM · VERIFIED FINAL MATCHES\n'
                + (f"{len(leagues)} downloaded competition(s): "
                   + ', '.join(leagues[:8]) if leagues else 'No league data in this selection')
                + (f"\nSeasons: {years[0]} — {years[-1]}" if years else ''))
            self.profile_summary.setText(
                f"{team_stats['matches']:,} played club matches · "
                f"{team_stats['seasons']} seasons · "
                f"{team_stats['leagues']} competitions."
                if team_stats['matches'] else
                'No completed club matches for this selection. '
                'Try full downloaded history or load the correct league in Data Manager.')
            stat_items = [
                ('MATCHES PLAYED',team_stats['matches']),
                ('MATCHES WON',team_stats['wins']),
                (('GOALS SCORED · CLUB' if self.sport_name=='Soccer'
                  else 'POINTS SCORED · CLUB'),team_stats['scored'])]
            for (value,caption),(title,measure) in zip(self.hero_metrics,stat_items):
                value.setText(fmt(measure))
                caption.setText(title)
            if team_stats['matches']:
                text = (
                    f"W {team_stats['wins']}  ·  D {team_stats['draws']}  ·  "
                    f"L {team_stats['losses']}  ·  "
                    f"For {fmt(team_stats['scored'])}  ·  "
                    f"Against {fmt(team_stats['conceded'])}  ·  "
                    f"Difference {fmt(team_stats['difference'])}  ·  "
                    f"Win rate {team_stats['win_rate']:.1f}%")
                if self.sport_name == 'Soccer' and team_stats['league_points'] is not None:
                    text += f"  ·  Reported 3/1/0 match points {fmt(team_stats['league_points'])}"
                self.profile_breakdown.setText(text)
            else:
                self.profile_breakdown.setText(
                    'Missing matches are never interpreted as losses or 0-0 results.')
            self._fill(self.history_table, club_season_table(data,self.sport_name))
            self._fill(self.profile_match_table, club_match_table(data,self.sport_name))
            summary_rows = [
                {'statistic':'Final match records','value':team_stats['matches']},
                {'statistic':'Wins','value':team_stats['wins']},
                {'statistic':'Draws','value':team_stats['draws']},
                {'statistic':'Losses','value':team_stats['losses']},
                {'statistic':'Goals scored' if self.sport_name=='Soccer'
                 else 'Points scored','value':team_stats['scored']},
                {'statistic':'Goals conceded' if self.sport_name=='Soccer'
                 else 'Points conceded','value':team_stats['conceded']},
                {'statistic':'Goal / point difference','value':team_stats['difference']},
                {'statistic':'Win percentage','value':team_stats['win_rate']},
            ]
            if team_stats['league_points'] is not None:
                summary_rows.append(
                    {'statistic':'3/1/0 match points in observed fixtures',
                     'value':team_stats['league_points']})
            self._fill(self.advanced_table,pd.DataFrame(summary_rows))
            self.profile_sources.setText(
                'This is a CLUB / TEAM profile. All goals and final scores are '
                'team-level; player goals, assists, lineups and xG are not inferred.\n\n'
                + ('Full downloaded club history shown across competition and '
                   'season filters. Uncheck the history option to apply the '
                   'top-of-page filters.\n\n' if full_history else
                   'Only the selected season and competition are shown.\n\n')
                + self._profile_provenance(data))
        else:
            self.profile_breakdown.setText('')
            self.profile_meta.setText(
                self.sport_name + ' · Athlete / driver\n'
                + (', '.join(data.get('team',pd.Series(dtype=str)).dropna().astype(str).unique()[:6])
                   or 'No records in the selected season')
                + (f"\n{years[0]} — {years[-1]}" if years else ''))
            self.profile_summary.setText(
                f"{len(data):,} local records · {len(years)} seasons"
                if not data.empty else
                'Download an approved player-level provider archive to retrieve missing history.')
            hero_keys = {
                'F1':['wins','podiums','points'],
                'NBA':['points','rebounds','assists'],
                'Soccer':['goals','assists','xg'],
                'AFL':['disposals','goals','tackles']}[self.sport_name]
            for (value,caption),metric in zip(self.hero_metrics,hero_keys):
                score=metric_summary(data,metric)
                value.setText(fmt(score['total']))
                caption.setText(metric.replace('_',' ').upper()+' · LOCAL TOTAL')
            metrics=available_metrics(data)
            self._fill(self.history_table,season_history(data,metrics[:16]))
            self._fill(self.advanced_table,pd.DataFrame(
                [{'statistic':m,**metric_summary(data,m)} for m in metrics]))
            self.profile_sources.setText(self._profile_provenance(data))
        self._set_metrics(self.profile_metric,data)
        self.fav_button.setText(
            'Saved favourite' if str(cid) in self._favourites()
            else 'Save favourite')
        self._plot_profile()

    @staticmethod
    def _profile_provenance(data):
        note = '\n\n'.join(
            f"{key}: "+', '.join(data[key].dropna().astype(str).unique()[:16])
            for key in ('provider','source_url','license','record_kind','entity_type')
            if key in data)
        return (note or 'No source records for this selection.') + (
            '\n\nAll statistics reflect downloaded completed records only. '
            'Historical coverage is not guaranteed complete. Missing values '
            'are unknown, never filled with zero.')

    def _plot_profile(self, *_):
        if not hasattr(self, 'profile_chart'):
            return
        data=getattr(self,'profile_frame',pd.DataFrame())
        metric=self.profile_metric.currentText()
        mode=self.profile_mode.currentText()
        self.profile_chart.plot(
            data,self.sport_name,metric=metric or None,mode=mode)
        summary=metric_summary(data,metric)
        club=bool(
            not data.empty and 'entity_type' in data
            and data['entity_type'].astype(str).eq('team').all())
        if club:
            self.profile_detail.setText(
                f"Club {metric.replace('_',' ').title() or 'result'} · "
                f"Observed total {fmt(summary['total'])} · "
                f"Average per finished match {fmt(summary['average'])} · "
                f"Best observed match {fmt(summary['best'])} · "
                f"{summary['count']} matches with this measure. "
                "Sources include CLUB final results only; historical coverage may be incomplete.")
        else:
            self.profile_detail.setText(
                f"{metric.replace('_',' ').title() or 'Statistic'} · "
                f"Total {fmt(summary['total'])} · "
                f"Average per recorded row {fmt(summary['average'])} · "
                f"Per game {fmt(summary['per_game'])} · "
                f"Best {fmt(summary['best'])} · "
                f"{summary['count']} observations. Partial downloaded history "
                "is not a complete career.")

    def _favourites(self):
        value = self.settings.value('favourites', '[]')
        try:
            return json.loads(value)
        except (ValueError, TypeError):
            return []

    def _toggle_favourite(self):
        cid = self.athlete.currentData()
        if cid is None:
            return
        favourites = self._favourites()
        if str(cid) in favourites:
            favourites.remove(str(cid))
        else:
            favourites.append(str(cid))
        self.settings.setValue('favourites', json.dumps(favourites))
        self.fav_button.setText('Saved favourite' if str(cid) in favourites else 'Save favourite')

    def _load_comparison(self, *_):
        if not hasattr(self, 'compare_chart'):
            return
        frames = []
        for combo, portrait in zip((self.compare_a, self.compare_b), self.compare_portraits):
            cid = combo.currentData()
            data = self._query(competitor_id=cid, limit=25000) if cid else pd.DataFrame()
            if not data.empty:
                frames.append(data)
            name = str(data['competitor'].iloc[0]) if not data.empty else ''
            portrait.set_athlete(str(cid or 'empty'), name, self.sport_name, online=self._online() and bool(cid) and not self.demo)
        self.comparison_frame = pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()
        if 'record_id' in self.comparison_frame:
            self.comparison_frame = self.comparison_frame.drop_duplicates('record_id')
        self._set_metrics(self.compare_metric, self.comparison_frame)
        self._plot_comparison()

    def _plot_comparison(self, *_):
        frame = getattr(self, 'comparison_frame', pd.DataFrame())
        metric = self.compare_metric.currentText()
        people = list(frame.get('competitor', pd.Series(dtype=str)).dropna().unique())
        self.compare_chart.plot(frame, self.sport_name, people=people, metric=metric or None, mode=self.compare_mode.currentText())
        rows = []
        for cid, group in frame.groupby('competitor_id') if not frame.empty and 'competitor_id' in frame else []:
            rows.append({'competitor':group['competitor'].iloc[-1], **metric_summary(group, metric)})
        self._fill(self.compare_table, pd.DataFrame(rows))

    def _open_selected_club_profile(self):
        team = self.team_select.currentText()
        data = self._query(team=team,limit=20000) if team else pd.DataFrame()
        if data.empty or 'entity_type' not in data:
            return
        clubs = data[data['entity_type'].astype(str).eq('team')]
        if clubs.empty:
            return
        self._open_identity(str(clubs.iloc[0]['competitor_id']))

    def _load_team(self, *_):
        team = self.team_select.currentText()
        data = self._query(team=team, limit=20000) if team else pd.DataFrame()
        identities = (
            data.drop_duplicates('competitor_id')
            if 'competitor_id' in data else pd.DataFrame())
        athletes = (
            identities.loc[identities['entity_type'].ne('team')]
            if not identities.empty and 'entity_type' in identities
            else pd.DataFrame())
        clubs = (
            identities.loc[identities['entity_type'].eq('team')]
            if not identities.empty and 'entity_type' in identities
            else pd.DataFrame())
        self.open_club_button.setEnabled(not clubs.empty)
        self._feature_cards(self.roster_grid, athletes.head(12), grid=True)
        if not clubs.empty:
            from .team_analytics import (
                club_summary,club_season_table,club_match_table)
            club_rows=data[data['entity_type'].astype(str).eq('team')]
            result=club_summary(club_rows,self.sport_name)
            self.team_note.setText(
                f"{team} · {result['matches']:,} observed club games · "
                f"{result['wins']} wins, {result['draws']} draws, "
                f"{result['losses']} losses · "
                f"scored {fmt(result['scored'])}, "
                f"conceded {fmt(result['conceded'])} · "
                f"{result['seasons']} season(s), "
                f"{result['leagues']} league(s). "
                + (f"{len(athletes)} separately sourced athletes. "
                   if len(athletes) else
                   'No verified player roster is provided by this match-result source.'))
            self._fill(self.team_table,
                       club_season_table(club_rows,self.sport_name))
            self._fill(self.team_matches,
                       club_match_table(club_rows,self.sport_name))
        else:
            self.team_note.setText(
                f"{team} · {len(data):,} real athlete records · "
                f"{len(athletes):,} known athlete identities. "
                'Team stats are not inferred from partial player rosters.')
            self._fill(self.team_table,
                       season_history(data,available_metrics(data)[:12]))
            self._fill(self.team_matches,pd.DataFrame())

    def _load_leaders(self, *_):
        if not hasattr(self, 'leader_table'):
            return
        metric = self.leader_metric.currentText()
        self.leader_frame = leaderboard(self.frame, metric, self.leader_total.isChecked())
        display = self.leader_frame.head(500).copy()
        display.insert(0, 'rank', range(1, len(display)+1))
        columns = [c for c in ['rank','competitor','team',metric,'records','competitor_id'] if c in display]
        self._fill(self.leader_table, display[columns])
        self._feature_cards(self.leaders_featured, self.leader_frame.head(3))

    def _turn_page(self, direction):
        self.page_offset = max(0, self.page_offset + direction*300)
        self.refresh()

    def _provider_description(self, provider):
        meta = provider.meta
        return '\n'.join(str(getattr(meta, key, '')) for key in ['description','scope','license','terms_url'] if getattr(meta, key, ''))

    def _provider_changed(self, *_):
        if not hasattr(self, 'provider_note'):
            return
        provider = PROVIDERS[self.provider.currentData()]
        self.provider_note.setText(self._provider_description(provider))
        football_mode = self.provider.currentData() == 'api_football'
        self.api_finder.setVisible(football_mode)
        self.free_leagues_card.setVisible(self.sport_name == 'Soccer')
        self.afl_research_card.setVisible(self.sport_name == 'AFL')
        for widget in (self.download_all, self.download_range, self.download_latest):
            widget.setVisible(not football_mode)
        self.download_seasons = []
        if hasattr(self, 'range_start'):
            self.range_start.clear()
            self.range_end.clear()
        if hasattr(self, 'competition'):
            self.competition.clear()
            self.competition.setVisible(hasattr(provider, 'competitions'))
            self.competition_button.setVisible(hasattr(provider, 'competitions'))

    def _download_free_club_results(self):
        if self.download_running or not self._online():
            return
        reply=QMessageBox.question(
            self, 'Add real football league seasons',
            'Build a REAL local club match library across the Premier League, '
            'La Liga, Bundesliga, Serie A, Ligue 1, Eredivisie and Primeira Liga?\n\n'
            'The application already includes CC0 starter seasons in new '
            'installers. This option requests older and newly available '
            'seasons from the free upstream source. It does not contain '
            'individual player identities, scorers or assists.\n\n'
            'The update can make many small network requests. You may '
            'cancel; completed year files remain cached.',
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.Yes)
        if reply != QMessageBox.StandardButton.Yes:
            return
        self.navigate('downloads')
        self.sport.setCurrentText('Soccer')
        index=self.provider.findData('openfootball')
        if index>=0:
            self.provider.setCurrentIndex(index)
        self._start_download('all')

    def _download_afl_player_archive(self):
        if self.download_running or not self._online():
            return
        reply=QMessageBox.question(
            self, 'Historical AFL player-game data — permissions',
            'This downloads a potentially LARGE third-party research archive '
            '(tens of MB compressed, substantially larger once imported).\n\n'
            'The original box scores came from AFL Tables. The research '
            'repository is marked MIT, but that does not automatically '
            'establish independent rights over its source statistics.\n\n'
            'Proceed for local personal study only, understanding that '
            'you must verify rights before publishing, repackaging or '
            'commercially redistributing the player records?\n\n'
            'Recorded per-game fields may be missing in historical eras; '
            'GameSense will not invent them.',
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No)
        if reply != QMessageBox.StandardButton.Yes:
            return
        self.navigate('downloads')
        self.sport.setCurrentText('AFL')
        index=self.provider.findData('afl_player_research')
        if index>=0:
            self.provider.setCurrentIndex(index)
        self._start_download('all')

    def _download_ronaldo_sample(self):
        if self.download_running or not self._online():
            return
        reply=QMessageBox.question(
            self,'Verified real football data',
            'Download Cristiano Ronaldo’s recorded Portugal matches from '
            'StatsBomb Open Data’s 2022 FIFA World Cup?\n\n'
            'This is a research/noncommercial dataset with source attribution. '
            'It does NOT include every Manchester United, Real Madrid, Juventus '
            'or Al Nassr season. It will not manufacture missing seasons.',
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.Yes)
        if reply != QMessageBox.StandardButton.Yes:
            return
        provider=PROVIDERS['statsbomb']
        self.cancel_event.clear()
        self.download_running=True
        self.cancel_button.setEnabled(True)
        self.provider.setEnabled(False)
        self.progress.setRange(0,0)
        self.progress_text.setText(
            'Retrieving real Cristiano Ronaldo Portugal World Cup records…')
        def run(progress):
            return provider.download_ronaldo_2022(
                self.archive,client=self._client(),
                progress=lambda a,b,msg: progress(f'{a} · {b} · {msg}'))
        def done(count):
            self._download_done(count)
            self.sport.setCurrentText('Soccer')
            self.search.setText('Cristiano Ronaldo')
            self.navigate('profiles')
            self.status.setText(
                f'{count} actual Ronaldo World Cup match records imported. '
                'The remaining club career is NOT covered by this source.')
        self._job('real-ronaldo-2022',run,done,self._download_failed)

    def _configure_api_football(self):
        provider = PROVIDERS['api_football']
        key = self.api_key_input.text().strip()
        if not key:
            self.api_search_status.setText(
                'Enter your own API-Football key. Credentials are never stored.')
            return None
        provider.set_api_key(key)
        return provider

    def _find_api_player(self):
        if self.download_running or not self._online():
            return
        provider = self._configure_api_football()
        if provider is None:
            return
        name = self.api_player_search.text().strip()
        if len(name) < 4:
            self.api_search_status.setText('Search at least four letters.')
            return
        self.api_search_status.setText('Searching the provider by real player identity…')
        def do_search(progress):
            return provider.search_profiles(name, client=self._client())
        def complete(results):
            self.api_player_results.clear()
            for item in results:
                detail = (f"{item['name']} · {item.get('nationality') or 'unknown country'} "
                          f"· born {item.get('birth') or 'unknown'} "
                          f"[ID {item['id']}]")
                self.api_player_results.addItem(detail, item)
            self.api_search_status.setText(
                f'{len(results)} verified provider profiles found. '
                'Choose the correct player ID before requesting career seasons.'
                if results else 'No players found. Check spelling and provider access.')
        self._job('api-football-search', do_search, complete,
                  lambda err: self.api_search_status.setText('Lookup failed: '+err))

    def _download_api_player(self):
        if self.download_running or not self._online():
            return
        provider = self._configure_api_football()
        item = self.api_player_results.currentData()
        if provider is None or not item:
            self.api_search_status.setText('Find and select a real provider player first.')
            return
        response = QMessageBox.question(
            self, 'Download historical player records',
            f"Retrieve all seasons your API-Football plan exposes for "
            f"{item['name']} (provider ID {item['id']})?\n\n"
            'This uses account API calls and stores the returned statistics locally. '
            'Source availability and data/image redistribution rights may be limited.',
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No)
        if response != QMessageBox.StandardButton.Yes:
            return
        self.cancel_event.clear()
        self.download_running=True
        self.provider.setEnabled(False)
        self.cancel_button.setEnabled(True)
        self.progress.setRange(0,0)
        self.progress_text.setText('Fetching verified historical athlete records…')
        def download(progress):
            def report(done,total,msg):
                progress(f'{done} · {total} · {msg}')
            return provider.download_player(self.archive,item['id'],
                                            client=self._client(),progress=report)
        def done(outcome):
            self._download_done(outcome['records'])
            missing=outcome.get('failures',[])
            self.api_search_status.setText(
                f"{outcome['records']} player/league/season records stored. "
                + (f"Unretrieved years: {', '.join(map(str,missing[:12]))}."
                   if missing else 'All returned provider seasons retrieved.'))
            self.sport.setCurrentText('Soccer')
            self.search.setText(item['name'])
            self.navigate('profiles')
        self._job('api-football-player',download,done,self._download_failed)

    def _job(self, key, fn, done, failed=None):
        if key in self.jobs:
            return
        job = Job(fn)
        self.jobs[key] = job
        def complete(result):
            self.jobs.pop(key, None)
            done(result)
        def failure(message):
            self.jobs.pop(key, None)
            (failed or self._job_failed)(message)
        job.signals.done.connect(complete)
        job.signals.failed.connect(failure)
        job.signals.progress.connect(self._progress_message)
        self.pool.start(job)

    def _client(self):
        return HttpClient(cache_dir=Path(self.archive.path).parent / 'http', cancel=self.cancel_event)

    def _discover_seasons(self):
        if not self._online():
            self.progress_text.setText('Offline mode is enabled. Change Preferences before discovering providers.')
            return
        if self.download_running:
            return
        self.cancel_event.clear()
        provider = PROVIDERS[self.provider.currentData()]
        if self.provider.currentData() == 'api_football':
            if self._configure_api_football() is None:
                return
        self.progress_text.setText('Discovering available seasons…')
        self.provider.setEnabled(False)
        def discover(progress):
            client = self._client()
            seasons = provider.available_seasons(client)
            competitions = provider.competitions(client) if hasattr(provider, 'competitions') else []
            return seasons, competitions
        self._job('discover', discover, self._seasons_ready)

    def _seasons_ready(self, seasons):
        self.provider.setEnabled(True)
        seasons, competitions = seasons
        self.competition.clear()
        for item in sorted(competitions, key=lambda r:(r.get('competition_name',''), r.get('season_name',''))):
            self.competition.addItem(str(item.get('competition_name', '')) + ' · ' + str(item.get('season_name','')), item)
        self.download_seasons = sorted(map(str, seasons))
        for combo in (self.range_start, self.range_end):
            combo.clear()
            combo.addItems(self.download_seasons)
        if self.download_seasons:
            self.range_end.setCurrentIndex(len(self.download_seasons)-1)
        self.progress_text.setText(f'{len(self.download_seasons)} season / competition entries are available from this provider. Review the coverage and usage terms above.')

    def _start_download(self, mode):
        if self.download_running:
            return
        if not self._online():
            self.progress_text.setText('Offline mode is enabled. Change Preferences to download history.')
            return
        provider = PROVIDERS[self.provider.currentData()]
        if self.provider.currentData() == 'api_football':
            if self._configure_api_football() is None:
                return
            if mode != 'competition':
                self.api_search_status.setText(
                    'API-Football requires a player or competition. '
                    'Use Find real player or Download competition.')
                return
        competition = self.competition.currentData() if mode == 'competition' else None
        if mode == 'competition' and not competition:
            self._discover_seasons()
            return
        if mode == 'range' and not self.download_seasons:
            self._discover_seasons()
            return
        selected = list(self.download_seasons)
        if mode == 'range':
            a, b = sorted([self.range_start.currentIndex(), self.range_end.currentIndex()])
            selected = selected[a:b+1]
        self.cancel_event.clear()
        self.download_running = True
        self.cancel_button.setEnabled(True)
        self.provider.setEnabled(False)
        self.progress.setRange(0, 0)
        self.progress_text.setText('Connecting to provider. Downloaded chunks will be committed immediately…')
        def run(progress):
            client = self._client()
            def report(*parts, **kwargs):
                progress(' · '.join(str(p) for p in parts) + (' ' + str(kwargs) if kwargs else ''))
            if competition:
                return provider.download_competition(self.archive, competition['competition_id'], competition['season_id'], client=client, cancel=self.cancel_event, progress=report)
            seasons = selected or sorted(map(str, provider.available_seasons(client)))
            if mode == 'latest':
                seasons = seasons[-1:]
            count = provider.download(self.archive, seasons, client=client, cancel=self.cancel_event, progress=report, force=mode == 'latest')
            return count
        self._job('download', run, self._download_done, self._download_failed)

    def _progress_message(self, message):
        import re
        counts = re.match(r'^(\d+) · (\d+) ·', message)
        if counts and int(counts[2]) > 0:
            self.progress.setRange(0, int(counts[2]))
            self.progress.setValue(int(counts[1]))
        self.progress_text.setText(message)
        self.status.setText(message)

    def _download_done(self, count):
        self.download_running = False
        self.provider.setEnabled(True)
        self.cancel_button.setEnabled(False)
        self.progress.setRange(0, 100)
        self.progress.setValue(100)
        self.progress_text.setText(f'Download finished: {count} records processed. Completed seasons stay cached; choose Update latest to refresh a season.')
        self.status.setText(self.progress_text.text())
        self._change_sport()

    def _remove_season(self):
        if self.download_running:
            self.status.setText('Cancel or finish the current download before managing stored seasons.')
            return
        selected = self.coverage_table.selectionModel().selectedRows() if self.coverage_table.selectionModel() else []
        if not selected:
            self.status.setText('Select a season in the coverage table first.')
            return
        record = self.coverage_table.model().frame.iloc[selected[0].row()]
        answer = QMessageBox.question(self, 'Remove downloaded season', f"Remove {record['provider']} / {record['season']} from this computer? You can download it again later.")
        if answer == QMessageBox.StandardButton.Yes:
            self.archive.delete_season(str(record['sport']), str(record['season']), str(record['provider']))
            self._change_sport()
            self.status.setText('Selected downloaded season removed locally.')

    def _download_failed(self, message):
        self.download_running = False
        self.provider.setEnabled(True)
        self.cancel_button.setEnabled(False)
        self.progress.setRange(0, 100)
        self.progress.setValue(0)
        self.progress_text.setText(('Download cancelled. ' if self.cancel_event.is_set() else 'Download stopped. ') + message + '\nCompleted chunks are saved. Resume skips completed seasons.')
        self.status.setText(self.progress_text.text())
        self._change_sport()

    def _job_failed(self, message):
        if not self.download_running:
            self.provider.setEnabled(True)
        self.progress_text.setText(message)
        self.status.setText(message)

    def _cancel_download(self):
        self.cancel_event.set()
        self.progress_text.setText('Cancelling after the current request; completed chunks remain in your archive…')

    def _save_contact(self):
        import re
        contact = self.contact_email.text().strip()
        if contact and not re.fullmatch(r'[^\s@]+@[^\s@]+\.[^\s@]+', contact):
            self.status.setText('Enter a valid contact email, or leave the field blank.')
            return
        self.archive.set_setting('contact_email', contact)
        self.status.setText('Provider contact saved locally.')

    def _offline_changed(self, enabled):
        self.settings.setValue('offline', enabled)
        if enabled:
            self.cancel_event.set()
        self.refresh()

    def _demo_changed(self, enabled):
        self.demo = enabled
        self.setWindowTitle('GameSense — FICTIONAL DEMONSTRATION' if enabled else 'GameSense — Sports Intelligence')
        self._change_sport()

    def _import_file(self):
        path, _ = QFileDialog.getOpenFileName(self, 'Import source-attributed sporting records', '', 'Data files (*.csv *.xlsx *.json)')
        if not path:
            return
        if self.demo:
            self.status.setText('Disable demonstration mode before importing real data.')
            return
        sport = self.sport_name
        def run(progress):
            suffix = Path(path).suffix.lower()
            raw = pd.read_csv(path) if suffix == '.csv' else pd.read_json(path) if suffix == '.json' else pd.read_excel(path)
            prepared, notes = prepare_import(raw, sport)
            clean, report = clean_data(prepared, sport)
            if notes:
                report['normalization'] = '; '.join(notes)
            if clean.empty:
                raise ValueError('No valid records remain after cleaning.')
            self.archive.import_frame(sport, clean, source='User import: ' + Path(path).name)
            return report
        self._job('import', run, lambda report: (self.status.setText('Import saved: ' + str(report)), self._change_sport()))

    def _save_frame(self, frame, suggested):
        path, _ = QFileDialog.getSaveFileName(self, 'Export statistics', suggested, 'CSV (*.csv)')
        if path:
            try:
                frame.to_csv(path, index=False)
                self.status.setText('Exported ' + str(len(frame)) + ' rows to ' + path)
            except OSError as exc:
                self.status.setText('Export failed: ' + str(exc))

    def _export_records(self):
        self._save_frame(self.raw_table.model().frame, 'gamesense_records.csv')

    def _export_leaders(self):
        self._save_frame(getattr(self, 'leader_frame', pd.DataFrame()), 'gamesense_leaderboard.csv')

    def _export_chart(self, chart):
        path, _ = QFileDialog.getSaveFileName(self, 'Export chart', 'gamesense_chart.png', 'PNG (*.png)')
        if path:
            try:
                chart.export_png(path)
                self.status.setText('Chart saved to ' + path)
            except Exception as exc:
                self.status.setText('Chart export failed: ' + str(exc))

    def _export_chart_data(self, chart):
        path, _ = QFileDialog.getSaveFileName(self, 'Export chart data', 'gamesense_chart.csv', 'CSV (*.csv)')
        if path:
            try:
                chart.export_csv(path)
                self.status.setText('Chart data saved to ' + path)
            except Exception as exc:
                self.status.setText('Chart data export failed: ' + str(exc))

    def _export_manifest(self):
        self._save_frame(pd.DataFrame(self.archive.coverage()), 'gamesense_coverage.csv')

    def closeEvent(self, event):
        self.cancel_event.set()
        event.accept()
