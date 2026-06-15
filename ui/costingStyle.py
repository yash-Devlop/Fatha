C_BG          = "#121212"
C_SURFACE     = "#1E1E1E"
C_SURFACE_HI  = "#2A2A3A"
C_SURFACE_ALT = "#252535"
C_TOPBAR      = "#1B1B2F"
C_SIDEBAR     = "#0F0F1A"
C_BORDER      = "#2E2E45"
C_BORDER_DARK = "#3A3A55"
C_WHITE       = "#F0F0F5"
C_WHITE_MUT   = "#A0A0B5"
C_WHITE_DIM   = "#707085"
C_GHOST       = "#555568"
C_GOLD        = "#C9A84C"
C_DANGER_BG   = "#2A1515"
C_DANGER_BORDER = "#6B2525"
FONT_UI       = "Segoe UI"

CARD_STYLE = f"""
    QFrame {{
        background: {C_SURFACE};
        border: 1px solid {C_BORDER};
        border-radius: 8px;
    }}
"""
BTN_PRIMARY = f"""
    QPushButton {{
        background: {C_GOLD}; color: #000; border: none;
        border-radius: 5px; padding: 6px 16px;
        font-size: 12px; font-weight: 700;
    }}
    QPushButton:hover {{ background: #DEB55C; }}
    QPushButton:disabled {{ background: #555; color: #888; }}
"""
BTN_OUTLINE = f"""
    QPushButton {{
        background: transparent; color: {C_WHITE_MUT};
        border: 1px solid {C_BORDER_DARK}; border-radius: 5px;
        padding: 6px 14px; font-size: 12px;
    }}
    QPushButton:hover {{ background: {C_SURFACE_HI}; color: {C_WHITE}; }}
"""
BTN_DANGER = f"""
    QPushButton {{
        background: {C_DANGER_BG}; color: #F07070;
        border: 1px solid {C_DANGER_BORDER}; border-radius: 5px;
        padding: 4px 10px; font-size: 12px;
    }}
    QPushButton:hover {{ background: #3A1515; }}
"""
BTN_SUCCESS = f"""
    QPushButton {{
        background: #1A3A1A; color: #7AE07A;
        border: 1px solid #2A5A2A; border-radius: 5px;
        padding: 4px 10px; font-size: 12px; font-weight: 600;
    }}
    QPushButton:hover {{ background: #1E4A1E; }}
"""
RO_STYLE = f"""
    QLineEdit {{
        background: {C_SURFACE_ALT}; color: {C_WHITE_MUT};
        border: 1px solid {C_BORDER}; border-radius: 5px;
        padding: 6px 10px;
    }}
"""
FIELD_STYLE = f"""
    QLineEdit {{
        background: {C_SURFACE_HI}; color: {C_WHITE};
        border: 1px solid {C_BORDER_DARK}; border-radius: 5px;
        padding: 6px 10px;
    }}
    QLineEdit:focus {{ border: 1px solid {C_GOLD}; }}
"""
COMBO_STYLE = f"""
    QComboBox {{
        background: {C_SURFACE_HI}; color: {C_WHITE};
        border: 1px solid {C_BORDER_DARK}; border-radius: 5px;
        padding: 5px 10px; font-size: 13px;
    }}
    QComboBox:focus {{ border: 1px solid {C_GOLD}; }}
    QComboBox::drop-down {{ border: none; width: 22px; }}
    QComboBox QAbstractItemView {{
        background: {C_TOPBAR}; color: {C_WHITE};
        selection-background-color: {C_SURFACE_ALT};
        border: 1px solid {C_BORDER};
    }}
"""
TABLE_STYLE = f"""
    QTableWidget {{
        background: {C_SURFACE}; color: {C_WHITE};
        border: 1px solid {C_BORDER}; border-radius: 4px;
        gridline-color: {C_BORDER};
        alternate-background-color: {C_SURFACE_ALT};
    }}
    QHeaderView::section {{
        background: {C_TOPBAR}; color: {C_WHITE_MUT};
        border: none; border-right: 1px solid {C_BORDER};
        padding: 6px 8px; font-weight: 600; font-size: 11px;
    }}
"""
SPIN_STYLE = f"""
    QDoubleSpinBox {{
        background: {C_SURFACE_HI}; color: {C_WHITE};
        border: 1px solid {C_BORDER_DARK}; border-radius: 4px;
        padding: 2px 6px; font-size: 12px;
    }}
    QDoubleSpinBox:focus {{ border: 1px solid {C_GOLD}; }}
    QDoubleSpinBox::up-button, QDoubleSpinBox::down-button {{
        width: 16px; background: {C_SURFACE_ALT};
        border: none;
    }}
"""
CHECK_STYLE = f"""
    QCheckBox {{
        background: transparent;
        spacing: 0px;
    }}
    QCheckBox::indicator {{
        width: 18px; height: 18px;
        border: 2px solid {C_BORDER_DARK};
        border-radius: 4px;
        background: {C_SURFACE_HI};
    }}
    QCheckBox::indicator:checked {{
        background: {C_GOLD};
        border: 2px solid {C_GOLD};
        image: none;
    }}
    QCheckBox::indicator:hover {{
        border: 2px solid {C_GOLD};
    }}
"""

