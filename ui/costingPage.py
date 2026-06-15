from __future__ import annotations

import os
import subprocess
import tempfile
from datetime import datetime

import pandas as pd
from PySide6.QtCore import QEvent, Qt, Signal, QTimer, QSettings
from PySide6.QtGui import (
    QDoubleValidator, QFont, QColor,
    QStandardItem, QStandardItemModel,
    QGuiApplication, QTextDocument,
)
from PySide6.QtPrintSupport import QPrinter
from PySide6.QtWidgets import (
    QAbstractItemView, QAbstractSpinBox, QCheckBox, QComboBox, QDialog,
    QDialogButtonBox, QFileDialog, QFormLayout, QFrame, QGroupBox,
    QHBoxLayout, QHeaderView, QLabel, QLineEdit, QMessageBox, QPushButton,
    QSizePolicy, QSplitter, QTabWidget, QTableWidget,
    QTableWidgetItem, QVBoxLayout, QWidget, QDoubleSpinBox,
)
from PySide6.QtGui import QPageLayout, QPageSize
from PySide6.QtCore import QMarginsF, QSizeF, QRectF

from ui.costingStyle import (
    C_BG, C_SURFACE, C_SURFACE_HI, C_SURFACE_ALT,
    C_TOPBAR, C_BORDER, C_BORDER_DARK,
    C_WHITE, C_WHITE_MUT, C_WHITE_DIM, C_GHOST, C_GOLD,
    BTN_PRIMARY, BTN_SUCCESS, BTN_DANGER, BTN_OUTLINE,
    CARD_STYLE, TABLE_STYLE, FIELD_STYLE, COMBO_STYLE,
    FONT_UI,
    SEARCH_STYLE, CHECK_STYLE, COUNT_LABEL_STYLE,
    BTN_PRIMARY_STYLE, BTN_OUTLINE_STYLE, STEPPER_SPIN_STYLE, STEPPER_BTN_STYLE,
)
from ui.Helpers.helpers import _lbl, _ti
from common import get_bridge_path
from Managers.costing_manager import CostingManager, UNIT_TYPES, UNIT_TYPE_LABELS

try:
    import matplotlib
    matplotlib.use("QtAgg")
    from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas
    from matplotlib.figure import Figure
    import matplotlib.dates as mdates
    import matplotlib.ticker as mticker
    _MPL = True
except ImportError:
    _MPL = False

def _get_screen_rect():
    screen = QGuiApplication.primaryScreen()
    return screen.availableGeometry() if screen else None


def _fit_widget_to_screen(window: QWidget):
    if not window or isinstance(window, QDialog):
        _center_on_screen(window)
        return
    screen = QGuiApplication.screenAt(window.geometry().center())
    if not screen:
        screen = QGuiApplication.primaryScreen()
    if screen:
        window.showMaximized()


def _center_on_screen(widget: QWidget):
    screen = QGuiApplication.primaryScreen()
    if not screen:
        return
    sg = screen.availableGeometry()
    widget.move(
        sg.center().x() - widget.width() // 2,
        sg.center().y() - widget.height() // 2,
    )


def _responsive_splitter_sizes(splitter: QSplitter, ratios: list[float]) -> list[int]:
    total = (
        splitter.width()
        if splitter.orientation() == Qt.Orientation.Horizontal
        else splitter.height()
    )
    if total < 100:
        rect = _get_screen_rect()
        if rect:
            total = (
                rect.width() * 0.85
                if splitter.orientation() == Qt.Orientation.Horizontal
                else rect.height() * 0.75
            )
        else:
            total = 960
    return [int(r * total) for r in ratios]

def _lbl(text: str, size: int = 12, bold: bool = False,
         color: str = C_WHITE_MUT) -> QLabel:
    lbl = QLabel(text)
    f = QFont(FONT_UI, size)
    f.setBold(bold)
    lbl.setFont(f)
    lbl.setStyleSheet(f"color: {color}; background: transparent;")
    return lbl


def _field(placeholder: str = "", width: int = 0) -> QLineEdit:
    e = QLineEdit()
    e.setPlaceholderText(placeholder)
    e.setStyleSheet(FIELD_STYLE)
    e.setMinimumHeight(30)
    if width:
        e.setFixedWidth(width)
    return e


def _combo(items: list[str] = ()) -> QComboBox:
    c = QComboBox()
    c.setStyleSheet(COMBO_STYLE)
    c.setMinimumHeight(30)
    c.addItems(items)
    c.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
    c.wheelEvent = lambda e: e.ignore()
    return c


def _btn(text: str, style: str = BTN_PRIMARY, width: int = 0) -> QPushButton:
    b = QPushButton(text)
    b.setStyleSheet(style)
    b.setMinimumHeight(30)
    if width:
        b.setFixedWidth(width)
    return b


def _divider() -> QFrame:
    f = QFrame()
    f.setFrameShape(QFrame.Shape.HLine)
    f.setStyleSheet(f"color: {C_BORDER}; background: {C_BORDER}; max-height: 1px;")
    return f


def _card(title: str) -> tuple[QFrame, QVBoxLayout]:
    frame = QFrame()
    frame.setStyleSheet(CARD_STYLE)
    vl = QVBoxLayout(frame)
    vl.setContentsMargins(10, 8, 10, 8)
    vl.setSpacing(6)
    hdr = _lbl(title, size=9, bold=True, color=C_GOLD)
    hdr.setStyleSheet(f"color: {C_GOLD}; letter-spacing: 2px; background: transparent;")
    vl.addWidget(hdr)
    vl.addWidget(_divider())
    return frame, vl


def _topbar(title: str, back_cb) -> QFrame:
    bar = QFrame()
    bar.setFixedHeight(46)
    bar.setStyleSheet(
        f"QFrame {{ background: {C_TOPBAR}; border: none; "
        f"border-bottom: 1px solid {C_BORDER}; }}"
    )
    hl = QHBoxLayout(bar)
    hl.setContentsMargins(14, 0, 14, 0)
    back = QPushButton("← Home")
    back.setStyleSheet(BTN_OUTLINE)
    back.setFixedHeight(26)
    back.setFixedWidth(76)
    back.clicked.connect(back_cb)
    hl.addWidget(back)
    hl.addSpacing(10)
    t = _lbl(title, size=12, bold=True, color=C_WHITE)
    hl.addWidget(t)
    hl.addStretch()
    return bar


def _warn(parent: QWidget, msg: str) -> None:
    QMessageBox.warning(parent, "Warning", msg)


def _make_table(cols: list[str]) -> QTableWidget:
    t = QTableWidget()
    t.setColumnCount(len(cols))
    t.setHorizontalHeaderLabels(cols)
    t.setStyleSheet(TABLE_STYLE)
    t.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
    t.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
    t.verticalHeader().setVisible(False)
    t.setAlternatingRowColors(True)
    t.verticalHeader().setDefaultSectionSize(26)
    t.horizontalHeader().setMinimumHeight(26)
    t.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
    t.horizontalHeader().setStretchLastSection(True)
    t.setVerticalScrollMode(QAbstractItemView.ScrollMode.ScrollPerPixel)
    return t


def _ti(text: str,
        align=Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft,
        color: str | None = None) -> QTableWidgetItem:
    item = QTableWidgetItem(str(text))
    item.setTextAlignment(align)
    item.setFlags(Qt.ItemFlag.ItemIsSelectable | Qt.ItemFlag.ItemIsEnabled)
    if color:
        item.setForeground(QColor(color))
    return item


def _sub_tab_style() -> str:
    return f"""
        QTabWidget::pane {{
            background: {C_BG};
            border: 1px solid {C_BORDER};
            border-top: none;
        }}
        QTabBar::tab {{
            background: {C_SURFACE};
            color: {C_WHITE_MUT};
            padding: 5px 14px;
            font-size: 11px;
            font-weight: 500;
            border: 1px solid {C_BORDER};
            border-bottom: none;
            margin-right: 2px;
        }}
        QTabBar::tab:selected {{
            color: {C_GOLD};
            background: {C_BG};
            border-bottom: 1px solid {C_BG};
        }}
        QTabBar::tab:hover {{
            background: {C_SURFACE_HI};
        }}
    """

class QtySpinBox(QDoubleSpinBox):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setRange(0.01, 999_999.0)
        self.setDecimals(2)
        self.setValue(1.00)
        self.setButtonSymbols(QAbstractSpinBox.ButtonSymbols.NoButtons)
        self.setMinimumHeight(30)
        self.setMinimumWidth(80)

    def wheelEvent(self, event):
        event.ignore()


class ChartWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._layout = QVBoxLayout(self)
        self._layout.setContentsMargins(0, 0, 0, 0)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

        if _MPL:
            self.figure = Figure(facecolor="#1A1A2A")
            self.canvas = FigureCanvas(self.figure)
            self.canvas.setStyleSheet("background: #1A1A2A;")
            self.canvas.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
            self._layout.addWidget(self.canvas)
        else:
            msg = _lbl("Install matplotlib:\n  pip install matplotlib", 11, color=C_WHITE_DIM)
            msg.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self._layout.addWidget(msg)

    def clear(self):
        if _MPL:
            self.figure.clear()
            self.canvas.draw()

    def _style_ax(self, ax):
        ax.set_facecolor("#1E1E30")
        ax.tick_params(colors=C_WHITE_MUT, labelsize=7)
        for spine in ("bottom", "left"):
            ax.spines[spine].set_color(C_BORDER_DARK)
        ax.spines["top"].set_visible(False)
        ax.spines["right"].set_visible(False)
        ax.grid(True, color=C_BORDER, alpha=0.4, linestyle="--", linewidth=0.5)
        ax.yaxis.set_major_formatter(mticker.FuncFormatter(lambda x, _: f"₹{x:,.0f}"))

    def _fmt_x_dates(self, ax):
        try:
            ax.xaxis.set_major_formatter(mdates.DateFormatter("%d %b %y"))
            ax.xaxis.set_major_locator(mdates.AutoDateLocator())
        except Exception:
            pass
        for lbl in ax.get_xticklabels():
            lbl.set_rotation(30)
            lbl.set_ha("right")
            lbl.set_fontsize(7)
            lbl.set_color(C_WHITE_MUT)

    def plot_cost_timeline(self, df: pd.DataFrame, product_name: str):
        if not _MPL or df.empty:
            return
        self.figure.clear()
        ax = self.figure.add_subplot(111)
        self._style_ax(ax)
        dates    = df["SnapshotAt"].dt.to_pydatetime()
        cost_col = "FinalCost" if "FinalCost" in df.columns else "TotalCost"
        ax.plot(dates, df[cost_col],    "o-", color="#E07070", lw=2, label="Final Cost",  markersize=4)
        ax.plot(dates, df["SalePrice"], "o-", color="#7AE07A", lw=2, label="Sale Price", markersize=4)
        ax.fill_between(dates, df[cost_col], df["SalePrice"],
                        where=df["SalePrice"] >= df[cost_col], alpha=0.15, color="#7AE07A")
        ax.fill_between(dates, df[cost_col], df["SalePrice"],
                        where=df["SalePrice"] <  df[cost_col], alpha=0.15, color="#E07070")
        ax.set_title(f"Cost vs Price — {product_name}", color=C_WHITE, pad=8, fontsize=10)
        ax.set_ylabel("₹ Amount", color=C_WHITE_MUT, fontsize=8)
        ax.legend(facecolor="#1A1A2A", edgecolor=C_BORDER, labelcolor=C_WHITE_MUT, fontsize=7)
        self._fmt_x_dates(ax)
        self.figure.tight_layout()
        self.canvas.draw()

    def plot_cost_stack(self, df: pd.DataFrame, product_name: str):
        if not _MPL or df.empty:
            return
        self.figure.clear()
        ax = self.figure.add_subplot(111)
        self._style_ax(ax)
        dates  = df["SnapshotAt"].dt.to_pydatetime()
        stacks = [df["RawMaterialCost"], df["TotalCustomCost"]]
        labels = ["Raw Material", "Overhead"]
        colors = ["#C9A84C", "#5A7AC9"]
        if "WarrantyCost" in df.columns:
            stacks.append(df["WarrantyCost"]); labels.append("Warranty"); colors.append("#C9604C")
        if "LabourCost" in df.columns:
            stacks.append(df["LabourCost"]);   labels.append("Labour");   colors.append("#7A5AC9")
        ax.stackplot(dates, *stacks, labels=labels, colors=colors, alpha=0.80)
        ax.plot(dates, df["SalePrice"], "--", color="#7AE07A", lw=1.5, label="Sale Price")
        ax.set_title(f"Cost Stack — {product_name}", color=C_WHITE, pad=8, fontsize=10)
        ax.set_ylabel("₹ Amount", color=C_WHITE_MUT, fontsize=8)
        ax.legend(facecolor="#1A1A2A", edgecolor=C_BORDER, labelcolor=C_WHITE_MUT, fontsize=7)
        self._fmt_x_dates(ax)
        self.figure.tight_layout()
        self.canvas.draw()

    def plot_material_trend(self, df: pd.DataFrame, mat_name: str):
        if not _MPL or df.empty:
            return
        self.figure.clear()
        ax    = self.figure.add_subplot(111)
        self._style_ax(ax)
        dates = df["ChangedAt"].dt.to_pydatetime()
        ax.step(dates, df["NewCost"].values, where="post", color=C_GOLD, lw=2)
        ax.scatter(dates, df["NewCost"].values, color=C_GOLD, zorder=5, s=30)
        ax.set_title(f"Cost History — {mat_name}", color=C_WHITE, pad=8, fontsize=10)
        ax.set_ylabel("₹ Cost per Unit", color=C_WHITE_MUT, fontsize=8)
        self._fmt_x_dates(ax)
        self.figure.tight_layout()
        self.canvas.draw()

    def plot_margin_bars(self, df: pd.DataFrame, product_name: str):
        if not _MPL or df.empty:
            return
        self.figure.clear()
        ax      = self.figure.add_subplot(111)
        self._style_ax(ax)
        x       = range(len(df))
        margins = df["MarginPct"].values
        colors  = ["#7AE07A" if m >= 0 else "#E07070" for m in margins]
        bars    = ax.bar(x, margins, color=colors, width=0.6, zorder=2)
        ax.axhline(0, color=C_WHITE_DIM, lw=0.8, ls="--")
        labels  = [str(d)[:10] for d in df["SnapshotAt"]]
        ax.set_xticks(list(x))
        ax.set_xticklabels(labels, rotation=30, ha="right", fontsize=7, color=C_WHITE_MUT)
        ax.set_title(f"Margin % Over Time — {product_name}", color=C_WHITE, pad=8, fontsize=10)
        ax.set_ylabel("Margin %", color=C_WHITE_MUT, fontsize=8)
        for bar, val in zip(bars, margins):
            ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 0.4,
                    f"{val:.1f}%", ha="center", va="bottom", fontsize=7, color=C_WHITE_MUT)
        self.figure.tight_layout()
        self.canvas.draw()

    def save_to_pdf(self, path: str) -> bool:
        if not _MPL:
            return False
        try:
            self.figure.savefig(path, format="pdf", facecolor=self.figure.get_facecolor())
            return True
        except Exception:
            return False


