C_BG          = "#0A0A0A"
C_SURFACE     = "#141414"
C_SURFACE_ALT = "#1A1A1A"
C_SURFACE_HI  = "#202020"
C_BORDER      = "#2E2E2E"
C_BORDER_DARK = "#3A3A3A"
C_WHITE       = "#FFFFFF"
C_WHITE_DIM   = "#E0E0E0"
C_WHITE_MUT   = "#AAAAAA"
C_GHOST       = "#666666"
C_BLACK_BTN   = "#0A0A0A"
C_SUCCESS     = "#FFFFFF"
C_SUCCESS_BG  = "#1A2A1A"
C_SUCCESS_BORDER = "#3A5A3A"
C_DANGER      = "#FFFFFF"
C_DANGER_BG   = "#2A1010"
C_DANGER_BORDER = "#5A2020"
C_WARNING     = "#FFFFFF"
C_WARNING_BG  = "#2A2010"
C_WARNING_BORDER = "#5A4A20"
C_SIDEBAR     = "#080808"
C_TOPBAR      = "#0E0E0E"

FONT_UI   = "Segoe UI"
FONT_MONO = "Consolas"

APP_STYLE = f"""
* {{
    font-family: '{FONT_UI}', 'Calibri', sans-serif;
    font-size: 13px;
    color: {C_WHITE_DIM};
    outline: none;
}}
QMainWindow, QDialog {{ background: {C_BG}; }}
QWidget {{ background: transparent; }}
QScrollArea {{ border: none; background: transparent; }}

QScrollBar:vertical {{
    background: {C_SURFACE_ALT}; width: 6px; border-radius: 3px;
}}
QScrollBar::handle:vertical {{
    background: {C_BORDER_DARK}; border-radius: 3px; min-height: 30px;
}}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}
QScrollBar:horizontal {{
    background: {C_SURFACE_ALT}; height: 6px; border-radius: 3px;
}}
QScrollBar::handle:horizontal {{
    background: {C_BORDER_DARK}; border-radius: 3px;
}}
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{ width: 0; }}

QLineEdit {{
    background: {C_SURFACE_HI};
    color: {C_WHITE};
    border: 1px solid {C_BORDER};
    border-radius: 5px;
    padding: 7px 11px;
    font-size: 13px;
    selection-background-color: {C_WHITE};
    selection-color: {C_BLACK_BTN};
}}
QLineEdit:focus {{
    border: 1.5px solid {C_WHITE_DIM};
    background: {C_SURFACE};
}}
QLineEdit:disabled {{
    background: {C_SURFACE_ALT};
    color: {C_GHOST};
    border-color: {C_BORDER};
}}
QLineEdit:read-only {{
    background: {C_SURFACE_ALT};
    color: {C_WHITE_MUT};
    border-color: {C_BORDER};
}}

QTextEdit {{
    background: {C_SURFACE_HI};
    color: {C_WHITE};
    border: 1px solid {C_BORDER};
    border-radius: 5px;
    padding: 7px 11px;
    font-size: 13px;
}}
QTextEdit:focus {{ border: 1.5px solid {C_WHITE_DIM}; }}

QComboBox {{
    background: {C_SURFACE_HI};
    color: {C_WHITE};
    border: 1px solid {C_BORDER};
    border-radius: 5px;
    padding: 7px 11px;
    font-size: 13px;
}}
QComboBox:focus {{ border: 1.5px solid {C_WHITE_DIM}; }}
QComboBox::drop-down {{ border: none; width: 28px; }}
QComboBox QAbstractItemView {{
    background: {C_SURFACE};
    color: {C_WHITE};
    border: 1px solid {C_BORDER_DARK};
    border-radius: 4px;
    selection-background-color: {C_WHITE};
    selection-color: {C_BLACK_BTN};
    outline: none;
    padding: 2px;
}}

QDateEdit {{
    background: {C_SURFACE_HI};
    color: {C_WHITE};
    border: 1px solid {C_BORDER};
    border-radius: 5px;
    padding: 7px 11px;
    font-size: 13px;
}}
QDateEdit:focus {{ border: 1.5px solid {C_WHITE_DIM}; }}
QDateEdit::drop-down {{ border: none; width: 28px; }}
QDateEdit QCalendarWidget {{ background: {C_SURFACE}; color: {C_WHITE}; }}

QDoubleSpinBox {{
    background: {C_SURFACE_HI};
    color: {C_WHITE};
    border: 1px solid {C_BORDER};
    border-radius: 5px;
    padding: 7px 11px;
    font-size: 13px;
}}
QDoubleSpinBox:focus {{ border: 1.5px solid {C_WHITE_DIM}; }}

QLabel {{ background: transparent; color: {C_WHITE_DIM}; }}
QMessageBox {{ background: {C_SURFACE}; }}
QMessageBox QLabel {{ color: {C_WHITE}; }}

QCheckBox {{ spacing: 8px; font-size: 13px; color: {C_WHITE_DIM}; }}
QCheckBox::indicator {{
    width: 15px; height: 15px;
    border: 1.5px solid {C_BORDER_DARK};
    border-radius: 3px;
    background: {C_SURFACE_HI};
}}
QCheckBox::indicator:checked {{
    background: {C_WHITE};
    border: 1.5px solid {C_WHITE};
    image: none;
}}

QTableWidget {{
    background: {C_SURFACE};
    color: {C_WHITE};
    border: 1px solid {C_BORDER};
    border-radius: 6px;
    gridline-color: {C_BORDER};
    font-size: 13px;
    outline: none;
    alternate-background-color: {C_SURFACE_ALT};
}}
QTableWidget::item {{
    padding: 6px 10px;
    border: none;
    color: {C_WHITE_DIM};
}}
QTableWidget::item:selected {{
    background: {C_BORDER_DARK};
    color: {C_WHITE};
}}
QHeaderView::section {{
    background: {C_BG};
    color: {C_WHITE_MUT};
    border: none;
    border-right: 1px solid {C_BORDER};
    border-bottom: 1px solid {C_BORDER};
    padding: 9px 10px;
    font-size: 11px;
    font-weight: 600;
    letter-spacing: 0.5px;
    text-transform: uppercase;
}}
QHeaderView::section:last {{ border-right: none; }}

QRadioButton {{ spacing: 8px; font-size: 13px; color: {C_WHITE_DIM}; }}
QRadioButton::indicator {{
    width: 15px; height: 15px;
    border: 1.5px solid {C_BORDER_DARK};
    border-radius: 8px;
    background: {C_SURFACE_HI};
}}
QRadioButton::indicator:checked {{
    background: {C_WHITE};
    border: 1.5px solid {C_WHITE};
}}

QGroupBox {{
    color: {C_WHITE_MUT};
    border: 1px solid {C_BORDER};
    border-radius: 6px;
    margin-top: 16px;
    font-size: 11px;
    font-weight: 600;
    padding: 8px;
}}
QGroupBox::title {{
    subcontrol-origin: margin;
    left: 14px;
    padding: 0 6px;
    background: {C_SURFACE};
    color: {C_WHITE_MUT};
}}

QTabWidget::pane {{
    border: 1px solid {C_BORDER};
    border-radius: 6px;
    background: {C_SURFACE};
}}
QTabBar::tab {{
    background: {C_SURFACE_ALT};
    color: {C_GHOST};
    border: 1px solid {C_BORDER};
    border-bottom: none;
    padding: 8px 20px;
    border-radius: 5px 5px 0 0;
    margin-right: 2px;
    font-size: 12px;
}}
QTabBar::tab:selected {{
    background: {C_SURFACE};
    color: {C_WHITE};
    border-bottom: 1px solid {C_SURFACE};
}}
QTabBar::tab:hover {{ color: {C_WHITE_DIM}; background: {C_SURFACE_HI}; }}

QListWidget {{
    background: {C_SURFACE};
    color: {C_WHITE_DIM};
    border: 1px solid {C_BORDER};
    border-radius: 6px;
    outline: none;
}}
QListWidget::item {{
    padding: 10px 14px;
    border-bottom: 1px solid {C_BORDER};
    font-size: 13px;
}}
QListWidget::item:selected {{
    background: {C_BORDER_DARK};
    color: {C_WHITE};
}}
QListWidget::item:hover {{ background: {C_SURFACE_HI}; }}

QSplitter::handle {{ background: {C_BORDER}; width: 1px; height: 1px; }}

QProgressDialog {{
    background: {C_SURFACE};
    color: {C_WHITE};
}}
"""

