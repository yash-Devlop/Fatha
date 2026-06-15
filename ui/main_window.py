from __future__ import annotations

import os
import subprocess
import tempfile
import pandas as pd
from datetime import datetime


from PySide6.QtWidgets import (
    QFrame, QGridLayout, QScrollArea, QSlider, QWidget, QVBoxLayout, QLabel,
    QFormLayout, QLineEdit, QTextEdit, QComboBox, QDoubleSpinBox,
    QHBoxLayout, QPushButton, QMessageBox, QMainWindow,
    QStackedWidget, QDialog, QRadioButton, QTableWidget, QTableWidgetItem,
    QHeaderView, QDateEdit, QFileDialog, QSizePolicy, QAbstractItemView,
    QListWidget, QListWidgetItem
)
from PySide6.QtGui import (
    QRegularExpressionValidator, QTextDocument, QFont, QColor,
    QDoubleValidator, QPageLayout, QPageSize, QPainter
)
from PySide6.QtCore import QRegularExpression, Qt, QDate, QMarginsF, QSizeF, QThread, Signal, QTimer, QSettings
from PySide6.QtPrintSupport import QPageSetupDialog, QPrintDialog, QPrintPreviewDialog, QPrinter

from common import acc_manager, costing_manager, state_code_map, get_bridge_path
from ui.Invoice.painter import draw_invoice

from GSTHelpers.GSTDetailFetcher import GSTFetchWorker

from ui.style import *
from ui.Helpers.helpers import *

from ui.costingPage import ProductCostingPage


PAGE_LAYOUT = QPageLayout(
    QPageSize(QPageSize.PageSizeId.A4),
    QPageLayout.Orientation.Portrait,
    QMarginsF(25, 15, 25, 15),
    QPageLayout.Unit.Millimeter,
)


class InvoicePainterPreview(QWidget):
    """
    Renders the invoice using draw_invoice → temp PDF → rasterised QImage.
    Default view fits the full page. Slider / mouse-wheel allow scaling.
    """

    def __init__(self, parent=None):
        super().__init__(parent)

        self._original_pixmap = None
        self._fit_mode = True
        self._manual_scale = 1.0
        self._bill_data: dict | None = None

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        self._scroll = QScrollArea()
        self._scroll.setWidgetResizable(False)
        self._scroll.setStyleSheet(f"""
            QScrollArea {{
                background: #1E1E1E;
                border: none;
                border-radius: 6px;
            }}
            QWidget#scroll_contents {{
                background: #1E1E1E;
            }}
        """)

        self._scroll_contents = QWidget()
        self._scroll_contents.setObjectName("scroll_contents")
        self._scroll_contents.setStyleSheet("background: #1E1E1E;")

        self._contents_layout = QVBoxLayout(self._scroll_contents)
        self._contents_layout.setAlignment(
            Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignTop
        )
        self._contents_layout.setContentsMargins(16, 16, 16, 16)
        self._contents_layout.setSpacing(0)

        self._page_lbl = QLabel()
        self._page_lbl.setAlignment(
            Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignHCenter
        )
        self._page_lbl.setStyleSheet(
            "background: white;"
            f"border: 1px solid {C_BORDER_DARK};"
        )
        self._contents_layout.addWidget(self._page_lbl)
        self._scroll.setWidget(self._scroll_contents)

        outer.addWidget(self._scroll, 1)

        self._toolbar = QFrame()
        self._toolbar.setFixedHeight(44)
        self._toolbar.setStyleSheet(f"""
            QFrame {{
                background: {C_SURFACE};
                border-top: 1px solid {C_BORDER};
            }}
        """)

        tb_layout = QHBoxLayout(self._toolbar)
        tb_layout.setContentsMargins(12, 6, 12, 6)
        tb_layout.setSpacing(6)

        reset_style = f"""
            QPushButton {{
                background: {C_SURFACE_HI};
                color: {C_WHITE_MUT};
                border: 1px solid {C_BORDER_DARK};
                border-radius: 5px;
                padding: 4px 10px;
                font-size: 12px;
                font-weight: 600;
                min-width: 56px;
                min-height: 28px;
            }}
            QPushButton:hover {{
                background: {C_BORDER_DARK};
                color: {C_WHITE};
            }}
        """

        self._zoom_lbl = QPushButton("Fit")
        self._zoom_lbl.setStyleSheet(reset_style)
        self._zoom_lbl.setFixedHeight(32)
        self._zoom_lbl.setMinimumWidth(64)
        self._zoom_lbl.setToolTip("Reset to fit page")
        self._zoom_lbl.clicked.connect(self._reset_fit)

        tb_layout.addStretch()
        tb_layout.addWidget(self._zoom_lbl)
        tb_layout.addStretch()

        outer.addWidget(self._toolbar)
        self._toolbar.hide()


    def set_zoom(self, factor: float):
        """
        Called by the external slider (and mouse-wheel shim in ViewBillsPage).
        factor: 0.30 … 2.0  (slider value / 100)
        """
        if self._original_pixmap is None:
            return
        self._fit_mode = False
        self._manual_scale = max(0.30, min(2.0, factor))
        self._apply_zoom()

    def load_bill(self, bill_data: dict):
        self._bill_data = bill_data
        self._render()

    def clear_bill(self):
        self._bill_data = None
        self._original_pixmap = None
        self._fit_mode = True
        self._manual_scale = 1.0

        self._page_lbl.clear()
        self._page_lbl.setText("Select a bill to preview")
        self._page_lbl.setStyleSheet(
            f"background: transparent; color: {C_GHOST}; font-size: 13px;"
        )
        self._page_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._page_lbl.setFixedSize(300, 80)

        self._toolbar.hide()
        self.update()
        self.repaint()


    def _calc_fit_scale(self) -> float:
        if self._original_pixmap is None:
            return 1.0
        vw = self._scroll.viewport().width()  - 32
        vh = self._scroll.viewport().height() - 32
        pw = self._original_pixmap.width()
        ph = self._original_pixmap.height()
        if pw <= 0 or ph <= 0:
            return 1.0
        return min(vw / pw, vh / ph)

    def _current_scale(self) -> float:
        if self._fit_mode:
            return self._calc_fit_scale()
        return self._manual_scale

    def _apply_zoom(self):
        if self._original_pixmap is None:
            return
        scale    = self._current_scale()
        target_w = max(1, int(self._original_pixmap.width()  * scale))
        target_h = max(1, int(self._original_pixmap.height() * scale))

        scaled = self._original_pixmap.scaled(
            target_w, target_h,
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
        self._page_lbl.setPixmap(scaled)
        self._page_lbl.setFixedSize(scaled.size())
        self._scroll_contents.setFixedSize(
            scaled.width()  + 32,
            scaled.height() + 32,
        )

        if self._fit_mode:
            self._zoom_lbl.setText("Fit")
        else:
            self._zoom_lbl.setText(f"{int(self._manual_scale * 100)}%")

    def _reset_fit(self):
        self._fit_mode = True
        self._manual_scale = 1.0
        self._apply_zoom()
        parent = self.parent()
        while parent is not None:
            if hasattr(parent, "zoom_slider"):
                parent.zoom_slider.setValue(100)
                break
            parent = parent.parent()


    def resizeEvent(self, event):
        super().resizeEvent(event)
        if self._fit_mode and self._original_pixmap is not None:
            self._apply_zoom()


    def _render(self):
        if not self._bill_data:
            return

        self._page_lbl.setText("Rendering…")
        self._page_lbl.setStyleSheet(
            f"background: transparent; color: {C_GHOST}; font-size: 13px;"
        )
        self._page_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._page_lbl.setFixedSize(300, 80)

        try:
            is_draft    = self._bill_data.get("_draft",    True)
            is_performa = self._bill_data.get("_performa", True)
            with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tf:
                tmp_path = tf.name

            ok = draw_invoice(self._bill_data, tmp_path, draft=is_draft, performa=is_performa)
            if not ok:
                self._page_lbl.setText("Could not render preview.")
                return

            try:
                from PySide6.QtPdf import QPdfDocument
                from PySide6.QtGui import QPixmap

                doc = QPdfDocument(self)
                doc.load(tmp_path)
                if doc.pageCount() == 0:
                    raise RuntimeError("empty PDF")

                dpi         = 250
                mm_per_inch = 25.4
                w_px = int(210 / mm_per_inch * dpi)
                h_px = int(297 / mm_per_inch * dpi)

                img = doc.render(0, QSizeF(w_px, h_px).toSize())
                if img.isNull():
                    raise RuntimeError("null image")

                self._original_pixmap = QPixmap.fromImage(img)
                doc.close()

                self._fit_mode    = True
                self._manual_scale = 1.0
                self._page_lbl.setStyleSheet(
                    "background: white;"
                    f"border: 1px solid {C_BORDER_DARK};"
                )

                QTimer.singleShot(30, self._on_render_ready)

            except Exception as e:
                self._page_lbl.setText(
                    "PDF preview requires PySide6 PDF module.\n"
                    "Use 'Print PDF' to view the invoice."
                )
                self._page_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
                print(f"Preview render error: {e}")
            finally:
                try:
                    os.unlink(tmp_path)
                except Exception:
                    pass

        except Exception as exc:
            self._page_lbl.setText(f"Preview error: {exc}")

    def _on_render_ready(self):
        self._apply_zoom()
        self._toolbar.show()


class HomePage(QWidget):
    def __init__(self, go_create, go_view, go_view_ledger, go_products,
                 go_billing, go_view_bills, go_products_costing):
        super().__init__()
        self._go_create      = go_create
        self._go_view        = go_view
        self._go_view_ledger = go_view_ledger
        self._go_products    = go_products
        self._go_billing     = go_billing
        self._go_view_bills  = go_view_bills
        self.go_products_costing = go_products_costing

        self.setStyleSheet(f"background: {C_BG};")
        self._root = QHBoxLayout(self)
        self._root.setContentsMargins(0, 0, 0, 0)
        self._root.setSpacing(0)
        self._build_sidebar()
        self._build_content()

    def _build_sidebar(self):
        sidebar = QFrame()
        sidebar.setFixedWidth(240)
        sidebar.setStyleSheet(f"""
            QFrame {{
                background: {C_SIDEBAR};
                border: none;
                border-right: 1px solid {C_BORDER};
                border-radius: 0;
            }}
        """)
        sb = QVBoxLayout(sidebar)
        sb.setContentsMargins(0, 0, 0, 0)
        sb.setSpacing(0)

        brand_frame = QFrame()
        brand_frame.setFixedHeight(88)
        brand_frame.setStyleSheet(
            f"background: {C_BG}; border: none; border-bottom: 1px solid {C_BORDER};"
        )
        brand_l = QVBoxLayout(brand_frame)
        brand_l.setContentsMargins(24, 20, 24, 16)
        brand_l.setSpacing(3)
        app_lbl = QLabel("FATHA")
        app_lbl.setFont(QFont(FONT_UI, 20, QFont.Weight.Bold))
        app_lbl.setStyleSheet(f"color: {C_WHITE}; background: transparent; letter-spacing: 6px;")
        sub_lbl = QLabel("Account Manager")
        sub_lbl.setFont(QFont(FONT_UI, 10))
        sub_lbl.setStyleSheet(f"color: {C_GHOST}; background: transparent;")
        brand_l.addWidget(app_lbl)
        brand_l.addWidget(sub_lbl)
        sb.addWidget(brand_frame)

        nav_heading = QLabel("NAVIGATION")
        nav_heading.setFont(QFont(FONT_UI, 9, QFont.Weight.Bold))
        nav_heading.setStyleSheet(
            f"color: {C_GHOST}; background: transparent;"
            f"letter-spacing: 2px; padding: 18px 24px 8px 24px;"
        )
        sb.addWidget(nav_heading)

        nav_items = [
            ("Create Client",  "⊕", self._go_create),
            ("View Clients",   "≡", self._go_view),
            ("View Ledger",    "◈", self._go_view_ledger),
            ("Products",       "◻", self._go_products),
            ("Create Invoice", "◇", self._go_billing),
            ("View Bills",     "◈", self._go_view_bills),
            ("Costing",     "💲", self.go_products_costing),
        ]
        for label, icon, cb in nav_items:
            sb.addWidget(self._nav_btn(icon, label, cb))
        sb.addStretch()

        owner = acc_manager.owner_name()
        if owner:
            div = QFrame()
            div.setFrameShape(QFrame.Shape.HLine)
            div.setStyleSheet(f"background: {C_BORDER}; border: none; max-height: 1px;")
            sb.addWidget(div)
            owner_frame = QFrame()
            owner_frame.setStyleSheet(f"background: {C_BG}; border: none;")
            owner_l = QVBoxLayout(owner_frame)
            owner_l.setContentsMargins(24, 12, 24, 16)
            owner_l.setSpacing(2)
            o_name = QLabel(owner)
            o_name.setFont(QFont(FONT_UI, 12, QFont.Weight.Bold))
            o_name.setStyleSheet(f"color: {C_WHITE}; background: transparent;")
            o_role = QLabel("Administrator")
            o_role.setFont(QFont(FONT_UI, 10))
            o_role.setStyleSheet(f"color: {C_GHOST}; background: transparent;")
            owner_l.addWidget(o_name)
            owner_l.addWidget(o_role)
            sb.addWidget(owner_frame)

        self._root.addWidget(sidebar)

    def _build_content(self):
        content = QWidget()
        content.setStyleSheet(f"background: {C_BG};")
        cl = QVBoxLayout(content)
        cl.setContentsMargins(52, 52, 52, 52)
        cl.setSpacing(0)
        cl.setAlignment(Qt.AlignmentFlag.AlignTop)

        owner = acc_manager.owner_name()
        greet = _h(12, "WELCOME BACK", color=C_GHOST)
        greet.setStyleSheet(f"color: {C_GHOST}; letter-spacing: 3px; background: transparent;")
        name      = _h(30, owner or "User", bold=True, color=C_WHITE)
        today_str = datetime.now().strftime("%A, %d %B %Y")
        date_lbl  = _h(12, today_str, color=C_GHOST)
        cl.addWidget(greet)
        cl.addWidget(name)
        cl.addSpacing(2)
        cl.addWidget(date_lbl)
        cl.addSpacing(40)
        cl.addWidget(_divider())
        cl.addSpacing(32)

        summary_heading = QLabel("OVERVIEW")
        summary_heading.setFont(QFont(FONT_UI, 9, QFont.Weight.Bold))
        summary_heading.setStyleSheet(
            f"color: {C_GHOST}; letter-spacing: 3px; background: transparent;"
        )
        cl.addWidget(summary_heading)
        cl.addSpacing(16)

        self._stats_row = QHBoxLayout()
        self._stats_row.setSpacing(14)

        self._sc_clients   = self._stat_card("Total Clients",   "0")
        self._sc_products  = self._stat_card("Total Products",  "0")
        self._sc_temp      = self._stat_card("Temp Bills",      "0")
        self._sc_permanent = self._stat_card("Finalized Bills", "0")

        for card in (self._sc_clients, self._sc_products, self._sc_temp, self._sc_permanent):
            self._stats_row.addWidget(card)
        self._stats_row.addStretch()
        cl.addLayout(self._stats_row)
        self._root.addWidget(content, 1)

        self.refresh_stats()

    def refresh_stats(self):
        """Reload counts from disk and update stat cards."""
        acc_manager.load_data()
        n_clients   = len(acc_manager.get_company_names())
        n_products  = len(acc_manager.products_data) if not acc_manager.products_data.empty else 0
        n_temp      = len(acc_manager.load_temp_bills())
        n_permanent = len(acc_manager.load_permanent_bills())

        def _set(card: QFrame, val: int):
            for child in card.findChildren(QLabel):
                if child.font().pointSize() >= 20:
                    child.setText(str(val))
                    break

        _set(self._sc_clients,   n_clients)
        _set(self._sc_products,  n_products)
        _set(self._sc_temp,      n_temp)
        _set(self._sc_permanent, n_permanent)

    def _nav_btn(self, icon: str, label: str, cb) -> QPushButton:
        btn = QPushButton(f"  {icon}   {label}")
        btn.setFixedHeight(42)
        btn.setStyleSheet(f"""
            QPushButton {{
                background: transparent;
                color: {C_GHOST};
                border: none;
                border-left: 2px solid transparent;
                border-radius: 0;
                padding: 0 24px;
                font-size: 13px;
                font-weight: 500;
                text-align: left;
            }}
            QPushButton:hover {{
                background: {C_SURFACE_ALT};
                color: {C_WHITE};
                border-left: 2px solid {C_WHITE};
            }}
        """)
        btn.clicked.connect(cb)
        return btn

    def _stat_card(self, label: str, value: str) -> QFrame:
        card = QFrame()
        card.setFixedSize(162, 82)
        card.setStyleSheet(f"""
            QFrame {{
                background: {C_SURFACE};
                border: 1px solid {C_BORDER};
                border-radius: 8px;
            }}
        """)
        vl = QVBoxLayout(card)
        vl.setContentsMargins(16, 12, 16, 12)
        vl.setSpacing(3)
        val_lbl = QLabel(value)
        val_lbl.setFont(QFont(FONT_UI, 24, QFont.Weight.Bold))
        val_lbl.setStyleSheet(f"color: {C_WHITE}; background: transparent;")
        lbl = QLabel(label)
        lbl.setFont(QFont(FONT_UI, 10))
        lbl.setStyleSheet(f"color: {C_GHOST}; background: transparent;")
        vl.addWidget(val_lbl)
        vl.addWidget(lbl)
        return card



class ProductRowWidget(QWidget):
    def __init__(self, remove_cb, recalculate_cb, parent=None):
        super().__init__(parent)
        self._remove_cb      = remove_cb
        self._recalculate_cb = recalculate_cb

        hl = QHBoxLayout(self)
        hl.setContentsMargins(0, 3, 0, 3)
        hl.setSpacing(6)

        self.product_combo = _NoScrollComboBox()
        self.product_combo.setMinimumWidth(210)
        self.product_combo.setMinimumHeight(36)

        self.qty_edit  = _field("Qty",  80)
        self.rate_edit = _field("Rate", 100)
        self.qty_edit.setValidator(QDoubleValidator(0, 999_999, 3))
        self.rate_edit.setValidator(QDoubleValidator(0, 9_999_999, 2))

        self.disc_type = _NoScrollComboBox()
        self.disc_type.addItems(["%", "Rs"])
        self.disc_type.setFixedWidth(56)
        self.disc_type.setMinimumHeight(36)

        self.disc_edit = _field("0", 75)
        self.disc_edit.setText("0")
        self.disc_edit.setValidator(QDoubleValidator(0, 9_999_999, 2))

        self.amount_field = QLineEdit("0.00")
        self.amount_field.setReadOnly(True)
        self.amount_field.setFixedWidth(110)
        self.amount_field.setMinimumHeight(36)
        self.amount_field.setStyleSheet(
            f"QLineEdit {{ background: {C_SURFACE_ALT}; color: {C_WHITE}; "
            f"border: 1px solid {C_BORDER_DARK}; border-radius: 5px; "
            f"padding: 7px 11px; font-weight: 700; }}"
        )
        self.amount_field.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)

        rem_btn = QPushButton("✕")
        rem_btn.setFixedSize(32, 32)
        rem_btn.setStyleSheet(f"""
            QPushButton {{
                background: transparent; color: {C_GHOST};
                border: 1px solid {C_BORDER}; border-radius: 4px;
                font-size: 11px; font-weight: bold;
            }}
            QPushButton:hover {{
                background: {C_DANGER_BG}; color: #F07070;
                border-color: {C_DANGER_BORDER};
            }}
        """)
        rem_btn.clicked.connect(lambda: self._remove_cb(self))

        hl.addWidget(self.product_combo, 3)
        hl.addWidget(_fl("Qty"))
        hl.addWidget(self.qty_edit, 1)
        hl.addWidget(_fl("Rate"))
        hl.addWidget(self.rate_edit, 1)
        hl.addWidget(_fl("Disc"))
        hl.addWidget(self.disc_edit, 1)
        hl.addWidget(self.disc_type)
        hl.addWidget(self.amount_field)
        hl.addWidget(rem_btn)

        self.product_combo.currentIndexChanged.connect(self._on_product_changed)
        self.qty_edit.textChanged.connect(self._on_value_changed)
        self.rate_edit.textChanged.connect(self._on_value_changed)
        self.disc_edit.textChanged.connect(self._on_value_changed)
        self.disc_type.currentIndexChanged.connect(self._on_value_changed)

    def populate_products(self, client_id: str):
        self.product_combo.blockSignals(True)
        self.product_combo.clear()
        self.product_combo.addItem("Select product...", None)
        df = acc_manager.get_products_with_client_rates(client_id)
        for _, row in df.iterrows():
            self.product_combo.addItem(f"{row['Name']}  [{row['HSN']}]", row.to_dict())
        self.product_combo.blockSignals(False)

    def _on_product_changed(self):
        data = self.product_combo.currentData()
        if data:
            self.rate_edit.setText(str(data.get("Rate", "0")))
        self._recalculate_cb()

    def _on_value_changed(self):
        self.amount_field.setText(f"{self.taxable_amount():.2f}")
        self._recalculate_cb()

    def taxable_amount(self) -> float:
        try:
            qty  = float(self.qty_edit.text()  or 0)
            rate = float(self.rate_edit.text() or 0)
            disc = float(self.disc_edit.text() or 0)
            base = qty * rate
            return base * (1 - disc / 100) if self.disc_type.currentText() == "%" \
                else max(base - disc, 0.0)
        except ValueError:
            return 0.0

    def row_data(self) -> dict | None:
        data = self.product_combo.currentData()
        if not data:
            return None
        try:
            qty      = float(self.qty_edit.text()  or 0)
            rate     = float(self.rate_edit.text() or 0)
            disc_val = float(self.disc_edit.text() or 0)
            disc_t   = self.disc_type.currentText()
            disc_d   = (f"{disc_val:.2f}%" if disc_t == "%" else f"Rs {disc_val:.2f}") if disc_val else "-"
            return {
                "description": data.get("Name", ""),
                "hsn":         str(data.get("HSN", "")),
                "qty":         qty,
                "rate":        f"{rate:.2f}",
                "discount":    disc_d,
                "amount":      f"{self.taxable_amount():.2f}",
                "product_id":  data.get("ProductId", ""),
            }
        except ValueError:
            return None