class MultiMaterialSelectorWidget(QWidget):
    materials_add_requested = Signal(list)

    def __init__(self, cm: CostingManager, parent=None):
        super().__init__(parent)
        self._cm = cm
        self._rows: list[tuple] = []

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        top_wrap = QWidget()
        top_wrap.setStyleSheet("background: #222222; border-bottom: 1px solid #2e2e2e;")
        top = QHBoxLayout(top_wrap)
        top.setContentsMargins(6, 5, 6, 5)
        top.setSpacing(5)

        self._search = QLineEdit()
        self._search.setPlaceholderText("🔍  Search materials…")
        self._search.setStyleSheet(SEARCH_STYLE)
        self._search.setFixedHeight(28)
        self._search.textChanged.connect(self._filter_rows)

        sel_all  = QPushButton("Select All")
        sel_all.setStyleSheet(BTN_OUTLINE_STYLE)
        sel_all.setFixedSize(76, 28)
        sel_none = QPushButton("Clear")
        sel_none.setStyleSheet(BTN_OUTLINE_STYLE)
        sel_none.setFixedSize(50, 28)
        sel_all.clicked.connect(self._select_all)
        sel_none.clicked.connect(self._select_none)

        top.addWidget(self._search, 1)
        top.addWidget(sel_all)
        top.addWidget(sel_none)
        layout.addWidget(top_wrap)

        self._table = QTableWidget()
        self._table.setColumnCount(6)
        self._table.setHorizontalHeaderLabels(["", "Material Name", "Type", "Unit", "₹/Unit", "Qty"])
        self._table.setStyleSheet(TABLE_STYLE)
        self._table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self._table.setSelectionMode(QAbstractItemView.SelectionMode.NoSelection)
        self._table.verticalHeader().setVisible(False)
        self._table.setAlternatingRowColors(True)
        self._table.setVerticalScrollMode(QAbstractItemView.ScrollMode.ScrollPerPixel)
        self._table.verticalHeader().setDefaultSectionSize(36)
        self._table.setMinimumHeight(150)
        self._table.setShowGrid(False)

        hh = self._table.horizontalHeader()
        hh.setSectionResizeMode(0, QHeaderView.ResizeMode.Fixed)
        self._table.setColumnWidth(0, 40)
        hh.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        hh.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        hh.setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        hh.setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents)
        hh.setSectionResizeMode(5, QHeaderView.ResizeMode.Fixed)
        self._table.setColumnWidth(5, 120)
        layout.addWidget(self._table, 1)

        bottom_wrap = QWidget()
        bottom_wrap.setStyleSheet("background: #252525; border-top: 1px solid #2e2e2e;")
        bottom = QHBoxLayout(bottom_wrap)
        bottom.setContentsMargins(8, 5, 8, 5)
        bottom.setSpacing(8)
        self._count_lbl = QLabel("0 materials selected")
        self._count_lbl.setStyleSheet(COUNT_LABEL_STYLE)
        self._add_btn = QPushButton("＋  Add Selected to BOM (Direct)")
        self._add_btn.setStyleSheet(BTN_PRIMARY_STYLE)
        self._add_btn.setFixedHeight(28)
        self._add_btn.setEnabled(False)
        self._add_btn.clicked.connect(self._emit_add)
        bottom.addWidget(self._count_lbl)
        bottom.addStretch()
        bottom.addWidget(self._add_btn)
        layout.addWidget(bottom_wrap)

    def load(self, existing_direct_ids: set | None = None):
        existing_direct_ids = existing_direct_ids or set()
        df = self._cm.get_raw_materials()
        self._table.setRowCount(0)
        self._rows.clear()
        if df.empty:
            self._update_count()
            return
        for i, (_, row) in enumerate(df.iterrows()):
            already_direct = row["MaterialId"] in existing_direct_ids
            self._table.insertRow(i)
            cb = QCheckBox()
            cb.setStyleSheet(CHECK_STYLE)
            cb.setEnabled(not already_direct)
            cb.stateChanged.connect(self._update_count)
            cb_w = QWidget()
            cb_l = QHBoxLayout(cb_w)
            cb_l.setContentsMargins(5, 2, 5, 2)
            cb_l.setAlignment(Qt.AlignmentFlag.AlignCenter)
            cb_l.addWidget(cb)
            cb_w.setStyleSheet("background: transparent;")
            self._table.setCellWidget(i, 0, cb_w)
            dim        = C_GHOST if already_direct else C_WHITE
            type_color = C_GHOST if already_direct else C_GOLD
            name_item  = _ti(row["Name"], color=dim)
            name_item.setData(Qt.ItemDataRole.UserRole, row["MaterialId"])
            self._table.setItem(i, 1, name_item)
            self._table.setItem(i, 2, _ti(UNIT_TYPE_LABELS.get(row["UnitType"], row["UnitType"]),
                                          color=type_color))
            self._table.setItem(i, 3, _ti(row["Unit"], color=dim))
            self._table.setItem(i, 4, _ti(f"₹{float(row['CostPerUnit']):,.4f}",
                Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter, color=dim))

            spin = QDoubleSpinBox()
            spin.setRange(0.01, 999_999)
            spin.setValue(1.00)
            spin.setDecimals(2)
            spin.setSingleStep(0.01)
            spin.setButtonSymbols(QAbstractSpinBox.ButtonSymbols.NoButtons)
            spin.setStyleSheet(STEPPER_SPIN_STYLE)
            spin.setFixedSize(54, 24)
            spin.setEnabled(not already_direct)
            spin.setAlignment(Qt.AlignmentFlag.AlignCenter)
            minus_btn = QPushButton("−")
            minus_btn.setFixedSize(24, 24)
            minus_btn.setStyleSheet(STEPPER_BTN_STYLE + "QPushButton { border-radius: 4px; border-top-right-radius: 0; border-bottom-right-radius: 0; }")
            minus_btn.setEnabled(not already_direct)
            plus_btn = QPushButton("+")
            plus_btn.setFixedSize(24, 24)
            plus_btn.setStyleSheet(STEPPER_BTN_STYLE + "QPushButton { border-radius: 4px; border-top-left-radius: 0; border-bottom-left-radius: 0; }")
            plus_btn.setEnabled(not already_direct)
            minus_btn.clicked.connect(lambda _, s=spin: s.setValue(max(s.minimum(), s.value() - s.singleStep())))
            plus_btn.clicked.connect(lambda _, s=spin: s.setValue(min(s.maximum(), s.value() + s.singleStep())))
            stepper_w = QWidget()
            stepper_w.setStyleSheet("background: transparent;")
            stepper_l = QHBoxLayout(stepper_w)
            stepper_l.setContentsMargins(3, 3, 3, 3)
            stepper_l.setSpacing(0)
            stepper_l.addWidget(minus_btn)
            stepper_l.addWidget(spin)
            stepper_l.addWidget(plus_btn)
            self._table.setCellWidget(i, 5, stepper_w)
            self._rows.append((cb, minus_btn, spin, plus_btn, row["MaterialId"]))
        self._update_count()

    def _filter_rows(self, text: str):
        text = text.strip().lower()
        for i in range(self._table.rowCount()):
            item = self._table.item(i, 1)
            hide = bool(text) and (not item or text not in item.text().lower())
            self._table.setRowHidden(i, hide)

    def _select_all(self):
        for i, (cb, *_) in enumerate(self._rows):
            if not self._table.isRowHidden(i) and cb.isEnabled():
                cb.setChecked(True)

    def _select_none(self):
        for cb, *_ in self._rows:
            cb.setChecked(False)

    def _update_count(self):
        n      = sum(1 for cb, *_ in self._rows if cb.isChecked())
        plural = "s" if n != 1 else ""
        self._count_lbl.setText(
            f'<span style="color:#c8a84b; font-weight:600;">{n}</span> material{plural} selected'
        )
        self._count_lbl.setTextFormat(Qt.TextFormat.RichText)
        self._add_btn.setText(
            f"＋  Add {n} Material{plural} to BOM (Direct)" if n
            else "＋  Add Selected to BOM (Direct)"
        )
        self._add_btn.setEnabled(n > 0)

    def _emit_add(self):
        selected = [(mid, spin.value()) for cb, _m, spin, _p, mid in self._rows if cb.isChecked()]
        if selected:
            self.materials_add_requested.emit(selected)


class PDFGenerator:

    @staticmethod
    def _html_head(title: str, subtitle: str) -> str:
        today = datetime.now().strftime("%d %b %Y  %H:%M")
        return f"""
        <html><head>
        <style>
          body {{ font-family: Arial, sans-serif; color: #222; margin: 0; padding: 16px; font-size: 10pt; }}
          h2   {{ color: #1B2A4A; margin-bottom: 4px; font-size: 14pt; }}
          h3   {{ color: #1B2A4A; margin-top: 18px; margin-bottom: 6px; font-size: 11pt; }}
          p.meta {{ color: #666; font-size: 9pt; margin-top: 0; }}
          table {{ border-collapse: collapse; width: 100%; font-size: 9pt; margin-bottom: 10px; }}
          th    {{ background: #1B2A4A; color: white; padding: 5px 8px; text-align: center; }}
          td    {{ border: 1px solid #e0e0e0; padding: 4px 7px; }}
          tr.subtotal td {{ background: #FFF8E1; font-weight: bold; }}
          tr.section  td {{ background: #E8EAF6; font-weight: bold; color: #1A237E; }}
          tr.grand    td {{ background: #1B2A4A; color: white; font-weight: bold; font-size: 10pt; }}
          .right  {{ text-align: right; }}
          .center {{ text-align: center; }}
          .muted  {{ color: #888; }}
          .profit {{ color: #2E7D32; font-weight: bold; }}
          .loss   {{ color: #C62828; font-weight: bold; }}
        </style>
        </head><body>
        <h2>{title}</h2>
        <p class="meta">{subtitle} &nbsp;|&nbsp; Generated: {today}</p>
        <hr style="border: 1px solid #ddd; margin: 10px 0;">
        """

    @staticmethod
    def _html_foot() -> str:
        return "</body></html>"

    @staticmethod
    def _html_kpi_band(label_vals: list[tuple[str, str, str]]) -> str:
        cells = "".join(
            f"""<td style="padding:10px 16px; background:{bg};
                          border:1px solid #ccc; width:{100//len(label_vals)}%">
                  <div style="font-size:8pt; color:#555;">{lbl}</div>
                  <div style="font-size:14pt; font-weight:bold;">{val}</div>
                </td>"""
            for lbl, val, bg in label_vals
        )
        return f"<table style='border-collapse:collapse;width:100%;margin-bottom:12px;'><tr>{cells}</tr></table>"

    @staticmethod
    def _html_bom_table_layered(rm_lines: list[dict],
                                layer_breakdown: list[dict] | None) -> str:
        if not rm_lines:
            return "<p class='muted'>No raw materials in BOM.</p>"

        # Flat fallback if no breakdown or only direct
        has_named = layer_breakdown and any(not b["is_direct"] for b in (layer_breakdown or []))
        if not has_named:
            rows = "".join(
                f"<tr><td>{m['name']}</td><td class='center'>{m['qty']:g}</td>"
                f"<td class='center'>{m['unit']}</td>"
                f"<td class='right'>₹{m['cost_per_unit']:,.4f}</td>"
                f"<td class='right'><b>₹{m['line_cost']:,.2f}</b></td></tr>"
                for m in rm_lines
            )
            subtotal = sum(m["line_cost"] for m in rm_lines)
            return f"""
            <table>
              <tr><th>Material</th><th>Qty</th><th>Unit</th><th>Rate/Unit</th><th>Amount</th></tr>
              {rows}
              <tr class='subtotal'>
                <td colspan='4' class='right'>Raw Material Subtotal</td>
                <td class='right'>₹{subtotal:,.2f}</td>
              </tr>
            </table>"""

        rows = ""
        for bucket in layer_breakdown:
            color = "#1A5276" if not bucket["is_direct"] else "#555555"
            bg    = "#EAF4FB" if not bucket["is_direct"] else "#F5F5F5"
            label = bucket["layer_name"]
            rows += (
                f"<tr><td colspan='5' style='background:{bg}; color:{color}; "
                f"font-weight:bold; font-style:italic; font-size:8pt; padding:4px 10px;'>"
                f"⬡ &nbsp;{label}</td></tr>"
            )
            for m in bucket["materials"]:
                rows += (
                    f"<tr><td style='padding-left:20px'>{m['name']}</td>"
                    f"<td class='center'>{m['qty']:g}</td>"
                    f"<td class='center'>{m['unit']}</td>"
                    f"<td class='right'>₹{m['cost_per_unit']:,.4f}</td>"
                    f"<td class='right'><b>₹{m['line_cost']:,.2f}</b></td></tr>"
                )
            rows += (
                f"<tr><td colspan='4' class='right' style='font-style:italic; color:{color}; font-size:8pt;'>"
                f"└─ {label} subtotal</td>"
                f"<td class='right' style='color:{color};'>₹{bucket['subtotal']:,.2f}</td></tr>"
            )

        grand = sum(m["line_cost"] for m in rm_lines)
        rows += (
            f"<tr class='subtotal'>"
            f"<td colspan='4' class='right'>Raw Material Subtotal</td>"
            f"<td class='right'>₹{grand:,.2f}</td></tr>"
        )
        return f"""
        <table>
        <tr><th>Material</th><th>Qty</th><th>Unit</th><th>Rate/Unit</th><th>Amount</th></tr>
        {rows}
        </table>"""

    @staticmethod
    def _html_overhead_table(cc_lines: list[dict]) -> str:
        if not cc_lines:
            return "<p class='muted'>No overhead costs configured.</p>"
        rows = "".join(
            f"<tr><td>{c['type_name']}</td><td class='right'><b>₹{c['rate']:,.2f}</b></td>"
            f"<td>{c['rate_unit']}</td></tr>"
            for c in cc_lines
        )
        subtotal = sum(c["rate"] for c in cc_lines)
        return f"""
        <table>
          <tr><th>Overhead Type</th><th>Rate (₹)</th><th>Per</th></tr>
          {rows}
          <tr class='subtotal'>
            <td colspan='2' class='right'>Overhead Subtotal</td>
            <td class='right'>₹{subtotal:,.2f}</td>
          </tr>
        </table>"""

    @staticmethod
    def _html_cost_ladder(cost: dict) -> str:
        wc_row = lc_row = ""
        if cost.get("warranty_pct", 0):
            wc_row = (
                f"<tr><td>Warranty Charge ({cost['warranty_pct']:.2f}% of base)</td>"
                f"<td class='right'>₹{cost['warranty_cost']:,.2f}</td></tr>"
                f"<tr class='subtotal'><td>After Warranty Total</td>"
                f"<td class='right'>₹{cost['after_warranty']:,.2f}</td></tr>"
            )
        if cost.get("labour_pct", 0):
            lc_row = (
                f"<tr><td>Labour Charge ({cost['labour_pct']:.2f}% of post-warranty)</td>"
                f"<td class='right'>₹{cost['labour_cost']:,.2f}</td></tr>"
            )
        return f"""
        <table style='width:50%; float:right; margin-bottom:12px;'>
          <tr><th colspan='2'>Cost Summary</th></tr>
          <tr><td>Raw Material Cost</td><td class='right'>₹{cost['raw_material_cost']:,.2f}</td></tr>
          <tr><td>Total Overhead</td><td class='right'>₹{cost['total_custom_cost']:,.2f}</td></tr>
          <tr class='subtotal'><td>Base Total</td><td class='right'>₹{cost['base_total']:,.2f}</td></tr>
          {wc_row}{lc_row}
          <tr class='grand'><td>FINAL COST / UNIT</td>
            <td class='right'>₹{cost['final_total_cost']:,.2f}</td></tr>
        </table>
        <div style='clear:both'></div>"""

    @classmethod
    def build_breakdown_html(cls, product_name: str, cost: dict,
                             sale_price: float = 0.0,
                             layer_breakdown: list[dict] | None = None) -> str:
        final      = cost["final_total_cost"]
        margin     = round(sale_price - final, 2)
        margin_pct = round((margin / sale_price * 100) if sale_price else 0.0, 2)
        kpi = cls._html_kpi_band([
            ("FINAL COST / UNIT", f"₹{final:,.2f}", "#FFF3E0"),
            ("SALE PRICE",        f"₹{sale_price:,.2f}", "#E8F5E9"),
            ("MARGIN",            f"₹{margin:,.2f} ({margin_pct:.1f}%)",
             "#E8F5E9" if margin >= 0 else "#FFEBEE"),
        ])
        lb = layer_breakdown or cost.get("layer_breakdown")
        return (
            cls._html_head("Cost Breakdown Report", product_name)
            + kpi
            + "<h3>Bill of Materials</h3>"
            + cls._html_bom_table_layered(cost["raw_material_lines"], lb)
            + "<h3>Overhead / Custom Costs</h3>"
            + cls._html_overhead_table(cost["custom_cost_lines"])
            + "<h3>Cost Summary</h3>"
            + cls._html_cost_ladder(cost)
            + cls._html_foot()
        )

    @classmethod
    def build_all_products_html(cls, rows: list[dict]) -> str:
        table_rows = ""
        for r in rows:
            margin = r["margin"]
            mc     = "profit" if margin >= 0 else "loss"
            table_rows += (
                f"<tr>"
                f"<td>{r['product_name']}</td>"
                f"<td class='right'>₹{r['raw_material_cost']:,.2f}</td>"
                f"<td class='right'>₹{r['total_custom_cost']:,.2f}</td>"
                f"<td class='right'>₹{r['base_total']:,.2f}</td>"
                f"<td class='right muted'>{r['warranty_pct']:.1f}%</td>"
                f"<td class='right'>₹{r['warranty_cost']:,.2f}</td>"
                f"<td class='right muted'>{r['labour_pct']:.1f}%</td>"
                f"<td class='right'>₹{r['labour_cost']:,.2f}</td>"
                f"<td class='right'><b>₹{r['final_total_cost']:,.2f}</b></td>"
                f"<td class='right'>₹{r['sale_price']:,.2f}</td>"
                f"<td class='right {mc}'>₹{margin:,.2f} ({r['margin_pct']:.1f}%)</td>"
                f"</tr>"
            )
        return (
            cls._html_head("All Products — Cost Summary", "Live Calculation")
            + """<table>
              <tr>
                <th>Product</th><th>Raw Mat.</th><th>Overhead</th><th>Base Total</th>
                <th>Warranty%</th><th>Warranty ₹</th>
                <th>Labour%</th><th>Labour ₹</th>
                <th>Final Cost</th><th>Sale Price</th><th>Margin</th>
              </tr>"""
            + table_rows
            + "</table>"
            + cls._html_foot()
        )

    @classmethod
    def build_analytics_html(cls, df: pd.DataFrame, product_name: str,
                             cost: dict,
                             layer_breakdown: list[dict] | None = None) -> str:
        if df.empty:
            last_cost = cost["final_total_cost"]
            sale_price = margin = margin_pct = 0.0
        else:
            last       = df.iloc[-1]
            last_cost  = float(last.get("FinalCost", last.get("TotalCost", 0)))
            sale_price = float(last.get("SalePrice", 0))
            margin     = float(last.get("Margin", 0))
            margin_pct = float(last.get("MarginPct", 0))

        kpi = cls._html_kpi_band([
            ("LATEST FINAL COST", f"₹{last_cost:,.2f}", "#FFF3E0"),
            ("LATEST SALE PRICE", f"₹{sale_price:,.2f}", "#E8F5E9"),
            ("LATEST MARGIN",     f"₹{margin:,.2f} ({margin_pct:.1f}%)",
             "#E8F5E9" if margin >= 0 else "#FFEBEE"),
        ])
        snap_rows = ""
        if not df.empty:
            for _, row in df.iloc[::-1].iterrows():
                m  = float(row.get("Margin", 0))
                mc = "profit" if m >= 0 else "loss"
                fc = float(row.get("FinalCost", row.get("TotalCost", 0)))
                snap_rows += (
                    f"<tr><td>{str(row['SnapshotAt'])[:16]}</td>"
                    f"<td class='right'>₹{fc:,.2f}</td>"
                    f"<td class='right'>₹{float(row['SalePrice']):,.2f}</td>"
                    f"<td class='right {mc}'>₹{m:,.2f}</td>"
                    f"<td class='right {mc}'>{float(row['MarginPct']):.1f}%</td>"
                    f"<td class='right muted'>{row.get('WarrantyPct', 0):.1f}%</td>"
                    f"<td class='right muted'>{row.get('LabourPct', 0):.1f}%</td>"
                    f"<td>{row.get('TriggerType','')}</td>"
                    f"<td>{row.get('Notes','')}</td></tr>"
                )

        lb = layer_breakdown or cost.get("layer_breakdown")
        return (
            cls._html_head("Cost Analytics Report", product_name)
            + kpi
            + "<h3>Bill of Materials</h3>"
            + cls._html_bom_table_layered(cost["raw_material_lines"], lb)
            + "<h3>Overhead / Custom Costs</h3>"
            + cls._html_overhead_table(cost["custom_cost_lines"])
            + "<h3>Cost Summary</h3>"
            + cls._html_cost_ladder(cost)
            + f"""<h3>Snapshot History</h3>
            <table>
              <tr>
                <th>Date</th><th>Final Cost</th><th>Sale Price</th>
                <th>Margin ₹</th><th>Margin %</th>
                <th>Warranty%</th><th>Labour%</th>
                <th>Trigger</th><th>Notes</th>
              </tr>
              {snap_rows if snap_rows else '<tr><td colspan="9" class="muted">No snapshots yet.</td></tr>'}
            </table>"""
            + cls._html_foot()
        )

    @staticmethod
    def print_html_to_pdf(html: str, fp: str) -> bool:
        try:
            printer = QPrinter(QPrinter.PrinterMode.HighResolution)
            printer.setOutputFormat(QPrinter.OutputFormat.PdfFormat)
            printer.setOutputFileName(fp)
            printer.setPageLayout(QPageLayout(
                QPageSize(QPageSize.PageSizeId.A4),
                QPageLayout.Orientation.Portrait,
                QMarginsF(18, 15, 18, 15),
                QPageLayout.Unit.Millimeter,
            ))
            doc = QTextDocument()
            doc.setHtml(html)
            doc.print_(printer)
            return True
        except Exception:
            return False

    @staticmethod
    def share_pdf(pdf_path: str, parent: QWidget):
        if not os.path.exists(pdf_path):
            QMessageBox.warning(parent, "Error", "PDF file not found.")
            return
        try:
            subprocess.Popen([get_bridge_path(), pdf_path])
        except Exception as e:
            QMessageBox.warning(parent, "Share Error", str(e))


