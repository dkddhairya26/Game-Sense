"""GameSense 0.3 — polished, native, sport-themed Qt desktop experience."""
from __future__ import annotations

from datetime import date
from pathlib import Path
from time import sleep

import pandas as pd
from PySide6.QtCore import QObject, Qt, QThread, QRectF, QLineF, Signal, Slot
from PySide6.QtGui import QColor, QFont, QLinearGradient, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import (
    QApplication, QComboBox, QFileDialog, QFrame, QGridLayout, QHBoxLayout,
    QHeaderView, QLabel, QLineEdit, QMainWindow, QMessageBox, QPushButton,
    QScrollArea, QSizePolicy, QSpinBox, QStackedWidget, QTableWidget,
    QTableWidgetItem, QVBoxLayout, QWidget,
)
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg
from matplotlib.figure import Figure

from .analytics import SPORTS, clean_data, rankings, recent_form, summary
from .demo import demo_data
from .providers import COVERAGE, SOURCE_URLS, fetch_season
from . import storage

STYLES = {
    "Soccer": {"accent": "#24E6A4", "second": "#0C664C", "label": "PITCH MODE", "title": "FOOTBALL / SOCCER", "icon": "⚽", "tagline": "Every attack tells a story."},
    "NBA": {"accent": "#FF9B57", "second": "#824021", "label": "COURT MODE", "title": "BASKETBALL / NBA", "icon": "🏀", "tagline": "Beyond the box score."},
    "AFL": {"accent": "#F2C66D", "second": "#805B21", "label": "OVAL MODE", "title": "AUSTRALIAN FOOTBALL", "icon": "🏉", "tagline": "Own every contest."},
    "F1": {"accent": "#FF5676", "second": "#781E34", "label": "RACE MODE", "title": "FORMULA 1", "icon": "🏎", "tagline": "Find every millisecond."},
}

STYLE = """
QMainWindow, QWidget {background:#080E19; color:#E9F1FF; font:12px 'Segoe UI',Arial;}
QFrame#sidebar {background:#0E1726; border-right:1px solid #233349;}
QFrame#card, QFrame#graphPanel, QFrame#filterPanel {background:#111E30; border:1px solid #24344C; border-radius:16px;}
QFrame#card:hover {border:1px solid #435975;}
QLabel#brand {font-size:27px; font-weight:900; letter-spacing:1px; color:white;}
QLabel#subtitle {color:#8299B6; font-size:11px;}
QLabel#section {font-size:20px; font-weight:800; color:#F4F8FF;}
QLabel#kpi {font-size:28px; font-weight:800; color:#F8FAFF;}
QLabel#eyebrow {font-size:11px; font-weight:700; color:#93A7BF;}
QLabel#content {color:#BBCCDF; font-size:12px;}
QLabel#status {padding:10px; background:#19283B; border-radius:9px; color:#B3C8E2;}
QPushButton {background:#1A2B43; border:1px solid #2E4565; color:#E8F1FF; border-radius:10px; padding:10px 14px; font-weight:650;}
QPushButton:hover {background:#263C5A; border-color:#54708D;}
QPushButton:disabled {color:#6C7C91; background:#142133;}
QPushButton#nav {border:0; background:transparent; text-align:left; padding:13px 15px; font-size:13px;}
QPushButton#nav:hover {background:#203047;}
QPushButton#nav[active="true"] {background:#263851; color:white; border-left:3px solid #24E6A4;}
QPushButton#sport {border:1px solid transparent; background:transparent; text-align:left; padding:12px 14px;}
QPushButton#sport:hover {background:#192A3F;}
QPushButton#sport[active="true"] {background:#1D2F44; border:1px solid #4A6077;}
QPushButton#primary {background:#24E6A4; border:0; color:#07211C; font-weight:800;}
QComboBox,QLineEdit,QSpinBox {background:#17263A; border:1px solid #34506B; border-radius:9px; padding:9px; color:white; min-height:18px;}
QComboBox QAbstractItemView {background:#182840; color:white; selection-background-color:#355672;}
QTableWidget {background:#101B2C; alternate-background-color:#18263A; color:#ECF2FD; border:1px solid #23344D; border-radius:10px; gridline-color:#263955; selection-background-color:#31536D;}
QHeaderView::section {background:#21334C; border:0; border-bottom:1px solid #42536B; color:#DBE9FB; padding:10px; font-weight:700;}
QScrollBar:vertical {background:#0D1826; width:10px;}
QScrollBar::handle:vertical {background:#30435D; border-radius:5px;}
"""

def label(text="", name=None, wrap=False):
    w = QLabel(str(text))
    if name:
        w.setObjectName(name)
    w.setWordWrap(wrap)
    return w


def panel(title=None):
    box = QFrame()
    box.setObjectName("graphPanel")
    layout = QVBoxLayout(box)
    layout.setContentsMargins(16, 14, 16, 14)
    layout.setSpacing(9)
    if title:
        layout.addWidget(label(title, "eyebrow"))
    return box, layout


