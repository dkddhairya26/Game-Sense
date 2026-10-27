"""Native Qt desktop interface; no web server or browser is required."""
from pathlib import Path
import pandas as pd
from PySide6.QtCore import Qt, QRectF
from PySide6.QtGui import QPainter, QColor, QPen, QBrush, QFont
from PySide6.QtWidgets import (QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QGridLayout, QLabel,
    QPushButton, QComboBox, QFileDialog, QMessageBox, QTableWidget, QTableWidgetItem,
    QTabWidget, QFrame, QSplitter, QHeaderView, QSpinBox)
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg
from matplotlib.figure import Figure
from .analytics import SPORTS, clean_data, rankings, recent_form, summary
from .demo import demo_data
from . import storage

DARK = '''
QMainWindow, QWidget {background:#0B1020; color:#E9EFFC; font-family:Segoe UI; font-size:12px;}
QLabel#brand {font-size:26px; font-weight:800; color:#FFFFFF;}
QLabel#subtitle {color:#9AAAC5; font-size:12px;}
QLabel#heading {font-size:19px; font-weight:700;}
QFrame#panel {background:#141E32; border:1px solid #25334F; border-radius:13px;}
QPushButton {background:#263A5E; color:#F5F8FF; border:1px solid #38517A; padding:10px 14px; border-radius:8px; font-weight:600;}
QPushButton:hover {background:#345281;}
QPushButton#primary {background:#00BFA6; color:#041B20; border:0;}
QComboBox,QSpinBox {background:#1C2B45; color:white; border:1px solid #3A4C69; padding:8px; border-radius:7px;}
QTabWidget::pane {border:1px solid #273956; border-radius:9px;}
QTabBar::tab {background:#192740; padding:11px 22px; color:#B8C8E2; border-radius:6px; margin-right:5px;}
QTabBar::tab:selected {background:#00BFA6; color:#071A20;}
QTableWidget {background:#111A2C; alternate-background-color:#18253C; color:#EAF0FB; gridline-color:#263653; border:0;}
QHeaderView::section {background:#233453; color:#EDF4FF; padding:8px; border:0;}
'''

SPORT_STYLES = {
    'Soccer': ('#21D88C', 'PITCH MODE', 'FOOTBALL / SOCCER'),
    'Basketball': ('#FF9D47', 'COURT MODE', 'BASKETBALL / NBA'),
    'AFL': ('#F5C55B', 'OVAL MODE', 'AUSTRALIAN FOOTBALL'),
    'Formula 1': ('#FF5569', 'RACE MODE', 'FORMULA 1'),
}