class CostBreakdownWidget(QWidget):

    def __init__(self, cm: CostingManager, parent=None):
        super().__init__(parent)
        self._cm = cm
        self._current_product_id: str | None   = None
        self._current_product_name: str | None = None
        self._settings = QSettings("Fatha", "AccountManager")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(5)

        hdr = QHBoxLayout()
        title = _lbl("LIVE COST BREAKDOWN", 9, True, C_GOLD)
        title.setStyleSheet(f"color: {C_GOLD}; letter-spacing: 2px; background: transparent;")
        hdr.addWidget(title)
        hdr.addStretch()
        self._share_btn = _btn("📤 Share", BTN_OUTLINE, 90)
        self._share_btn.setFixedHeight(26)
        self._share_btn.setEnabled(False)
        self._share_btn.clicked.connect(self._share_pdf)
        self._pdf_btn = _btn("⬇ PDF", BTN_OUTLINE, 80)
        self._pdf_btn.setFixedHeight(26)
        self._pdf_btn.setEnabled(False)
        self._pdf_btn.clicked.connect(self._export_pdf)
        hdr.addWidget(self._share_btn)
        hdr.addWidget(self._pdf_btn)
        layout.addLayout(hdr)
        layout.addWidget(_divider())

        self._table = QTableWidget()
        self._table.setColumnCount(5)
        self._table.setHorizontalHeaderLabels(["Item", "Qty", "Unit", "Rate / Unit", "Amount"])
        self._table.setStyleSheet(TABLE_STYLE)
        self._table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self._table.setSelectionMode(QAbstractItemView.SelectionMode.NoSelection)
        self._table.verticalHeader().setVisible(False)
        self._table.setAlternatingRowColors(False)
        self._table.setVerticalScrollMode(QAbstractItemView.ScrollMode.ScrollPerPixel)
        hh = self._table.horizontalHeader()
        hh.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        for c in (1, 2, 3, 4):
            hh.setSectionResizeMode(c, QHeaderView.ResizeMode.ResizeToContents)
        layout.addWidget(self._table, 1)

        self._total_banner = QFrame()
        self._total_banner.setStyleSheet(f"""
            QFrame {{
                background: qlineargradient(x1:0,y1:0,x2:1,y2:0,
                    stop:0 #1B2A1B, stop:1 #1B1B2F);
                border: 1px solid {C_GOLD};
                border-radius: 5px;
            }}
        """)
        tbl = QHBoxLayout(self._total_banner)
        tbl.setContentsMargins(12, 5, 12, 5)
        self._total_label = _lbl("Final Cost / Unit:", 10, True, C_WHITE_MUT)
        self._total_value = _lbl("—", 14, True, C_GOLD)
        self._total_value.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        tbl.addWidget(self._total_label)
        tbl.addStretch()
        tbl.addWidget(self._total_value)
        self._total_banner.setFixedHeight(36)
        layout.addWidget(self._total_banner)

    def update_breakdown(self, product_id: str, product_name: str):
        self._current_product_id   = product_id
        self._current_product_name = product_name
        self._refresh()

    def clear_breakdown(self):
        self._current_product_id   = None
        self._current_product_name = None
        self._table.setRowCount(0)
        self._total_value.setText("—")
        self._share_btn.setEnabled(False)
        self._pdf_btn.setEnabled(False)

    def _refresh(self):
        if not self._current_product_id:
            self.clear_breakdown()
            return
        cost = self._cm.calculate_product_cost(self._current_product_id)
        self._table.setRowCount(0)
        self._share_btn.setEnabled(True)
        self._pdf_btn.setEnabled(True)
        row_idx = [0]

        def next_row() -> int:
            r = row_idx[0]
            self._table.insertRow(r)
            row_idx[0] += 1
            return r

        def section_header(text: str):
            r = next_row()
            for col in range(5):
                cell = QTableWidgetItem("" if col else text)
                cell.setFlags(Qt.ItemFlag.ItemIsEnabled)
                cell.setBackground(QColor(C_TOPBAR))
                if col == 0:
                    cell.setForeground(QColor(C_GOLD))
                    f = QFont(FONT_UI, 9)
                    f.setBold(True)
                    f.setLetterSpacing(QFont.SpacingType.AbsoluteSpacing, 1.5)
                    cell.setFont(f)
                self._table.setItem(r, col, cell)
            self._table.setSpan(r, 0, 1, 5)
            self._table.setRowHeight(r, 24)

        def layer_subheader(layer_name: str, is_direct: bool):
            r = next_row()
            color = "#7EC8E3" if not is_direct else "#A0A0A0"
            tag   = f"  ⬡  {layer_name}"
            lbl   = QTableWidgetItem(tag)
            lbl.setFlags(Qt.ItemFlag.ItemIsEnabled)
            lbl.setBackground(QColor("#1A2535"))
            lbl.setForeground(QColor(color))
            f2 = QFont(FONT_UI, 8)
            f2.setBold(True)
            f2.setItalic(True)
            lbl.setFont(f2)
            self._table.setItem(r, 0, lbl)
            self._table.setSpan(r, 0, 1, 5)
            self._table.setRowHeight(r, 22)

        def material_row(m: dict):
            r = next_row()
            self._table.setItem(r, 0, _ti(f"   {m['name']}"))
            self._table.setItem(r, 1, _ti(f"{m['qty']:g}",
                Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter))
            self._table.setItem(r, 2, _ti(m["unit"]))
            self._table.setItem(r, 3, _ti(f"₹{m['cost_per_unit']:,.4f}",
                Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter))
            self._table.setItem(r, 4, _ti(f"₹{m['line_cost']:,.2f}",
                Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter, C_WHITE))

        def overhead_row(c: dict):
            r = next_row()
            self._table.setItem(r, 0, _ti(f"   {c['type_name']}"))
            self._table.setItem(r, 1, _ti(""))
            self._table.setItem(r, 2, _ti(""))
            self._table.setItem(r, 3, _ti(c["rate_unit"]))
            self._table.setItem(r, 4, _ti(f"₹{c['rate']:,.2f}",
                Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter, C_WHITE))

        def subtotal_row(label: str, amount: float, color: str = C_GOLD):
            r = next_row()
            lbl = QTableWidgetItem(f"  {label}")
            lbl.setFlags(Qt.ItemFlag.ItemIsEnabled)
            lbl.setBackground(QColor(C_SURFACE_ALT))
            lbl.setForeground(QColor(color))
            f = QFont(FONT_UI, 9)
            f.setBold(True)
            lbl.setFont(f)
            self._table.setItem(r, 0, lbl)
            self._table.setSpan(r, 0, 1, 4)
            amt = QTableWidgetItem(f"₹{amount:,.2f}")
            amt.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            amt.setFlags(Qt.ItemFlag.ItemIsEnabled)
            amt.setBackground(QColor(C_SURFACE_ALT))
            amt.setForeground(QColor(color))
            amt.setFont(f)
            self._table.setItem(r, 4, amt)
            self._table.setRowHeight(r, 28)

        def pct_charge_row(label: str, pct: float, amount: float, color: str = "#E0A060"):
            r = next_row()
            lbl_cell = QTableWidgetItem(f"   {label}")
            lbl_cell.setFlags(Qt.ItemFlag.ItemIsEnabled)
            lbl_cell.setForeground(QColor(color))
            self._table.setItem(r, 0, lbl_cell)
            pct_cell = QTableWidgetItem(f"{pct:.2f}%")
            pct_cell.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            pct_cell.setFlags(Qt.ItemFlag.ItemIsEnabled)
            pct_cell.setForeground(QColor(color))
            self._table.setItem(r, 1, pct_cell)
            self._table.setSpan(r, 1, 1, 3)
            amt_cell = QTableWidgetItem(f"₹{amount:,.2f}")
            amt_cell.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            amt_cell.setFlags(Qt.ItemFlag.ItemIsEnabled)
            amt_cell.setForeground(QColor(color))
            self._table.setItem(r, 4, amt_cell)

        def spacer_row():
            r = next_row()
            cell = QTableWidgetItem("")
            cell.setFlags(Qt.ItemFlag.ItemIsEnabled)
            cell.setBackground(QColor(C_BG))
            self._table.setItem(r, 0, cell)
            self._table.setSpan(r, 0, 1, 5)
            self._table.setRowHeight(r, 5)

        section_header("▸   RAW MATERIALS")

        if cost["raw_material_lines"]:
            layer_breakdown = cost["layer_breakdown"]
            has_named       = any(not b["is_direct"] for b in layer_breakdown)

            if has_named or len(layer_breakdown) > 1:
                # Grouped by layer
                for bucket in layer_breakdown:
                    layer_subheader(bucket["layer_name"], bucket["is_direct"])
                    for m in bucket["materials"]:
                        material_row(m)
                    subtotal_row(
                        f"   └─ {bucket['layer_name']} subtotal",
                        bucket["subtotal"],
                        "#7EC8E3" if not bucket["is_direct"] else "#909090",
                    )
                    spacer_row()
            else:
                # No layers — flat list
                for m in cost["raw_material_lines"]:
                    material_row(m)

            subtotal_row("Raw Material Subtotal", cost["raw_material_cost"])
        else:
            r = next_row()
            self._table.setItem(r, 0, _ti("   (no materials in BOM)", color=C_GHOST))
            self._table.setSpan(r, 0, 1, 5)

        spacer_row()

        # ── OVERHEAD section ──────────────────────────────────────────────
        section_header("▸   OVERHEAD / CUSTOM COSTS")
        if cost["custom_cost_lines"]:
            for c in cost["custom_cost_lines"]:
                overhead_row(c)
            subtotal_row("Overhead Subtotal", cost["total_custom_cost"])
        else:
            r = next_row()
            self._table.setItem(r, 0, _ti("   (no overhead costs defined)", color=C_GHOST))
            self._table.setSpan(r, 0, 1, 5)

        spacer_row()
        subtotal_row("  ┄   BASE TOTAL  (Materials + Overhead)", cost["base_total"], "#C8A840")

        # Warranty
        if cost["warranty_pct"] > 0:
            spacer_row()
            section_header("▸   WARRANTY CHARGE")
            pct_charge_row(
                f"Warranty ({cost['warranty_pct']:.2f}% of base ₹{cost['base_total']:,.2f})",
                cost["warranty_pct"], cost["warranty_cost"], "#E09040",
            )
            subtotal_row("  ┄   AFTER WARRANTY TOTAL", cost["after_warranty"], "#C8A840")

        # Labour
        if cost["labour_pct"] > 0:
            spacer_row()
            section_header("▸   LABOUR CHARGE")
            pct_charge_row(
                f"Labour ({cost['labour_pct']:.2f}% of post-warranty ₹{cost['after_warranty']:,.2f})",
                cost["labour_pct"], cost["labour_cost"], "#9090E0",
            )

        spacer_row()
        subtotal_row("═══   FINAL TOTAL COST / UNIT", cost["final_total_cost"], "#FFD700")
        self._total_value.setText(f"₹ {cost['final_total_cost']:,.2f}")

    def _get_sale_price(self) -> float:
        return 0.0

    def _export_pdf(self):
        if not self._current_product_id:
            return
        name     = self._current_product_name or "Product"
        default  = f"{name.replace(' ', '_')}_cost_breakdown.pdf"
        last_dir = self._settings.value("pdf_export_dir", "", type=str)
        fp, _    = QFileDialog.getSaveFileName(
            self, "Save Cost Breakdown PDF",
            os.path.join(last_dir, default) if last_dir else default,
            "PDF Files (*.pdf)",
        )
        if not fp:
            return
        cost = self._cm.calculate_product_cost(self._current_product_id)
        html = PDFGenerator.build_breakdown_html(name, cost, self._get_sale_price())
        if PDFGenerator.print_html_to_pdf(html, fp):
            self._settings.setValue("pdf_export_dir", os.path.dirname(fp))
            QMessageBox.information(self, "Success", f"PDF exported:\n{fp}")
        else:
            QMessageBox.warning(self, "Error", "Failed to generate PDF.")

    def _share_pdf(self):
        if not self._current_product_id:
            return
        name     = self._current_product_name or "Product"
        cost     = self._cm.calculate_product_cost(self._current_product_id)
        html     = PDFGenerator.build_breakdown_html(name, cost, self._get_sale_price())
        tmp_path = os.path.join(tempfile.gettempdir(),
                                f"{name.replace(' ', '_')}_cost_breakdown.pdf")
        if PDFGenerator.print_html_to_pdf(html, tmp_path):
            PDFGenerator.share_pdf(tmp_path, self)
        else:
            QMessageBox.warning(self, "Error", "Failed to generate PDF.")