# ── Button styles ──────────────────────────────────────────────────────────────

BTN_PRIMARY = f"""QPushButton {{
    background: {C_WHITE};
    color: {C_BLACK_BTN};
    border-radius: 5px;
    padding: 8px 22px;
    font-weight: 700;
    font-size: 13px;
    border: none;
    min-width: 90px;
}}
QPushButton:hover {{ background: {C_WHITE_DIM}; color: {C_BLACK_BTN}; }}
QPushButton:pressed {{ background: #CCCCCC; }}
QPushButton:disabled {{ background: {C_BORDER}; color: {C_GHOST}; }}"""

BTN_NAVY = f"""QPushButton {{
    background: transparent;
    color: {C_WHITE};
    border: 1.5px solid {C_WHITE};
    border-radius: 5px;
    padding: 8px 22px;
    font-weight: 600;
    font-size: 13px;
    min-width: 90px;
}}
QPushButton:hover {{ background: {C_WHITE}; color: {C_BLACK_BTN}; }}
QPushButton:pressed {{ background: {C_WHITE_DIM}; color: {C_BLACK_BTN}; }}"""

BTN_SUCCESS = f"""QPushButton {{
    background: {C_SUCCESS_BG};
    color: #7AE07A;
    border: 1.5px solid {C_SUCCESS_BORDER};
    border-radius: 5px;
    padding: 8px 22px;
    font-weight: 700;
    font-size: 13px;
    min-width: 90px;
}}
QPushButton:hover {{ background: #224422; color: #A0F0A0; border-color: #5A9A5A; }}
QPushButton:pressed {{ background: #1A3A1A; }}"""