class _ProductEntry(QWidget):

    def __init__(self, remove_cb, recalc_cb, parent=None):
        super().__init__(parent)
        self.setStyleSheet("background: transparent;")

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 2)
        outer.setSpacing(2)

        # ── main product row ──────────────────────────────────────────
        self.row = ProductRowWidget(remove_cb, recalc_cb)
        outer.addWidget(self.row)

        # Fix product combo readability — dark background to match theme
        if hasattr(self.row, "product_combo"):
            self.row.product_combo.setStyleSheet(
                f"QComboBox {{"
                f"  background: {C_TOPBAR}; color: {C_WHITE};"
                f"  border: 1px solid {C_BORDER}; border-radius: 5px;"
                f"  padding: 4px 10px; font-size: 13px;"
                f"}}"
                f"QComboBox:focus {{ border: 1px solid {C_WHITE_MUT}; }}"
                f"QComboBox::drop-down {{ border: none; width: 24px; }}"
                f"QComboBox QAbstractItemView {{"
                f"  background: {C_TOPBAR}; color: {C_WHITE};"
                f"  selection-background-color: {C_SURFACE_ALT};"
                f"  selection-color: {C_WHITE};"
                f"  border: 1px solid {C_BORDER}; outline: none;"
                f"}}"
            )

        # ── serial-no / note sub-row ──────────────────────────────────
        note_frame = QFrame()
        note_frame.setStyleSheet("background: transparent;")
        note_hl = QHBoxLayout(note_frame)
        note_hl.setContentsMargins(8, 0, 8, 0)
        note_hl.setSpacing(6)

        note_icon = QLabel("↳")
        note_icon.setStyleSheet(f"color: {C_GHOST}; background: transparent; font-size: 11px;")
        note_icon.setFixedWidth(14)

        self.serial_edit = QLineEdit()
        self.serial_edit.setPlaceholderText(
            "Sr. No. / Batch / Note (optional) — e.g.  Sr: 001–050  or  Lot: XY-2025"
        )
        self.serial_edit.setMinimumHeight(28)
        self.serial_edit.setStyleSheet(
            f"QLineEdit {{"
            f"  background: transparent;"
            f"  color: {C_WHITE_MUT};"
            f"  border: none;"
            f"  border-bottom: 1px dashed {C_BORDER};"
            f"  border-radius: 0px;"
            f"  font-size: 11px;"
            f"  font-style: italic;"
            f"  padding: 2px 4px;"
            f"}}"
            f"QLineEdit:focus {{"
            f"  border-bottom: 1px dashed {C_WHITE_MUT};"
            f"}}"
        )

        note_hl.addWidget(note_icon)
        note_hl.addWidget(self.serial_edit, 1)
        outer.addWidget(note_frame)

    # ── convenience accessors ─────────────────────────────────────────

    def populate_products(self, client_id: str):
        self.row.populate_products(client_id)

    def row_data(self) -> dict | None:
        base = self.row.row_data()
        if base is None:
            return None

        # ── normalise qty ─────────────────────────────────────────────
        try:
            qty = float(str(base.get("qty") or "0").replace(",", "").strip())
        except (TypeError, ValueError):
            qty = 0.0

        if qty == 0:
            # ── 1. try rate from dict ─────────────────────────────────
            rate = 0.0
            for key in ("rate", "unit_rate", "price", "Rate"):
                raw = base.get(key)
                if raw:
                    try:
                        rate = float(str(raw).replace(",", "").strip())
                        if rate:
                            break
                    except (TypeError, ValueError):
                        pass

            # ── 2. fallback: read directly from the widget ────────────
            if rate == 0:
                for attr in ("rate_edit", "rate_spin", "price_edit", "rate_field"):
                    w = getattr(self.row, attr, None)
                    if w is None:
                        continue
                    try:
                        txt = w.text() if hasattr(w, "text") else str(w.value())
                        rate = float(txt.replace(",", "").strip())
                        if rate:
                            break
                    except (TypeError, ValueError, AttributeError):
                        pass

            disc_pct = 0.0
            for key in ("discount", "disc", "Discount"):
                raw = base.get(key)
                if raw:
                    try:
                        disc_pct = float(
                            str(raw).replace("%", "").replace(",", "").strip()
                        )
                        if disc_pct:
                            break
                    except (TypeError, ValueError):
                        pass

            if disc_pct == 0:
                w = getattr(self.row, "disc_edit", None)
                if w is not None:
                    try:
                        disc_pct = float(
                            w.text().replace("%", "").replace(",", "").strip() or "0"
                        )
                    except (TypeError, ValueError, AttributeError):
                        pass

            amount = round(rate * (1.0 - disc_pct / 100.0), 2)

            if amount == 0:
                amount = base.get("amount") or 0

            base = {**base, "qty": "", "amount": amount}

        serial = self.serial_edit.text().strip()
        return {**base, "serial_no": serial}

    def clear(self):
        self.row.product_combo.setCurrentIndex(0)
        self.row.qty_edit.clear()
        self.row.disc_edit.setText("0")
        self.serial_edit.clear()