class WarrantyLabourPanel(QFrame):
    config_changed = Signal()

    def __init__(self, cm: CostingManager, parent=None):
        super().__init__(parent)
        self._cm         = cm
        self._product_id: str | None = None
        self.setStyleSheet(CARD_STYLE)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 8, 10, 8)
        layout.setSpacing(6)

        hdr_row = QHBoxLayout()
        hdr_row.addWidget(_lbl("WARRANTY & LABOUR CONFIG", 9, True, C_GOLD))
        hdr_row.addStretch()
        hdr_row.addWidget(_lbl("(% applied after base total)", 9, False, C_GHOST))
        layout.addLayout(hdr_row)
        layout.addWidget(_divider())

        form_row = QHBoxLayout()
        form_row.setSpacing(10)
        form_row.addWidget(_lbl("Warranty %", 11))
        self._warranty_in = _field("e.g. 2.5")
        self._warranty_in.setValidator(QDoubleValidator(0, 100, 4))
        self._warranty_in.setFixedWidth(90)
        form_row.addWidget(self._warranty_in)
        form_row.addSpacing(12)
        form_row.addWidget(_lbl("Labour %", 11))
        self._labour_in = _field("e.g. 5.0")
        self._labour_in.setValidator(QDoubleValidator(0, 100, 4))
        self._labour_in.setFixedWidth(90)
        form_row.addWidget(self._labour_in)
        form_row.addSpacing(8)
        save_btn = _btn("Save", BTN_SUCCESS, 70)
        save_btn.setFixedHeight(28)
        save_btn.clicked.connect(self._save)
        form_row.addWidget(save_btn)
        form_row.addStretch()
        layout.addLayout(form_row)

        self._info_lbl = _lbl("— select a product —", 9, False, C_GHOST)
        layout.addWidget(self._info_lbl)

    def load_product(self, product_id: str | None):
        self._product_id = product_id
        if not product_id:
            self._warranty_in.clear()
            self._labour_in.clear()
            self._info_lbl.setText("— select a product —")
            return
        cfg = self._cm.get_product_warranty_config(product_id)
        self._warranty_in.setText(f"{cfg['warranty_pct']:.4f}".rstrip("0").rstrip("."))
        self._labour_in.setText(f"{cfg['labour_pct']:.4f}".rstrip("0").rstrip("."))
        self._update_info(cfg)

    def _update_info(self, cfg: dict):
        self._info_lbl.setText(
            f"Current config  →  "
            f"Warranty: <b>{cfg['warranty_pct']:.2f}%</b>  |  "
            f"Labour: <b>{cfg['labour_pct']:.2f}%</b>"
        )
        self._info_lbl.setTextFormat(Qt.TextFormat.RichText)

    def _save(self):
        if not self._product_id:
            _warn(self, "Select a product first.")
            return
        w = self._warranty_in.text().strip() or "0"
        l = self._labour_in.text().strip()   or "0"
        status, msg = self._cm.set_product_warranty_config(self._product_id, w, l)
        QMessageBox.information(self, status, msg)
        if status == "Success":
            cfg = self._cm.get_product_warranty_config(self._product_id)
            self._update_info(cfg)
            self.config_changed.emit()

class AllProductsSummaryTab(QWidget):

    def __init__(self, cm: CostingManager, acc_mgr, parent=None):
        super().__init__(parent)
        self._cm           = cm
        self._acc_mgr      = acc_mgr
        self._summary_data: list[dict] = []
        self.setStyleSheet(f"background: {C_BG};")

        root = QVBoxLayout(self)
        root.setContentsMargins(8, 8, 8, 8)
        root.setSpacing(6)

        root.addWidget(self._build_toolbar())

        splitter = QSplitter(Qt.Orientation.Vertical)
        splitter.setStyleSheet("QSplitter::handle { background: #2E2E45; height: 3px; }")

        table_frame, tvl = _card("ALL PRODUCTS — LIVE COST SUMMARY")
        self._summary_table = _make_table([
            "Product", "Raw Mat ₹", "Overhead ₹", "Base Total ₹",
            "Warranty%", "Warranty ₹", "Labour%", "Labour ₹",
            "Final Cost ₹", "Sale Price ₹", "Margin ₹", "Margin %", "Detail",
        ])
        self._summary_table.setMinimumHeight(200)
        self._summary_table.currentCellChanged.connect(self._on_row_selected)
        hh = self._summary_table.horizontalHeader()
        hh.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        for c in range(1, 12):
            hh.setSectionResizeMode(c, QHeaderView.ResizeMode.ResizeToContents)
        hh.setSectionResizeMode(12, QHeaderView.ResizeMode.Fixed)
        self._summary_table.setColumnWidth(12, 70)
        tvl.addWidget(self._summary_table, 1)
        splitter.addWidget(table_frame)

        detail_frame, dvl = _card("PRODUCT DETAIL BREAKDOWN")
        self._detail_tabs  = QTabWidget()
        self._detail_tabs.setStyleSheet(_sub_tab_style())
        self._breakdown_widget = CostBreakdownWidget(cm)
        self._detail_tabs.addTab(self._breakdown_widget, "📊 Cost Breakdown")

        bom_page = QWidget()
        bom_page.setStyleSheet(f"background: {C_BG};")
        bom_vl = QVBoxLayout(bom_page)
        bom_vl.setContentsMargins(4, 4, 4, 4)
        self._detail_bom_table = _make_table(["Material", "Source", "Qty", "Unit", "Cost/Unit", "Line Cost"])
        bom_vl.addWidget(self._detail_bom_table)
        self._detail_tabs.addTab(bom_page, "🔩 BOM Details")

        dvl.addWidget(self._detail_tabs, 1)

        det_export_row = QHBoxLayout()
        det_export_row.addStretch()
        self._det_share_btn = _btn("📤 Share", BTN_OUTLINE, 90)
        self._det_share_btn.setEnabled(False)
        self._det_share_btn.clicked.connect(self._share_selected_pdf)
        self._det_pdf_btn = _btn("⬇ Export This Product PDF", BTN_SUCCESS, 210)
        self._det_pdf_btn.setEnabled(False)
        self._det_pdf_btn.clicked.connect(self._export_selected_pdf)
        det_export_row.addWidget(self._det_share_btn)
        det_export_row.addWidget(self._det_pdf_btn)
        dvl.addLayout(det_export_row)

        splitter.addWidget(detail_frame)
        splitter.setStretchFactor(0, 3)
        splitter.setStretchFactor(1, 2)
        QTimer.singleShot(0, lambda: splitter.setSizes(
            _responsive_splitter_sizes(splitter, [0.58, 0.42])
        ))
        root.addWidget(splitter, 1)
        self._selected_product_data: dict | None = None

    def _build_toolbar(self) -> QFrame:
        bar = QFrame()
        bar.setStyleSheet(CARD_STYLE)
        bar.setMaximumHeight(52)
        hl = QHBoxLayout(bar)
        hl.setContentsMargins(10, 6, 10, 6)
        hl.setSpacing(8)
        refresh_btn = _btn("🔄 Refresh", BTN_OUTLINE, 100)
        refresh_btn.clicked.connect(self.refresh)
        hl.addWidget(refresh_btn)
        hl.addWidget(_lbl("Filter:", 11))
        self._filter_in = _field("Search products…")
        self._filter_in.setFixedWidth(200)
        self._filter_in.textChanged.connect(self._apply_filter)
        hl.addWidget(self._filter_in)
        hl.addStretch()
        batch_pdf_btn   = _btn("⬇ All Products PDF", BTN_PRIMARY, 160)
        batch_share_btn = _btn("📤 Share All",        BTN_OUTLINE,  100)
        batch_pdf_btn.clicked.connect(self._export_all_pdf)
        batch_share_btn.clicked.connect(self._share_all_pdf)
        hl.addWidget(batch_pdf_btn)
        hl.addWidget(batch_share_btn)
        return bar

    def refresh(self):
        self._acc_mgr.load_data()
        products_df      = self._acc_mgr.products_data
        self._summary_data = self._cm.get_all_products_cost_summary(products_df)
        self._populate_table(self._summary_data)
        self._clear_detail()

    def _populate_table(self, rows: list[dict]):
        self._summary_table.setRowCount(0)
        for i, r in enumerate(rows):
            self._summary_table.insertRow(i)
            margin  = r["margin"]
            m_color = "#7AE07A" if margin >= 0 else "#E07070"
            RA = Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
            self._summary_table.setItem(i,  0, _ti(r["product_name"]))
            self._summary_table.setItem(i,  1, _ti(f"₹{r['raw_material_cost']:,.2f}", RA))
            self._summary_table.setItem(i,  2, _ti(f"₹{r['total_custom_cost']:,.2f}", RA))
            self._summary_table.setItem(i,  3, _ti(f"₹{r['base_total']:,.2f}", RA, C_GOLD))
            self._summary_table.setItem(i,  4, _ti(f"{r['warranty_pct']:.1f}%", RA, C_WHITE_MUT))
            self._summary_table.setItem(i,  5, _ti(f"₹{r['warranty_cost']:,.2f}", RA))
            self._summary_table.setItem(i,  6, _ti(f"{r['labour_pct']:.1f}%", RA, C_WHITE_MUT))
            self._summary_table.setItem(i,  7, _ti(f"₹{r['labour_cost']:,.2f}", RA))
            self._summary_table.setItem(i,  8, _ti(f"₹{r['final_total_cost']:,.2f}", RA, "#FFD700"))
            self._summary_table.setItem(i,  9, _ti(f"₹{r['sale_price']:,.2f}", RA))
            self._summary_table.setItem(i, 10, _ti(f"₹{margin:,.2f}", RA, m_color))
            self._summary_table.setItem(i, 11, _ti(f"{r['margin_pct']:.1f}%", RA, m_color))
            det_btn = _btn("📋 View", BTN_OUTLINE)
            det_btn.setFixedHeight(22)
            det_btn.clicked.connect(lambda _, row=r: self._show_detail(row))
            w = QWidget(); w.setStyleSheet("background: transparent;")
            wl = QHBoxLayout(w); wl.setContentsMargins(2, 2, 2, 2); wl.addWidget(det_btn)
            self._summary_table.setCellWidget(i, 12, w)
            self._summary_table.item(i, 0).setData(Qt.ItemDataRole.UserRole, r)

    def _apply_filter(self, text: str):
        text = text.strip().lower()
        for i in range(self._summary_table.rowCount()):
            item = self._summary_table.item(i, 0)
            hide = bool(text) and (not item or text not in item.text().lower())
            self._summary_table.setRowHidden(i, hide)

    def _on_row_selected(self, current_row, *_):
        if current_row < 0:
            return
        item = self._summary_table.item(current_row, 0)
        if item:
            r = item.data(Qt.ItemDataRole.UserRole)
            if r:
                self._show_detail(r)

    def _show_detail(self, row_data: dict):
        self._selected_product_data = row_data
        pid   = row_data["product_id"]
        pname = row_data["product_name"]
        self._breakdown_widget.update_breakdown(pid, pname)

        # BOM detail with source column
        rm_lines = row_data.get("raw_material_lines", [])
        self._detail_bom_table.setRowCount(0)
        RA = Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
        for i, m in enumerate(rm_lines):
            self._detail_bom_table.insertRow(i)
            src_label = m.get("layer_name") or "Direct"
            self._detail_bom_table.setItem(i, 0, _ti(m["name"]))
            self._detail_bom_table.setItem(i, 1, _ti(src_label, color=C_GOLD if src_label != "Direct" else C_WHITE_MUT))
            self._detail_bom_table.setItem(i, 2, _ti(f"{m['qty']:g}", RA))
            self._detail_bom_table.setItem(i, 3, _ti(m["unit"]))
            self._detail_bom_table.setItem(i, 4, _ti(f"₹{m['cost_per_unit']:,.4f}", RA))
            self._detail_bom_table.setItem(i, 5, _ti(f"₹{m['line_cost']:,.2f}", RA, C_GOLD))

        self._det_pdf_btn.setEnabled(True)
        self._det_share_btn.setEnabled(True)

    def _clear_detail(self):
        self._selected_product_data = None
        self._breakdown_widget.clear_breakdown()
        self._detail_bom_table.setRowCount(0)
        self._det_pdf_btn.setEnabled(False)
        self._det_share_btn.setEnabled(False)

    def _export_selected_pdf(self):
        r = self._selected_product_data
        if not r:
            return
        cost = self._cm.calculate_product_cost(r["product_id"])
        html = PDFGenerator.build_breakdown_html(r["product_name"], cost, r["sale_price"])
        fp, _ = QFileDialog.getSaveFileName(
            self, "Export Cost Breakdown PDF",
            f"{r['product_name'].replace(' ', '_')}_breakdown.pdf", "PDF Files (*.pdf)",
        )
        if fp and PDFGenerator.print_html_to_pdf(html, fp):
            QMessageBox.information(self, "Exported", f"Saved:\n{fp}")
        elif fp:
            QMessageBox.warning(self, "Error", "PDF generation failed.")

    def _share_selected_pdf(self):
        r = self._selected_product_data
        if not r:
            return
        cost     = self._cm.calculate_product_cost(r["product_id"])
        html     = PDFGenerator.build_breakdown_html(r["product_name"], cost, r["sale_price"])
        tmp_path = os.path.join(tempfile.gettempdir(),
                                f"{r['product_name'].replace(' ', '_')}_breakdown.pdf")
        if PDFGenerator.print_html_to_pdf(html, tmp_path):
            PDFGenerator.share_pdf(tmp_path, self)
        else:
            QMessageBox.warning(self, "Error", "PDF generation failed.")

    def _build_all_pdf_and_run(self, fp: str | None = None) -> str | None:
        if not self._summary_data:
            _warn(self, "No products to export. Click Refresh first.")
            return None
        visible = []
        for i in range(self._summary_table.rowCount()):
            if not self._summary_table.isRowHidden(i):
                item = self._summary_table.item(i, 0)
                if item:
                    r = item.data(Qt.ItemDataRole.UserRole)
                    if r:
                        visible.append(r)
        if not visible:
            _warn(self, "No visible rows to export.")
            return None
        html = PDFGenerator.build_all_products_html(visible)
        if fp is None:
            fp = os.path.join(tempfile.gettempdir(), "all_products_cost_summary.pdf")
        return fp if PDFGenerator.print_html_to_pdf(html, fp) else None

    def _export_all_pdf(self):
        fp, _ = QFileDialog.getSaveFileName(
            self, "Export All Products PDF",
            "all_products_cost_summary.pdf", "PDF Files (*.pdf)",
        )
        if not fp:
            return
        result = self._build_all_pdf_and_run(fp)
        if result:
            QMessageBox.information(self, "Exported", f"Saved:\n{result}")
        else:
            QMessageBox.warning(self, "Error", "PDF generation failed.")

    def _share_all_pdf(self):
        tmp = self._build_all_pdf_and_run()
        if tmp:
            PDFGenerator.share_pdf(tmp, self)
        else:
            QMessageBox.warning(self, "Error", "PDF generation failed.")