class SportBanner(QWidget):
    """Sport-specific vector artwork; no external assets or licensing required."""
    def __init__(self):
        super().__init__()
        self.sport = 'Soccer'
        self.setMinimumHeight(116)

    def set_sport(self, sport):
        self.sport = sport
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        rect = self.rect().adjusted(2, 2, -2, -2)
        painter.setBrush(QColor('#141E32'))
        painter.setPen(QPen(QColor('#29374D'), 1))
        painter.drawRoundedRect(rect, 16, 16)
        accent, mode, title = SPORT_STYLES.get(self.sport, SPORT_STYLES['Soccer'])
        color = QColor(accent)
        painter.setPen(QPen(color, 2))
        x, y, w, h = rect.width() * .65, 14, rect.width() * .31, rect.height() - 28
        if self.sport == 'Soccer':
            painter.drawRect(QRectF(x, y, w, h))
            painter.drawLine(int(x+w/2), y, int(x+w/2), int(y+h))
            painter.drawEllipse(QRectF(x+w*.39, y+h*.3, w*.22, h*.4))
            painter.drawRect(QRectF(x, y+h*.27, w*.15, h*.46))
            painter.drawRect(QRectF(x+w*.85, y+h*.27, w*.15, h*.46))
        elif self.sport == 'Basketball':
            painter.drawRect(QRectF(x, y, w, h))
            painter.drawEllipse(QRectF(x+w*.39, y+h*.22, w*.22, h*.56))
            painter.drawLine(int(x+w/2), y, int(x+w/2), int(y+h))
            painter.drawEllipse(QRectF(x+w*.05, y+h*.31, w*.15, h*.38))
            painter.drawEllipse(QRectF(x+w*.80, y+h*.31, w*.15, h*.38))
        elif self.sport == 'AFL':
            painter.drawEllipse(QRectF(x, y, w, h))
            painter.drawEllipse(QRectF(x+w*.36, y+h*.30, w*.28, h*.4))
            painter.drawLine(int(x+w/2), y, int(x+w/2), int(y+h))
        else:
            points = [(x,y+h*.7),(x+w*.2,y+h*.7),(x+w*.24,y+h*.3),(x+w*.49,y+h*.3),(x+w*.56,y+h*.5),(x+w*.74,y+h*.5),(x+w*.80,y+h*.16),(x+w,y+h*.16)]
            for a,b in zip(points, points[1:]): painter.drawLine(int(a[0]),int(a[1]),int(b[0]),int(b[1]))
        painter.setPen(QColor('#F5F8FF'))
        painter.setFont(QFont('Segoe UI', 18, QFont.Weight.Bold))
        painter.drawText(24, 43, title)
        painter.setPen(color)
        painter.setFont(QFont('Segoe UI', 11, QFont.Weight.Bold))
        painter.drawText(25, 70, mode + '  /  PERFORMANCE INTELLIGENCE')
        painter.setPen(QColor('#A4B4CD'))
        painter.setFont(QFont('Segoe UI', 9))
        painter.drawText(25, 94, 'Explore  •  Compare  •  Analyse')
        painter.end()

def text_label(value, name=None):
    label = QLabel(value)
    if name: label.setObjectName(name)
    return label

class Graph(FigureCanvasQTAgg):
    def __init__(self):
        self.figure = Figure(figsize=(8, 4), facecolor='#141E32', tight_layout=True)
        super().__init__(self.figure)
        self.setMinimumHeight(250)
    def plot(self, df, sport, people):
        self.figure.clear()
        ax = self.figure.add_subplot(111)
        ax.set_facecolor('#141E32')
        colors = [SPORT_STYLES.get(sport, SPORT_STYLES['Soccer'])[0], '#7AA8FF', '#FFB454']
        for i, person in enumerate(people):
            rows = df[df['competitor'] == person].sort_values('date')
            if not rows.empty:
                ax.plot(rows['date'], rows['rating'].rolling(5, min_periods=1).mean(), label=person, color=colors[i % len(colors)], linewidth=2)
        ax.set_title(f'{sport} • Rolling 5-event performance rating', color='white', fontsize=12)
        ax.set_ylabel('Custom rating (not official)', color='#BAC9E2')
        ax.tick_params(colors='#A9BBD7')
        ax.grid(alpha=.15)
        for spine in ax.spines.values(): spine.set_color('#344763')
        if people: ax.legend(facecolor='#18253C', labelcolor='white', fontsize=9)
        self.draw_idle()

class GameSenseWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle('GameSense | Sports Performance Intelligence')
        self.resize(1280, 820)
        self.setStyleSheet(DARK)
        self.data = {}
        self.sources = {}
        for sport in SPORTS:
            saved = storage.load(sport)
            if saved is not None and not saved.empty:
                self.data[sport], _ = clean_data(saved, sport)
                self.sources[sport] = 'Local SQLite database (imported data)'
            else:
                self.data[sport], _ = clean_data(demo_data(sport), sport)
                self.sources[sport] = 'FICTIONAL DEMO DATA — not real sporting results'
        self.build()
        self.refresh()

    def build(self):
        root = QWidget(); self.setCentralWidget(root)
        main = QVBoxLayout(root); main.setContentsMargins(22, 18, 22, 18); main.setSpacing(15)
        top = QHBoxLayout()
        brand = QVBoxLayout(); brand.addWidget(text_label('GAMESENSE', 'brand')); brand.addWidget(text_label('SPORTS PERFORMANCE INTELLIGENCE', 'subtitle'))
        top.addLayout(brand); top.addStretch()
        top.addWidget(text_label('SPORT'))
        self.sport = QComboBox(); self.sport.addItems(SPORTS); self.sport.currentTextChanged.connect(self.refresh); top.addWidget(self.sport)
        self.import_btn = QPushButton('Import CSV / Excel'); self.import_btn.setObjectName('primary'); self.import_btn.clicked.connect(self.import_file); top.addWidget(self.import_btn)
        export_btn = QPushButton('Export CSV'); export_btn.clicked.connect(self.export_file); top.addWidget(export_btn)
        main.addLayout(top)
        self.banner = SportBanner(); main.addWidget(self.banner)
        self.source = text_label('', 'subtitle'); main.addWidget(self.source)
        self.cards = QHBoxLayout(); self.card_values = []
        for name in ['RECORDS', 'COMPETITORS', 'TEAMS', 'SEASONS', 'AVG RATING']:
            panel = QFrame(); panel.setObjectName('panel'); layout = QVBoxLayout(panel)
            caption = text_label(name, 'subtitle'); layout.addWidget(caption)
            val = text_label('—', 'heading'); layout.addWidget(val)
            self.card_values.append(val); self.cards.addWidget(panel)
        main.addLayout(self.cards)
        filters = QHBoxLayout()
        filters.addWidget(text_label('Season'))
        self.season = QComboBox(); self.season.currentTextChanged.connect(self.refresh_views); filters.addWidget(self.season)
        filters.addWidget(text_label('Competitor A'))
        self.person_a = QComboBox(); self.person_a.currentTextChanged.connect(self.refresh_views); filters.addWidget(self.person_a)
        filters.addWidget(text_label('Competitor B'))
        self.person_b = QComboBox(); self.person_b.currentTextChanged.connect(self.refresh_views); filters.addWidget(self.person_b)
        filters.addStretch(); main.addLayout(filters)
        self.tabs = QTabWidget(); main.addWidget(self.tabs, 1)
        overview = QWidget(); ov = QVBoxLayout(overview)
        self.graph = Graph(); ov.addWidget(self.graph)
        self.insight = text_label('', 'subtitle'); self.insight.setWordWrap(True); ov.addWidget(self.insight)
        self.tabs.addTab(overview, 'Dashboard & Trends')
        rank_page = QWidget(); rlayout = QVBoxLayout(rank_page)
        rlayout.addWidget(text_label('COMPETITOR RANKINGS', 'heading'))
        self.rank_table = QTableWidget(); self.rank_table.setAlternatingRowColors(True)
        rlayout.addWidget(self.rank_table); self.tabs.addTab(rank_page, 'Rankings')
        compare_page = QWidget(); clayout = QVBoxLayout(compare_page)
        clayout.addWidget(text_label('HEAD-TO-HEAD COMPARISON', 'heading'))
        self.compare_table = QTableWidget(); clayout.addWidget(self.compare_table)
        self.tabs.addTab(compare_page, 'Compare')
        raw_page = QWidget(); dlayout = QVBoxLayout(raw_page)
        dlayout.addWidget(text_label('VALIDATED EVENT RECORDS', 'heading'))
        self.raw_table = QTableWidget(); self.raw_table.setAlternatingRowColors(True)
        dlayout.addWidget(self.raw_table); self.tabs.addTab(raw_page, 'Data Explorer')
        main.addWidget(text_label('Data is sourced from your imports or fictional offline demo records. Custom ratings are experimental and not official statistics.', 'subtitle'))

    def current(self):
        df = self.data[self.sport.currentText()]
        season = self.season.currentText()
        return df if not season or season == 'All seasons' else df[df['season'].astype(str) == season]

    def refresh(self):
        if not hasattr(self, 'season'): return
        sport = self.sport.currentText(); df = self.data[sport]
        accent = SPORT_STYLES.get(sport, SPORT_STYLES['Soccer'])[0]
        self.banner.set_sport(sport)
        self.import_btn.setStyleSheet(f'background:{accent}; color:#09111F; border:0;')
        self.tabs.setStyleSheet(f'QTabBar::tab:selected {{background:{accent};color:#09111F;}}')
        self.source.setText('DATA SOURCE: ' + self.sources[sport])
        self.season.blockSignals(True); self.season.clear()
        self.season.addItems(['All seasons'] + sorted(df['season'].astype(str).unique().tolist(), reverse=True))
        self.season.blockSignals(False)
        self.refresh_views()

    def refresh_views(self):
        if not hasattr(self, 'person_a') or not self.sport.currentText(): return
        df = self.current(); sport = self.sport.currentText()
        stats = summary(df, sport)
        for label, value in zip(self.card_values, [stats['records'], stats['competitors'], stats['teams'], stats['seasons'], stats['average_rating']]):
            label.setText(str(value) if value is not None else 'N/A')
        people = sorted(df['competitor'].dropna().unique().tolist())
        previous_a, previous_b = self.person_a.currentText(), self.person_b.currentText()
        for combo, old, fallback in [(self.person_a, previous_a, 0), (self.person_b, previous_b, 1)]:
            combo.blockSignals(True); combo.clear(); combo.addItems(people)
            if old in people: combo.setCurrentText(old)
            elif people: combo.setCurrentIndex(min(fallback, len(people)-1))
            combo.blockSignals(False)
        a, b = self.person_a.currentText(), self.person_b.currentText()
        selected = list(dict.fromkeys([p for p in [a, b] if p]))
        self.graph.plot(df, sport, selected)
        form = ', '.join(f'{p}: {recent_form(df, p) if recent_form(df,p) is not None else "N/A"}' for p in selected)
        self.insight.setText('Recent form (last 5 recorded events): ' + form + '. Higher rating is better under the illustrative GameSense formula.')
        rank = rankings(df, sport)
        self.fill_table(self.rank_table, rank.round(2), limit=500)
        compare = rank[rank['competitor'].isin(selected)].set_index('competitor') if not rank.empty else pd.DataFrame()
        if not compare.empty:
            compare = compare.drop(columns=['team'], errors='ignore').T.reset_index().rename(columns={'index':'Statistic'})
        self.fill_table(self.compare_table, compare.round(2) if not compare.empty else pd.DataFrame())
        self.fill_table(self.raw_table, df.sort_values('date', ascending=False).head(1500))

    def fill_table(self, table, df, limit=1000):
        df = df.head(limit)
        table.setSortingEnabled(False); table.clear()
        table.setRowCount(len(df)); table.setColumnCount(len(df.columns))
        table.setHorizontalHeaderLabels([str(c).replace('_', ' ').title() for c in df.columns])
        for i, row in enumerate(df.itertuples(index=False, name=None)):
            for j, value in enumerate(row):
                item = QTableWidgetItem('—' if pd.isna(value) else str(value))
                item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
                table.setItem(i, j, item)
        table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        table.setSortingEnabled(True)

    def import_file(self):
        path, _ = QFileDialog.getOpenFileName(self, 'Import sport records', '', 'Data files (*.csv *.xlsx *.xls)')
        if not path: return
        try:
            raw = pd.read_csv(path) if path.lower().endswith('.csv') else pd.read_excel(path)
            sport = self.sport.currentText(); cleaned, report = clean_data(raw, sport)
            if cleaned.empty: raise ValueError('No valid rows after cleaning.')
            self.data[sport] = cleaned
            self.sources[sport] = f'Imported: {Path(path).name} (saved locally)'
            storage.save(sport, cleaned)
            self.refresh()
            QMessageBox.information(self, 'Import successful', '\n'.join(f'{k}: {v}' for k, v in report.items()))
        except Exception as exc:
            QMessageBox.critical(self, 'Import failed', str(exc))

    def export_file(self):
        path, _ = QFileDialog.getSaveFileName(self, 'Export filtered data', 'gamesense_export.csv', 'CSV (*.csv)')
        if path:
            try:
                self.current().to_csv(path, index=False)
                QMessageBox.information(self, 'Export complete', f'Saved to {path}')
            except Exception as exc:
                QMessageBox.critical(self, 'Export failed', str(exc))