class SportHero(QWidget):
    """Paint original vector pitch/court/oval/track art — no licensed imagery."""
    def __init__(self):
        super().__init__()
        self.sport = "Soccer"
        self.setMinimumHeight(185)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

    def set_sport(self, sport):
        self.sport = sport
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        s = STYLES[self.sport]
        rect = self.rect().adjusted(1, 1, -1, -1)
        gradient = QLinearGradient(0, 0, rect.width(), rect.height())
        gradient.setColorAt(0, QColor("#192D43"))
        gradient.setColorAt(.60, QColor(s["second"]))
        gradient.setColorAt(1, QColor("#0D1524"))
        painter.setBrush(gradient)
        painter.setPen(QPen(QColor(s["accent"]), 1))
        painter.drawRoundedRect(rect, 20, 20)
        x, y, w, h = self.width()*.66, 24, self.width()*.29, self.height()-48
        painter.setOpacity(.65)
        painter.setPen(QPen(QColor("#DDEAF5"), 2))
        if self.sport == "Soccer":
            painter.drawRect(QRectF(x, y, w, h))
            painter.drawLine(QLineF(x+w/2, y, x+w/2, y+h))
            painter.drawEllipse(QRectF(x+w*.39, y+h*.28, w*.22, h*.44))
            painter.drawRect(QRectF(x, y+h*.23, w*.17, h*.54))
            painter.drawRect(QRectF(x+w*.83, y+h*.23, w*.17, h*.54))
        elif self.sport == "NBA":
            painter.drawRect(QRectF(x, y, w, h))
            painter.drawLine(QLineF(x+w/2, y, x+w/2, y+h))
            painter.drawEllipse(QRectF(x+w*.40, y+h*.28, w*.20, h*.44))
            for xx in (x+w*.03, x+w*.83):
                painter.drawEllipse(QRectF(xx, y+h*.27, w*.14, h*.46))
            painter.drawRect(QRectF(x, y+h*.32, w*.17, h*.36))
            painter.drawRect(QRectF(x+w*.83, y+h*.32, w*.17, h*.36))
        elif self.sport == "AFL":
            painter.drawEllipse(QRectF(x, y, w, h))
            painter.drawEllipse(QRectF(x+w*.37, y+h*.29, w*.26, h*.42))
            painter.drawLine(QLineF(x+w/2, y, x+w/2, y+h))
            for yy in (.35, .65):
                painter.drawLine(QLineF(x+w*.10, y+h*yy, x+w*.25, y+h*yy))
                painter.drawLine(QLineF(x+w*.75, y+h*yy, x+w*.90, y+h*yy))
        else:
            points = [(0,.65),(.14,.65),(.20,.23),(.43,.23),(.47,.48),(.63,.48),(.71,.15),(.97,.15),(.97,.75),(.79,.75)]
            path = QPainterPath()
            path.moveTo(x+points[0][0]*w, y+points[0][1]*h)
            for a,b in points[1:]:
                path.lineTo(x+a*w,y+b*h)
            path.closeSubpath()
            painter.setPen(QPen(QColor("#FFFFFF"), 5))
            painter.drawPath(path)
            painter.setPen(QPen(QColor(s["accent"]), 2))
            painter.drawPath(path)
        painter.setOpacity(1)
        painter.setPen(QColor(s["accent"]))
        painter.setFont(QFont("Segoe UI", 10, QFont.Weight.Bold))
        painter.drawText(26, 34, s["label"]+"  /  GAMESENSE INTELLIGENCE")
        painter.setPen(QColor("#FFFFFF"))
        painter.setFont(QFont("Segoe UI", 23, QFont.Weight.Bold))
        painter.drawText(25, 89, s["title"])
        painter.setPen(QColor("#D7E5F3"))
        painter.setFont(QFont("Segoe UI", 12))
        painter.drawText(27, 123, s["tagline"])
        painter.setPen(QColor("#B6CBDA"))
        painter.setFont(QFont("Segoe UI", 10))
        painter.drawText(27, 153, "Historical analytics  •  Form  •  Competitor insights")