BTN_DANGER = f"""QPushButton {{
    background: {C_DANGER_BG};
    color: #F07070;
    border: 1.5px solid {C_DANGER_BORDER};
    border-radius: 5px;
    padding: 7px 18px;
    font-weight: 600;
    font-size: 12px;
    min-width: 70px;
}}
QPushButton:hover {{ background: #3A1414; color: #FFA0A0; border-color: #7A2A2A; }}"""

BTN_WARNING = f"""QPushButton {{
    background: {C_WARNING_BG};
    color: #E0B860;
    border: 1.5px solid {C_WARNING_BORDER};
    border-radius: 5px;
    padding: 8px 22px;
    font-weight: 600;
    font-size: 13px;
    min-width: 90px;
}}
QPushButton:hover {{ background: #3A2E10; color: #F0D080; border-color: #7A6030; }}"""

BTN_GHOST = f"""QPushButton {{
    background: transparent;
    color: {C_WHITE_MUT};
    border: none;
    padding: 6px 12px;
    font-size: 13px;
    font-weight: 500;
}}
QPushButton:hover {{ color: {C_WHITE}; background: {C_SURFACE_HI}; border-radius: 4px; }}"""

BTN_OUTLINE = f"""QPushButton {{
    background: transparent;
    color: {C_WHITE_MUT};
    border: 1px solid {C_BORDER_DARK};
    border-radius: 5px;
    padding: 7px 16px;
    font-size: 12px;
    font-weight: 500;
    min-width: 70px;
}}
QPushButton:hover {{ background: {C_SURFACE_HI}; border-color: {C_WHITE_MUT}; color: {C_WHITE}; }}"""