class RawMaterialsTab(QWidget):
    data_changed = Signal()

    def __init__(self, cm: CostingManager, parent=None):
        super().__init__(parent)
        self._cm = cm
        self.setStyleSheet(f"background: {C_BG};")

        root = QVBoxLayout(self)
        root.setContentsMargins(8, 8, 8, 8)
        root.setSpacing(0)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.setStyleSheet("QSplitter::handle { background: #2E2E45; width: 3px; }")

        # LEFT
        left = QWidget(); left.setStyleSheet(f"background: {C_BG};")
        lv = QVBoxLayout(left); lv.setContentsMargins(0, 0, 5, 0); lv.setSpacing(6)

        list_frame = QFrame(); list_frame.setStyleSheet(CARD_STYLE)
        ll = QVBoxLayout(list_frame); ll.setContentsMargins(10, 8, 10, 8); ll.setSpacing(6)
        ll.addWidget(_lbl("RAW MATERIALS", 9, True, C_GOLD))
        ll.addWidget(_divider())
        self._rm_table = _make_table(["Name", "Type", "Unit", "₹ / Unit", "Updated", "Actions"])
        self._rm_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self._rm_table.horizontalHeader().setSectionResizeMode(5, QHeaderView.ResizeMode.Fixed)
        self._rm_table.setColumnWidth(5, 76)
        self._rm_table.setMinimumHeight(160)
        self._rm_table.currentCellChanged.connect(self._on_rm_selected)
        ll.addWidget(self._rm_table, 1)
        lv.addWidget(list_frame, 1)

        add_frame, avl = _card("ADD RAW MATERIAL")
        ar1 = QHBoxLayout(); ar1.setSpacing(5)
        self._name_in    = _field("Material name")
        self._ut_combo   = _combo(list(UNIT_TYPE_LABELS.values())); self._ut_combo.setFixedWidth(120)
        self._unit_combo = _combo([]); self._unit_combo.setFixedWidth(90)
        self._ut_combo.currentIndexChanged.connect(self._sync_units)
        self._sync_units(0)
        ar1.addWidget(_lbl("Name", 11)); ar1.addWidget(self._name_in, 2)
        ar1.addWidget(_lbl("Type", 11)); ar1.addWidget(self._ut_combo)
        ar1.addWidget(_lbl("Unit", 11)); ar1.addWidget(self._unit_combo)
        avl.addLayout(ar1)
        ar2 = QHBoxLayout(); ar2.setSpacing(5)
        self._cost_in = _field("Cost / unit (₹)")
        self._cost_in.setValidator(QDoubleValidator(0, 9_999_999, 4))
        self._cost_in.setFixedWidth(140)
        add_rm_btn = _btn("Add Material", BTN_PRIMARY, 110)
        add_rm_btn.clicked.connect(self._add_material)
        ar2.addWidget(_lbl("Cost / Unit  ₹", 11)); ar2.addWidget(self._cost_in)
        ar2.addStretch(); ar2.addWidget(add_rm_btn)
        avl.addLayout(ar2)
        lv.addWidget(add_frame)
        splitter.addWidget(left)

        # RIGHT
        right = QWidget(); right.setStyleSheet(f"background: {C_BG};")
        rv = QVBoxLayout(right); rv.setContentsMargins(5, 0, 0, 0); rv.setSpacing(6)

        upd_frame, uvl = _card("UPDATE COST  (select a material first)")
        ur = QHBoxLayout(); ur.setSpacing(5)
        self._sel_lbl   = _lbl("— select a material —", 11, False, C_GHOST)
        self._new_cost  = _field("New cost / unit (₹)")
        self._new_cost.setValidator(QDoubleValidator(0, 9_999_999, 4))
        self._new_cost.setFixedWidth(130)
        self._cost_notes = _field("Notes (optional)")
        upd_btn = _btn("Update Cost", BTN_SUCCESS, 100)
        upd_btn.clicked.connect(self._update_cost)
        ur.addWidget(self._sel_lbl, 1); ur.addWidget(_lbl("New ₹", 11))
        ur.addWidget(self._new_cost); ur.addWidget(self._cost_notes); ur.addWidget(upd_btn)
        uvl.addLayout(ur)
        rv.addWidget(upd_frame)

        chart_frame, cvl = _card("COST HISTORY CHART")
        self._mat_chart = ChartWidget(); self._mat_chart.setMinimumHeight(160)
        cvl.addWidget(self._mat_chart)
        rv.addWidget(chart_frame, 1)

        ht_frame, hvl = _card("COST CHANGE LOG")
        self._hist_table = _make_table(["Changed At", "Old ₹", "New ₹", "Notes"])
        self._hist_table.setMaximumHeight(140); self._hist_table.setMinimumHeight(80)
        hvl.addWidget(self._hist_table)
        rv.addWidget(ht_frame)
        splitter.addWidget(right)

        splitter.setStretchFactor(0, 11); splitter.setStretchFactor(1, 9)
        QTimer.singleShot(0, lambda: splitter.setSizes(
            _responsive_splitter_sizes(splitter, [0.55, 0.45])
        ))
        root.addWidget(splitter, 1)
        self._selected_id: str | None = None
        self.load()

    def load(self):
        df = self._cm.get_raw_materials()
        self._rm_table.setRowCount(0)
        if df.empty:
            return
        for i, (_, row) in enumerate(df.iterrows()):
            self._rm_table.insertRow(i)
            self._rm_table.setItem(i, 0, _ti(row["Name"]))
            self._rm_table.setItem(i, 1, _ti(
                UNIT_TYPE_LABELS.get(row["UnitType"], row["UnitType"]), color=C_GOLD))
            self._rm_table.setItem(i, 2, _ti(row["Unit"]))
            self._rm_table.setItem(i, 3, _ti(f"₹ {float(row['CostPerUnit']):,.2f}",
                Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter))
            self._rm_table.setItem(i, 4, _ti(str(row.get("UpdatedAt", ""))[:16]))
            del_btn = _btn("Delete", BTN_DANGER); del_btn.setFixedHeight(24)
            del_btn.clicked.connect(lambda _, mid=row["MaterialId"]: self._delete_material(mid))
            btn_w = QWidget(); btn_l = QHBoxLayout(btn_w)
            btn_l.setContentsMargins(2, 2, 2, 2); btn_l.setSpacing(2); btn_l.addWidget(del_btn)
            self._rm_table.setCellWidget(i, 5, btn_w)
            self._rm_table.item(i, 0).setData(Qt.ItemDataRole.UserRole, row["MaterialId"])

    def _on_rm_selected(self, currentRow, *_):
        if currentRow < 0:
            return
        item = self._rm_table.item(currentRow, 0)
        if not item:
            return
        mid = item.data(Qt.ItemDataRole.UserRole)
        self._selected_id = mid
        self._sel_lbl.setText(f"Selected:  {item.text()}")
        self._load_history(mid, item.text())

    def _load_history(self, mid: str, name: str):
        df = self._cm.get_raw_material_cost_history(mid)
        self._hist_table.setRowCount(0)
        if df.empty:
            return
        for i, (_, row) in enumerate(df.iterrows()):
            self._hist_table.insertRow(i)
            self._hist_table.setItem(i, 0, _ti(str(row["ChangedAt"])[:16]))
            self._hist_table.setItem(i, 1, _ti(f"₹ {float(row['OldCost']):,.4f}",
                Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter))
            self._hist_table.setItem(i, 2, _ti(f"₹ {float(row['NewCost']):,.4f}",
                Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter, C_GOLD))
            self._hist_table.setItem(i, 3, _ti(str(row.get("Notes", ""))))
        trend = self._cm.get_material_cost_trend(mid)
        if not trend.empty:
            self._mat_chart.plot_material_trend(trend, name)

    def _sync_units(self, _=None):
        label  = self._ut_combo.currentText()
        ut_key = next((k for k, v in UNIT_TYPE_LABELS.items() if v == label), "count")
        self._unit_combo.clear()
        self._unit_combo.addItems(UNIT_TYPES.get(ut_key, []))

    def _add_material(self):
        label  = self._ut_combo.currentText()
        ut_key = next((k for k, v in UNIT_TYPE_LABELS.items() if v == label), "count")
        status, msg = self._cm.add_raw_material(
            self._name_in.text(), ut_key,
            self._unit_combo.currentText(), self._cost_in.text() or "0",
        )
        QMessageBox.information(self, status, msg)
        if status == "Success":
            self._name_in.clear(); self._cost_in.clear()
            self.load(); self.data_changed.emit()

    def _update_cost(self):
        if not self._selected_id:
            _warn(self, "Select a material first.")
            return
        new_cost = self._new_cost.text().strip()
        if not new_cost:
            _warn(self, "Enter the new cost.")
            return
        status, msg = self._cm.update_raw_material_cost(
            self._selected_id, new_cost, self._cost_notes.text()
        )
        QMessageBox.information(self, status, msg)
        if status == "Success":
            self._new_cost.clear(); self._cost_notes.clear()
            self.load()
            if self._rm_table.currentRow() >= 0:
                self._on_rm_selected(self._rm_table.currentRow(), 0)
            self.data_changed.emit()

    def _delete_material(self, material_id: str):
        reply = QMessageBox.question(
            self, "Confirm Delete",
            "Delete this raw material?\nCannot delete if used in any product BOM.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return
        status, msg = self._cm.delete_raw_material(material_id)
        QMessageBox.information(self, status, msg)
        if status == "Success":
            self._mat_chart.clear(); self._hist_table.setRowCount(0)
            self._selected_id = None; self.load(); self.data_changed.emit()


class ProductBOMTab(QWidget):
    data_changed = Signal()

    def __init__(self, cm: CostingManager, acc_mgr,
                 layer_injector, layer_manager_box, parent=None):
        super().__init__(parent)
        self._cm      = cm
        self._acc_mgr = acc_mgr
        self.setStyleSheet(f"background: {C_BG};")

        root = QVBoxLayout(self)
        root.setContentsMargins(8, 8, 8, 8)
        root.setSpacing(6)

        # Product selector
        sel_frame = QFrame(); sel_frame.setStyleSheet(CARD_STYLE); sel_frame.setMaximumHeight(50)
        sl = QHBoxLayout(sel_frame); sl.setContentsMargins(10, 6, 10, 6); sl.setSpacing(8)
        self._prod_combo = _combo(); self._prod_combo.setMinimumWidth(220)
        self._prod_combo.currentIndexChanged.connect(self._on_product_changed)
        sl.addWidget(_lbl("Product", bold=True)); sl.addWidget(self._prod_combo, 1)
        sl.addStretch()
        snap_btn = _btn("📸  Take Snapshot", BTN_PRIMARY, 145)
        snap_btn.setToolTip("Save a timestamped cost + sale-price record")
        snap_btn.clicked.connect(self._take_snapshot)
        sl.addWidget(snap_btn)
        root.addWidget(sel_frame)

        self._wl_panel = WarrantyLabourPanel(cm)
        self._wl_panel.config_changed.connect(self._refresh_breakdown)
        self._wl_panel.config_changed.connect(self.data_changed)
        root.addWidget(self._wl_panel)

        h_splitter = QSplitter(Qt.Orientation.Horizontal)
        h_splitter.setStyleSheet("QSplitter::handle { background: #2E2E45; width: 3px; }")

        bom_card = QFrame(); bom_card.setStyleSheet(CARD_STYLE); bom_card.setMinimumWidth(220)
        bom_layout = QVBoxLayout(bom_card)
        bom_layout.setContentsMargins(10, 8, 10, 8); bom_layout.setSpacing(6)
        bom_hdr = QHBoxLayout()
        bom_hdr.addWidget(_lbl("BILL OF MATERIALS", 9, True, C_GOLD))
        bom_hdr.addStretch()
        self._bom_count_lbl = _lbl("0 items", 9, False, C_GHOST)
        bom_hdr.addWidget(self._bom_count_lbl)
        bom_layout.addLayout(bom_hdr)
        bom_layout.addWidget(_divider())
        bom_layout.addWidget(layer_injector)
        self._bom_table = _make_table(
            ["Material", "Source", "Unit", "Qty", "Cost/Unit", "Line Cost", ""]
        )
        hdr = self._bom_table.horizontalHeader()
        hdr.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        for c in (1, 2, 3, 4, 5):
            hdr.setSectionResizeMode(c, QHeaderView.ResizeMode.ResizeToContents)
        hdr.setSectionResizeMode(6, QHeaderView.ResizeMode.Fixed)
        self._bom_table.setColumnWidth(6, 32)
        self._bom_table.setMinimumHeight(140)
        bom_layout.addWidget(self._bom_table, 1)
        h_splitter.addWidget(bom_card)

        right_tabs = QTabWidget(); right_tabs.setStyleSheet(_sub_tab_style())
        right_tabs.setMinimumWidth(280)

        add_mat_page = QWidget(); add_mat_page.setStyleSheet(f"background: {C_BG};")
        aml = QVBoxLayout(add_mat_page); aml.setContentsMargins(6, 6, 6, 6); aml.setSpacing(0)
        self._mat_selector = MultiMaterialSelectorWidget(cm)
        self._mat_selector.materials_add_requested.connect(self._add_multiple_to_bom)
        aml.addWidget(self._mat_selector, 1)
        right_tabs.addTab(add_mat_page, "+ Add Materials (Direct)")

        layer_mgmt_page = QWidget(); layer_mgmt_page.setStyleSheet(f"background: {C_BG};")
        lml = QVBoxLayout(layer_mgmt_page); lml.setContentsMargins(6, 6, 6, 6)
        lml.addWidget(layer_manager_box, 1)
        right_tabs.addTab(layer_mgmt_page, "🥞 Layer Templates")

        overhead_page = QWidget(); overhead_page.setStyleSheet(f"background: {C_BG};")
        ov = QVBoxLayout(overhead_page); ov.setContentsMargins(6, 6, 6, 6); ov.setSpacing(6)

        cct_frame, ccvl = _card("OVERHEAD COST TYPES")
        cct_r = QHBoxLayout(); cct_r.setSpacing(5)
        self._cct_name = _field("e.g. Labour, Electricity")
        self._cct_desc = _field("Description (optional)")
        add_cct_btn = _btn("+", BTN_OUTLINE, 30); add_cct_btn.clicked.connect(self._add_cct)
        cct_r.addWidget(self._cct_name, 2); cct_r.addWidget(self._cct_desc, 2); cct_r.addWidget(add_cct_btn)
        ccvl.addLayout(cct_r)
        self._cct_table = _make_table(["Name", "Description", ""])
        self._cct_table.setMinimumHeight(100)
        self._cct_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self._cct_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Fixed)
        self._cct_table.setColumnWidth(2, 40)
        ccvl.addWidget(self._cct_table, 1)
        ov.addWidget(cct_frame, 1)

        pcc_frame, pcvl = _card("CUSTOM COSTS  (this product)")
        pc_r = QHBoxLayout(); pc_r.setSpacing(5)
        self._pcc_type_combo = _combo(); self._pcc_type_combo.setMinimumWidth(110)
        self._pcc_rate = _field("Rate (₹)")
        self._pcc_rate.setValidator(QDoubleValidator(0, 999_999, 2)); self._pcc_rate.setFixedWidth(80)
        self._pcc_unit = _field("per unit"); self._pcc_unit.setFixedWidth(90)
        add_pcc_btn = _btn("Set Rate", BTN_SUCCESS, 74); add_pcc_btn.clicked.connect(self._set_pcc)
        pc_r.addWidget(_lbl("Type", 11)); pc_r.addWidget(self._pcc_type_combo)
        pc_r.addWidget(_lbl("₹", 11)); pc_r.addWidget(self._pcc_rate)
        pc_r.addWidget(self._pcc_unit); pc_r.addWidget(add_pcc_btn)
        pcvl.addLayout(pc_r)
        self._pcc_table = _make_table(["Overhead Type", "Rate (₹)", "Per", ""])
        self._pcc_table.setMinimumHeight(100)
        self._pcc_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self._pcc_table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.Fixed)
        self._pcc_table.setColumnWidth(3, 40)
        pcvl.addWidget(self._pcc_table, 1)
        ov.addWidget(pcc_frame, 1)
        right_tabs.addTab(overhead_page, "⚙  Overhead Config")

        bd_page = QWidget(); bd_page.setStyleSheet(f"background: {C_BG};")
        bd_layout = QVBoxLayout(bd_page); bd_layout.setContentsMargins(6, 6, 6, 6); bd_layout.setSpacing(6)
        bd_card = QFrame(); bd_card.setStyleSheet(CARD_STYLE)
        bd_inner = QVBoxLayout(bd_card); bd_inner.setContentsMargins(10, 8, 10, 8); bd_inner.setSpacing(6)
        self._breakdown_widget = CostBreakdownWidget(cm)
        bd_inner.addWidget(self._breakdown_widget, 1)
        bd_layout.addWidget(bd_card, 1)
        right_tabs.addTab(bd_page, "📊  Live Breakdown")

        h_splitter.addWidget(right_tabs)
        h_splitter.setStretchFactor(0, 2); h_splitter.setStretchFactor(1, 3)
        QTimer.singleShot(0, lambda: h_splitter.setSizes(
            _responsive_splitter_sizes(h_splitter, [0.46, 0.54])
        ))
        root.addWidget(h_splitter, 1)

        self._current_product_id: str | None   = None
        self._current_product_name: str | None = None
        self.refresh()

    def refresh(self):
        self._acc_mgr.load_data()
        current = self._prod_combo.currentText()
        self._prod_combo.blockSignals(True)
        self._prod_combo.clear()
        self._prod_combo.addItem("— Select product —", None)
        if not self._acc_mgr.products_data.empty:
            for _, row in self._acc_mgr.products_data.iterrows():
                self._prod_combo.addItem(row["Name"], (row["ProductId"], row["Name"]))
        idx = self._prod_combo.findText(current)
        self._prod_combo.setCurrentIndex(idx if idx >= 0 else 0)
        self._prod_combo.blockSignals(False)
        self._load_cct()
        self._reload_selector()
        if self._current_product_id:
            self._load_bom()
            self._load_pcc()
            self._refresh_breakdown()

    def _on_product_changed(self, _=None):
        data = self._prod_combo.currentData()
        if data:
            self._current_product_id, self._current_product_name = data
        else:
            self._current_product_id = self._current_product_name = None
        self._load_bom()
        self._load_pcc()
        self._refresh_breakdown()
        self._reload_selector()
        self._wl_panel.load_product(self._current_product_id)

    def _reload_selector(self):
        direct_ids: set[str] = set()
        if self._current_product_id:
            bom = self._cm.get_product_bom(self._current_product_id)
            if not bom.empty and "SourceType" in bom.columns:
                direct_ids = set(
                    bom[bom["SourceType"] == "direct"]["MaterialId"].tolist()
                )
        self._mat_selector.load(existing_direct_ids=direct_ids)

    def _load_bom(self):
        self._bom_table.setRowCount(0)
        self._bom_count_lbl.setText("0 items")
        if not self._current_product_id:
            return

        bom   = self._cm.get_product_bom(self._current_product_id)
        rm_df = self._cm.get_raw_materials()
        if bom.empty:
            return

        cost           = self._cm.calculate_product_cost(self._current_product_id)
        layer_breakdown = cost["layer_breakdown"]

        row_i = [0]
        RA = Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter

        def insert_separator(label: str, layer_id: str | None, is_direct: bool):
            """Insert a non-data header row for a layer group."""
            r = row_i[0]; self._bom_table.insertRow(r); row_i[0] += 1
            color = "#7EC8E3" if not is_direct else "#A0A0A0"
            bg    = "#1A2535"

            lbl_item = QTableWidgetItem(f"  ⬡  {label}")
            lbl_item.setFlags(Qt.ItemFlag.ItemIsEnabled)
            lbl_item.setBackground(QColor(bg))
            lbl_item.setForeground(QColor(color))
            f2 = QFont(FONT_UI, 8); f2.setBold(True); f2.setItalic(True)
            lbl_item.setFont(f2)
            self._bom_table.setItem(r, 0, lbl_item)
            self._bom_table.setSpan(r, 0, 1, 6)
            self._bom_table.setRowHeight(r, 22)

            if layer_id and not is_direct:
                rem_btn = _btn("× Layer", BTN_DANGER)
                rem_btn.setFixedSize(60, 20)
                rem_btn.setToolTip(f"Remove entire '{label}' layer from BOM")
                rem_btn.clicked.connect(
                    lambda _, lid=layer_id, lname=label: self._remove_layer(lid, lname)
                )
                w = QWidget(); w.setStyleSheet("background: transparent;")
                wl = QHBoxLayout(w); wl.setContentsMargins(2, 1, 2, 1); wl.addWidget(rem_btn)
                self._bom_table.setCellWidget(r, 6, w)

        def insert_bom_row(bom_row, cpu: float, source_label: str):
            r = row_i[0]; self._bom_table.insertRow(r); row_i[0] += 1
            qty = float(bom_row["QuantityUsed"])
            lc  = round(cpu * qty, 2)

            self._bom_table.setItem(r, 0, _ti(f"   {bom_row['MaterialName']}"))
            self._bom_table.setItem(r, 1, _ti(source_label, color=C_GHOST))
            self._bom_table.setItem(r, 2, _ti(bom_row["Unit"]))
            self._bom_table.setItem(r, 3, _ti(f"{qty:g}", RA))
            self._bom_table.setItem(r, 4, _ti(f"₹{cpu:,.4f}", RA))
            self._bom_table.setItem(r, 5, _ti(f"₹{lc:,.2f}", RA, C_GOLD))

            del_btn = _btn("×", BTN_DANGER); del_btn.setFixedSize(24, 24)
            del_btn.setToolTip("Remove this single BOM entry")
            del_btn.clicked.connect(lambda _, bid=bom_row["BOMId"]: self._remove_from_bom(bid))
            w = QWidget(); l = QHBoxLayout(w)
            l.setContentsMargins(2, 2, 2, 2); l.addWidget(del_btn)
            self._bom_table.setCellWidget(r, 6, w)

        for bucket in layer_breakdown:
            insert_separator(
                bucket["layer_name"],
                bucket["layer_id"],
                bucket["is_direct"],
            )
            mat_ids_in_bucket = {m["bom_id"] for m in bucket["materials"]}
            bucket_bom = bom[bom["BOMId"].isin(mat_ids_in_bucket)]
            for _, brow in bucket_bom.iterrows():
                m   = rm_df[rm_df["MaterialId"] == brow["MaterialId"]]
                cpu = float(m.iloc[0]["CostPerUnit"]) if not m.empty else 0.0
                src = "direct" if brow.get("SourceType") == "direct" else brow.get("LayerName", "layer")
                insert_bom_row(brow, cpu, src)

        represented_bom_ids = {
            m["bom_id"] for b in layer_breakdown for m in b["materials"]
        }
        orphan_rows = bom[~bom["BOMId"].isin(represented_bom_ids)]
        if not orphan_rows.empty:
            insert_separator("Unclassified", None, True)
            for _, brow in orphan_rows.iterrows():
                m   = rm_df[rm_df["MaterialId"] == brow["MaterialId"]]
                cpu = float(m.iloc[0]["CostPerUnit"]) if not m.empty else 0.0
                insert_bom_row(brow, cpu, "unknown")

        n = sum(1 for b in layer_breakdown for _ in b["materials"])
        self._bom_count_lbl.setText(f"{n} item{'s' if n != 1 else ''}")

    def _add_multiple_to_bom(self, selections: list[tuple[str, float]]):
        if not self._current_product_id:
            _warn(self, "Select a product first.")
            return
        added, skipped, errors = [], [], []
        for mid, qty in selections:
            status, msg = self._cm.add_material_to_product(
                self._current_product_id, self._current_product_name, mid, qty
            )
            if status == "Success":
                added.append(msg)
            elif "already added directly" in msg:
                skipped.append(msg)
            else:
                errors.append(msg)
        parts = []
        if added:   parts.append(f"✅  Added {len(added)} material(s) directly.")
        if skipped: parts.append(f"⚠️  {len(skipped)} already have direct entries (skipped).")
        if errors:  parts.append(f"❌  {len(errors)} error(s): {'; '.join(errors)}")
        QMessageBox.information(self, "BOM Update", "\n".join(parts) if parts else "No changes.")
        if added:
            self._load_bom(); self._refresh_breakdown(); self._reload_selector()
            self.data_changed.emit()

    def _remove_from_bom(self, bom_id: str):
        reply = QMessageBox.question(
            self, "Remove", "Remove this material entry from BOM?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return
        status, msg = self._cm.remove_material_from_product(bom_id)
        QMessageBox.information(self, status, msg)
        if status == "Success":
            self._load_bom(); self._refresh_breakdown(); self._reload_selector()
            self.data_changed.emit()

    def _remove_layer(self, layer_id: str, layer_name: str):
        reply = QMessageBox.question(
            self, "Remove Layer",
            f"Remove entire layer '{layer_name}' from this product's BOM?\n"
            f"All materials added by this layer will be removed.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return
        status, msg = self._cm.remove_layer_from_product(self._current_product_id, layer_id)
        QMessageBox.information(self, status, msg)
        if status == "Success":
            self._load_bom(); self._refresh_breakdown(); self._reload_selector()
            self.data_changed.emit()

    def _load_cct(self):
        df = self._cm.get_custom_cost_types()
        self._cct_table.setRowCount(0); self._pcc_type_combo.clear()
        if df.empty:
            return
        for i, (_, row) in enumerate(df.iterrows()):
            self._cct_table.insertRow(i)
            self._cct_table.setItem(i, 0, _ti(row["Name"], color=C_GOLD))
            self._cct_table.setItem(i, 1, _ti(str(row.get("Description", ""))))
            del_btn = _btn("×", BTN_DANGER); del_btn.setFixedSize(24, 24)
            del_btn.clicked.connect(lambda _, t=row["TypeId"]: self._del_cct(t))
            w = QWidget(); l = QHBoxLayout(w); l.setContentsMargins(2, 2, 2, 2); l.addWidget(del_btn)
            self._cct_table.setCellWidget(i, 2, w)
            self._pcc_type_combo.addItem(row["Name"], row["TypeId"])

    def _add_cct(self):
        name = self._cct_name.text().strip()
        if not name:
            _warn(self, "Enter a name."); return
        status, msg = self._cm.add_custom_cost_type(name, self._cct_desc.text())
        QMessageBox.information(self, status, msg)
        if status == "Success":
            self._cct_name.clear(); self._cct_desc.clear(); self._load_cct()

    def _del_cct(self, type_id: str):
        reply = QMessageBox.question(self, "Delete", "Delete this cost type?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        if reply != QMessageBox.StandardButton.Yes: return
        status, msg = self._cm.delete_custom_cost_type(type_id)
        QMessageBox.information(self, status, msg)
        if status == "Success": self._load_cct()

    def _load_pcc(self):
        self._pcc_table.setRowCount(0)
        if not self._current_product_id: return
        df = self._cm.get_product_custom_costs(self._current_product_id)
        if df.empty: return
        for i, (_, row) in enumerate(df.iterrows()):
            self._pcc_table.insertRow(i)
            self._pcc_table.setItem(i, 0, _ti(row["TypeName"], color=C_GOLD))
            self._pcc_table.setItem(i, 1, _ti(f"₹ {float(row['Rate']):,.2f}",
                Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter))
            self._pcc_table.setItem(i, 2, _ti(str(row.get("RateUnit", "per unit"))))
            del_btn = _btn("×", BTN_DANGER); del_btn.setFixedSize(24, 24)
            del_btn.clicked.connect(lambda _, p=row["PCCId"]: self._remove_pcc(p))
            w = QWidget(); l = QHBoxLayout(w); l.setContentsMargins(2, 2, 2, 2); l.addWidget(del_btn)
            self._pcc_table.setCellWidget(i, 3, w)

    def _set_pcc(self):
        if not self._current_product_id:
            _warn(self, "Select a product first."); return
        tid = self._pcc_type_combo.currentData()
        if not tid: _warn(self, "Select a cost type."); return
        rate = self._pcc_rate.text().strip()
        if not rate: _warn(self, "Enter a rate."); return
        ru = self._pcc_unit.text().strip() or "per unit"
        status, msg = self._cm.set_product_custom_cost(
            self._current_product_id, self._current_product_name, tid, rate, ru
        )
        QMessageBox.information(self, status, msg)
        if status == "Success":
            self._pcc_rate.clear(); self._load_pcc(); self._refresh_breakdown()
            self.data_changed.emit()

    def _remove_pcc(self, pcc_id: str):
        status, msg = self._cm.remove_product_custom_cost(pcc_id)
        QMessageBox.information(self, status, msg)
        if status == "Success":
            self._load_pcc(); self._refresh_breakdown(); self.data_changed.emit()

    def _refresh_breakdown(self):
        if not self._current_product_id:
            self._breakdown_widget.clear_breakdown()
        else:
            self._breakdown_widget.update_breakdown(
                self._current_product_id, self._current_product_name or ""
            )

    def _take_snapshot(self):
        if not self._current_product_id:
            _warn(self, "Select a product first."); return
        cost = self._cm.calculate_product_cost(self._current_product_id)
        sale_price = 0.0
        if not self._acc_mgr.products_data.empty:
            row = self._acc_mgr.products_data[
                self._acc_mgr.products_data["ProductId"] == self._current_product_id
            ]
            if not row.empty:
                try: sale_price = float(row.iloc[0]["Rate"])
                except Exception: pass
        dlg = SnapshotDialog(
            self._current_product_name, cost["final_total_cost"], sale_price, self
        )
        if dlg.exec() != QDialog.DialogCode.Accepted: return
        status, msg = self._cm.take_cost_snapshot(
            self._current_product_id, self._current_product_name,
            dlg.sale_price(), dlg.notes(), trigger="manual",
        )
        QMessageBox.information(self, status, msg)
        if status == "Success": self.data_changed.emit()


class SnapshotDialog(QDialog):
    def __init__(self, product_name: str, total_cost: float,
                 current_price: float, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Take Cost Snapshot")
        self.setFixedWidth(400)
        self.setStyleSheet(f"background: {C_BG};")
        vl = QVBoxLayout(self)
        vl.setContentsMargins(20, 16, 20, 16); vl.setSpacing(10)
        vl.addWidget(_lbl(f"Product: {product_name}", 12, True))
        vl.addWidget(_lbl(f"Final computed cost:  ₹{total_cost:,.2f}", 11, False, C_GOLD))
        vl.addWidget(_divider())
        form = QFormLayout(); form.setSpacing(8)
        self._price_in = _field(f"{current_price:.2f}")
        self._price_in.setValidator(QDoubleValidator(0, 99_999_999, 2))
        self._price_in.setText(f"{current_price:.2f}")
        self._notes_in = _field("Optional notes")
        form.addRow(_lbl("Sale Price  ₹"), self._price_in)
        form.addRow(_lbl("Notes"),         self._notes_in)
        vl.addLayout(form)
        vl.addWidget(_divider())
        bb = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        bb.accepted.connect(self.accept); bb.rejected.connect(self.reject)
        vl.addWidget(bb)

    def showEvent(self, event):
        super().showEvent(event)
        QTimer.singleShot(0, lambda: _center_on_screen(self))

    def sale_price(self) -> float:
        try: return float(self._price_in.text())
        except (ValueError, TypeError): return 0.0

    def notes(self) -> str:
        return self._notes_in.text().strip()


class AnalyticsTab(QWidget):

    def __init__(self, cm: CostingManager, acc_mgr, get_bridge_path_fn, parent=None):
        super().__init__(parent)
        self._cm          = cm
        self._acc_mgr     = acc_mgr
        self._bridge_path = get_bridge_path_fn
        self.setStyleSheet(f"background: {C_BG};")

        root = QVBoxLayout(self)
        root.setContentsMargins(8, 8, 8, 8); root.setSpacing(6)

        ctrl_frame = QFrame(); ctrl_frame.setStyleSheet(CARD_STYLE); ctrl_frame.setMaximumHeight(50)
        cl = QHBoxLayout(ctrl_frame); cl.setContentsMargins(10, 6, 10, 6); cl.setSpacing(6)
        self._prod_combo = _combo(); self._prod_combo.setMinimumWidth(190)
        self._chart_type = _combo([
            "Cost vs Price Timeline",
            "Cost Stack (Raw vs Overhead)",
            "Margin % Bars",
        ]); self._chart_type.setFixedWidth(200)
        load_btn = _btn("Refresh", BTN_PRIMARY, 80); load_btn.clicked.connect(self._load_chart)
        cl.addWidget(_lbl("Product", bold=True)); cl.addWidget(self._prod_combo, 1)
        cl.addWidget(_lbl("Chart", 11)); cl.addWidget(self._chart_type); cl.addWidget(load_btn)
        cl.addSpacing(4)
        exp_pdf = _btn("PDF",   BTN_OUTLINE, 54); exp_pdf.setToolTip("Export Cost Report as PDF")
        exp_xls = _btn("Excel", BTN_OUTLINE, 54); exp_xls.setToolTip("Export Cost Report as Excel")
        exp_wa  = _btn("📤",    BTN_OUTLINE, 36); exp_wa.setToolTip("Share via native share")
        exp_pdf.clicked.connect(self._export_pdf)
        exp_xls.clicked.connect(self._export_excel)
        exp_wa.clicked.connect(self._share_pdf)
        cl.addWidget(exp_pdf); cl.addWidget(exp_xls); cl.addWidget(exp_wa)
        root.addWidget(ctrl_frame)

        splitter = QSplitter(Qt.Orientation.Vertical)
        splitter.setStyleSheet("QSplitter::handle { background: #2E2E45; height: 3px; }")

        chart_frame = QFrame(); chart_frame.setStyleSheet(CARD_STYLE)
        cvl = QVBoxLayout(chart_frame); cvl.setContentsMargins(6, 6, 6, 6)
        self._chart = ChartWidget(); self._chart.setMinimumHeight(180); cvl.addWidget(self._chart)
        splitter.addWidget(chart_frame)

        hist_frame = QFrame(); hist_frame.setStyleSheet(CARD_STYLE)
        hvl = QVBoxLayout(hist_frame); hvl.setContentsMargins(10, 6, 10, 6); hvl.setSpacing(5)
        hvl.addWidget(_lbl("SNAPSHOT HISTORY", 9, True, C_GOLD)); hvl.addWidget(_divider())
        self._hist_table = _make_table([
            "Snapshot At", "Final Cost", "Sale Price",
            "Margin ₹", "Margin %", "Warranty%", "Labour%",
            "Raw Mat.", "Overhead", "Trigger", "Notes", "",
        ])
        hh = self._hist_table.horizontalHeader()
        hh.setSectionResizeMode(0,  QHeaderView.ResizeMode.ResizeToContents)
        hh.setSectionResizeMode(11, QHeaderView.ResizeMode.Fixed)
        self._hist_table.setColumnWidth(11, 40)
        self._hist_table.setMinimumHeight(110)
        hvl.addWidget(self._hist_table, 1)
        splitter.addWidget(hist_frame)

        splitter.setStretchFactor(0, 3); splitter.setStretchFactor(1, 2)
        QTimer.singleShot(0, lambda: splitter.setSizes(
            _responsive_splitter_sizes(splitter, [0.60, 0.40])
        ))
        root.addWidget(splitter, 1)
        self._current_df: pd.DataFrame | None = None
        self.refresh()

    def refresh(self):
        self._acc_mgr.load_data()
        current = self._prod_combo.currentText()
        self._prod_combo.blockSignals(True)
        self._prod_combo.clear()
        self._prod_combo.addItem("— Select product —", None)
        if not self._acc_mgr.products_data.empty:
            for _, row in self._acc_mgr.products_data.iterrows():
                self._prod_combo.addItem(row["Name"], (row["ProductId"], row["Name"]))
        idx = self._prod_combo.findText(current)
        self._prod_combo.setCurrentIndex(idx if idx >= 0 else 0)
        self._prod_combo.blockSignals(False)

    def _load_chart(self):
        data = self._prod_combo.currentData()
        if not data: _warn(self, "Select a product first."); return
        product_id, product_name = data
        df = self._cm.get_cost_vs_price_timeline(product_id)
        self._current_df = df
        self._load_hist_table(product_id, product_name)
        if df.empty:
            self._chart.clear()
            QMessageBox.information(self, "No Data",
                "No snapshots found.\nTake a snapshot from the BOM tab first.")
            return
        ct = self._chart_type.currentText()
        if ct == "Cost vs Price Timeline":     self._chart.plot_cost_timeline(df, product_name)
        elif ct == "Cost Stack (Raw vs Overhead)": self._chart.plot_cost_stack(df, product_name)
        elif ct == "Margin % Bars":            self._chart.plot_margin_bars(df, product_name)

    def _load_hist_table(self, product_id: str, product_name: str):
        snaps = self._cm.get_product_cost_history(product_id)
        self._hist_table.setRowCount(0)
        if snaps.empty: return
        RA = Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
        for i, (_, row) in enumerate(snaps.iloc[::-1].reset_index(drop=True).iterrows()):
            self._hist_table.insertRow(i)
            margin = float(row.get("Margin", 0) or 0)
            m_pct  = float(row.get("MarginPct", 0) or 0)
            color  = "#7AE07A" if margin >= 0 else "#E07070"
            fc     = float(row.get("FinalCost", row.get("TotalCost", 0)))
            self._hist_table.setItem(i,  0, _ti(str(row["SnapshotAt"])[:16]))
            self._hist_table.setItem(i,  1, _ti(f"₹ {fc:,.2f}", RA))
            self._hist_table.setItem(i,  2, _ti(f"₹ {float(row['SalePrice']):,.2f}", RA))
            self._hist_table.setItem(i,  3, _ti(f"₹ {margin:,.2f}", RA, color))
            self._hist_table.setItem(i,  4, _ti(f"{m_pct:.1f}%", RA, color))
            self._hist_table.setItem(i,  5, _ti(f"{float(row.get('WarrantyPct',0)):.1f}%", RA, C_WHITE_MUT))
            self._hist_table.setItem(i,  6, _ti(f"{float(row.get('LabourPct',0)):.1f}%", RA, C_WHITE_MUT))
            self._hist_table.setItem(i,  7, _ti(f"₹ {float(row.get('RawMaterialCost',0)):,.2f}", RA))
            self._hist_table.setItem(i,  8, _ti(f"₹ {float(row.get('TotalCustomCost',0)):,.2f}", RA))
            self._hist_table.setItem(i,  9, _ti(str(row.get("TriggerType", ""))))
            self._hist_table.setItem(i, 10, _ti(str(row.get("Notes", ""))))
            snap_id = row["SnapshotId"]
            del_btn = _btn("×", BTN_DANGER); del_btn.setFixedSize(24, 24)
            del_btn.clicked.connect(
                lambda _, sid=snap_id, pn=product_name, pid=product_id:
                    self._del_snapshot(sid, pid, pn)
            )
            w = QWidget(); l = QHBoxLayout(w); l.setContentsMargins(2, 2, 2, 2); l.addWidget(del_btn)
            self._hist_table.setCellWidget(i, 11, w)

    def _del_snapshot(self, snap_id: str, product_id: str, product_name: str):
        reply = QMessageBox.question(self, "Delete Snapshot", "Delete this snapshot?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        if reply != QMessageBox.StandardButton.Yes: return
        status, msg = self._cm.delete_snapshot(snap_id)
        QMessageBox.information(self, status, msg)
        if status == "Success":
            self._load_hist_table(product_id, product_name); self._load_chart()

    def _get_product_info(self) -> tuple[str, str] | None:
        data = self._prod_combo.currentData()
        if not data: _warn(self, "Select a product first."); return None
        return data

    def _export_pdf(self):
        info = self._get_product_info()
        if not info: return
        product_id, product_name = info
        df   = self._cm.get_product_cost_history(product_id)
        cost = self._cm.calculate_product_cost(product_id)
        html = PDFGenerator.build_analytics_html(df, product_name, cost)
        fp, _ = QFileDialog.getSaveFileName(
            self, "Export Cost Report (PDF)",
            f"{product_name.replace(' ', '_')}_cost_report.pdf", "PDF Files (*.pdf)",
        )
        if fp:
            if PDFGenerator.print_html_to_pdf(html, fp):
                QMessageBox.information(self, "Exported", f"Saved to:\n{fp}")
            else:
                QMessageBox.warning(self, "Error", "PDF generation failed.")

    def _share_pdf(self):
        info = self._get_product_info()
        if not info: return
        product_id, product_name = info
        df   = self._cm.get_product_cost_history(product_id)
        cost = self._cm.calculate_product_cost(product_id)
        html = PDFGenerator.build_analytics_html(df, product_name, cost)
        tmp  = os.path.join(tempfile.gettempdir(),
                            f"CostReport_{product_name.replace(' ', '_')}.pdf")
        if PDFGenerator.print_html_to_pdf(html, tmp):
            PDFGenerator.share_pdf(tmp, self)
        else:
            QMessageBox.warning(self, "Error", "PDF generation failed.")

    def _export_excel(self):
        info = self._get_product_info()
        if not info: return
        product_id, product_name = info
        df = self._cm.get_product_cost_history(product_id)
        if df.empty: _warn(self, "No snapshots to export."); return
        fp, _ = QFileDialog.getSaveFileName(
            self, "Export Cost Report (Excel)",
            f"{product_name.replace(' ', '_')}_cost_report.xlsx", "Excel Files (*.xlsx)",
        )
        if not fp: return
        cost  = self._cm.calculate_product_cost(product_id)
        bom   = self._cm.get_product_bom(product_id)
        pcc   = self._cm.get_product_custom_costs(product_id)
        rm_df = self._cm.get_raw_materials()
        bom_rows = []
        for _, row in bom.iterrows():
            m   = rm_df[rm_df["MaterialId"] == row["MaterialId"]]
            cpu = float(m.iloc[0]["CostPerUnit"]) if not m.empty else 0.0
            bom_rows.append({
                "Material":      row["MaterialName"],
                "Source":        row.get("LayerName") or "Direct",
                "Unit":          row["Unit"],
                "Quantity Used": float(row["QuantityUsed"]),
                "Cost per Unit": cpu,
                "Line Cost":     round(float(row["QuantityUsed"]) * cpu, 4),
            })
        pcc_rows = [
            {"Overhead Type": r["TypeName"], "Rate (₹)": float(r["Rate"]),
             "Rate Unit": r.get("RateUnit", "per unit")}
            for _, r in pcc.iterrows()
        ]
        exp_cols  = ["SnapshotAt", "FinalCost", "TotalCost", "SalePrice", "Margin",
                     "MarginPct", "RawMaterialCost", "TotalCustomCost",
                     "WarrantyPct", "WarrantyCost", "LabourPct", "LabourCost",
                     "TriggerType", "Notes"]
        export_df = df[[c for c in exp_cols if c in df.columns]].copy()
        try:
            with pd.ExcelWriter(fp, engine="openpyxl") as writer:
                export_df.to_excel(writer, sheet_name="Snapshots", index=False)
                if bom_rows:
                    pd.DataFrame(bom_rows).to_excel(writer, sheet_name="BOM", index=False)
                if pcc_rows:
                    pd.DataFrame(pcc_rows).to_excel(writer, sheet_name="Overheads", index=False)
            QMessageBox.information(self, "Exported", f"Saved to:\n{fp}")
        except Exception as e:
            _warn(self, f"Export failed: {e}")


class LayerInjectionPanel(QWidget):
    def __init__(self, costing_manager, get_active_product_id_cb,
                 get_active_product_name_cb, on_success_cb):
        super().__init__()
        self.manager          = costing_manager
        self.get_product_id   = get_active_product_id_cb
        self.get_product_name = get_active_product_name_cb
        self.success_callback = on_success_cb
        self._init_ui()

    def _init_ui(self):
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 4, 0, 8)
        lbl = QLabel("⚡ Inject Layer(s):")
        lbl.setStyleSheet("font-weight: bold; color: #E0E0E0;")
        layout.addWidget(lbl)

        self.layer_dropdown = QComboBox()
        self.layer_dropdown.setEditable(True)
        self.layer_dropdown.lineEdit().setReadOnly(True)
        self.layer_dropdown.setMinimumWidth(220)
        self.layer_dropdown.setMinimumHeight(26)
        self.layer_dropdown.setStyleSheet("""
            QComboBox { color:#FFFFFF; background-color:#1E1E1E; border:1px solid #555;
                        border-radius:4px; padding-left:6px; }
            QComboBox::drop-down { border:none; background:transparent; }
            QComboBox QAbstractItemView { color:#E0E0E0; background-color:#1E1E1E;
                selection-background-color:#0288D1; selection-color:#FFFFFF;
                border:1px solid #555; }
        """)
        self.layer_dropdown.lineEdit().installEventFilter(self)
        self.layer_dropdown.view().pressed.connect(self._force_combobox_text_refresh)
        layout.addWidget(self.layer_dropdown)

        self.inject_btn = QPushButton("Apply Selected Layers")
        self.inject_btn.setStyleSheet("""
            QPushButton { font-weight:bold; background-color:#0288D1; color:white;
                padding:3px 10px; border-radius:4px; border:none; }
            QPushButton:hover { background-color:#039BE5; }
            QPushButton:disabled { background-color:#424242; color:#757575; }
        """)
        self.inject_btn.clicked.connect(self._inject_now)
        layout.addWidget(self.inject_btn)

        info_lbl = QLabel("Re-injecting a layer updates its existing BOM entries")
        info_lbl.setStyleSheet("color: #888; font-size: 10px; font-style: italic;")
        layout.addWidget(info_lbl)
        layout.addStretch()
        self.refresh_dropdown()

    def eventFilter(self, watched, event):
        if watched == self.layer_dropdown.lineEdit() and \
                event.type() == QEvent.Type.MouseButtonPress:
            if not self.layer_dropdown.view().isVisible():
                self.layer_dropdown.showPopup()
                return True
        return super().eventFilter(watched, event)

    def refresh_dropdown(self):
        layers = self.manager.get_layer_names()
        model  = QStandardItemModel()
        model.itemChanged.connect(self._force_combobox_text_refresh)
        if layers:
            for name in layers:
                item = QStandardItem(name)
                item.setFlags(Qt.ItemFlag.ItemIsUserCheckable | Qt.ItemFlag.ItemIsEnabled)
                item.setCheckState(Qt.CheckState.Unchecked)
                model.appendRow(item)
            self.layer_dropdown.setModel(model)
            self.layer_dropdown.setEditText("Select layers to apply...")
            self.inject_btn.setEnabled(True)
        else:
            item = QStandardItem("No saved templates found")
            item.setFlags(Qt.ItemFlag.ItemIsEnabled)
            model.appendRow(item)
            self.layer_dropdown.setModel(model)
            self.layer_dropdown.setEditText("No layers available")
            self.inject_btn.setEnabled(False)

    def _force_combobox_text_refresh(self, *_):
        QTimer.singleShot(0, self._update_combo_text)

    def _update_combo_text(self):
        selected = self._get_selected_layers()
        if not selected:
            self.layer_dropdown.setEditText("Select layers to apply...")
        elif len(selected) == 1:
            self.layer_dropdown.setEditText(selected[0])
        else:
            self.layer_dropdown.setEditText(f"{len(selected)} Layers Selected")

    def _get_selected_layers(self) -> list[str]:
        model = self.layer_dropdown.model()
        if not model:
            return []
        return [
            model.item(i).text()
            for i in range(model.rowCount())
            if model.item(i) and
               (model.item(i).flags() & Qt.ItemFlag.ItemIsUserCheckable) and
               model.item(i).checkState() == Qt.CheckState.Checked
        ]

    def _inject_now(self):
        p_id   = self.get_product_id()
        p_name = self.get_product_name()
        layers = self._get_selected_layers()
        if not p_id:
            QMessageBox.warning(self, "Context Requirement", "Select a product first.")
            return
        if not layers:
            QMessageBox.warning(self, "Selection Empty", "Check at least one layer.")
            return
        results = []
        for layer_name in layers:
            status, message = self.manager.inject_layer_to_product(p_id, p_name, layer_name)
            results.append((layer_name, status, message))
        ok     = [r for r in results if r[1] == "Success"]
        failed = [r for r in results if r[1] != "Success"]
        parts  = []
        if ok:
            parts.append(f"✅  {len(ok)} layer(s) injected successfully.")
        if failed:
            parts.append("❌  " + "; ".join(f"{r[0]}: {r[2]}" for r in failed))
        QMessageBox.information(self, "Layer Injection", "\n".join(parts))
        self.refresh_dropdown()
        self.success_callback()


class IntegratedLayerPresetCreator(QGroupBox):
    def __init__(self, costing_manager: CostingManager, on_preset_pool_changed_cb):
        super().__init__("🥞 Reusable Layer Blueprint Registry")
        self.manager         = costing_manager
        self.on_pool_changed = on_preset_pool_changed_cb
        self.staged_items: list[dict] = []
        self.is_refreshing   = False
        self._init_ui()

    @staticmethod
    def _dark_btn_style() -> str:
        return ("QPushButton { background-color:#2E2E2E; color:white; border:1px solid #555;"
                "border-radius:4px; font-size:15px; font-weight:bold; }"
                "QPushButton:hover { background-color:#3A3A3A; }"
                "QPushButton:disabled { color:#555; }")

    @staticmethod
    def _light_btn_style() -> str:
        return ("QPushButton { background-color:#D0D0D0; color:#212121; border:1px solid #9E9E9E;"
                "border-radius:4px; font-size:15px; font-weight:bold; }"
                "QPushButton:hover { background-color:#BDBDBD; }")

    @staticmethod
    def _dark_spin_style() -> str:
        return ("QDoubleSpinBox { font-size:12px; font-weight:500; color:#F5F5F5;"
                "background-color:#1E1E1E; border:1px solid #555; border-radius:4px; padding:2px 4px; }")

    @staticmethod
    def _light_spin_style() -> str:
        return ("QDoubleSpinBox { font-size:12px; font-weight:500; color:#212121;"
                "background-color:#EAEAEA; border:1px solid #9E9E9E; border-radius:4px; padding:2px 4px; }")

    @staticmethod
    def _make_stepper(spin_style, btn_style, step=0.01):
        container = QWidget(); container.setStyleSheet("background: transparent;")
        layout = QHBoxLayout(container)
        layout.setContentsMargins(4, 4, 4, 4); layout.setSpacing(2)
        minus = QPushButton("−"); minus.setFixedSize(28, 28); minus.setStyleSheet(btn_style)
        spin  = QtySpinBox(); spin.setFixedSize(72, 28)
        spin.setAlignment(Qt.AlignmentFlag.AlignCenter); spin.setStyleSheet(spin_style)
        spin.setSingleStep(step); container.qty_spin = spin
        plus  = QPushButton("+"); plus.setFixedSize(28, 28); plus.setStyleSheet(btn_style)
        minus.clicked.connect(lambda _, s=spin: s.setValue(max(s.minimum(), s.value() - s.singleStep())))
        plus.clicked.connect( lambda _, s=spin: s.setValue(min(s.maximum(), s.value() + s.singleStep())))
        layout.addStretch(); layout.addWidget(minus); layout.addWidget(spin)
        layout.addWidget(plus); layout.addStretch()
        return minus, spin, plus, container

    def _init_ui(self):
        main_layout = QHBoxLayout(self)
        main_layout.setSpacing(12); main_layout.setContentsMargins(8, 8, 8, 8)

        left_panel = QVBoxLayout(); left_panel.setSpacing(6)
        left_panel.addWidget(QLabel("📋 Step 1: Pick Components & Set Initial Qty"))
        self.mat_search = QLineEdit()
        self.mat_search.setPlaceholderText("🔍 Filter materials by keyword...")
        self.mat_search.setMinimumHeight(28)
        self.mat_search.textChanged.connect(self._filter_materials)
        left_panel.addWidget(self.mat_search)

        self.mat_table = QTableWidget(0, 3)
        self.mat_table.setHorizontalHeaderLabels(["", "Material Description", "Qty"])
        hh = self.mat_table.horizontalHeader()
        hh.setSectionResizeMode(0, QHeaderView.ResizeMode.Fixed)
        hh.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        hh.setSectionResizeMode(2, QHeaderView.ResizeMode.Fixed)
        self.mat_table.setColumnWidth(0, 32); self.mat_table.setColumnWidth(2, 155)
        self.mat_table.verticalHeader().setVisible(False)
        self.mat_table.verticalHeader().setDefaultSectionSize(40)
        self.mat_table.setSelectionMode(QAbstractItemView.SelectionMode.NoSelection)
        self.mat_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.mat_table.setAlternatingRowColors(True)
        self.mat_table.setShowGrid(False)
        self.mat_table.setVerticalScrollMode(QAbstractItemView.ScrollMode.ScrollPerPixel)
        self.mat_table.itemChanged.connect(self._handle_table_checkbox_toggled)
        left_panel.addWidget(self.mat_table, 1)
        main_layout.addLayout(left_panel, 1)

        sep = QFrame(); sep.setFrameShape(QFrame.Shape.VLine)
        sep.setFrameShadow(QFrame.Shadow.Sunken); sep.setStyleSheet("color: #3A3A3A;")
        main_layout.addWidget(sep)

        right_panel = QVBoxLayout(); right_panel.setSpacing(6)
        form = QFormLayout(); form.setSpacing(6)
        self.name_input = QLineEdit()
        self.name_input.setPlaceholderText("e.g., OUTER CHASSIS SHEET COATING")
        self.name_input.setMinimumHeight(28)
        form.addRow("Blueprint Profile Name:", self.name_input)
        right_panel.addLayout(form)
        right_panel.addWidget(QLabel("🥞 Step 2: Staged Layer Blueprint Composition (Editable)"))

        self.staging_table = QTableWidget(0, 3)
        self.staging_table.setHorizontalHeaderLabels(["Staged Material", "Qty (Editable)", ""])
        sh = self.staging_table.horizontalHeader()
        sh.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        sh.setSectionResizeMode(1, QHeaderView.ResizeMode.Fixed)
        sh.setSectionResizeMode(2, QHeaderView.ResizeMode.Fixed)
        self.staging_table.setColumnWidth(1, 165); self.staging_table.setColumnWidth(2, 46)
        self.staging_table.verticalHeader().setVisible(False)
        self.staging_table.verticalHeader().setDefaultSectionSize(40)
        self.staging_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.staging_table.setSelectionMode(QAbstractItemView.SelectionMode.NoSelection)
        self.staging_table.setAlternatingRowColors(True)
        self.staging_table.setShowGrid(False)
        self.staging_table.setVerticalScrollMode(QAbstractItemView.ScrollMode.ScrollPerPixel)
        right_panel.addWidget(self.staging_table, 1)

        action_row = QHBoxLayout(); action_row.setSpacing(8)
        self.clear_btn = QPushButton("Clear Canvas"); self.clear_btn.setMinimumHeight(30)
        self.clear_btn.clicked.connect(self._clear_all)
        self.save_btn = QPushButton("💾 Commit & Save Layer"); self.save_btn.setMinimumHeight(30)
        self.save_btn.setStyleSheet(
            "QPushButton { font-weight:bold; background-color:#2E7D32; color:white;"
            "border-radius:4px; border:none; padding:4px 10px; }"
            "QPushButton:hover { background-color:#388E3C; }"
        )
        self.save_btn.clicked.connect(self._save_layer)
        action_row.addWidget(self.clear_btn); action_row.addWidget(self.save_btn)
        right_panel.addLayout(action_row)

        right_panel.addWidget(QLabel("🛠️ Template Registry Actions:"))
        tmpl_row = QHBoxLayout(); tmpl_row.setSpacing(6)
        self.saved_layers_dropdown = QComboBox(); self.saved_layers_dropdown.setMinimumHeight(28)
        self.load_btn = QPushButton("✏️ Load Profile"); self.load_btn.setMinimumHeight(28)
        self.del_btn  = QPushButton("🗑️ Delete");       self.del_btn.setMinimumHeight(28)
        self.del_btn.setStyleSheet(
            "QPushButton { background-color:#C62828; color:white; border-radius:4px; border:none; padding:2px 8px; }"
            "QPushButton:hover { background-color:#D32F2F; }"
        )
        self.load_btn.clicked.connect(self._load_selected_template)
        self.del_btn.clicked.connect(self._delete_selected_template)
        tmpl_row.addWidget(self.saved_layers_dropdown, 2)
        tmpl_row.addWidget(self.load_btn, 1); tmpl_row.addWidget(self.del_btn, 1)
        right_panel.addLayout(tmpl_row)
        main_layout.addLayout(right_panel, 1)

        self.refresh_materials(); self.refresh_saved_presets()

    def refresh_materials(self):
        self.is_refreshing = True
        df = self.manager.get_raw_materials()
        self.mat_table.setRowCount(0)
        if df.empty:
            self.mat_table.setRowCount(1)
            placeholder = QTableWidgetItem("No warehouse inventory definitions found.")
            placeholder.setFlags(Qt.ItemFlag.ItemIsEnabled)
            self.mat_table.setItem(0, 0, placeholder)
            self.mat_table.setSpan(0, 0, 1, 3)
            self.is_refreshing = False; return
        for i, row in df.iterrows():
            self.mat_table.insertRow(i)
            cb_item = QTableWidgetItem()
            cb_item.setData(Qt.ItemDataRole.UserRole, row["MaterialId"])
            cb_item.setFlags(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsUserCheckable | Qt.ItemFlag.ItemIsSelectable)
            cb_item.setCheckState(Qt.CheckState.Unchecked)
            cb_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.mat_table.setItem(i, 0, cb_item)
            lbl_item = QTableWidgetItem(f" {row['Name']} ({row['Unit']})")
            lbl_item.setData(Qt.ItemDataRole.UserRole, row["MaterialId"])
            lbl_item.setFlags(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable)
            self.mat_table.setItem(i, 1, lbl_item)
            _m, _s, _p, container = self._make_stepper(
                self._dark_spin_style(), self._dark_btn_style(), step=0.01
            )
            _s.valueChanged.connect(lambda val, r_idx=i: self._handle_picker_spinbox_value_changed(r_idx, val))
            self.mat_table.setCellWidget(i, 2, container)
        self.is_refreshing = False

    def _filter_materials(self, text: str):
        text = text.strip().lower()
        for i in range(self.mat_table.rowCount()):
            lbl = self.mat_table.item(i, 1)
            self.mat_table.setRowHidden(i, bool(text) and (not lbl or text not in lbl.text().lower()))

    def _handle_table_checkbox_toggled(self, item):
        if self.is_refreshing or item.column() != 0: return
        m_id      = item.data(Qt.ItemDataRole.UserRole)
        row_idx   = item.row()
        lbl_item  = self.mat_table.item(row_idx, 1)
        m_lbl     = lbl_item.text().strip() if lbl_item else str(m_id)
        qty_widget = self.mat_table.cellWidget(row_idx, 2)
        qty = qty_widget.qty_spin.value() if qty_widget and hasattr(qty_widget, "qty_spin") else 1.0
        if item.checkState() == Qt.CheckState.Checked:
            found = next((x for x in self.staged_items if x["material_id"] == m_id), None)
            if found:
                found["quantity_used"] = qty
            else:
                self.staged_items.append({"material_id": m_id, "label": m_lbl, "quantity_used": qty})
        else:
            self.staged_items = [x for x in self.staged_items if x["material_id"] != m_id]
        self._redraw_staging()

    def _handle_picker_spinbox_value_changed(self, row_idx, val):
        cb_item = self.mat_table.item(row_idx, 0)
        if not cb_item or cb_item.checkState() != Qt.CheckState.Checked: return
        m_id = cb_item.data(Qt.ItemDataRole.UserRole)
        for existing in self.staged_items:
            if existing["material_id"] == m_id:
                existing["quantity_used"] = float(val); break
        self._redraw_staging()

    def _handle_canvas_spinbox_value_changed(self, staged_idx, val):
        if 0 <= staged_idx < len(self.staged_items):
            self.staged_items[staged_idx]["quantity_used"] = float(val)
            target_id = self.staged_items[staged_idx]["material_id"]
            self.is_refreshing = True
            for i in range(self.mat_table.rowCount()):
                cb_item = self.mat_table.item(i, 0)
                if cb_item and cb_item.data(Qt.ItemDataRole.UserRole) == target_id:
                    cw = self.mat_table.cellWidget(i, 2)
                    if cw and hasattr(cw, "qty_spin"): cw.qty_spin.setValue(float(val))
                    break
            self.is_refreshing = False

    def _redraw_staging(self):
        self.staging_table.setRowCount(0)
        for i, item in enumerate(self.staged_items):
            self.staging_table.insertRow(i)
            lbl_cell = QTableWidgetItem(item["label"]); lbl_cell.setFlags(Qt.ItemFlag.ItemIsEnabled)
            self.staging_table.setItem(i, 0, lbl_cell)
            _m, canvas_spin, _p, container = self._make_stepper(
                self._light_spin_style(), self._light_btn_style(), step=1.0
            )
            canvas_spin.setValue(item["quantity_used"])
            canvas_spin.valueChanged.connect(
                lambda val, idx=i: self._handle_canvas_spinbox_value_changed(idx, val)
            )
            self.staging_table.setCellWidget(i, 1, container)
            drop_btn = QPushButton("✕"); drop_btn.setFixedSize(36, 28)
            drop_btn.setStyleSheet(
                "QPushButton { background-color:#B71C1C; color:#FFFFFF; font-weight:bold;"
                "font-size:13px; border-radius:4px; border:none; }"
                "QPushButton:hover { background-color:#D32F2F; }"
            )
            drop_btn.clicked.connect(lambda checked=False, idx=i: self._drop_staged_item(idx))
            w = QWidget(); w.setStyleSheet("background: transparent;")
            wl = QHBoxLayout(w); wl.setContentsMargins(4, 5, 4, 5); wl.addWidget(drop_btn)
            self.staging_table.setCellWidget(i, 2, w)

    def _drop_staged_item(self, idx: int):
        if idx >= len(self.staged_items): return
        target_id = self.staged_items[idx]["material_id"]
        self.is_refreshing = True
        for i in range(self.mat_table.rowCount()):
            cb_item = self.mat_table.item(i, 0)
            if cb_item and cb_item.data(Qt.ItemDataRole.UserRole) == target_id:
                cb_item.setCheckState(Qt.CheckState.Unchecked); break
        self.is_refreshing = False
        del self.staged_items[idx]
        self._redraw_staging()

    def _clear_all(self):
        self.staged_items.clear(); self.name_input.clear(); self.mat_search.clear()
        self.refresh_materials(); self._redraw_staging()

    def refresh_saved_presets(self):
        self.saved_layers_dropdown.clear()
        layers = self.manager.get_layer_names()
        if layers:
            self.saved_layers_dropdown.addItems(layers)
            self.load_btn.setEnabled(True); self.del_btn.setEnabled(True)
        else:
            self.saved_layers_dropdown.addItem("No saved templates found")
            self.load_btn.setEnabled(False); self.del_btn.setEnabled(False)

    def _save_layer(self):
        name = self.name_input.text().strip()
        if not name:
            QMessageBox.warning(self, "Missing Name", "Enter a Layer Blueprint Name before saving."); return
        if not self.staged_items:
            QMessageBox.warning(self, "No Materials", "Stage at least one material before saving."); return
        status, msg = self.manager.save_layer(name, self.staged_items)
        if status == "Success":
            QMessageBox.information(self, "Saved", msg)
            self._clear_all(); self.refresh_saved_presets(); self.on_pool_changed()
        else:
            QMessageBox.critical(self, "Error", msg)

    def _load_selected_template(self):
        name = self.saved_layers_dropdown.currentText()
        if not name or name == "No saved templates found": return
        self._clear_all(); self.name_input.setText(name)
        df     = self.manager.get_all_layers()
        target = df[df["LayerName"] == name].sort_values("MaterialName")
        self.is_refreshing = True
        for _, row in target.iterrows():
            m_id  = row["MaterialId"]
            m_qty = float(row["QuantityUsed"])
            m_lbl = f"{row['MaterialName']} ({row['Unit']})"
            self.staged_items.append({"material_id": m_id, "label": m_lbl, "quantity_used": m_qty})
            for i in range(self.mat_table.rowCount()):
                cb_item = self.mat_table.item(i, 0)
                if cb_item and cb_item.data(Qt.ItemDataRole.UserRole) == m_id:
                    cb_item.setCheckState(Qt.CheckState.Checked)
                    cw = self.mat_table.cellWidget(i, 2)
                    if cw and hasattr(cw, "qty_spin"): cw.qty_spin.setValue(m_qty)
                    break
        self.is_refreshing = False
        self._redraw_staging()

    def _delete_selected_template(self):
        name = self.saved_layers_dropdown.currentText()
        if not name or name == "No saved templates found": return
        confirm = QMessageBox.question(self, "Confirm Delete",
                                       f"Delete preset layer layout '{name}'?")
        if confirm == QMessageBox.StandardButton.Yes:
            self.manager.delete_layer(name)
            self.refresh_saved_presets(); self.on_pool_changed()

class ProductCostingPage(QWidget):

    costing_updated = Signal()

    def __init__(self, cm: CostingManager, acc_mgr,
                 go_home_cb, get_bridge_path_fn, parent=None):
        super().__init__(parent)
        self._cm = cm

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0); root.setSpacing(0)
        root.addWidget(_topbar("Product Costing", go_home_cb))

        self.layer_injector = LayerInjectionPanel(
            costing_manager=self._cm,
            get_active_product_id_cb=self._get_current_product_id,
            get_active_product_name_cb=self._get_current_product_name,
            on_success_cb=self._refresh_after_layer_injection,
        )
        self.layer_preset_manager_box = IntegratedLayerPresetCreator(
            costing_manager=self._cm,
            on_preset_pool_changed_cb=self.layer_injector.refresh_dropdown,
        )

        self._tabs = QTabWidget()
        self._tabs.setStyleSheet(f"""
            QTabWidget::pane {{ background: {C_BG}; border: none; }}
            QTabBar::tab {{
                background: {C_SURFACE}; color: {C_WHITE_MUT};
                padding: 6px 18px; font-size: 11px; font-weight: 500;
                border: none; border-bottom: 2px solid transparent;
                min-width: 110px;
            }}
            QTabBar::tab:selected {{
                color: {C_GOLD}; border-bottom: 2px solid {C_GOLD};
                background: {C_SURFACE_HI};
            }}
            QTabBar::tab:hover {{ background: {C_SURFACE_HI}; }}
        """)

        self._tab_rm        = RawMaterialsTab(cm)
        self._tab_bom       = ProductBOMTab(
            cm, acc_mgr,
            layer_injector=self.layer_injector,
            layer_manager_box=self.layer_preset_manager_box,
        )
        self._tab_summary   = AllProductsSummaryTab(cm, acc_mgr)
        self._tab_analytics = AnalyticsTab(cm, acc_mgr, get_bridge_path_fn)

        self._tabs.addTab(self._tab_rm,        "⚙  Raw Materials")
        self._tabs.addTab(self._tab_bom,       "🔩  Product BOM & Costs")
        self._tabs.addTab(self._tab_summary,   "📋  All Products Summary")
        self._tabs.addTab(self._tab_analytics, "📊  Analytics & History")

        self._tab_rm.data_changed.connect(self._tab_bom.refresh)
        self._tab_rm.data_changed.connect(self._tab_analytics.refresh)
        self._tab_rm.data_changed.connect(self._tab_summary.refresh)
        self._tab_bom.data_changed.connect(self._tab_analytics.refresh)
        self._tab_bom.data_changed.connect(self._tab_summary.refresh)
        self._tabs.currentChanged.connect(self._on_tab_changed)

        root.addWidget(self._tabs, 1)

    def _get_current_product_id(self) -> str:
        return getattr(self._tab_bom, "_current_product_id", "") or ""

    def _get_current_product_name(self) -> str:
        return getattr(self._tab_bom, "_current_product_name", "") or ""

    def _refresh_after_layer_injection(self):
        self._tab_bom.refresh()

    def _on_tab_changed(self, idx: int):
        if self._tabs.widget(idx) is self._tab_summary:
            self._tab_summary.refresh()

    def showEvent(self, event):
        super().showEvent(event)
        win = self.window()
        if win:
            win.showMaximized()

    def refresh(self):
        self._tab_rm.load()
        self._tab_bom.refresh()
        self._tab_analytics.refresh()
        self._tab_summary.refresh()
        if hasattr(self, "layer_preset_manager_box"):
            self.layer_preset_manager_box.refresh_materials()
            self.layer_preset_manager_box.refresh_saved_presets()
        if hasattr(self, "layer_injector"):
            self.layer_injector.refresh_dropdown()
        win = self.window()
        if win:
            QTimer.singleShot(100, lambda: _fit_widget_to_screen(win))