class Viz(FigureCanvasQTAgg):
    """Native embedded charts with consistent sport palette."""
    def __init__(self, height=275):
        self.figure = Figure(figsize=(6.8, 3), facecolor="#111E30", tight_layout=True)
        super().__init__(self.figure)
        self.setMinimumHeight(height)

    def render(self, df, sport, people, metric, kind):
        self.figure.clear()
        ax = self.figure.add_subplot(111)
        ax.set_facecolor("#111E30")
        ax.tick_params(colors="#A6BAD3", labelsize=9)
        for spine in ax.spines.values():
            spine.set_color("#29405A")
        ax.grid(alpha=.12, color="#9ABBD5", axis="y")
        accent = STYLES[sport]["accent"]
        palette = [accent, "#75AFFF", "#EFC77C", "#CBA8FF"]
        if df.empty or metric not in df:
            ax.text(.5,.5,"No matching statistics yet",color="#B8CADD",ha="center",va="center",transform=ax.transAxes)
        elif kind == "trend":
            for i, person in enumerate(people):
                rows = df[df["competitor"] == person].sort_values("date")
                values = pd.to_numeric(rows[metric], errors="coerce")
                if values.notna().any():
                    ax.plot(rows["date"], values.rolling(5, min_periods=1).mean(),
                            color=palette[i % len(palette)], linewidth=2.7, label=person)
                    ax.scatter(rows["date"].iloc[-1:], values.rolling(5,min_periods=1).mean().iloc[-1:],
                               color=palette[i % len(palette)], s=29)
            if people and ax.lines:
                ax.legend(facecolor="#182B42", edgecolor="#314B65", labelcolor="#EDF4FF", fontsize=9)
            ax.set_title("ROLLING FORM / LAST FIVE RECORDS", color="#D7E7F6", fontsize=10, loc="left", pad=15)
        elif kind == "sport":
            chosen = people[0] if people else None
            subset = df[df["competitor"] == chosen] if chosen else df.iloc[0:0]
            if subset.empty:
                ax.text(.5,.5,"Select a competitor to explore",ha="center",va="center",
                        transform=ax.transAxes,color="#B8CADD")
            elif sport == "Soccer":
                if {"wins","draws","losses"} <= set(subset.columns) and (
                        "record_type" in subset and subset["record_type"].eq("team match").any()):
                    totals = subset[["wins","draws","losses"]].apply(pd.to_numeric,errors="coerce").sum()
                    if totals.sum() > 0:
                        ax.pie(totals, labels=["Wins","Draws","Losses"],
                               colors=[accent,"#6D90B8","#FF7292"], startangle=90,
                               wedgeprops={"width":.34,"edgecolor":"#111E30"},
                               textprops={"color":"#E5EEFC","fontsize":9})
                        ax.text(0,0,str(int(totals.sum()))+"\nmatches",ha="center",va="center",
                                color="white",fontsize=11,fontweight="bold")
                else:
                    metrics = [m for m in ["goals","assists","shots","passes","tackles"] if m in subset]
                    avg = subset[metrics].apply(pd.to_numeric,errors="coerce").mean().dropna()
                    ax.bar(avg.index.astype(str),avg.values,color=accent,alpha=.9)
                    ax.tick_params(axis="x",labelrotation=20)
                ax.set_title("FOOTBALL / FORM & ATTACK",color="#DBE8F8",fontsize=10,loc="left",pad=11)
            elif sport == "F1":
                if {"grid_position","finish_position"} <= set(subset.columns):
                    grid = pd.to_numeric(subset["grid_position"],errors="coerce")
                    finish = pd.to_numeric(subset["finish_position"],errors="coerce")
                    valid = grid.notna() & finish.notna()
                    if valid.any():
                        ax.scatter(grid[valid],finish[valid],s=65,c=accent,alpha=.85,
                                   edgecolors="#F6F9FF",linewidths=.5)
                        mx=max(grid[valid].max(),finish[valid].max(),20)
                        ax.plot([1,mx],[1,mx],color="#778CA6",linestyle="--",alpha=.6)
                        ax.set_xlim(0,mx+1)
                        ax.set_ylim(mx+1,0)
                        ax.set_xlabel("Starting grid",color="#A6BAD3")
                        ax.set_ylabel("Finishing position",color="#A6BAD3")
                        ax.text(.03,.03,"Above the line = positions gained",color="#A8C2D8",
                                transform=ax.transAxes,fontsize=8)
                ax.set_title("RACECRAFT / GRID VS FINISH",color="#DBE8F8",fontsize=10,loc="left",pad=11)
            else:
                fields = (["points","rebounds","assists","steals","blocks"] if sport == "NBA"
                          else ["disposals","marks","tackles","goals","clearances"])
                metrics = [m for m in fields if m in subset]
                avg = subset[metrics].apply(pd.to_numeric,errors="coerce").mean().dropna()
                if len(avg):
                    ax.bar([m.replace("_"," ").title() for m in avg.index],
                           avg.values,color=accent,alpha=.9,width=.55)
                    ax.tick_params(axis="x",labelrotation=19)
                ax.set_title(("COURT / PLAYER STAT LINE" if sport == "NBA"
                              else "OVAL / PLAYER STAT LINE"),
                             color="#DBE8F8",fontsize=10,loc="left",pad=11)
        elif kind == "quality":
            fields = [m for m in df.select_dtypes(include="number").columns if m!="rating"]
            if fields and len(df):
                completeness = df[fields].notna().mean().sort_values().tail(8)
                ax.barh([c.replace("_"," ").title() for c in completeness.index],
                        completeness.values*100,color=accent,alpha=.85,height=.55)
                ax.set_xlim(0,100)
                ax.set_xlabel("Non-missing records (%)",color="#A6BAD3")
            else:
                ax.text(.5,.5,"No numeric stat columns available",ha="center",va="center",
                        transform=ax.transAxes,color="#B8CADD")
            ax.set_title("DATA QUALITY / METRIC COVERAGE",color="#DBE8F8",fontsize=10,loc="left",pad=11)
        elif kind == "breakdown":
            person = people[0] if people else None
            fields = [m for m in SPORTS[sport]["metrics"] if m in df]
            if person and fields:
                row = df[df["competitor"] == person]
                means = row[fields].apply(pd.to_numeric, errors="coerce").mean().dropna().sort_values()
                if len(means):
                    ax.barh([x.replace("_"," ").title() for x in means.index],
                            means.values, color=accent, height=.52)
            ax.set_title("PLAYER / TEAM METRIC PROFILE", color="#D7E7F6",fontsize=10,loc="left",pad=12)
        elif kind == "seasons":
            for i, person in enumerate(people):
                person_df = df[df["competitor"] == person]
                grouped = person_df.groupby("season")[metric].mean().sort_index()
                if len(grouped):
                    xs=list(range(len(grouped)))
                    ax.plot(xs, grouped.values, marker="o", markersize=4,
                            color=palette[i % len(palette)], linewidth=2.4, label=person)
                    skip=max(1, len(xs)//7)
                    ax.set_xticks(xs[::skip])
                    ax.set_xticklabels([str(y) for y in grouped.index[::skip]],rotation=20)
            if ax.lines:
                ax.legend(facecolor="#182B42", edgecolor="#314B65", labelcolor="#EDF4FF", fontsize=8)
            ax.set_title("SEASON-BY-SEASON EVOLUTION", color="#D7E7F6",fontsize=10,loc="left",pad=12)
        elif kind == "leaders":
            ranks = df.groupby("competitor")[metric].mean().dropna().nlargest(8).sort_values()
            if len(ranks):
                bars = ax.barh(ranks.index.astype(str), ranks.values, color=accent, alpha=.9, height=.62)
                for bar in bars:
                    bar.set_alpha(.92)
            ax.set_title("TOP COMPETITORS / AVERAGE "+metric.replace("_"," ").upper(),
                         color="#D7E7F6", fontsize=10, loc="left", pad=12)
        else:
            grouped = df[df["competitor"].isin(people)].groupby("competitor")[metric].mean().reindex(people).dropna()
            if len(grouped):
                ax.barh(grouped.index, grouped.values, color=palette[:len(grouped)], height=.40)
            ax.set_title("DIRECT METRIC COMPARISON", color="#D7E7F6", fontsize=10, loc="left", pad=12)
        self.draw_idle()


class DownloadWorker(QObject):
    """Fetch a small, sequential historical range without blocking the native UI."""
    finished = Signal(object, str)
    failed = Signal(str)
    progress = Signal(str)
    done = Signal()

    def __init__(self, sport, start, end):
        super().__init__()
        self.sport, self.start, self.end = sport, int(start), int(end)

    @Slot()
    def run(self):
        try:
            frames, failed, provenance = [], [], []
            years = list(range(self.start, self.end + 1))
            for i, year in enumerate(years):
                self.progress.emit(f"Downloading {self.sport} {year} ({i + 1}/{len(years)})...")
                try:
                    frame, source = fetch_season(self.sport, year)
                    if frame.empty:
                        raise ValueError("No recorded results found")
                    frame = frame.copy()
                    frame["data_source"] = source
                    frames.append(frame)
                    provenance.append(source)
                except Exception as exc:
                    failed.append(f"{year}: {exc}")
                if i < len(years) - 1:
                    sleep(.75)  # Avoid parallel requests and respect small free API services.
            if not frames:
                raise RuntimeError("No seasons downloaded successfully. " + " | ".join(failed))
            cleaned, report = clean_data(pd.concat(frames, ignore_index=True), self.sport)
            if cleaned.empty:
                raise ValueError("The provider returned no usable historical records.")
            family = provenance[0].split(" · ")[0]
            status = f"{family} · {len(frames)} downloaded seasons"
            if failed:
                status += " · INCOMPLETE: " + "; ".join(failed)
            self.finished.emit(cleaned, status)
        except Exception as exc:
            self.failed.emit(str(exc))
        finally:
            self.done.emit()


class GameSenseWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("GameSense  |  Performance Intelligence")
        self.resize(1470, 920)
        self.setMinimumSize(1060, 725)
        self.setStyleSheet(STYLE)
        self.data, self.sources, self.is_demo = {}, {}, {}
        for sport in SPORTS:
            stored = storage.load(sport)
            if stored is None or stored.empty:
                stored = demo_data(sport)
                self.sources[sport] = "FICTIONAL DEMO DATA · NOT REAL PLAYERS OR RESULTS"
                self.is_demo[sport] = True
            else:
                self.sources[sport] = storage.load_source(sport) or "Imported local dataset · provenance unverified"
                self.is_demo[sport] = False
            self.data[sport], _ = clean_data(stored, sport)
        self.current_sport = "Soccer"
        self.current_page = 0
        self._thread = None
        self.build()
        self.change_sport("Soccer")

    def build(self):
        base = QWidget()
        self.setCentralWidget(base)
        outer = QHBoxLayout(base)
        outer.setContentsMargins(0,0,0,0)
        outer.setSpacing(0)

        side = QFrame()
        side.setObjectName("sidebar")
        side.setFixedWidth(226)
        sl = QVBoxLayout(side)
        sl.setContentsMargins(15,22,15,16)
        sl.setSpacing(7)
        sl.addWidget(label("GAME  SENSE", "brand"))
        sl.addWidget(label("PERFORMANCE INTELLIGENCE", "subtitle"))
        sl.addSpacing(29)
        sl.addWidget(label("YOUR SPORTS", "eyebrow"))
        self.sport_buttons = {}
        for sport in SPORTS:
            btn = QPushButton(f"{STYLES[sport]['icon']}    {STYLES[sport]['title'].title()}")
            btn.setObjectName("sport")
            btn.clicked.connect(lambda checked=False, s=sport: self.change_sport(s))
            sl.addWidget(btn)
            self.sport_buttons[sport] = btn
        sl.addSpacing(23)
        sl.addWidget(label("EXPLORE", "eyebrow"))
        self.nav_buttons = []
        for i, name in enumerate(["◈    Overview", "▤    Leaderboards", "⇄    Head to head", "▦    Data studio"]):
            btn = QPushButton(name)
            btn.setObjectName("nav")
            btn.clicked.connect(lambda checked=False, index=i: self.change_page(index))
            sl.addWidget(btn)
            self.nav_buttons.append(btn)
        sl.addStretch()
        self.sidebar_status = label("", "status", wrap=True)
        sl.addWidget(self.sidebar_status)
        sl.addWidget(label("v0.3  •  DESKTOP EDITION", "subtitle"))
        outer.addWidget(side)

        body = QWidget()
        bl = QVBoxLayout(body)
        bl.setContentsMargins(24,20,24,12)
        bl.setSpacing(12)
        head = QHBoxLayout()
        heading = QVBoxLayout()
        self.page_title = label("The game, decoded.", "section")
        heading.addWidget(self.page_title)
        heading.addWidget(label("Scout players, uncover trends and explore the numbers.", "subtitle"))
        head.addLayout(heading)
        head.addStretch()
        self.import_btn = QPushButton("＋  Import data")
        self.import_btn.clicked.connect(self.import_file)
        head.addWidget(self.import_btn)
        export_btn = QPushButton("↓  Export CSV")
        export_btn.clicked.connect(self.export_file)
        head.addWidget(export_btn)
        bl.addLayout(head)

        self.hero = SportHero()
        bl.addWidget(self.hero)

        kpis = QHBoxLayout()
        kpis.setSpacing(11)
        self.kpi_widgets = []
        for name in ["EVENT RECORDS", "COMPETITORS", "TEAMS", "SEASONS", "AVG RATING"]:
            card = QFrame()
            card.setObjectName("card")
            lay = QVBoxLayout(card)
            lay.setContentsMargins(18,14,18,14)
            lay.addWidget(label(name, "eyebrow"))
            val = label("—", "kpi")
            lay.addWidget(val)
            self.kpi_widgets.append(val)
            kpis.addWidget(card,1)
        bl.addLayout(kpis)

        filters = QFrame()
        filters.setObjectName("filterPanel")
        fl = QHBoxLayout(filters)
        fl.setContentsMargins(14,10,14,10)
        self.season = QComboBox()
        self.season.currentTextChanged.connect(self.refresh_views)
        self.a = QComboBox()
        self.a.setMinimumWidth(155)
        self.a.currentTextChanged.connect(self.refresh_graphs)
        self.b = QComboBox()
        self.b.setMinimumWidth(155)
        self.b.currentTextChanged.connect(self.refresh_graphs)
        self.metric = QComboBox()
        self.metric.setMinimumWidth(130)
        self.metric.currentTextChanged.connect(self.refresh_graphs)
        for title, widget in [("SEASON",self.season),("ATHLETE / TEAM A",self.a),("COMPARE WITH",self.b),("METRIC",self.metric)]:
            group = QVBoxLayout()
            group.setSpacing(3)
            group.addWidget(label(title,"eyebrow"))
            group.addWidget(widget)
            fl.addLayout(group,1)
        bl.addWidget(filters)

        self.pages = QStackedWidget()
        bl.addWidget(self.pages,1)
        # Overview: a large performance timeline and top-eight ranking, plus clear source attribution.
        overview = QWidget()
        ov = QVBoxLayout(overview)
        ov.setContentsMargins(0,0,0,0)
        graphs = QHBoxLayout()
        p1,l1=panel("PERFORMANCE TREND")
        self.trend = Viz(245)
        l1.addWidget(self.trend)
        graphs.addWidget(p1, 3)
        p2,l2=panel("THE LEADERBOARD")
        self.leaders = Viz(245)
        l2.addWidget(self.leaders)
        graphs.addWidget(p2, 2)
        ov.addLayout(graphs)
        extra = QHBoxLayout()
        p4,l4=panel("STATISTICAL BREAKDOWN")
        self.breakdown = Viz(218)
        l4.addWidget(self.breakdown)
        extra.addWidget(p4,2)
        p5,l5=panel("HISTORICAL SEASONS")
        self.seasons_chart = Viz(218)
        l5.addWidget(self.seasons_chart)
        extra.addWidget(p5,3)
        ov.addLayout(extra)
        detail_row = QHBoxLayout()
        p6,l6=panel("SPORT-SPECIFIC INTELLIGENCE")
        self.sport_chart=Viz(220)
        l6.addWidget(self.sport_chart)
        detail_row.addWidget(p6,3)
        p7,l7=panel("RECORD COMPLETENESS")
        self.quality_chart=Viz(220)
        l7.addWidget(self.quality_chart)
        detail_row.addWidget(p7,2)
        ov.addLayout(detail_row)
        insight_card, inslay = panel("GAME INSIGHT / WHAT THE DATA SHOWS")
        self.insight = label("", "content", wrap=True)
        inslay.addWidget(self.insight)
        ov.addWidget(insight_card)
        scroll=QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setWidget(overview)
        self.pages.addWidget(scroll)

        leaderboard = QWidget()
        ll = QVBoxLayout(leaderboard)
        ll.setContentsMargins(0,0,0,0)
        search_row = QHBoxLayout()
        search_row.addWidget(label("PLAYER / TEAM LEADERBOARD","section"))
        search_row.addStretch()
        self.search = QLineEdit()
        self.search.setPlaceholderText("Search competitors...")
        self.search.textChanged.connect(self.fill_rankings)
        search_row.addWidget(self.search)
        ll.addLayout(search_row)
        self.rank_table = QTableWidget()
        self.rank_table.setAlternatingRowColors(True)
        ll.addWidget(self.rank_table)
        self.pages.addWidget(leaderboard)

        comparison = QWidget()
        cl = QVBoxLayout(comparison)
        cl.setContentsMargins(0,0,0,0)
        p3,l3=panel("HEAD TO HEAD / SAME SPORT AND SEASON")
        self.comparison = Viz(255)
        l3.addWidget(self.comparison)
        cl.addWidget(p3,2)
        self.compare_table = QTableWidget()
        cl.addWidget(self.compare_table, 2)
        self.pages.addWidget(comparison)

        data_page = QWidget()
        dl = QVBoxLayout(data_page)
        dl.setContentsMargins(0,0,0,0)
        source_box, sbl = panel("DATA ORIGIN / VERIFIED COVERAGE")
        self.coverage_label = label("", "content", wrap=True)
        sbl.addWidget(self.coverage_label)
        controls = QHBoxLayout()
        controls.addWidget(label("FETCH HISTORICAL SEASON", "eyebrow"))
        self.start_year = QSpinBox()
        self.start_year.setRange(1950, date.today().year)
        self.start_year.setValue(date.today().year-5)
        self.end_year = QSpinBox()
        self.end_year.setRange(1950, date.today().year)
        self.end_year.setValue(date.today().year-1)
        controls.addWidget(label("FROM", "eyebrow"))
        controls.addWidget(self.start_year)
        controls.addWidget(label("TO", "eyebrow"))
        controls.addWidget(self.end_year)
        self.download_btn = QPushButton("↓  Download up to 5 seasons")
        self.download_btn.setObjectName("primary")
        self.download_btn.clicked.connect(self.download_season)
        controls.addWidget(self.download_btn)
        controls.addStretch()
        sbl.addLayout(controls)
        dl.addWidget(source_box)
        dl.addWidget(label("SAVED EVENT / PLAYER RECORDS", "section"))
        self.raw_table = QTableWidget()
        self.raw_table.setAlternatingRowColors(True)
        dl.addWidget(self.raw_table,1)
        self.pages.addWidget(data_page)
        self.data_badge = label("CUSTOM RATINGS ARE EXPERIMENTAL. MISSING STATS ARE NOT ZERO.", "subtitle")
        bl.addWidget(self.data_badge)
        outer.addWidget(body,1)
        self.change_page(0)

    def change_page(self,index):
        self.current_page = index
        self.pages.setCurrentIndex(index)
        titles = ["The game, decoded.", "Rankings & records.", "Head-to-head intelligence.", "Your data command centre."]
        self.page_title.setText(titles[index])
        for i,btn in enumerate(self.nav_buttons):
            btn.setProperty("active", "true" if i==index else "false")
            btn.style().unpolish(btn); btn.style().polish(btn)

    def change_sport(self,sport):
        self.current_sport = sport
        style=STYLES[sport]
        self.hero.set_sport(sport)
        self.import_btn.setStyleSheet(f"QPushButton {{background:{style['accent']}; color:#071622; border:0; font-weight:800}}")
        self.download_btn.setStyleSheet(f"QPushButton {{background:{style['accent']}; color:#071622; border:0; font-weight:800}}")
        for key,btn in self.sport_buttons.items():
            btn.setProperty("active","true" if key==sport else "false")
            btn.style().unpolish(btn); btn.style().polish(btn)
        self.sidebar_status.setText(("●  DEMO DATA" if self.is_demo[sport] else "●  SAVED DATA") +
                                    "\n" + style["label"])
        df=self.data[sport]
        self.season.blockSignals(True)
        prev=self.season.currentText()
        self.season.clear()
        self.season.addItems(["All seasons"]+sorted(df["season"].dropna().astype(str).unique(),reverse=True))
        if prev in [self.season.itemText(i) for i in range(self.season.count())]:
            self.season.setCurrentText(prev)
        self.season.blockSignals(False)
        self._set_metric_items()
        self.coverage_label.setText(
            f"CURRENT DATA: {self.sources[sport]}\n\n"
            f"AVAILABLE CONNECTOR: {COVERAGE[sport][0]}\n"
            f"LIMITATIONS: {COVERAGE[sport][1]}\n"
            f"Source information: {SOURCE_URLS[sport]}\n"
            "Data downloads are on demand; complete historical coverage is not guaranteed."
        )
        self.download_btn.setEnabled(sport!="AFL")
        earliest={"Soccer":1963,"NBA":1996,"AFL":2000,"F1":1950}[sport]
        self.start_year.setMinimum(earliest)
        self.end_year.setMinimum(earliest)
        self.start_year.setValue(max(earliest,date.today().year-5))
        self.end_year.setValue(date.today().year-1)
        self.refresh_views()

    def _set_metric_items(self):
        df=self.data[self.current_sport]
        old=self.metric.currentText()
        numeric = [col for col in df.columns
                   if col not in ("season","date","player_id")
                   and pd.api.types.is_numeric_dtype(df[col])
                   and df[col].notna().any()]
        preferred = ["rating"]+[m for m in SPORTS[self.current_sport]["metrics"] if m in numeric]
        ordered=list(dict.fromkeys([m for m in preferred if m in numeric]+sorted(numeric)))
        self.metric.blockSignals(True)
        self.metric.clear()
        self.metric.addItems(ordered)
        self.metric.setCurrentText(old if old in ordered else ("rating" if "rating" in ordered else ordered[0] if ordered else ""))
        self.metric.blockSignals(False)

    def current(self):
        df=self.data[self.current_sport]
        season=self.season.currentText()
        return df if not season or season=="All seasons" else df.loc[df["season"].astype(str)==season]

    def refresh_views(self):
        if not hasattr(self,"rank_table"):
            return
        df=self.current()
        summary_data=summary(df,self.current_sport)
        values=[summary_data["records"],summary_data["competitors"],summary_data["teams"],
                summary_data["seasons"],summary_data["average_rating"]]
        for widget,value in zip(self.kpi_widgets,values):
            widget.setText("—" if value is None or pd.isna(value) else str(value))
        competitors=sorted(df["competitor"].dropna().astype(str).unique())
        prev=(self.a.currentText(),self.b.currentText())
        for combo,old,idx in [(self.a,prev[0],0),(self.b,prev[1],1)]:
            combo.blockSignals(True)
            combo.clear()
            combo.addItems(competitors)
            if old in competitors: combo.setCurrentText(old)
            elif competitors: combo.setCurrentIndex(min(idx,len(competitors)-1))
            combo.blockSignals(False)
        self.fill_rankings()
        self.fill_table(self.raw_table,df.sort_values("date",ascending=False).head(800))
        self.refresh_graphs()

    def refresh_graphs(self):
        if not hasattr(self,"trend"):
            return
        df=self.current()
        selected=list(dict.fromkeys(x for x in (self.a.currentText(),self.b.currentText()) if x))
        metric=self.metric.currentText()
        self.trend.render(df,self.current_sport,selected,metric,"trend")
        self.leaders.render(df,self.current_sport,selected,metric,"leaders")
        self.comparison.render(df,self.current_sport,selected,metric,"compare")
        self.breakdown.render(df,self.current_sport,selected,metric,"breakdown")
        self.seasons_chart.render(self.data[self.current_sport],self.current_sport,selected,metric,"seasons")
        self.sport_chart.render(df,self.current_sport,selected,metric,"sport")
        self.quality_chart.render(df,self.current_sport,selected,metric,"quality")
        form=", ".join(f"{p}: {recent_form(df,p) if recent_form(df,p) is not None else 'N/A'}"
                       for p in selected)
        kind = ", ".join(sorted(df["record_type"].dropna().astype(str).unique())) if "record_type" in df else "imported records"
        self.insight.setText(
            f"Selected: {', '.join(selected) or 'none'}     •     Recent custom rating: {form or 'N/A'}\n"
            f"Data grain: {kind}    •    Source: {self.sources[self.current_sport]}\n"
            "These ratings are GameSense indicators, not official athlete ratings. "
            "One NBA season row is not an individual game."
        )
        ranks=self.extended_rankings(df)
        compare=ranks[ranks["competitor"].isin(selected)] if not ranks.empty else pd.DataFrame()
        if not compare.empty:
            compare=compare.set_index("competitor").drop(columns=["team"],errors="ignore").T.reset_index().rename(columns={"index":"Statistic"})
        self.fill_table(self.compare_table,compare.round(2) if not compare.empty else pd.DataFrame())
        self.fill_rankings()

    def extended_rankings(self,df):
        """Show EVERY present numeric metric, not only the five core sport ratings."""
        ranked=rankings(df,self.current_sport)
        extras=[name for name in df.columns
                if name not in ranked.columns and name not in ("season","date","player_id")
                and pd.api.types.is_numeric_dtype(df[name])]
        if extras and not df.empty:
            additional=df.groupby("competitor")[extras].mean().reset_index()
            ranked=ranked.merge(additional,on="competitor",how="left")
        return ranked

    def fill_rankings(self):
        if not hasattr(self,"rank_table"):
            return
        df=self.current()
        rank=self.extended_rankings(df)
        term=self.search.text().strip().casefold()
        if term and not rank.empty:
            rank=rank[rank["competitor"].astype(str).str.casefold().str.contains(term,regex=False)]
        metric=self.metric.currentText()
        if metric in rank:
            rank=rank.sort_values(metric,ascending=False,na_position="last")
        self.fill_table(self.rank_table,rank.round(2).head(700))

    @staticmethod
    def fill_table(table,df):
        table.setUpdatesEnabled(False)
        table.setSortingEnabled(False)
        table.clear()
        table.setRowCount(len(df))
        table.setColumnCount(len(df.columns))
        table.setHorizontalHeaderLabels([str(x).replace("_"," ").title() for x in df.columns])
        for i,row in enumerate(df.itertuples(index=False,name=None)):
            for j,v in enumerate(row):
                text="—" if pd.isna(v) else str(v)
                item=QTableWidgetItem(text)
                item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
                table.setItem(i,j,item)
        table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        table.horizontalHeader().setStretchLastSection(True)
        table.setSortingEnabled(True)
        table.setUpdatesEnabled(True)

    def import_file(self):
        path,_=QFileDialog.getOpenFileName(self,"Import sports data","","Sports data (*.csv *.xlsx *.xls *.json)")
        if not path:
            return
        try:
            if path.lower().endswith(".csv"):
                raw=pd.read_csv(path)
            elif path.lower().endswith(".json"):
                raw=pd.read_json(path)
            else:
                raw=pd.read_excel(path)
            sport=self.current_sport
            cleaned,report=clean_data(raw,sport)
            if cleaned.empty: raise ValueError("No valid records after cleaning.")
            self.data[sport]=cleaned
            self.sources[sport]=f"USER IMPORT · {Path(path).name} (licensing and provenance supplied by user)"
            self.is_demo[sport]=False
            storage.save(sport,cleaned,self.sources[sport])
            self.change_sport(sport)
            QMessageBox.information(self,"Data imported","Imported "+str(report["valid_rows"])+" valid records.\n"
                                    +str(report["duplicates_removed"])+" duplicates removed.")
        except Exception as exc:
            QMessageBox.critical(self,"Import failed",str(exc))

    def download_season(self):
        if self._thread is not None:
            return
        sport=self.current_sport
        start,end=self.start_year.value(),self.end_year.value()
        if end<start:
            QMessageBox.warning(self,"Invalid range","The end year must be on or after the start year.")
            return
        if end-start+1>5:
            QMessageBox.information(self,"Use smaller batches",
                "To protect free public data providers, GameSense downloads a maximum of "
                "five seasons per batch. Choose a five-year range, then repeat for more history.")
            return
        self.download_btn.setEnabled(False)
        self.download_btn.setText("Downloading...")
        self.statusBar().showMessage(f"Downloading {sport} {start}–{end} from the data provider...")
        self._thread=QThread()
        self._worker=DownloadWorker(sport,start,end)
        self._worker.moveToThread(self._thread)
        self._thread.started.connect(self._worker.run)
        self._worker.finished.connect(lambda df,source: self.receive_download(sport,df,source))
        self._worker.failed.connect(lambda message: QMessageBox.warning(self,"Download not available",message))
        self._worker.progress.connect(self.statusBar().showMessage)
        self._worker.done.connect(self._thread.quit)
        self._worker.done.connect(self._worker.deleteLater)
        self._thread.finished.connect(self._download_complete)
        self._thread.finished.connect(self._thread.deleteLater)
        self._thread.start()

    def _download_complete(self):
        self._thread=None
        self.download_btn.setText("↓  Download up to 5 seasons")
        self.download_btn.setEnabled(self.current_sport!="AFL")
        self.statusBar().showMessage("Ready",4000)

    def receive_download(self,sport,df,source):
        existing=self.data[sport]
        prev=self.sources[sport]
        # Keep only same-provider data when extending a historical archive.
        family=source.split(" · ")[0]
        if not self.is_demo[sport] and prev.startswith(family):
            merged=pd.concat([existing,df],ignore_index=True)
            subset=["date","season","competitor","team"]
            merged=merged.drop_duplicates(subset=subset,keep="last")
            cleaned,_=clean_data(merged,sport)
        else:
            cleaned=df
        self.data[sport]=cleaned
        self.sources[sport]=family+" · downloaded seasons, cached locally"
        self.is_demo[sport]=False
        storage.save(sport,cleaned,self.sources[sport])
        self.change_sport(sport)
        QMessageBox.information(self,"Historical data ready",
                                f"Loaded {len(df):,} actual records for {sport}.\n"
                                f"Local archive: {len(cleaned):,} records.\n"
                                f"Source: {source}\n\nCoverage is limited to the fields provided.")

    def export_file(self):
        path,_=QFileDialog.getSaveFileName(self,"Export filtered data","gamesense_export.csv","CSV (*.csv)")
        if path:
            try:
                self.current().to_csv(path,index=False)
                QMessageBox.information(self,"Export complete",f"Saved {path}")
            except Exception as exc:
                QMessageBox.critical(self,"Export failed",str(exc))
