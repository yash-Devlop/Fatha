import os

from PySide6.QtWidgets import (
    QComboBox, QDoubleSpinBox, QLabel, QLineEdit, QFrame,
    QMessageBox, QTableWidgetItem, QWidget, QVBoxLayout, QHBoxLayout, QPushButton,
    QFileDialog
)

from PySide6.QtCore import QSettings, Qt

from PySide6.QtGui import QColor, QFont

from ui.style import (
    C_WHITE_DIM, FONT_UI, C_WHITE_MUT, RO_STYLE,
    C_BORDER, C_BORDER_DARK, CARD_STYLE, C_GHOST,
    TOPBAR_STYLE, BTN_GHOST, C_WHITE
)

from ui.Invoice.painter import draw_invoice

class _NoScrollComboBox(QComboBox):
    def wheelEvent(self, e):
        e.ignore()

class NoScrollDoubleSpinBox(QDoubleSpinBox):
    def wheelEvent(self, event):
        event.ignore()

def _h(size: int, text: str, bold: bool = False, color: str = C_WHITE_DIM) -> QLabel:
    lbl = QLabel(text)
    lbl.setFont(QFont(FONT_UI, size, QFont.Weight.Bold if bold else QFont.Weight.Normal))
    lbl.setStyleSheet(f"color: {color}; background: transparent;")
    return lbl


def _fl(text: str) -> QLabel:
    lbl = QLabel(text)
    lbl.setFont(QFont(FONT_UI, 12))
    lbl.setStyleSheet(f"color: {C_WHITE_MUT}; background: transparent;")
    return lbl


def _field(placeholder: str = "", width: int | None = None) -> QLineEdit:
    le = QLineEdit()
    le.setPlaceholderText(placeholder)
    le.setMinimumHeight(36)
    if width:
        le.setFixedWidth(width)
    return le


def _ro(width: int = 120) -> QLineEdit:
    f = QLineEdit()
    f.setReadOnly(True)
    f.setStyleSheet(RO_STYLE)
    f.setMinimumHeight(36)
    f.setFixedWidth(width)
    return f


def _divider() -> QFrame:
    d = QFrame()
    d.setFrameShape(QFrame.Shape.HLine)
    d.setStyleSheet(f"background: {C_BORDER}; border: none; max-height: 1px; margin: 2px 0;")
    return d


def _vline() -> QFrame:
    d = QFrame()
    d.setFrameShape(QFrame.Shape.VLine)
    d.setStyleSheet(f"color: {C_BORDER_DARK}; max-width: 1px;")
    return d


def _warn(parent: QWidget, msg: str):
    QMessageBox.warning(parent, "Validation Error", msg)



def _amount_to_words(amount: int | float) -> str:
    ones  = ["", "One", "Two", "Three", "Four", "Five", "Six", "Seven",
             "Eight", "Nine", "Ten", "Eleven", "Twelve", "Thirteen",
             "Fourteen", "Fifteen", "Sixteen", "Seventeen", "Eighteen", "Nineteen"]
    tens_ = ["", "", "Twenty", "Thirty", "Forty", "Fifty",
             "Sixty", "Seventy", "Eighty", "Ninety"]

    def _two(n):
        return ones[n] if n < 20 else tens_[n // 10] + (" " + ones[n % 10] if n % 10 else "")

    def _three(n):
        return (ones[n // 100] + " Hundred" + (" " + _two(n % 100) if n % 100 else "")
                if n >= 100 else _two(n))

    amount = int(round(float(amount)))
    if amount == 0:
        return "Zero Rupees"
    neg    = amount < 0
    amount = abs(amount)
    crore  = amount // 10_000_000;  amount %= 10_000_000
    lakh   = amount // 100_000;     amount %= 100_000
    thous  = amount // 1_000;       amount %= 1_000
    parts  = []
    if crore: parts.append(_three(crore) + " Crore")
    if lakh:  parts.append(_three(lakh)  + " Lakh")
    if thous: parts.append(_three(thous) + " Thousand")
    if amount: parts.append(_three(amount))
    return ("Minus " if neg else "") + " ".join(parts) + " Rupees"


def _card(heading: str = "") -> tuple[QFrame, QVBoxLayout]:
    frame = QFrame()
    frame.setStyleSheet(CARD_STYLE)
    vl = QVBoxLayout(frame)
    vl.setContentsMargins(20, 16, 20, 16)
    vl.setSpacing(12)
    if heading:
        h = QLabel(heading)
        h.setFont(QFont(FONT_UI, 9, QFont.Weight.Bold))
        h.setStyleSheet(f"color: {C_GHOST}; letter-spacing: 2px; background: transparent;")
        vl.addWidget(h)
        vl.addWidget(_divider())
    return frame, vl


def _topbar(title: str, go_back) -> QFrame:
    bar = QFrame()
    bar.setFixedHeight(54)
    bar.setStyleSheet(TOPBAR_STYLE)
    hl  = QHBoxLayout(bar)
    hl.setContentsMargins(20, 0, 24, 0)
    hl.setSpacing(12)
    back = QPushButton("← Back")
    back.setStyleSheet(BTN_GHOST)
    back.setFixedHeight(32)
    back.setFixedWidth(76)
    back.clicked.connect(go_back)
    hl.addWidget(back)
    hl.addWidget(_vline())
    hl.addSpacing(8)
    hl.addWidget(_h(14, title, bold=True, color=C_WHITE))
    hl.addStretch()
    return bar


def _print_invoice_pdf(data: dict, parent: QWidget, draft: bool = False, performa: bool = False) -> bool:
    settings = QSettings("YourCompany", "YourApp")

    last_dir = settings.value("last_pdf_dir", "")

    if not performa:
        performa = "performa_no" in data.keys()

    if not performa:
        default_name = "Invoice " + data.get("invoice_no", "").replace("/", "_") + ".pdf"
    else:
        default_name = "PerformaInvoice " + data.get("client_name", "") + ".pdf"
        
    default_path = os.path.join(last_dir, default_name) if last_dir else default_name

    file_path, _ = QFileDialog.getSaveFileName(
        parent,
        "Save Invoice PDF",
        default_path,
        "PDF Files (*.pdf)"
    )

    if not file_path:
        return False

    if not file_path.lower().endswith(".pdf"):
        file_path += ".pdf"

    settings.setValue("last_pdf_dir", os.path.dirname(file_path))

    ok = draw_invoice(data, file_path, draft=draft, performa=performa)

    if not ok:
        QMessageBox.warning(parent, "PDF Error", "Could not generate PDF.")

    return ok

def _lbl(text: str, size: int = 12, bold: bool = False, color: str = C_WHITE) -> QLabel:
    lbl = QLabel(text)
    lbl.setStyleSheet(
        f"font-size: {size}px; font-weight: {'600' if bold else '400'}; color: {color};"
    )
    return lbl
 
 
def _ti(
    text: str,
    alignment=Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft,
    color: str = C_WHITE,
) -> QTableWidgetItem:
    item = QTableWidgetItem(text)
    item.setTextAlignment(alignment)
    item.setForeground(QColor(color))
    return item

__all__ = [
    "_NoScrollComboBox",
    "NoScrollDoubleSpinBox",
    "_h", "_fl", "_field", "_ro",
    "_divider", "_vline",
    "_warn", "_amount_to_words",
    "_card", "_topbar",
    "_print_invoice_pdf",
    "_lbl",
    "_ti"
]