class BillingPage(QWidget):
    """Create / save Tax Invoices and Proforma Invoices."""

    bill_saved = Signal()

    def __init__(self, go_home_cb, parent=None):
        super().__init__(parent)
        self._go_home = go_home_cb

        self._entries: list[_ProductEntry] = []

        self.cgst_lbl         = _ro(110)
        self.sgst_lbl         = _ro(110)
        self.igst_lbl         = _ro(110)
        self.total_qty_lbl    = _ro(90)
        self.total_amount_lbl = _ro(150)
        self.roff_lbl         = _ro(90)
        self.grand_total_lbl  = _ro(150)
        self.amount_words_lbl = QLabel("")
        self._build_ui()


    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)
        root.addWidget(_topbar("Create Invoice", self._go_home))

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("background: transparent; border: none;")
        body = QWidget()
        body.setStyleSheet(f"background: {C_BG};")
        bl = QVBoxLayout(body)
        bl.setSpacing(16)
        bl.setContentsMargins(28, 24, 28, 24)
        scroll.setWidget(body)
        root.addWidget(scroll, 1)

        bl.addWidget(self._section_bill_details())
        bl.addWidget(self._section_transport())
        bl.addWidget(self._section_shipto())
        bl.addWidget(self._section_products())
        bl.addWidget(self._section_tax())
        bl.addStretch()

        actbar = QFrame()
        actbar.setFixedHeight(64)
        actbar.setStyleSheet(
            f"QFrame {{ background: {C_TOPBAR}; border: none;"
            f"          border-top: 1px solid {C_BORDER}; }}"
        )
        al = QHBoxLayout(actbar)
        al.setContentsMargins(24, 0, 24, 0)
        al.setSpacing(10)

        clear_btn         = QPushButton("Clear Form")
        save_performa_btn = QPushButton("Save as Performa")
        save_btn          = QPushButton("Save Invoice")

        clear_btn.setStyleSheet(BTN_OUTLINE)
        save_performa_btn.setStyleSheet(BTN_PRIMARY)
        save_btn.setStyleSheet(BTN_PRIMARY)
        for b in (clear_btn, save_btn, save_performa_btn):
            b.setMinimumHeight(40)

        clear_btn.clicked.connect(self._clear_form)
        save_performa_btn.clicked.connect(self._save_performa_bill)
        save_btn.clicked.connect(self._save_bill)

        al.addStretch()
        al.addWidget(clear_btn)
        al.addWidget(save_performa_btn)
        al.addWidget(save_btn)
        root.addWidget(actbar)

    def _section_bill_details(self) -> QFrame:
        frame, vl = _card("BILL DETAILS")

        r1 = QHBoxLayout()
        r1.setSpacing(16)
        self.client_combo = _NoScrollComboBox()
        self.client_combo.setMinimumWidth(260)
        self.client_combo.setMinimumHeight(36)
        self.client_combo.addItem("Select client...")
        for name in acc_manager.get_company_names():
            self.client_combo.addItem(name)
        self.client_combo.currentTextChanged.connect(self._on_client_changed)

        self.invoice_no_lbl = QLabel("-")
        self.invoice_no_lbl.setStyleSheet(GOLD_BADGE)
        self.invoice_no_lbl.setMinimumWidth(200)

        supply_frame = QFrame()
        supply_frame.setStyleSheet("background: transparent;")
        supply_hl = QHBoxLayout(supply_frame)
        supply_hl.setContentsMargins(0, 0, 0, 0)
        supply_hl.setSpacing(12)
        self.within_state_radio = QRadioButton("Within State")
        self.out_state_radio    = QRadioButton("Out of State")
        self.within_state_radio.setChecked(True)
        supply_hl.addWidget(_fl("Supply:"))
        supply_hl.addWidget(self.within_state_radio)
        supply_hl.addWidget(self.out_state_radio)
        self.within_state_radio.toggled.connect(self._recalculate)

        r1.addWidget(_fl("Client"))
        r1.addWidget(self.client_combo, 2)
        r1.addSpacing(16)
        r1.addWidget(_fl("Invoice No."))
        r1.addWidget(self.invoice_no_lbl)
        r1.addSpacing(16)
        r1.addWidget(supply_frame)
        r1.addStretch()
        vl.addLayout(r1)

        r_po = QHBoxLayout()
        r_po.setSpacing(16)
        self.po_no_edit = _field("P.O. Number (leave blank for Verbal)")
        self.po_no_edit.setMinimumWidth(280)
        r_po.addWidget(_fl("P.O. No."))
        r_po.addWidget(self.po_no_edit, 2)
        r_po.addStretch()
        vl.addLayout(r_po)

        r2 = QHBoxLayout()
        r2.setSpacing(16)
        self.order_date_edit = QDateEdit(QDate.currentDate())
        self.order_date_edit.setCalendarPopup(True)
        self.order_date_edit.setDisplayFormat("dd/MM/yyyy")
        self.order_date_edit.setMinimumHeight(36)
        self.order_date_edit.setFixedWidth(160)

        self.bill_date_edit = QDateEdit(QDate.currentDate())
        self.bill_date_edit.setCalendarPopup(True)
        self.bill_date_edit.setDisplayFormat("dd/MM/yyyy")
        self.bill_date_edit.setMinimumHeight(36)
        self.bill_date_edit.setFixedWidth(160)

        r2.addWidget(_fl("Order Date"))
        r2.addWidget(self.order_date_edit)
        r2.addSpacing(16)
        r2.addWidget(_fl("Bill Date"))
        r2.addWidget(self.bill_date_edit)
        r2.addStretch()
        vl.addLayout(r2)
        return frame

    def _section_transport(self) -> QFrame:
        frame, vl = _card("DISPATCH DETAILS")
        hl = QHBoxLayout()
        hl.setSpacing(16)
        self.dispatch_edit    = _field("Dispatched through (transporter name / vehicle)", 260)
        self.destination_edit = _field("Destination", 180)
        self.eway_edit        = _field("E-Way Bill No. (optional)", 210)
        hl.addWidget(_fl("Dispatched Through"))
        hl.addWidget(self.dispatch_edit)
        hl.addSpacing(16)
        hl.addWidget(_fl("Destination"))
        hl.addWidget(self.destination_edit)
        hl.addSpacing(16)
        hl.addWidget(_fl("E-Way Bill No."))
        hl.addWidget(self.eway_edit)
        hl.addStretch()
        vl.addLayout(hl)
        return frame

    def _section_shipto(self) -> QFrame:
        frame, vl = _card("SHIP TO")
        note = _h(11, "Leave blank to use the billing address", color=C_GHOST)
        vl.addWidget(note)
        hl = QHBoxLayout()
        hl.setSpacing(16)
        self.ship_name_edit    = _field("Recipient name")
        self.ship_address_edit = _field("Delivery address")
        hl.addWidget(_fl("Name"))
        hl.addWidget(self.ship_name_edit, 1)
        hl.addSpacing(16)
        hl.addWidget(_fl("Address"))
        hl.addWidget(self.ship_address_edit, 2)
        hl.addStretch()
        vl.addLayout(hl)
        return frame

    def _section_products(self) -> QFrame:
        frame, vl = _card("LINE ITEMS")

        hdr_frame = QFrame()
        hdr_frame.setStyleSheet(
            f"background: {C_SURFACE_ALT}; border-radius: 4px; border: 1px solid {C_BORDER};"
        )
        hdr_l = QHBoxLayout(hdr_frame)
        hdr_l.setContentsMargins(8, 7, 8, 7)
        hdr_l.setSpacing(6)
        for txt, stretch in [
            ("Product",    3),
            ("Qty",        1),
            ("Rate",       1),
            ("Discount",   1),
            ("",           0),
            ("Amount (₹)", 1),
            ("",           0),
        ]:
            h = QLabel(txt)
            h.setFont(QFont(FONT_UI, 10, QFont.Weight.Bold))
            h.setStyleSheet(f"color: {C_WHITE_MUT}; background: transparent;")
            if stretch:
                hdr_l.addWidget(h, stretch)
            else:
                hdr_l.addWidget(h)
        vl.addWidget(hdr_frame)

        hint = _h(10,
            "↳  Each item has an optional  Sr. No. / Batch / Note  field — "
            "type there to print a small sub-line below the product description.",
            color=C_GHOST)
        hint.setWordWrap(True)
        vl.addWidget(hint)

        self.products_container = QVBoxLayout()
        self.products_container.setSpacing(6)
        vl.addLayout(self.products_container)

        add_btn = QPushButton("+ Add Line Item")
        add_btn.setStyleSheet(BTN_OUTLINE)
        add_btn.setFixedWidth(160)
        add_btn.setFixedHeight(34)
        add_btn.clicked.connect(self._add_product_row)
        vl.addWidget(add_btn)

        self._add_product_row()
        return frame

    def _section_tax(self) -> QFrame:
        frame, vl = _card("TAX & TOTALS")
        grid = QGridLayout()
        grid.setColumnStretch(1, 1)
        grid.setColumnStretch(3, 1)
        grid.setHorizontalSpacing(28)
        grid.setVerticalSpacing(12)

        for f in (self.cgst_lbl, self.sgst_lbl, self.igst_lbl):
            f.setStyleSheet(RO_STYLE)

        self.grand_total_lbl.setStyleSheet(
            f"QLineEdit {{ background: {C_SURFACE_ALT}; color: {C_WHITE}; "
            f"border: 1.5px solid {C_WHITE_MUT}; border-radius: 5px; "
            f"padding: 7px 11px; font-size: 16px; font-weight: 700; }}"
        )
        self.grand_total_lbl.setFixedWidth(170)

        self.amount_words_lbl.setWordWrap(True)
        self.amount_words_lbl.setStyleSheet(
            f"color: {C_WHITE_MUT}; font-style: italic; "
            f"background: transparent; font-size: 12px;"
        )

        grand_lbl = QLabel("Grand Total  ₹")
        grand_lbl.setFont(QFont(FONT_UI, 13, QFont.Weight.Bold))
        grand_lbl.setStyleSheet(f"color: {C_WHITE}; background: transparent;")

        r = 0
        grid.addWidget(_fl("Total Qty"),       r, 0); grid.addWidget(self.total_qty_lbl,    r, 1)
        grid.addWidget(_fl("Taxable Amount"),  r, 2); grid.addWidget(self.total_amount_lbl, r, 3); r += 1
        grid.addWidget(_fl("CGST 9% (₹)"),    r, 0); grid.addWidget(self.cgst_lbl,         r, 1)
        grid.addWidget(_fl("SGST 9% (₹)"),    r, 2); grid.addWidget(self.sgst_lbl,         r, 3); r += 1
        grid.addWidget(_fl("IGST 18% (₹)"),   r, 0); grid.addWidget(self.igst_lbl,         r, 1)
        grid.addWidget(_fl("Round Off"),       r, 2); grid.addWidget(self.roff_lbl,         r, 3); r += 1
        grid.addWidget(grand_lbl,              r, 0); grid.addWidget(self.grand_total_lbl,  r, 1); r += 1
        grid.addWidget(_fl("Amount in Words"), r, 0); grid.addWidget(self.amount_words_lbl, r, 1, 1, 3)
        vl.addLayout(grid)
        return frame


    def _add_product_row(self):
        entry = _ProductEntry(self._remove_entry, self._recalculate)
        entry.populate_products(self._current_client_id())
        self._entries.append(entry)
        self.products_container.addWidget(entry)
        self._recalculate()

    def _remove_entry(self, row_widget):
        """
        Called by ProductRowWidget's own delete button.
        We find the parent _ProductEntry that owns this row and remove it.
        """
        if len(self._entries) <= 1:
            return
        entry = next((e for e in self._entries if e.row is row_widget), None)
        if entry is None:
            return
        self._entries.remove(entry)
        self.products_container.removeWidget(entry)
        entry.deleteLater()
        self._recalculate()


    def _recalculate(self):
        total_qty = total_amount = 0.0
        for entry in self._entries:
            rd = entry.row_data()
            if rd:
                total_qty    += rd.get("qty") or 1
                total_amount += float(rd.get("amount", 0) or 0)

        within = self.within_state_radio.isChecked()
        if within:
            cgst = round(total_amount * 0.09, 2)
            sgst = round(total_amount * 0.09, 2)
            igst = 0.0
        else:
            cgst = 0.0
            sgst = 0.0
            igst = round(total_amount * 0.18, 2)

        raw         = total_amount + cgst + sgst + igst
        grand_total = round(raw)
        roff        = round(grand_total - raw, 2)
        roff_str    = (f"+{roff:.2f}" if roff > 0 else f"{roff:.2f}") if roff != 0 else "0.00"

        self.total_qty_lbl.setText(f"{total_qty:.2f}")
        self.total_amount_lbl.setText(f"{total_amount:,.2f}")
        self.cgst_lbl.setText(f"{cgst:.2f}")
        self.sgst_lbl.setText(f"{sgst:.2f}")
        self.igst_lbl.setText(f"{igst:.2f}")
        self.roff_lbl.setText(roff_str)
        self.grand_total_lbl.setText(f"{grand_total:,.2f}")
        self.amount_words_lbl.setText(_amount_to_words(grand_total) + " Only")

    def _current_client_id(self) -> str:
        company = self.client_combo.currentText()
        if company and company != "Select client...":
            return acc_manager.client_details(company).get("ClientId", "")
        return ""

    def _on_client_changed(self, company: str):
        cid = self._current_client_id()
        for entry in self._entries:
            entry.populate_products(cid)
        if company and company != "Select client...":
            self.invoice_no_lbl.setText(acc_manager.generate_invoice_number(company))
        else:
            self.invoice_no_lbl.setText("-")


    def _collect_bill_data(self) -> dict | None:
        company = self.client_combo.currentText()
        if not company or company == "Select client...":
            _warn(self, "Please select a client."); return None

        invoice_no = self.invoice_no_lbl.text().strip()
        if not invoice_no or invoice_no == "-":
            _warn(self, "Invoice number could not be generated."); return None

        rows = [e.row_data() for e in self._entries]
        rows = [r for r in rows if r]
        if not rows:
            _warn(self, "Add at least one product line."); return None

        dispatch    = self.dispatch_edit.text().strip()
        destination = self.destination_edit.text().strip()
        eway        = self.eway_edit.text().strip()

        total_qty    = sum((r.get("qty") or 1) for r in rows)
        total_amount = sum(float(r.get("amount") or 0) for r in rows)

        within = self.within_state_radio.isChecked()
        if within:
            cgst = round(total_amount * 0.09, 2)
            sgst = round(total_amount * 0.09, 2)
            igst = 0.0
        else:
            cgst = 0.0
            sgst = 0.0
            igst = round(total_amount * 0.18, 2)

        raw         = total_amount + cgst + sgst + igst
        grand_total = round(raw)
        roff        = round(grand_total - raw, 2)
        roff_str    = (f"+{roff:.2f}" if roff > 0 else f"{roff:.2f}") if roff != 0 else "0.00"

        client = acc_manager.client_details(company)
        owner  = acc_manager.owner_data

        ship_name    = self.ship_name_edit.text().strip()    or client.get("Company", "")
        ship_address = self.ship_address_edit.text().strip() or client.get("Address", "")

        c_state          = client.get("State", "")
        c_state_code     = client.get("StateCode", "")
        owner_state_code = state_code_map.get(owner.get("State", ""), "")

        po_no               = self.po_no_edit.text().strip() or "Verbal"
        client_display_name = client.get("Company", client.get("Client_name", ""))

        return {
            # ── company / owner ───────────────────────────────────────
            "company_name":    owner.get("Company",  ""),
            "company_gstin":   owner.get("GST",      ""),
            "company_address": owner.get("Address",  ""),
            "company_mobile":  owner.get("Mobile",   ""),
            "company_email":   owner.get("Email",    ""),
            "bank_name":       owner.get("Bank",     ""),
            "account":         owner.get("Account",  ""),
            "ifsc":            owner.get("IFSC",     ""),
            # ── invoice meta ─────────────────────────────────────────
            "invoice_no":      invoice_no,
            "order_date":      self.order_date_edit.date().toString("dd/MM/yyyy"),
            "bill_date":       self.bill_date_edit.date().toString("dd/MM/yyyy"),
            "date":            self.bill_date_edit.date().toString("dd/MM/yyyy"),
            "transport_mode":  dispatch      if dispatch      else "—",
            "destination":     destination   if destination   else "—",
            "eway":            eway,
            "state":           owner.get("State", c_state),
            "state_code":      owner_state_code,
            "po_no":           po_no,
            "supply_type":     "within" if within else "out",
            # ── client ───────────────────────────────────────────────
            "client_name":        client_display_name,
            "client_company":     company,           # real name for ledger
            "client_address":     client.get("Address",   ""),
            "client_gstin":       client.get("GST",       ""),
            "client_state":       c_state,
            "client_state_code":  c_state_code,
            "client_mobile":       client.get("Mobile", "-"),
            "client_alt_mobile":       client.get("AltMobile", "-"),
            # ── ship-to ──────────────────────────────────────────────
            "ship_name":     ship_name,
            "ship_address":  ship_address,
            "rows": rows,
            # ── totals ───────────────────────────────────────────────
            "total_qty":    f"{total_qty:.2f}",
            "total_amount": f"{total_amount:,.2f}",
            "cgst":         f"{cgst:.2f}",
            "sgst":         f"{sgst:.2f}",
            "igst":         f"{igst:.2f}",
            "roff":         roff_str,
            "grand_total":  f"{grand_total:,.2f}",
            "amount_words": _amount_to_words(grand_total),
        }


    def _save_bill(self):
        data = self._collect_bill_data()
        if not data:
            return
        status, msg = acc_manager.save_temp_bill(data)
        if status != "Success":
            _warn(self, msg); return
        QMessageBox.information(self, "Saved",
            f"Invoice {msg} saved to temp bills.")
        self.bill_saved.emit()
        self._clear_form()

    def _save_performa_bill(self):
        data = self._collect_bill_data()
        if not data:
            return
        del data["invoice_no"]
        data["performa_no"] = acc_manager.generate_performa_number()
        status, msg = acc_manager.save_performa_bill(data)
        if status != "Success":
            _warn(self, msg); return
        QMessageBox.information(self, "Saved",
            f"Proforma {msg} saved.")
        self.bill_saved.emit()
        self._clear_form()


    def _clear_form(self):
        self.client_combo.setCurrentIndex(0)
        self.po_no_edit.clear()
        self.order_date_edit.setDate(QDate.currentDate())
        self.bill_date_edit.setDate(QDate.currentDate())
        self.dispatch_edit.clear()
        self.destination_edit.clear()
        self.eway_edit.clear()
        self.ship_name_edit.clear()
        self.ship_address_edit.clear()
        self.within_state_radio.setChecked(True)

        while len(self._entries) > 1:
            entry = self._entries[-1]
            self._entries.remove(entry)
            self.products_container.removeWidget(entry)
            entry.deleteLater()
        if self._entries:
            self._entries[0].clear()

        self._recalculate()

    def refresh(self):
        acc_manager.load_data()
        current = self.client_combo.currentText()
        self.client_combo.blockSignals(True)
        self.client_combo.clear()
        self.client_combo.addItem("Select client...")
        for name in acc_manager.get_company_names():
            self.client_combo.addItem(name)
        idx = self.client_combo.findText(current)
        self.client_combo.setCurrentIndex(idx if idx >= 0 else 0)
        self.client_combo.blockSignals(False)
        cid = self._current_client_id()
        for entry in self._entries:
            entry.populate_products(cid)
        company = self.client_combo.currentText()
        if company and company != "Select client...":
            self.invoice_no_lbl.setText(acc_manager.generate_invoice_number(company))