BTN_DISCARD = f"""QPushButton {{
    background: transparent;
    color: #D0A040;
    border: 1px solid #5A4A20;
    border-radius: 5px;
    padding: 7px 16px;
    font-size: 12px;
    font-weight: 500;
    min-width: 80px;
}}
QPushButton:hover {{ background: rgba(200,160,60,0.10); }}"""

BTN_CELL_EDIT = f"""QPushButton {{
    background: {C_SURFACE_HI};
    color: {C_WHITE_MUT};
    border: 1px solid {C_BORDER_DARK};
    border-radius: 4px;
    padding: 4px 12px;
    font-size: 11px;
    font-weight: 500;
    min-width: 38px;
}}
QPushButton:hover {{ background: {C_WHITE}; color: {C_BLACK_BTN}; border-color: {C_WHITE}; }}"""

BTN_CELL_SAVE = f"""QPushButton {{
    background: {C_SUCCESS_BG};
    color: #7AE07A;
    border: 1px solid {C_SUCCESS_BORDER};
    border-radius: 4px;
    padding: 4px 12px;
    font-size: 11px;
    font-weight: 700;
    min-width: 38px;
}}
QPushButton:hover {{ background: #224422; color: #A0F0A0; }}"""

BTN_CELL_DISCARD = f"""QPushButton {{
    background: transparent;
    color: #D0A040;
    border: 1px solid #5A4A20;
    border-radius: 4px;
    padding: 4px 10px;
    font-size: 11px;
    font-weight: 500;
    min-width: 38px;
}}
QPushButton:hover {{ background: rgba(200,160,60,0.12); }}"""

BTN_CELL_LEDGER = f"""QPushButton {{
    background: {C_SURFACE_HI};
    color: {C_WHITE};
    border: 1px solid {C_BORDER_DARK};
    border-radius: 4px;
    padding: 4px 12px;
    font-size: 11px;
    font-weight: 600;
    min-width: 46px;
}}
QPushButton:hover {{ background: {C_WHITE}; color: {C_BLACK_BTN}; border-color: {C_WHITE}; }}"""

BTN_CELL_VIEW = f"""QPushButton {{
    background: {C_SURFACE_HI};
    color: {C_WHITE_MUT};
    border: 1px solid {C_BORDER_DARK};
    border-radius: 4px;
    padding: 4px 12px;
    font-size: 11px;
    font-weight: 500;
    min-width: 38px;
}}
QPushButton:hover {{ background: {C_SURFACE}; color: {C_WHITE}; border-color: {C_WHITE_MUT}; }}"""

BTN_CELL_DANGER = f"""QPushButton {{
    background: transparent;
    color: #F07070;
    border: 1px solid #5A2020;
    border-radius: 4px;
    padding: 4px 10px;
    font-size: 11px;
    font-weight: 500;
    min-width: 38px;
}}
QPushButton:hover {{ background: {C_DANGER_BG}; color: #FFA0A0; border-color: #7A3030; }}"""

CARD_STYLE = f"""QFrame {{
    background: {C_SURFACE};
    border: 1px solid {C_BORDER};
    border-radius: 8px;
}}"""

RO_STYLE = f"""QLineEdit {{
    background: {C_SURFACE_ALT};
    color: {C_WHITE_MUT};
    border: 1px solid {C_BORDER};
    border-radius: 5px;
    padding: 7px 11px;
    font-size: 13px;
    font-weight: 600;
}}"""

GOLD_BADGE = f"""QLabel {{
    background: {C_SURFACE_ALT};
    color: {C_WHITE};
    border: 1px solid {C_BORDER_DARK};
    border-radius: 4px;
    padding: 5px 12px;
    font-size: 13px;
    font-weight: 700;
    font-family: '{FONT_MONO}';
    letter-spacing: 0.5px;
}}"""

TOPBAR_STYLE = f"""QFrame {{
    background: {C_TOPBAR};
    border: none;
    border-bottom: 1px solid {C_BORDER};
}}"""

__all__ = [name for name in globals() if name.isupper()]