STEPPER_BTN_STYLE = """
    QPushButton {
        background: #2a2a2a;
        border: 1px solid #484848;
        color: #c8c8c8;
        font-size: 16px;
        font-weight: 400;
        padding: 0;
    }
    QPushButton:hover {
        background: #c8a84b;
        border-color: #c8a84b;
        color: #1a1a1a;
    }
    QPushButton:pressed {
        background: #b5933a;
        border-color: #b5933a;
        color: #1a1a1a;
    }
    QPushButton:disabled {
        background: #1e1e1e;
        border-color: #333;
        color: #444;
    }
"""
 
STEPPER_SPIN_STYLE = """
    QDoubleSpinBox {
        background: #222222;
        border: 1px solid #484848;
        border-left: none;
        border-right: none;
        color: #e0e0e0;
        font-size: 12px;
        font-family: Consolas, monospace;
        padding: 0 4px;
    }
    QDoubleSpinBox:focus {
        background: #2a2a2a;
        color: #c8a84b;
    }
    QDoubleSpinBox:disabled {
        background: #1a1a1a;
        color: #444;
        border-color: #333;
    }
"""
 
CHECK_STYLE = """
    QCheckBox {
        spacing: 0px;
    }
    QCheckBox::indicator {
        width: 20px;
        height: 20px;
        border-radius: 4px;
        border: 2px solid #484848;
        background: #2a2a2a;
    }
    QCheckBox::indicator:hover {
        border-color: #c8a84b;
        background: #2e2b1f;
    }
    QCheckBox::indicator:checked {
        background: #c8a84b;
        border-color: #c8a84b;
        image: url(none);
    }
    QCheckBox::indicator:checked:hover {
        background: #d4b45e;
        border-color: #d4b45e;
    }
    QCheckBox::indicator:disabled {
        background: #1e1e1e;
        border-color: #333;
    }
"""
 
TABLE_STYLE = """
    QTableWidget {
        background: #1e1e1e;
        alternate-background-color: #222222;
        border: none;
        gridline-color: #2a2a2a;
        color: #e0e0e0;
        font-size: 12px;
        selection-background-color: transparent;
    }
    QTableWidget::item {
        padding: 0px 2px;
        border-bottom: 1px solid #282828;
    }
    QTableWidget::item:selected {
        background: transparent;
        color: #e0e0e0;
    }
    QHeaderView::section {
        background: #2a2a2a;
        color: #787878;
        font-size: 10px;
        font-weight: 600;
        letter-spacing: 1px;
        text-transform: uppercase;
        padding: 6px 10px;
        border: none;
        border-bottom: 1px solid #3a3a3a;
        border-right: 1px solid #333;
    }
    QHeaderView::section:last {
        border-right: none;
    }
    QScrollBar:vertical {
        background: #1a1a1a;
        width: 6px;
        border: none;
    }
    QScrollBar::handle:vertical {
        background: #3a3a3a;
        border-radius: 3px;
        min-height: 20px;
    }
    QScrollBar::handle:vertical:hover {
        background: #c8a84b;
    }
    QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
        height: 0px;
    }
"""
 
SEARCH_STYLE = """
    QLineEdit {
        background: #2a2a2a;
        border: 1px solid #3a3a3a;
        border-radius: 5px;
        color: #e0e0e0;
        font-size: 12px;
        padding: 6px 10px 6px 10px;
    }
    QLineEdit:focus {
        border-color: #c8a84b;
        background: #2e2b1f;
    }
    QLineEdit::placeholder {
        color: #555;
    }
"""
 
BTN_OUTLINE_STYLE = """
    QPushButton {
        background: #2a2a2a;
        border: 1px solid #3a3a3a;
        border-radius: 5px;
        color: #a0a0a0;
        font-size: 11px;
        font-weight: 600;
        padding: 0 12px;
    }
    QPushButton:hover {
        border-color: #c8a84b;
        color: #c8a84b;
        background: #2a2718;
    }
    QPushButton:pressed {
        background: #221f10;
    }
"""
 
BTN_PRIMARY_STYLE = """
    QPushButton {
        background: #c8a84b;
        border: none;
        border-radius: 5px;
        color: #1a1a1a;
        font-size: 12px;
        font-weight: 700;
        padding: 0 16px;
    }
    QPushButton:hover {
        background: #d4b45e;
    }
    QPushButton:pressed {
        background: #b5933a;
    }
    QPushButton:disabled {
        background: #3a3530;
        color: #666;
    }
"""
 
COUNT_LABEL_STYLE = "font-size: 11px; color: #666;"

__all__ = [name for name in globals() if name.isupper()]