class ViewBillsPage(QWidget):
    bill_finalized = Signal()
    bill_deleted   = Signal()

    def __init__(self, go_home):
        super().__init__()
        self._go_home = go_home
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)
        root.addWidget(_topbar("View Bills", go_home))

        body = QWidget()
        body.setStyleSheet(f"background: {C_BG};")
        bl   = QHBoxLayout(body)
        bl.setContentsMargins(28, 24, 28, 24)
        bl.setSpacing(16)

        left = QFrame()
        left.setFixedWidth(360)
        left.setStyleSheet(CARD_STYLE)
        lv = QVBoxLayout(left)
        lv.setContentsMargins(16, 16, 16, 16)
        lv.setSpacing(10)

        lv.addWidget(_h(13, "Bills", bold=True, color=C_WHITE))
        lv.addWidget(_divider())

        filter_row = QHBoxLayout()
        filter_row.setSpacing(8)
        self.search_edit = _field("Search invoice or company...")
        search_btn = QPushButton("Search")
        search_btn.setStyleSheet(BTN_PRIMARY)
        search_btn.setFixedHeight(36)
        search_btn.clicked.connect(self.load_bills)
        filter_row.addWidget(self.search_edit)
        filter_row.addWidget(search_btn)
        lv.addLayout(filter_row)

        self.show_temp = QRadioButton("Temp")
        self.show_perm = QRadioButton("Finalized")
        self.show_performa  = QRadioButton("PI")
        self.show_all  = QRadioButton("All")
        self.show_all.setChecked(True)
        radio_row = QHBoxLayout()
        radio_row.addWidget(self.show_temp)
        radio_row.addWidget(self.show_perm)
        radio_row.addWidget(self.show_performa)
        radio_row.addWidget(self.show_all)
        lv.addLayout(radio_row)
        for r in (self.show_temp, self.show_perm, self.show_all):
            r.toggled.connect(self.load_bills)

        self.bill_list = QListWidget()
        self.bill_list.currentRowChanged.connect(self._on_bill_selected)
        lv.addWidget(self.bill_list, 1)

        bl.addWidget(left)

        right = QFrame()
        right.setStyleSheet(CARD_STYLE)
        rv = QVBoxLayout(right)
        rv.setContentsMargins(16, 16, 16, 16)
        rv.setSpacing(12)

        info_row = QHBoxLayout()
        self.bill_status_lbl = QLabel("Select a bill to preview")
        self.bill_status_lbl.setStyleSheet(GOLD_BADGE)
        info_row.addWidget(self.bill_status_lbl)
        info_row.addStretch()

        self.finalize_btn = QPushButton("✓  Finalize")
        self.finalize_btn.setStyleSheet(BTN_SUCCESS)
        self.finalize_btn.setFixedHeight(34)
        self.finalize_btn.setMinimumWidth(110)
        self.finalize_btn.setVisible(False)
        self.finalize_btn.clicked.connect(self._finalize_current)

        self.print_btn = QPushButton("Export BILL")
        self.print_btn.setStyleSheet(BTN_NAVY)
        self.print_btn.setFixedHeight(34)
        self.print_btn.setMinimumWidth(110)
        self.print_btn.setVisible(False)
        self.print_btn.clicked.connect(self._print_current)

        self.direct_print_btn = QPushButton("🖨 Print Paper")
        self.direct_print_btn.setStyleSheet(BTN_NAVY)
        self.direct_print_btn.setFixedHeight(34)
        self.direct_print_btn.setMinimumWidth(110)
        self.direct_print_btn.setVisible(False)
        self.direct_print_btn.clicked.connect(self._print_current_direct)

        self.share_wa_btn = QPushButton("Share")
        self.share_wa_btn.setStyleSheet(BTN_OUTLINE)
        self.share_wa_btn.setFixedHeight(34)
        self.share_wa_btn.setMinimumWidth(150)
        self.share_wa_btn.setVisible(False)
        self.share_wa_btn.clicked.connect(self._share_current_whatsapp)

        self.delete_temp_btn = QPushButton("🗑  Delete")
        self.delete_temp_btn.setStyleSheet(BTN_DANGER)
        self.delete_temp_btn.setFixedHeight(34)
        self.delete_temp_btn.setMinimumWidth(90)
        self.delete_temp_btn.setVisible(False)
        self.delete_temp_btn.clicked.connect(self._delete_current_temp)

        info_row.addWidget(self.finalize_btn)
        info_row.addWidget(self.print_btn)
        info_row.addWidget(self.direct_print_btn)
        info_row.addWidget(self.share_wa_btn)
        info_row.addWidget(self.delete_temp_btn)
        rv.addLayout(info_row)
        rv.addWidget(_divider())

        zoom_row = QHBoxLayout()
        zoom_row.setSpacing(8)

        zoom_lbl = QLabel("Zoom")
        zoom_lbl.setStyleSheet(f"color: {C_WHITE}; font-size: 12px;")
        zoom_lbl.setFixedWidth(36)

        self.zoom_slider = QSlider(Qt.Orientation.Horizontal)
        self.zoom_slider.setMinimum(30)
        self.zoom_slider.setMaximum(200)
        self.zoom_slider.setValue(100)
        self.zoom_slider.setTickInterval(10)
        self.zoom_slider.setFixedHeight(22)
        self.zoom_slider.setStyleSheet("""
            QSlider::groove:horizontal {
                height: 4px;
                background: #444;
                border-radius: 2px;
            }
            QSlider::handle:horizontal {
                background: #c9a84c;
                border: none;
                width: 14px;
                height: 14px;
                margin: -5px 0;
                border-radius: 7px;
            }
            QSlider::sub-page:horizontal {
                background: #c9a84c;
                border-radius: 2px;
            }
        """)
        self.zoom_slider.valueChanged.connect(self._on_zoom_changed)

        self.zoom_pct_lbl = QLabel("100%")
        self.zoom_pct_lbl.setStyleSheet(f"color: {C_WHITE}; font-size: 12px;")
        self.zoom_pct_lbl.setFixedWidth(42)
        self.zoom_pct_lbl.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)

        zoom_row.addWidget(zoom_lbl)
        zoom_row.addWidget(self.zoom_slider, 1)
        zoom_row.addWidget(self.zoom_pct_lbl)
        rv.addLayout(zoom_row)

        self.preview_widget = InvoicePainterPreview()
        rv.addWidget(self.preview_widget, 1)

        bl.addWidget(right, 1)
        root.addWidget(body, 1)

        self._current_bill: dict | None = None
        self._current_store: str = ""


    def _on_zoom_changed(self, value: int):
        """Slider moved — update label and tell the preview widget."""
        self.zoom_pct_lbl.setText(f"{value}%")
        self.preview_widget.set_zoom(value / 100.0)


    def load_bills(self):
        self.bill_list.clear()
        query = self.search_edit.text().strip().lower()
        store = "all"
        if self.show_temp.isChecked():
            store = "temp"
        elif self.show_perm.isChecked():
            store = "permanent"
        elif self.show_performa.isChecked():
            store = "performa"
        all_bills = acc_manager.get_all_bill_invoice_numbers(store)
        for (s, inv, client, date_str) in all_bills:
            if query and query not in inv.lower() and query not in client.lower():
                continue
            if s == "temp":
                tag  = "⏳ TEMP"
            elif s == "permanent":
                tag = "✓ FINAL"
            elif s == "performa":
                tag = " 💲Performa"
            item = QListWidgetItem(f"{tag}  {inv}\n{client}  •  {date_str[:10]}")
            item.setData(Qt.ItemDataRole.UserRole, (s, inv))
            self.bill_list.addItem(item)

    def _on_bill_selected(self, row: int):
        if row < 0:
            return
        item = self.bill_list.item(row)
        if not item:
            return
        s, inv = item.data(Qt.ItemDataRole.UserRole)
        self._current_store = s
        if s == "temp":
            bill = acc_manager.get_temp_bill_by_invoice(inv)
        elif s == "performa":
            bill = acc_manager.get_performa_bill_by_invoice(inv)
        elif s == "permanent":
            bill = acc_manager.get_permanent_bill_by_invoice(inv)
        if not bill:
            return
        self._current_bill = bill

        bill_for_preview = dict(bill)
        is_draft = (s == "temp")
        is_performa = (s == "performa")
        bill_for_preview["_draft"] = is_draft
        bill_for_preview["_performa"] = is_performa
        self.preview_widget.load_bill(bill_for_preview)

        self.zoom_slider.setValue(100)

        self.bill_status_lbl.setText(f"{inv}  ({'Temp' if s == 'temp' else 'Finalized'})")
        self.finalize_btn.setVisible(s == "temp")
        self.print_btn.setVisible(True)
        self.direct_print_btn.setVisible(True)
        self.share_wa_btn.setVisible(True)
        self.delete_temp_btn.setVisible(s == "temp" or s == "performa")

    def _finalize_current(self):
        if not self._current_bill:
            return
        inv = self._current_bill.get("invoice_no", "")
        grand_total_str = self._current_bill.get("grand_total", "0").replace(",", "")
        try:
            grand_total = float(grand_total_str)
        except Exception:
            grand_total = 0.0

        eway_no = self._current_bill.get("eway", "").strip()
        if grand_total > 50_000 and not eway_no:
            eway_dialog = _EwayDialog(inv, self)
            if eway_dialog.exec() != QDialog.DialogCode.Accepted:
                return
            eway_no = eway_dialog.eway_value()
            if not eway_no:
                QMessageBox.warning(self, "Required",
                    "E-Way Bill No. is required for invoices above ₹50,000.")
                return

        reply = QMessageBox.question(
            self, "Confirm Finalization",
            f"Are you sure you want to finalize invoice {inv}?\n"
            f"This will move it to permanent records and update the client ledger.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if reply != QMessageBox.StandardButton.Yes:
            return

        status, msg = acc_manager.finalize_bill(inv, eway_no=eway_no)
        QMessageBox.information(self, status, msg)
        self.bill_finalized.emit()
        self.load_bills()
        self.preview_widget.clear_bill()
        self.finalize_btn.setVisible(False)
        self.print_btn.setVisible(False)
        self.direct_print_btn.setVisible(False)
        self.delete_temp_btn.setVisible(False)
        self.share_wa_btn.setVisible(False)
        self.bill_status_lbl.setText("Select a bill to preview")
        self._current_bill = None

    def _delete_current_temp(self):
        is_performa = False
        if not self._current_bill:
            return
        inv = self._current_bill.get("invoice_no", "")
        if "performa_no" in self._current_bill:
            is_performa = True
            inv = self._current_bill.get("performa_no")
        if is_performa:
            dialog = (f"Are you sure you want to permanently delete Performa invoice {inv}?\n"
                      f"This action cannot be undone.")
        else:
            dialog = (f"Are you sure you want to permanently delete temp invoice {inv}?\n"
                      f"This action cannot be undone.")
        reply = QMessageBox.question(
            self, "Confirm Delete",
            dialog,
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if reply != QMessageBox.StandardButton.Yes:
            return
        if not is_performa:
            status, msg = acc_manager.delete_temp_bill(inv)
        else:
            status, msg = acc_manager.delete_performa_bill(inv)
        QMessageBox.information(self, status, msg)
        if status == "Success":
            self.bill_deleted.emit()
            self.load_bills()
            self.preview_widget.clear_bill()
            self.finalize_btn.setVisible(False)
            self.print_btn.setVisible(False)
            self.direct_print_btn.setVisible(False)
            self.delete_temp_btn.setVisible(False)
            self.bill_status_lbl.setText("Select a bill to preview")
            self._current_bill = None

    def _print_current(self):
        if not self._current_bill:
            return
        is_draft = (self._current_store == "temp")
        _print_invoice_pdf(self._current_bill, self, draft=is_draft)

    def _print_current_direct(self):
        if not self._current_bill:
            return
        is_draft = (self._current_store == "temp")
        
        printer = QPrinter(QPrinter.PrinterMode.HighResolution)
        dialog = QPrintDialog(printer, self)
        dialog.setWindowTitle("Print Invoice")
        if dialog.exec() != QPrintDialog.DialogCode.Accepted:
            return

        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tf:
            tmp_path = tf.name

        try:
            ok = draw_invoice(self._current_bill, tmp_path, draft=is_draft)
            if not ok:
                QMessageBox.warning(self, "Print Error", "Could not render invoice.")
                return

            from PySide6.QtPdf import QPdfDocument
            doc = QPdfDocument(self)
            doc.load(tmp_path)
            if doc.pageCount() == 0:
                QMessageBox.warning(self, "Print Error", "Empty PDF rendered.")
                return

            painter = QPainter()
            painter.begin(printer)
            try:
                page_rect = printer.pageRect(QPrinter.Unit.DevicePixel)
                for i in range(doc.pageCount()):
                    if i > 0:
                        printer.newPage()
                    from PySide6.QtCore import QSizeF
                    img = doc.render(i, QSizeF(page_rect.width(), page_rect.height()).toSize())
                    painter.drawImage(page_rect, img)
            finally:
                painter.end()

            doc.close()
        finally:
            try:
                os.unlink(tmp_path)
            except Exception:
                pass

    def _share_current_whatsapp(self):
        if not self._current_bill:
            return

        try:
            inv = (
                self._current_bill.get("invoice_no")
                or self._current_bill.get("performa_no")
                or "invoice"
            )

            fname = f"Invoice_{inv.replace('/', '_').replace(' ', '_')}.pdf"
            pdf_path = os.path.join(tempfile.gettempdir(), fname)

            is_draft = (self._current_store == "temp")
            is_performa = (self._current_store == "performa")

            ok = draw_invoice(
                self._current_bill,
                pdf_path,
                draft=is_draft,
                performa=is_performa
            )

            if not ok:
                QMessageBox.warning(self, "Error", "Failed to generate PDF")
                return

            self._call_share_bridge(pdf_path)

        except Exception as e:
            QMessageBox.warning(self, "Error sharing", str(e))

    def _call_share_bridge(self, pdf_path):

        if not os.path.exists(pdf_path):
            QMessageBox.warning(self, "Error", "PDF not found")
            return

        try:
            subprocess.Popen([
                get_bridge_path(),
                pdf_path
            ])
        except Exception as e:
            QMessageBox.warning(self, "Bridge Error", str(e))

    def refresh(self):
        self.load_bills()


class _EwayDialog(QDialog):
    def __init__(self, invoice_no: str, parent=None):
        super().__init__(parent)
        self.setWindowTitle("E-Way Bill Required")
        self.setFixedWidth(420)
        self.setStyleSheet(f"background: {C_BG};")
        vl = QVBoxLayout(self)
        vl.setContentsMargins(24, 20, 24, 20)
        vl.setSpacing(14)
        vl.addWidget(_h(13,
            f"Invoice {invoice_no} exceeds ₹50,000.\n"
            f"Please enter the E-Way Bill number to finalize.",
            color=C_WHITE_DIM))
        vl.addWidget(_divider())
        self._edit = _field("E-Way Bill No.")
        vl.addWidget(self._edit)
        btns = QHBoxLayout()
        ok_btn = QPushButton("Proceed")
        ok_btn.setStyleSheet(BTN_PRIMARY)
        ok_btn.setMinimumHeight(36)
        ok_btn.clicked.connect(self.accept)
        cancel_btn = QPushButton("Cancel")
        cancel_btn.setStyleSheet(BTN_OUTLINE)
        cancel_btn.setMinimumHeight(36)
        cancel_btn.clicked.connect(self.reject)
        btns.addStretch()
        btns.addWidget(cancel_btn)
        btns.addWidget(ok_btn)
        vl.addLayout(btns)

    def eway_value(self) -> str:
        return self._edit.text().strip()


class ProductsPage(QWidget):
    product_changed = Signal()

    def __init__(self, go_home):
        super().__init__()
        self.go_home = go_home
        self.editing_row        = None
        self.editing_product_id = None

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        root.addWidget(_topbar("Products", go_home))

        # 2. Create the Scroll Area
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.NoFrame)
        scroll.setStyleSheet(f"QScrollArea {{ background: {C_BG}; border: none; }}")

        # 3. Create the Scroll Content Widget (The Body)
        body = QWidget()
        body.setStyleSheet(f"background: {C_BG};")
        bl = QVBoxLayout(body)
        bl.setContentsMargins(16, 16, 16, 16)
        bl.setSpacing(16)

        tcard, tvl = _card("PRODUCT LIST")
        self.table = QTableWidget()
        self.table.setColumnCount(4)
        self.table.setHorizontalHeaderLabels(["Product Name", "HSN Code", "Rate (₹)", "Action"])
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.verticalHeader().setVisible(False)
        self.table.setAlternatingRowColors(True)
        self.table.verticalHeader().setDefaultSectionSize(65)
        self.table.setVerticalScrollMode(QAbstractItemView.ScrollPerPixel)

        self.table.setMinimumHeight(400) 

        hdr = self.table.horizontalHeader()
        hdr.setSectionResizeMode(0, QHeaderView.Stretch)
        hdr.setSectionResizeMode(1, QHeaderView.ResizeToContents)
        hdr.setSectionResizeMode(2, QHeaderView.ResizeToContents)
        hdr.setSectionResizeMode(3, QHeaderView.Fixed)
        hdr.resizeSection(3, 200)

        tvl.addWidget(self.table)
        bl.addWidget(tcard)

        acard, avl = _card("ADD PRODUCT")
        arow = QHBoxLayout()
        arow.setSpacing(8)

        self.name_input = _field("Product name")
        self.hsn_input  = _field("HSN code")
        self.rate_input = _field("Default rate (₹)")

        add_btn = QPushButton("Add Product")
        add_btn.setStyleSheet(BTN_PRIMARY)
        add_btn.setMinimumHeight(34)
        add_btn.setMaximumWidth(130)
        add_btn.clicked.connect(self.add_product)

        arow.addWidget(self.name_input, 3)
        arow.addWidget(self.hsn_input, 1)
        arow.addWidget(self.rate_input, 1)
        arow.addWidget(add_btn)
        avl.addLayout(arow)
        bl.addWidget(acard)

        rcard, rvl = _card("CLIENT-SPECIFIC RATES")

        srow = QHBoxLayout()
        srow.setSpacing(8)

        self.client_combo = _NoScrollComboBox()
        self.client_combo.setMinimumHeight(34)
        self.product_combo = _NoScrollComboBox()
        self.product_combo.setMinimumHeight(34)
        self.client_rate_input = _field("Custom rate (₹)")

        set_btn = QPushButton("Set Rate")
        set_btn.setStyleSheet(BTN_NAVY)
        set_btn.setMinimumHeight(34)
        set_btn.setMaximumWidth(100)
        set_btn.clicked.connect(self.set_client_rate)

        srow.addWidget(_fl("Client"))
        srow.addWidget(self.client_combo, 2)
        srow.addWidget(_fl("Product"))
        srow.addWidget(self.product_combo, 2)
        srow.addWidget(_fl("Rate"))
        srow.addWidget(self.client_rate_input, 1)
        srow.addWidget(set_btn)
        rvl.addLayout(srow)

        vrow = QHBoxLayout()
        self.view_rates_combo = _NoScrollComboBox()
        self.view_rates_combo.setMinimumHeight(34)

        view_rates_btn = QPushButton("View Rates")
        view_rates_btn.setStyleSheet(BTN_OUTLINE)
        view_rates_btn.setMinimumHeight(34)
        view_rates_btn.setMaximumWidth(110)
        view_rates_btn.clicked.connect(self._view_client_rates)

        vrow.addWidget(_fl("View rates for"))
        vrow.addWidget(self.view_rates_combo, 2)
        vrow.addWidget(view_rates_btn)
        vrow.addStretch()
        rvl.addLayout(vrow)

        self.rates_table = QTableWidget()
        self.rates_table.setColumnCount(5)
        self.rates_table.setHorizontalHeaderLabels(
            ["Product Name", "HSN", "Default Rate", "Client Rate", "Action"]
        )
        self.rates_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.rates_table.verticalHeader().setVisible(False)
        self.rates_table.setAlternatingRowColors(True)
        self.rates_table.verticalHeader().setDefaultSectionSize(40)
        self.rates_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)

        self.rates_table.setMinimumHeight(300)

        rvl.addWidget(self.rates_table)
        bl.addWidget(rcard)

        bl.addStretch()
        scroll.setWidget(body)
        root.addWidget(scroll)

        self.load_products()
        self.load_clients()

    # ─────────────────────────────────────────────

    def _btns(self, *btns):
        container = QWidget()
        container.setStyleSheet("background: transparent;")
        
        layout = QHBoxLayout(container)
        layout.setContentsMargins(5, 0, 5, 0)
        layout.setSpacing(8)
        layout.setAlignment(Qt.AlignCenter)

        for b in btns:
            b.setFixedHeight(30)
            b.setMinimumWidth(70)
            layout.addWidget(b)

        return container

    def load_products(self):
        _, _, df = acc_manager.view_products()
        self.table.setRowCount(0)
        self.product_combo.clear()

        if df is None or df.empty:
            return

        self.table.verticalHeader().setDefaultSectionSize(60) 

        for i, (_, row) in enumerate(df.iterrows()):
            self.table.insertRow(i)

            # Center Name
            name_item = QTableWidgetItem(row["Name"])
            name_item.setData(Qt.UserRole, row["ProductId"])
            name_item.setTextAlignment(Qt.AlignVCenter | Qt.AlignLeft)

            hsn_item = QTableWidgetItem(str(row["HSN"]))
            hsn_item.setTextAlignment(Qt.AlignVCenter | Qt.AlignCenter)

            rate_item = QTableWidgetItem(str(row["Rate"]))
            rate_item.setTextAlignment(Qt.AlignVCenter | Qt.AlignCenter)

            self.table.setItem(i, 0, name_item)
            self.table.setItem(i, 1, hsn_item)
            self.table.setItem(i, 2, rate_item)

            eb = QPushButton("Edit")
            eb.setStyleSheet(BTN_CELL_EDIT)
            eb.clicked.connect(lambda _, r=i: self.start_edit(r))

            db = QPushButton("Delete")
            db.setStyleSheet(BTN_CELL_DANGER)
            pid = row["ProductId"]
            db.clicked.connect(lambda _, p=pid: self._delete_product(p))

            self.table.setCellWidget(i, 3, self._btns(eb, db))
            self.product_combo.addItem(row["Name"], row["ProductId"])

    def add_product(self):
        status, msg = acc_manager.save_products(
            self.name_input.text(), self.hsn_input.text(), self.rate_input.text()
        )
        QMessageBox.information(self, status, msg)

        if status == "Success":
            self.name_input.clear()
            self.hsn_input.clear()
            self.rate_input.clear()
            self.load_products()
            self.product_changed.emit()

    def _delete_product(self, product_id: str):
        name = product_id
        if not acc_manager.products_data.empty:
            row = acc_manager.products_data[
                acc_manager.products_data["ProductId"] == product_id
            ]
            if not row.empty:
                name = row.iloc[0]["Name"]

        reply = QMessageBox.question(
            self, "Confirm Delete",
            f"Are you sure you want to delete product '{name}'?\n\n"
            f"This product will be removed from the product list.\n"
            f"Client-specific rates for this product will no longer apply.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if reply != QMessageBox.StandardButton.Yes:
            return

        if self.editing_row is not None:
            name_item = self.table.item(self.editing_row, 0)
            if name_item and name_item.data(Qt.UserRole) == product_id:
                self._discard_edit()

        status, msg = acc_manager.delete_product(product_id)
        QMessageBox.information(self, status, msg)
        if status == "Success":
            self.load_products()
            self.product_changed.emit()

    def start_edit(self, row):
        if self.editing_row is not None:
            QMessageBox.warning(self, "Edit In Progress", "Finish current edit first.")
            return

        self.editing_row = row
        self.editing_product_id = self.table.item(row, 0).data(Qt.UserRole)

        # Wider editable fields so text doesn't get cut off
        for col in (1, 2):
            f = QLineEdit(self.table.item(row, col).text())
            f.setMinimumWidth(80)
            f.setStyleSheet(
                f"QLineEdit {{ background: {C_SURFACE_HI}; color: {C_WHITE}; "
                f"border: 1px solid {C_BORDER_DARK}; border-radius: 4px; padding: 4px 8px; }}"
            )
            self.table.setCellWidget(row, col, f)

        sb = QPushButton("Save")
        sb.setStyleSheet(BTN_CELL_SAVE)
        sb.clicked.connect(self.update_product)

        db = QPushButton("Discard")
        db.setStyleSheet(BTN_CELL_DISCARD)
        db.clicked.connect(self._discard_edit)

        self.table.setCellWidget(row, 3, self._btns(sb, db))

    def _discard_edit(self):
        self.editing_row = None
        self.editing_product_id = None
        self.load_products()

    def update_product(self):
        row  = self.editing_row
        hsn  = self.table.cellWidget(row, 1).text()
        rate = self.table.cellWidget(row, 2).text()
        name = self.table.item(row, 0).text()

        status, msg = acc_manager.edit_product(self.editing_product_id, name, hsn, rate)
        QMessageBox.information(self, status, msg)

        if status == "Success":
            self.editing_row = None
            self.editing_product_id = None
            self.load_products()

    def load_clients(self):
        acc_manager.load_data()
        df = acc_manager.load_clients()

        self.client_combo.clear()
        self.view_rates_combo.clear()

        if df is None or df.empty:
            return

        for _, row in df.iterrows():
            self.client_combo.addItem(row["Company"], row["ClientId"])
            self.view_rates_combo.addItem(row["Company"], row["ClientId"])

    def set_client_rate(self):
        status, msg = acc_manager.set_client_rates(
            self.client_combo.currentData(),
            self.product_combo.currentData(),
            self.client_rate_input.text()
        )
        QMessageBox.information(self, status, msg)

        if status == "Success":
            self.client_rate_input.clear()

    def _view_client_rates(self):
        client_id = self.view_rates_combo.currentData()
        if not client_id:
            return

        df = acc_manager.get_client_rates_for_company(client_id)
        self.rates_table.setRowCount(0)

        if df.empty:
            return

        self.rates_table.verticalHeader().setDefaultSectionSize(60)

        for i, (_, row) in enumerate(df.iterrows()):
            self.rates_table.insertRow(i)

            name_item = QTableWidgetItem(str(row["Name"]))
            name_item.setTextAlignment(Qt.AlignVCenter | Qt.AlignLeft)
            self.rates_table.setItem(i, 0, name_item)

            hsn_item = QTableWidgetItem(str(row["HSN"]))
            hsn_item.setTextAlignment(Qt.AlignVCenter | Qt.AlignCenter)
            self.rates_table.setItem(i, 1, hsn_item)

            def_rate_item = QTableWidgetItem(str(row["DefaultRate"]))
            def_rate_item.setTextAlignment(Qt.AlignVCenter | Qt.AlignCenter)
            self.rates_table.setItem(i, 2, def_rate_item)

            cr = row["ClientRate"]
            client_rate_text = str(cr) if pd.notna(cr) else "—"
            cr_item = QTableWidgetItem(client_rate_text)
            cr_item.setTextAlignment(Qt.AlignVCenter | Qt.AlignCenter)
            self.rates_table.setItem(i, 3, cr_item)

            if pd.notna(cr):
                btn = QPushButton("Delete")
                btn.setStyleSheet(BTN_CELL_DANGER)
                pid = row["ProductId"]
                # Connect click event
                btn.clicked.connect(lambda _, p=pid: self._delete_client_rate(client_id, p))

                self.rates_table.setCellWidget(i, 4, self._btns(btn))

    def _delete_client_rate(self, client_id, product_id):
        status, msg = acc_manager.delete_client_rate(client_id, product_id)
        QMessageBox.information(self, status, msg)

        if status == "Success":
            self._view_client_rates()

class ViewLedgerDialog(QDialog):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Ledger Statement")
        self.resize(1000, 680)
        self.setStyleSheet(f"background: {C_BG};")

        root = QVBoxLayout(self)
        root.setContentsMargins(24, 20, 24, 20)
        root.setSpacing(16)
        root.addWidget(_h(17, "Ledger Statement", bold=True, color=C_WHITE))

        fcard, fvl = _card("FILTER")
        frow = QHBoxLayout()
        frow.setSpacing(16)
        self.company_combo = _NoScrollComboBox()
        self.company_combo.setMinimumHeight(36)
        self.company_combo.setMinimumWidth(220)
        companies = acc_manager.get_company_names()
        if companies:
            self.company_combo.addItems(companies)
        self.from_date = QDateEdit()
        self.from_date.setCalendarPopup(True)
        self.from_date.setDate(QDate.currentDate().addMonths(-1))
        self.from_date.setMinimumHeight(36)
        self.to_date = QDateEdit()
        self.to_date.setCalendarPopup(True)
        self.to_date.setDate(QDate.currentDate())
        self.to_date.setMinimumHeight(36)
        view_btn = QPushButton("View Ledger")
        view_btn.setStyleSheet(BTN_NAVY)
        view_btn.setMinimumHeight(36)
        view_btn.clicked.connect(self.load_ledger)

        # REPLACE dl_xls with share_btn
        self.share_btn = QPushButton("Share") 
        dl_pdf  = QPushButton("Export PDF")
        btn_prt = QPushButton("🖨  Print")
        
        self.share_btn.setStyleSheet(BTN_OUTLINE)
        dl_pdf.setStyleSheet(BTN_OUTLINE)
        btn_prt.setStyleSheet(BTN_NAVY)

        for b in (self.share_btn, dl_pdf, btn_prt):
            b.setMinimumHeight(36)

        self.share_btn.clicked.connect(self.share_ledger)
        dl_pdf.clicked.connect(self.export_pdf)
        btn_prt.clicked.connect(self.print_document)

        frow.addWidget(_fl("Company"))
        frow.addWidget(self.company_combo, 2)
        frow.addWidget(_fl("From"))
        frow.addWidget(self.from_date)
        frow.addWidget(_fl("To"))
        frow.addWidget(self.to_date)
        frow.addStretch()
        frow.addWidget(view_btn)
        frow.addWidget(self.share_btn)
        frow.addWidget(dl_pdf)
        frow.addWidget(btn_prt)
        fvl.addLayout(frow)
        root.addWidget(fcard)

        self.table = QTableWidget()
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.verticalHeader().setVisible(False)
        self.table.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.table.setAlternatingRowColors(True)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        root.addWidget(self.table, 1)

        self.df          = None
        self.client_data = None
        self.owner_data  = acc_manager.owner_data

    def share_ledger(self):
        if self.df is None:
            QMessageBox.warning(self, "No Data", "Load a ledger first.")
            return

        try:
            # 1. Create a safe filename
            company = self.company_combo.currentText().replace("/", "_").replace(" ", "_")
            fname = f"Ledger_{company}_{self.from_date.date().toString('yyyyMMdd')}.pdf"
            pdf_path = os.path.join(tempfile.gettempdir(), fname)

            # 2. Render the PDF (Reuse your existing PDF generation logic)
            printer = self._build_printer(output_file=pdf_path)
            doc = self._make_document(printer)
            doc.print_(printer)

            # 3. Call the bridge
            self._call_share_bridge(pdf_path)

        except Exception as e:
            QMessageBox.warning(self, "Error sharing", f"Could not share ledger: {str(e)}")

    def _call_share_bridge(self, pdf_path):
        if not os.path.exists(pdf_path):
            QMessageBox.warning(self, "Error", "PDF not found")
            return

        try:
            subprocess.Popen([
                get_bridge_path(),
                pdf_path
            ])
        except Exception as e:
            QMessageBox.warning(self, "Bridge Error", str(e))

    def load_ledger(self):
        company   = self.company_combo.currentText()
        from_date = self.from_date.date().toPython()
        to_date   = self.to_date.date().toPython()
        status, message, df = acc_manager.view_ledger(company, from_date, to_date)
        if status:
            QMessageBox.warning(self, status, message); return
        self.df = df.replace({r"\n": " "}, regex=True).fillna("")
        self.client_data = acc_manager.client_details(company)
        self._populate_table()

    def _populate_table(self):
        self.table.clearContents()
        self.table.setRowCount(len(self.df))
        self.table.setColumnCount(len(self.df.columns))
        self.table.setHorizontalHeaderLabels(self.df.columns.tolist())
        for r in range(len(self.df)):
            is_special = str(self.df.iloc[r, 1]) in ("Total", "Closing Balance", "Opening Balance")
            for c in range(len(self.df.columns)):
                item = QTableWidgetItem(str(self.df.iloc[r, c]))
                item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                item.setFlags(Qt.ItemFlag.ItemIsSelectable | Qt.ItemFlag.ItemIsEnabled)
                if is_special:
                    item.setFont(QFont(FONT_UI, 12, QFont.Weight.Bold))
                    item.setForeground(QColor(C_WHITE))
                self.table.setItem(r, c, item)

    def _create_html(self):
        df     = self.df.copy().replace({r"\n": " "}, regex=True).fillna("")
        owner  = {k: v for k, v in self.owner_data.items()  if v}
        client = {k: v for k, v in self.client_data.items() if v}
        from_d = self.from_date.date().toString("dd MMM yyyy")
        to_d   = self.to_date.date().toString("dd MMM yyyy")
        today  = QDate.currentDate().toString("dd MMM yyyy")

        # Count columns to decide font size — more columns = slightly smaller
        n_cols = len(df.columns)
        font_size = max(7, 11 - max(0, n_cols - 5))  # 11px for ≤5 cols, down to 7px min

        table_html = (
            df.to_html(index=False, border=0)
            .replace(
                "<table",
                f'<table style="border-collapse:collapse;width:100%;table-layout:fixed;font-size:{font_size}px;"'
            )
            .replace(
                "<th>",
                f'<th style="border:1px solid #ccc;padding:5px 6px;background:#1B2A4A;'
                f'color:white;text-align:center;word-wrap:break-word;overflow-wrap:break-word;">'
            )
            .replace(
                "<td>",
                f'<td style="border:1px solid #e5e7eb;padding:5px 6px;'
                f'word-wrap:break-word;overflow-wrap:break-word;white-space:normal;">'
            )
        )

        header = f"""
        <div style="text-align:center;margin-bottom:16px;font-family:Arial;">
            <div style="font-size:16px;font-weight:bold;color:#1B2A4A;">{owner.get('Company','')}</div>
            <div style="font-size:10px;color:#4A5568;margin-top:3px;">{owner.get('Address','')}</div>
            <hr style="border:1px solid #e5e7eb;margin:10px 0;">
            <div style="font-size:12px;font-weight:bold;">{client.get('Company','')}</div>
            <div style="font-size:9px;color:#4A5568;">{client.get('Address','')}</div>
            <br>
            <div style="font-size:12px;font-weight:bold;color:#1B2A4A;">Ledger Statement</div>
            <div style="font-size:9px;color:#4A5568;">{from_d} to {to_d} &nbsp;|&nbsp; Printed: {today}</div>
        </div>"""

        return f'<div style="width:100%;font-family:Arial;">{header}{table_html}</div>'

    def _build_printer(self, output_file: str | None = None) -> QPrinter:
        """Create a QPrinter pre-configured with A4 portrait + hole-punch margins."""
        printer = QPrinter(QPrinter.PrinterMode.HighResolution)
        if output_file:
            printer.setOutputFormat(QPrinter.OutputFormat.PdfFormat)
            printer.setOutputFileName(output_file)
        else:
            printer.setOutputFormat(QPrinter.OutputFormat.NativeFormat)
        printer.setPageLayout(PAGE_LAYOUT)
        return printer

    def _make_document(self, printer: QPrinter) -> QTextDocument:
        doc = QTextDocument()
        page_rect = printer.pageRect(QPrinter.Unit.Point)
        doc.setPageSize(QSizeF(page_rect.width(), page_rect.height()))
        doc.setHtml(self._create_html())
        doc.setDocumentMargin(0)
        return doc

    def export_pdf(self):
        if self.df is None:
            QMessageBox.warning(self, "No Data", "Load a ledger first.")
            return

        settings = QSettings("YourCompany", "YourApp")

        last_dir = settings.value("last_export_dir", "")

        company = self.company_combo.currentText().replace(" ", "_")
        default_filename = f"{company}_ledger_{self.from_date.date().toString('yyyy-MM-dd')}.pdf"

        default_path = os.path.join(last_dir, default_filename) if last_dir else default_filename

        fp, _ = QFileDialog.getSaveFileName(
            self, 
            "Export PDF", 
            default_path, 
            "PDF Files (*.pdf)"
        )

        if not fp:
            return

        new_dir = os.path.dirname(fp)
        settings.setValue("last_export_dir", new_dir)

        printer = self._build_printer(output_file=fp)
        doc = self._make_document(printer)
        doc.print_(printer)
        
        QMessageBox.information(self, "Success", f"PDF saved to:\n{fp}")

    def print_document(self):
        if self.df is None:
            QMessageBox.warning(self, "No Data", "Load a ledger first.")
            return

        printer = self._build_printer()

        page_dlg = QPageSetupDialog(printer, self)
        page_dlg.setWindowTitle("Page Setup")
        if page_dlg.exec() != QPageSetupDialog.DialogCode.Accepted:
            return

        print_dlg = QPrintDialog(printer, self)
        print_dlg.setWindowTitle("Select Printer")
        print_dlg.setOption(QPrintDialog.PrintDialogOption.PrintToFile, True)
        print_dlg.setOption(QPrintDialog.PrintDialogOption.PrintPageRange, False)
        if print_dlg.exec() != QPrintDialog.DialogCode.Accepted:
            return

        self._show_print_preview(printer)

    def _show_print_preview(self, printer: QPrinter):
        preview = QPrintPreviewDialog(printer, self)
        preview.setWindowTitle("Print Preview – Ledger Statement")
        preview.setWindowState(Qt.WindowState.WindowMaximized)

        def render(pr: QPrinter):
            doc = self._make_document(pr)
            doc.print_(pr)

        preview.paintRequested.connect(render)
        preview.exec()

    def export_excel(self):
        if self.df is None:
            QMessageBox.warning(self, "No Data", "Load a ledger first."); return
        company = self.company_combo.currentText().replace(" ", "_")
        fp, _ = QFileDialog.getSaveFileName(
            self, "Save Excel",
            f"{company}_ledger_{self.from_date.date().toString('yyyy-MM-dd')}.xlsx",
            "Excel Files (*.xlsx)"
        )
        if not fp:
            return
        with pd.ExcelWriter(fp, engine="openpyxl") as writer:
            self.df.to_excel(writer, index=False, startrow=10)
            sheet = writer.sheets["Sheet1"]
            sheet["A1"] = self.owner_data.get("Company", "")
            sheet["A4"] = self.client_data.get("Company", "")
            sheet["A7"] = "Ledger Statement"
        QMessageBox.information(self, "Success", "Excel exported.")


class LedgerDialog(QDialog):
    def __init__(self, clientId: str):
        super().__init__()
        self.clientId = clientId
        self.setWindowTitle("Ledger Entry")
        self.setFixedWidth(440)
        self.setStyleSheet(f"background: {C_BG};")

        root = QVBoxLayout(self)
        root.setContentsMargins(24, 20, 24, 20)
        root.setSpacing(16)
        root.addWidget(_h(15, "New Ledger Entry", bold=True, color=C_WHITE))
        root.addWidget(_divider())

        mode_row = QHBoxLayout()
        mode_row.setSpacing(12)
        self.manual_radio = QRadioButton("Manual Entry")
        self.bill_radio   = QRadioButton("From Bill Number")
        self.manual_radio.setChecked(True)
        mode_row.addWidget(self.manual_radio)
        mode_row.addWidget(self.bill_radio)
        mode_row.addStretch()
        root.addLayout(mode_row)

        self.bill_panel = QFrame()
        self.bill_panel.setStyleSheet(
            f"background: {C_SURFACE}; border: 1px solid {C_BORDER}; border-radius: 5px;"
        )
        bp = QHBoxLayout(self.bill_panel)
        bp.setContentsMargins(12, 10, 12, 10)
        bp.setSpacing(10)
        self.bill_no_combo = _NoScrollComboBox()
        self.bill_no_combo.setMinimumHeight(36)
        self.bill_no_combo.setMinimumWidth(220)
        for (_, inv, client, _) in acc_manager.get_all_bill_invoice_numbers("temp"):
            self.bill_no_combo.addItem(f"{inv}  ({client})", inv)
        load_bill_btn = QPushButton("Load")
        load_bill_btn.setStyleSheet(BTN_NAVY)
        load_bill_btn.setFixedHeight(36)
        load_bill_btn.clicked.connect(self._load_from_bill)
        bp.addWidget(_fl("Bill No."))
        bp.addWidget(self.bill_no_combo, 1)
        bp.addWidget(load_bill_btn)
        root.addWidget(self.bill_panel)
        self.bill_panel.setVisible(False)

        form = QFormLayout()
        form.setSpacing(12)
        form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)

        id_badge = QLabel(clientId)
        id_badge.setStyleSheet(GOLD_BADGE)
        form.addRow(_fl("Client ID"), id_badge)

        self.date_input = QDateEdit()
        self.date_input.setCalendarPopup(True)
        self.date_input.setDate(QDate.currentDate())
        self.date_input.setDisplayFormat("dd/MM/yyyy")
        self.date_input.setMinimumHeight(36)
        form.addRow(_fl("Date"), self.date_input)

        self.amount = NoScrollDoubleSpinBox()
        self.amount.setRange(0, 999_999_999)
        self.amount.setDecimals(2)
        self.amount.setPrefix("₹ ")
        self.amount.setMinimumHeight(36)
        form.addRow(_fl("Amount"), self.amount)

        entry_row = QHBoxLayout()
        self.credit_radio = QRadioButton("Credit")
        self.debit_radio  = QRadioButton("Debit")
        self.debit_radio.setChecked(True)
        entry_row.addWidget(self.credit_radio)
        entry_row.addSpacing(20)
        entry_row.addWidget(self.debit_radio)
        entry_row.addStretch()
        form.addRow(_fl("Entry Type"), entry_row)

        self.voucher_combo = _NoScrollComboBox()
        self.voucher_combo.addItems(["Sales", "Purchase", "Payment", "Receipt", "Custom"])
        self.voucher_combo.setMinimumHeight(36)
        self.voucher_combo.currentTextChanged.connect(
            lambda t: self.custom_voucher_input.setVisible(t == "Custom")
        )
        form.addRow(_fl("Voucher Type"), self.voucher_combo)

        self.custom_voucher_input = _field("Enter custom voucher type")
        self.custom_voucher_input.setVisible(False)
        form.addRow("", self.custom_voucher_input)

        self.manual_voucher_no = _field("Auto-generate if blank")
        form.addRow(_fl("Voucher No."), self.manual_voucher_no)

        root.addLayout(form)
        root.addWidget(_divider())

        btn_row = QHBoxLayout()
        btn_row.setSpacing(10)
        save_btn = QPushButton("Save Entry")
        save_btn.setStyleSheet(BTN_PRIMARY)
        save_btn.setMinimumHeight(38)
        save_btn.setMinimumWidth(130)
        save_btn.clicked.connect(self.save_entry)
        cancel_btn = QPushButton("Cancel")
        cancel_btn.setStyleSheet(BTN_OUTLINE)
        cancel_btn.setMinimumHeight(38)
        cancel_btn.setMinimumWidth(90)
        cancel_btn.clicked.connect(self.reject)
        btn_row.addStretch()
        btn_row.addWidget(cancel_btn)
        btn_row.addWidget(save_btn)
        root.addLayout(btn_row)

        self.manual_radio.toggled.connect(self._toggle_mode)
        self.bill_radio.toggled.connect(self._toggle_mode)

    def _toggle_mode(self):
        self.bill_panel.setVisible(self.bill_radio.isChecked())

    def _load_from_bill(self):
        inv = self.bill_no_combo.currentData()
        if not inv:
            return
        bill = acc_manager.get_temp_bill_by_invoice(inv)
        if not bill:
            _warn(self, f"Invoice {inv} not found in temp bills."); return
        grand_total = bill.get("grand_total", "0").replace(",", "")
        bill_date   = bill.get("bill_date") or bill.get("date", "")
        try:
            dt = datetime.strptime(bill_date, "%d/%m/%Y")
            self.date_input.setDate(QDate(dt.year, dt.month, dt.day))
        except Exception:
            pass
        try:
            self.amount.setValue(float(grand_total))
        except Exception:
            pass
        self.debit_radio.setChecked(True)
        self.voucher_combo.setCurrentText("Sales")
        self.manual_voucher_no.setText(inv)
        QMessageBox.information(self, "Loaded", f"Bill {inv} loaded. Review and save.")

    def save_entry(self):
        amount = self.amount.value()
        if amount <= 0:
            _warn(self, "Amount must be greater than 0."); return
        entry_type   = "Credit" if self.credit_radio.isChecked() else "Debit"
        voucher_type = self.voucher_combo.currentText()
        if voucher_type == "Custom":
            voucher_type = self.custom_voucher_input.text().strip()
            if not voucher_type:
                _warn(self, "Enter a custom voucher type."); return
        manual_vno = self.manual_voucher_no.text().strip()
        status, message = acc_manager.update_ledger(
            self.date_input.date().toString("dd/MM/yyyy"),
            self.clientId, amount, entry_type, voucher_type,
            manual_voucher_no=manual_vno
        )
        QMessageBox.information(self, status, message)
        if status == "Success":
            self.accept()


class ViewClientsPage(QWidget):
    def __init__(self, go_home):
        super().__init__()
        self.go_home        = go_home
        self.state_code_map = state_code_map
        self._editing_row   = None
        self._visible_rows  = 0

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)
        root.addWidget(_topbar("Clients", go_home))

        body = QWidget()
        body.setStyleSheet(f"background: {C_BG};")
        bl = QVBoxLayout(body)
        bl.setContentsMargins(28, 24, 28, 24)

        self.table = QTableWidget()
        self._body = body
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.verticalHeader().setVisible(False)
        self.table.setAlternatingRowColors(True)
        self.table.verticalHeader().setDefaultSectionSize(60)
        self.table.setVerticalScrollMode(QAbstractItemView.ScrollPerPixel)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.table.horizontalHeader().setStretchLastSection(False)

        bl.addWidget(self.table)
        root.addWidget(body, 1)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        topbar_h = 56
        margins  = 24 + 24
        header_h = self.table.horizontalHeader().height()
        row_h    = self.table.verticalHeader().defaultSectionSize()
        available = self.height() - topbar_h - margins - header_h
        self._visible_rows = max(1, available // row_h)
        self.table.setMaximumHeight(header_h + self._visible_rows * row_h)

    def _btns(self, *btns):
        w = QWidget()
        l = QHBoxLayout(w)
        l.setContentsMargins(4, 4, 4, 4)
        l.setSpacing(6)
        l.addStretch()
        for b in btns:
            b.setFixedHeight(30)
            b.setMinimumWidth(60)
            b.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
            l.addWidget(b)
        l.addStretch()
        return w

    def load_clients(self):
        self._editing_row = None
        try:
            acc_manager.load_data()
            df = acc_manager.load_clients()
            if df.empty:
                self._load_empty(); return
        except Exception:
            self._load_empty(); return

        self._df = df
        display_cols = ["Company", "Client_name", "Mobile"]
        available    = list(df.columns)
        show_cols    = [c for c in available if c in display_cols]

        self.table.setColumnCount(len(show_cols) + 2)
        self.table.clearContents()
        self.table.setRowCount(len(df))

        labels = []
        for c in show_cols:
            friendly = {"Company": "Company", "Client_name": "Client Name", "Mobile": "Mobile"}.get(c, c)
            labels.append(friendly)
        labels += ["Details", "Ledger"]
        self.table.setHorizontalHeaderLabels(labels)

        n = len(show_cols)
        for col_idx, width in [(n, 100), (n + 1, 100)]:
            self.table.horizontalHeader().setSectionResizeMode(col_idx, QHeaderView.Fixed)
            self.table.setColumnWidth(col_idx, width)

        for row in range(len(df)):
            for col_idx, col_name in enumerate(show_cols):
                val = df.iloc[row][col_name]
                item = QTableWidgetItem("" if pd.isna(val) else str(val))
                item.setFlags(Qt.ItemIsSelectable | Qt.ItemIsEnabled)
                self.table.setItem(row, col_idx, item)

            details_btn = QPushButton("Details")
            details_btn.setStyleSheet(BTN_CELL_VIEW)
            details_btn.clicked.connect(lambda _, r=row: self._open_detail_dialog(r))
            self.table.setCellWidget(row, n, self._btns(details_btn))

            ledger_btn = QPushButton("Ledger")
            ledger_btn.setStyleSheet(BTN_CELL_LEDGER)
            ledger_btn.clicked.connect(lambda _, r=row: self.update_ledger(r))
            self.table.setCellWidget(row, n + 1, self._btns(ledger_btn))

        self.resizeEvent(None)

    def _open_detail_dialog(self, row):
        if not hasattr(self, "_df") or self._df is None:
            return
        row_data = self._df.iloc[row]
        details  = {col: ("" if pd.isna(val) else str(val)) for col, val in row_data.items()}
        dlg = ClientDetailDialog(details, self)
        dlg.exec()
        self.load_clients()

    def update_ledger(self, row):
        if not hasattr(self, "_df") or self._df is None:
            return
        clientId = str(self._df.iloc[row]["ClientId"])
        d = LedgerDialog(clientId)
        d.exec()
        self.load_clients()

    def _load_empty(self):
        self.table.clear()
        self.table.setRowCount(1)
        self.table.setColumnCount(1)
        self.table.setHorizontalHeaderLabels(["Status"])
        item = QTableWidgetItem("No clients found")
        item.setTextAlignment(Qt.AlignCenter)
        item.setFlags(Qt.ItemIsEnabled)
        self.table.setItem(0, 0, item)


class ClientDetailDialog(QDialog):
    _NO_EDIT = {"ClientId", "createdAt", "Company", "CreatedAT"}
    _FIELD_LABELS = {
        "ClientId":    "Client ID",
        "CreatedAT":   "Created At",
        "Company":     "Company",
        "Client_name": "Contact Name",
        "Mobile":      "Mobile",
        "AltMobile":   "Alt. Mobile",
        "GST":         "GST Number",
        "Address":     "Address",
        "Pincode":     "Pincode",
        "State":       "State",
        "StateCode":   "State Code",
        "BankName":    "Bank Name",
        "Account_no":  "Account No.",
        "IFSC":        "IFSC Code",
    }

    def __init__(self, details: dict, parent: QWidget | None = None):
        super().__init__(parent)
        self.setWindowTitle("Client Details")
        self.resize(560, 560)
        self.setStyleSheet(f"background: {C_BG};")

        self._details   = dict(details)
        self._edit_mode = False
        self._widgets   = {}

        self._root = QVBoxLayout(self)
        self._root.setContentsMargins(24, 20, 24, 20)
        self._root.setSpacing(14)

        company = details.get("Company", "—")
        self._root.addWidget(_h(16, company, bold=True, color=C_WHITE))
        self._root.addWidget(_divider())

        self._scroll = QScrollArea()
        self._scroll.setWidgetResizable(True)
        self._scroll.setStyleSheet("border: none; background: transparent;")
        self._inner  = QWidget()
        self._inner.setStyleSheet("background: transparent;")
        self._form   = QFormLayout(self._inner)
        self._form.setSpacing(10)
        self._form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)
        self._form.setContentsMargins(0, 8, 0, 8)
        self._scroll.setWidget(self._inner)
        self._root.addWidget(self._scroll, 1)

        self._build_form_view()

        self._btn_row = QHBoxLayout()
        self._btn_row.setSpacing(8)
        self._edit_btn    = QPushButton("Edit")
        self._save_btn    = QPushButton("Save")
        self._discard_btn = QPushButton("Discard")
        self._close_btn   = QPushButton("Close")
        self._edit_btn.setStyleSheet(BTN_CELL_EDIT)
        self._save_btn.setStyleSheet(BTN_CELL_SAVE)
        self._discard_btn.setStyleSheet(BTN_CELL_DISCARD)
        self._close_btn.setStyleSheet(BTN_OUTLINE)
        for btn in (self._edit_btn, self._save_btn, self._discard_btn, self._close_btn):
            btn.setFixedHeight(36)
            btn.setMinimumWidth(80)
        self._edit_btn.clicked.connect(self._enter_edit_mode)
        self._save_btn.clicked.connect(self._save_edits)
        self._discard_btn.clicked.connect(self._discard_edits)
        self._close_btn.clicked.connect(self.reject)
        self._btn_row.addStretch()
        self._btn_row.addWidget(self._edit_btn)
        self._btn_row.addWidget(self._save_btn)
        self._btn_row.addWidget(self._discard_btn)
        self._btn_row.addWidget(self._close_btn)
        self._root.addLayout(self._btn_row)
        self._set_button_state(editing=False)

    def _clear_form(self):
        while self._form.rowCount():
            self._form.removeRow(0)
        self._widgets.clear()

    def _build_form_view(self):
        self._clear_form()
        for key, label in self._FIELD_LABELS.items():
            if key not in self._details:
                continue
            val = str(self._details.get(key) or "—")
            val_lbl = QLabel(val)
            val_lbl.setWordWrap(True)
            val_lbl.setStyleSheet(
                f"color: {C_WHITE}; background: transparent; font-size: 13px;"
            )
            self._form.addRow(_fl(label), val_lbl)
            self._widgets[key] = val_lbl

    def _build_form_edit(self):
        _line_style = (
            f"color: {C_WHITE}; background: #2a2a3a; "
            f"border: 1px solid #444; border-radius: 4px; padding: 4px 6px;"
        )
        _combo_style = (
            f"color: {C_WHITE}; background-color: #000000; "
            f"border: 1px solid #444; border-radius: 4px; padding: 2px 4px;"
        )
        self._clear_form()
        for key, label in self._FIELD_LABELS.items():
            if key not in self._details:
                continue
            val = str(self._details.get(key) or "")
            if key in self._NO_EDIT:
                widget = QLabel(val or "—")
                widget.setWordWrap(True)
                widget.setStyleSheet("color: #aaa; background: transparent; font-size: 13px;")
            elif key == "State":
                widget = _NoScrollComboBox()
                widget.addItems(sorted(state_code_map.keys()))
                widget.addItem("Custom")
                widget.setCurrentText(val if val in state_code_map else "Custom")
                widget.currentTextChanged.connect(self._sync_state_code)
                widget.setStyleSheet(_combo_style)
            elif key == "StateCode":
                widget = _NoScrollComboBox()
                widget.addItems(sorted(state_code_map.values()))
                widget.setEditable(True)
                widget.setCurrentText(val)
                widget.setStyleSheet(_combo_style)
            elif key == "Address":
                widget = QTextEdit(val)
                widget.setFixedHeight(72)
                widget.setStyleSheet(_line_style)
            elif key in ("Mobile", "AltMobile"):
                widget = QLineEdit(val)
                widget.setMaxLength(10)
                widget.setValidator(
                    QRegularExpressionValidator(QRegularExpression("^[0-9]{0,10}$"))
                )
                widget.setStyleSheet(_line_style)
            elif key == "Pincode":
                widget = QLineEdit(val)
                widget.setMaxLength(6)
                widget.setValidator(
                    QRegularExpressionValidator(QRegularExpression("^[0-9]{0,6}$"))
                )
                widget.setStyleSheet(_line_style)
            else:
                widget = QLineEdit(val)
                widget.setStyleSheet(_line_style)
            self._form.addRow(_fl(label), widget)
            self._widgets[key] = widget

    def _set_button_state(self, editing: bool):
        self._edit_btn.setVisible(not editing)
        self._save_btn.setVisible(editing)
        self._discard_btn.setVisible(editing)

    def _sync_state_code(self, state_name: str):
        if state_name not in state_code_map:
            return
        sc_widget = self._widgets.get("StateCode")
        if isinstance(sc_widget, QComboBox):
            sc_widget.setCurrentText(state_code_map[state_name])

    def _enter_edit_mode(self):
        self._edit_mode = True
        self._build_form_edit()
        self._set_button_state(editing=True)

    def _discard_edits(self):
        self._edit_mode = False
        self._build_form_view()
        self._set_button_state(editing=False)

    def _save_edits(self):
        for mob_key, mob_label in (("Mobile", "Mobile"), ("AltMobile", "Alt. Mobile")):
            w = self._widgets.get(mob_key)
            if not isinstance(w, QLineEdit):
                continue
            val = w.text().strip()
            if mob_key == "Mobile" and val and len(val) != 10:
                QMessageBox.warning(self, "Validation", "Mobile must be exactly 10 digits.")
                return
            if mob_key == "AltMobile" and val and len(val) != 10:
                QMessageBox.warning(self, "Validation", "Alt. Mobile must be exactly 10 digits.")
                return

        updated = {}
        for key, widget in self._widgets.items():
            if isinstance(widget, QComboBox):
                updated[key] = widget.currentText().strip() or None
            elif isinstance(widget, QTextEdit):
                updated[key] = widget.toPlainText().strip() or None
            elif isinstance(widget, QLineEdit):
                updated[key] = widget.text().strip() or None
            else:
                updated[key] = self._details.get(key) or None

        status, message = acc_manager.update_client(updated)
        QMessageBox.information(self, status, message)
        if status.lower() in ("success", "ok", "saved"):
            for key, val in updated.items():
                self._details[key] = val or ""
        self._edit_mode = False
        self._build_form_view()
        self._set_button_state(editing=False)


class CreateClientPage(QWidget):
    client_saved = Signal()

    def __init__(self, go_home):
        super().__init__()
        self.go_home        = go_home
        self.state_code_map = state_code_map
        self._gst_worker: GSTFetchWorker | None = None

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)
        root.addWidget(_topbar("Create Client", go_home))

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("border: none;")
        body = QWidget()
        body.setStyleSheet(f"background: {C_BG};")
        bl = QVBoxLayout(body)
        bl.setContentsMargins(28, 24, 28, 24)
        bl.setSpacing(16)
        scroll.setWidget(body)
        root.addWidget(scroll, 1)

        # ── GST AUTO-FILL ─────────────────────────────────────────
        gcard, gvl = _card("GST AUTO-FILL")
        gst_note = _h(11,
            "Enter GST number and click Fetch to auto-fill company details from the GST portal.",
            color=C_GHOST)
        gst_note.setWordWrap(True)
        gvl.addWidget(gst_note)
        gst_row = QHBoxLayout()
        gst_row.setSpacing(12)
        self.gst_fetch_input = _field("15-character GST number")
        self.gst_fetch_input.setMaxLength(15)
        self.gst_fetch_input.textChanged.connect(
            lambda t: self.gst_fetch_input.setText(t.upper())
        )
        self.fetch_btn = QPushButton("Fetch Details")
        self.fetch_btn.setStyleSheet(BTN_NAVY)
        self.fetch_btn.setMinimumHeight(36)
        self.fetch_btn.setMinimumWidth(130)
        self.fetch_btn.clicked.connect(self._fetch_gst)
        self.gst_status_lbl = QLabel("")
        self.gst_status_lbl.setStyleSheet(f"color: {C_GHOST}; font-size: 11px;")
        gst_row.addWidget(_fl("GST No."))
        gst_row.addWidget(self.gst_fetch_input, 2)
        gst_row.addWidget(self.fetch_btn)
        gst_row.addWidget(self.gst_status_lbl, 1)
        gvl.addLayout(gst_row)
        bl.addWidget(gcard)

        # ── CLIENT INFO ─────────────────────────────────────────
        ccard, cvl = _card("CLIENT INFORMATION")
        cform = QFormLayout()
        self.company    = _field("Company name")
        self.client     = _field("Client name")
        self.mobile     = _field("Mobile")
        self.mobile.setMaxLength(10)
        self.mobile.setValidator(QRegularExpressionValidator(QRegularExpression("^[0-9]{0,10}$")))
        self.alt_mobile = _field("Alternate mobile (optional)")
        self.alt_mobile.setMaxLength(10)
        self.alt_mobile.setValidator(QRegularExpressionValidator(QRegularExpression("^[0-9]{0,10}$")))

        self.balance = NoScrollDoubleSpinBox()
        self.balance.setRange(-9_999_999_999, 9_999_999_999)
        self.balance.setDecimals(2)
        self.balance.setPrefix("₹ ")
        self.balance.setMinimumHeight(36)
        self.balance.setEnabled(False)
        self.balance_toggle = QPushButton("🔒")
        self.balance_toggle.setCheckable(True)
        self.balance_toggle.setChecked(True)
        self.balance_toggle.setFixedWidth(40)
        self.balance_toggle.clicked.connect(
            lambda: (
                self.balance.setEnabled(not self.balance_toggle.isChecked()),
                self.balance_toggle.setText("🔒" if self.balance_toggle.isChecked() else "🔓")
            )
        )
        balance_row = QHBoxLayout()
        balance_row.addWidget(self.balance)
        balance_row.addWidget(self.balance_toggle)

        self.gst = _field("GST")
        self.gst.setMaxLength(15)
        self.address = QTextEdit()
        self.address.setFixedHeight(80)
        self.pincode = _field("Pincode")
        self.pincode.setMaxLength(6)
        self.pincode.setValidator(QRegularExpressionValidator(QRegularExpression("^[0-9]{0,6}$")))

        self.state = _NoScrollComboBox()
        self.state.addItems(sorted(self.state_code_map.keys()))
        self.state.addItem("Other (Custom)")
        self.state.setMinimumHeight(36)
        self.state.setEnabled(False)
        self.state_toggle = QPushButton("🔒")
        self.state_toggle.setCheckable(True)
        self.state_toggle.setChecked(True)
        self.state_toggle.setFixedWidth(40)
        self.custom_state = _field("Custom State")
        self.custom_state.setVisible(False)
        self.state_code_field = _field("Code")
        self.state_code_field.setReadOnly(True)
        self.state_toggle.clicked.connect(
            lambda: (
                self.state.setEnabled(not self.state_toggle.isChecked()),
                self.custom_state.setEnabled(not self.state_toggle.isChecked()),
                self.state_code_field.setReadOnly(self.state_toggle.isChecked()),
                self.state_toggle.setText("🔒" if self.state_toggle.isChecked() else "🔓")
            )
        )
        state_row = QHBoxLayout()
        state_row.addWidget(self.state)
        state_row.addWidget(self.state_toggle)

        def update_state():
            sel = self.state.currentText()
            is_custom = sel == "Other (Custom)"
            self.custom_state.setVisible(is_custom)
            if is_custom:
                self.state_code_field.setReadOnly(False)
                self.state_code_field.setStyleSheet("")
                self.state_code_field.clear()
            else:
                self.state_code_field.setReadOnly(True)
                self.state_code_field.setStyleSheet(RO_STYLE)
                self.state_code_field.setText(self.state_code_map.get(sel, ""))

        self.state.currentIndexChanged.connect(update_state)
        self.state.setCurrentText("Haryana")
        update_state()

        for label, widget in [
            ("Company Name *",   self.company),
            ("Client Name *",    self.client),
            ("Mobile *",         self.mobile),
            ("Alternate Mobile", self.alt_mobile),
            ("Opening Balance",  balance_row),
            ("GST Number",       self.gst),
            ("Address *",        self.address),
            ("Pincode",          self.pincode),
            ("State *",          state_row),
            ("Custom State",     self.custom_state),
            ("State Code *",     self.state_code_field),
        ]:
            cform.addRow(_fl(label), widget)
        cvl.addLayout(cform)
        bl.addWidget(ccard)

        bcard, bvl = _card("BANK DETAILS  (Optional)")
        bform = QFormLayout()
        self.bank_name  = _field("Bank name")
        self.account_no = _field("Account number")
        self.ifsc       = _field("IFSC code")
        bform.addRow(_fl("Bank Name"),      self.bank_name)
        bform.addRow(_fl("Account Number"), self.account_no)
        bform.addRow(_fl("IFSC Code"),      self.ifsc)
        bvl.addLayout(bform)
        bl.addWidget(bcard)

        save_btn = QPushButton("Save Client")
        save_btn.setStyleSheet(BTN_PRIMARY)
        save_btn.setMinimumHeight(42)
        save_btn.setFixedWidth(180)
        save_btn.clicked.connect(self.save_client)
        bl.addWidget(save_btn, alignment=Qt.AlignmentFlag.AlignRight)
        bl.addStretch()

    def _fetch_gst(self):
        gst_no = self.gst_fetch_input.text().strip().upper()
        if len(gst_no) != 15:
            _warn(self, "GST number must be exactly 15 characters.")
            return
        self.fetch_btn.setEnabled(False)
        self.fetch_btn.setText("Fetching…")
        self.gst_status_lbl.setText("Connecting…")
        self.gst_status_lbl.setStyleSheet(
            f"color: {C_WHITE_MUT}; font-size: 11px; background: transparent;"
        )
        self._gst_worker = GSTFetchWorker(gst_no)
        self._gst_worker.result_ready.connect(self._on_gst_fetched)
        self._gst_worker.error.connect(self._on_gst_error)
        self._gst_worker.finished.connect(self._gst_fetch_done)
        self._gst_worker.start()

    def _on_gst_fetched(self, data: dict):
        try:
            info = data.get("data", data)
            if isinstance(info, list) and info:
                info = info[0]
            trade_name   = (info.get("tradeName") or info.get("tradeNam") or "").strip().upper()
            legal_name   = (info.get("legalName") or info.get("lgnm")     or "").strip().title()
            company_name = trade_name or legal_name
            gst_no = (
                info.get("gstNumber") or info.get("gstin") or self.gst_fetch_input.text()
            ).strip().upper()

            principal = info.get("principalAddress", {})
            addr = principal.get("address", {}) if isinstance(principal, dict) else {}
            if not addr:
                pradr = info.get("pradr") or {}
                if isinstance(pradr, dict):
                    addr = pradr.get("address", pradr)
                elif isinstance(pradr, str):
                    addr = {"_raw": pradr}

            address_parts = []
            pincode_val   = ""
            state_from_addr = ""

            if isinstance(addr, dict):
                for key in ("buildingNumber", "buildingName", "floorNumber",
                            "street", "locality", "district", "location"):
                    v = str(addr.get(key, "") or "").strip()
                    if v and v.lower() not in {"0", "00", "na", "n/a", "null", "none", "-"}:
                        address_parts.append(v)
                raw_adr = str(addr.get("adr", "") or addr.get("_raw", "") or "").strip()
                if not address_parts and raw_adr:
                    address_parts = [raw_adr]
                pincode_val = str(addr.get("pincode", "") or addr.get("pncd", "") or "").strip()
                if pincode_val in {"0", "00", "na", "null", "none", ""}:
                    pincode_val = ""
                if pincode_val:
                    address_parts.append(pincode_val)
                state_from_addr = str(
                    addr.get("stateCode", "") or addr.get("stcd", "") or ""
                ).strip().title()
            elif isinstance(addr, str) and addr:
                address_parts = [addr]

            gst_state_code = gst_no[:2] if len(gst_no) >= 2 else ""
            state_candidates = [
                state_from_addr,
                str(info.get("stateJurisdiction") or "").strip().title(),
                str(info.get("stateName")          or "").strip().title(),
                str(info.get("state")              or "").strip().title(),
            ]
            self.state.setEnabled(True)
            if company_name:  self.company.setText(company_name)
            if legal_name and legal_name.upper() != company_name:
                self.client.setText(legal_name)
            if gst_no:        self.gst.setText(gst_no)
            if address_parts: self.address.setPlainText(", ".join(address_parts))
            if pincode_val:   self.pincode.setText(pincode_val)

            matched = False
            for candidate in state_candidates:
                if candidate and candidate in self.state_code_map:
                    self.state.setCurrentText(candidate)
                    matched = True
                    break
            if not matched and gst_state_code:
                for sname, scode in self.state_code_map.items():
                    if scode == gst_state_code:
                        self.state.setCurrentText(sname)
                        matched = True
                        break

            filled = []
            if company_name:   filled.append("company")
            if legal_name:     filled.append("legal name")
            if address_parts:  filled.append("address")
            if pincode_val:    filled.append("pincode")
            if matched:        filled.append("state")
            self.gst_status_lbl.setText(
                "✓ Filled: " + ", ".join(filled) if filled else "✓ Fetched (no fields to fill)"
            )
            self.gst_status_lbl.setStyleSheet(
                "color: #7AE07A; font-size: 11px; background: transparent;"
            )
            self.state_toggle.setChecked(True)
            self.state.setEnabled(False)
            self.state_toggle.setText("🔒")
            self.balance_toggle.setChecked(True)
            self.balance.setEnabled(False)
            self.balance_toggle.setText("🔒")
        except Exception as exc:
            self.gst_status_lbl.setText(f"Parse error: {exc}")
            self.gst_status_lbl.setStyleSheet(
                f"color: #F07070; font-size: 11px; background: transparent;"
            )

    def _on_gst_error(self, code: str):
        if code == "no_internet":
            reply = QMessageBox.question(
                self, "No Internet Connection",
                "Cannot reach the internet to fetch GST details.\n"
                "Would you like to fill the details manually?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            )
            if reply == QMessageBox.StandardButton.Yes:
                self.gst.setText(self.gst_fetch_input.text())
                self.company.setFocus()
            self.gst_status_lbl.setText("Offline — please fill manually")
            self.gst_status_lbl.setStyleSheet(
                f"color: #E0B860; font-size: 11px; background: transparent;"
            )
        else:
            self.gst_status_lbl.setText("API error — please fill manually")
            self.gst_status_lbl.setStyleSheet(
                f"color: #F07070; font-size: 11px; background: transparent;"
            )

    def _gst_fetch_done(self):
        self.fetch_btn.setEnabled(True)
        self.fetch_btn.setText("Fetch Details")

    def _reset_form(self):
        self.gst_fetch_input.clear()
        self.gst_status_lbl.setText("")
        self.company.clear()
        self.client.clear()
        self.mobile.clear()
        self.alt_mobile.clear()
        self.balance.setValue(0)
        self.gst.clear()
        self.address.clear()
        self.pincode.clear()
        self.state.setCurrentText("Haryana")
        self.custom_state.clear()
        self.bank_name.clear()
        self.account_no.clear()
        self.ifsc.clear()

    def save_client(self):
        company = self.company.text().strip()
        client  = self.client.text().strip()
        mobile  = self.mobile.text().strip()
        alt_mob = self.alt_mobile.text().strip() or None
        opening = self.balance.value()
        gst     = self.gst.text().strip()       or None
        address = self.address.toPlainText().strip()
        pincode = self.pincode.text().strip()   or None
        state   = self.state.currentText()
        sc      = self.state_code_field.text().strip()
        bank    = self.bank_name.text().strip()  or None
        account = self.account_no.text().strip() or None
        ifsc    = self.ifsc.text().strip()       or None

        if not company:       _warn(self, "Company Name is required."); return
        if not client:        _warn(self, "Client Name is required."); return
        if len(mobile) != 10: _warn(self, "Mobile must be exactly 10 digits."); return
        if alt_mob and len(alt_mob) != 10:
            _warn(self, "Alternate Mobile must be exactly 10 digits."); return
        if not address:       _warn(self, "Address is required."); return
        if pincode and not QRegularExpression("^[0-9]{6}$").match(pincode).hasMatch():
            _warn(self, "Pincode must be exactly 6 digits."); return
        if state == "Other (Custom)" and not self.custom_state.text().strip():
            _warn(self, "Custom State Name is required."); return
        if not sc:            _warn(self, "State Code is required."); return
        if gst and not QRegularExpression(
            "^[0-9]{2}[A-Z]{5}[0-9]{4}[A-Z][A-Z0-9]Z[0-9A-Z]$"
        ).match(gst).hasMatch():
            _warn(self, "Invalid GST format."); return
        if account and not QRegularExpression("^[0-9]{9,18}$").match(account).hasMatch():
            _warn(self, "Account number must be 9-18 digits."); return
        if ifsc and not QRegularExpression("^[A-Z]{4}0[A-Z0-9]{6}$").match(ifsc).hasMatch():
            _warn(self, "Invalid IFSC format."); return

        status, message = acc_manager.save_client_to_csv(
            company, client, mobile, alt_mob, opening,
            gst, address, pincode, state, sc, bank, account, ifsc
        )
        QMessageBox.information(self, status, message)
        if status.lower() == "success":
            self.client_saved.emit()
            self._reset_form()
            self.go_home()

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Fatha — Account Manager")
        self.resize(1340, 820)
        self.setStyleSheet(APP_STYLE)

        self.stack = QStackedWidget()

        self.view_bills = ViewBillsPage(self.go_home)
        self.home       = HomePage(
            self.go_create, self.go_view,
            self.open_ledger_view, self.go_products,
            self.go_billing, self.go_view_bills, self.go_products_costing
        )
        self.create   = CreateClientPage(self.go_home)
        self.view     = ViewClientsPage(self.go_home)
        self.products = ProductsPage(self.go_home)
        self.billing  = BillingPage(self.go_home)
        self.costing = ProductCostingPage(costing_manager, acc_manager, self.go_home, get_bridge_path)

        self.create.client_saved.connect(self.home.refresh_stats)
        self.billing.bill_saved.connect(self.home.refresh_stats)
        self.view_bills.bill_finalized.connect(self.home.refresh_stats)
        self.view_bills.bill_deleted.connect(self.home.refresh_stats)
        self.products.product_changed.connect(self.home.refresh_stats)

        for w in (self.home, self.create, self.view,
                  self.products, self.billing, self.view_bills, self.costing):
            self.stack.addWidget(w)

        self.setCentralWidget(self.stack)

    def go_home(self):
        self.home.refresh_stats()
        self.stack.setCurrentWidget(self.home)

    def go_create(self):
        self.create._reset_form()
        self.stack.setCurrentWidget(self.create)

    def go_view(self):
        self.view.load_clients()
        self.stack.setCurrentWidget(self.view)

    def go_products(self):
        acc_manager.load_data()
        self.products.load_products()
        self.products.load_clients()
        self.products.editing_row = None
        self.stack.setCurrentWidget(self.products)

    def go_billing(self):
        self.billing.refresh()
        self.stack.setCurrentWidget(self.billing)

    def go_view_bills(self):
        self.view_bills.refresh()
        self.stack.setCurrentWidget(self.view_bills)

    def open_ledger_view(self):
        ViewLedgerDialog().exec()
    
    def go_products_costing(self):
        self.costing.refresh()
        self.stack.setCurrentWidget(self.costing)
