from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QMessageBox, QFrame, QScrollArea,
)
from PySide6.QtGui import QFont
from PySide6.QtCore import Qt

from common import acc_manager

from ui.style import (
    APP_STYLE, C_BG, C_BORDER, C_WHITE,
    C_WHITE_DIM, C_WHITE_MUT, C_GHOST,
    C_SIDEBAR, C_TOPBAR, FONT_UI,
    BTN_PRIMARY, CARD_STYLE
)

from ui.main_window import (MainWindow, _h, _field, _divider)


class RegisterWindow(QWidget):

    def __init__(self):
        super().__init__()
        self.setWindowTitle("Fatha — Register Owner")
        self.setMinimumSize(560, 700)
        self.setStyleSheet(APP_STYLE + f"QWidget#root {{ background: {C_BG}; }}")
        self._build_ui()

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        banner = QFrame()
        banner.setFixedHeight(80)
        banner.setStyleSheet(f"""
            QFrame {{
                background: {C_SIDEBAR};
                border: none;
                border-bottom: 1px solid {C_BORDER};
            }}
        """)
        bl = QVBoxLayout(banner)
        bl.setContentsMargins(32, 0, 32, 0)
        bl.setSpacing(2)
        app_lbl = QLabel("FATHA")
        app_lbl.setFont(QFont(FONT_UI, 20, QFont.Weight.Bold))
        app_lbl.setStyleSheet(
            f"color: {C_WHITE}; background: transparent; letter-spacing: 6px;"
        )
        sub_lbl = QLabel("Owner Registration")
        sub_lbl.setFont(QFont(FONT_UI, 10))
        sub_lbl.setStyleSheet(f"color: {C_GHOST}; background: transparent;")
        bl.addStretch()
        bl.addWidget(app_lbl)
        bl.addWidget(sub_lbl)
        bl.addStretch()
        root.addWidget(banner)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("border: none; background: transparent;")
        body = QWidget()
        body.setObjectName("root")
        body.setStyleSheet(f"background: {C_BG};")
        bv = QVBoxLayout(body)
        bv.setContentsMargins(32, 28, 32, 28)
        bv.setSpacing(20)
        scroll.setWidget(body)
        root.addWidget(scroll, 1)

        bv.addWidget(_h(17, "Set up your account", bold=True, color=C_WHITE))
        hint = _h(12,
                  "This information will appear on your invoices. Fill all required fields.",
                  color=C_GHOST)
        hint.setWordWrap(True)
        bv.addWidget(hint)
        bv.addWidget(_divider())
        bv.addSpacing(4)

        def _section(title: str):
            frame = QFrame()
            frame.setStyleSheet(CARD_STYLE)
            vl = QVBoxLayout(frame)
            vl.setContentsMargins(24, 18, 24, 18)
            vl.setSpacing(14)
            hd = QLabel(title)
            hd.setFont(QFont(FONT_UI, 9, QFont.Weight.Bold))
            hd.setStyleSheet(
                f"color: {C_GHOST}; letter-spacing: 2px; background: transparent;"
            )
            vl.addWidget(hd)
            vl.addWidget(_divider())
            return frame, vl

        def _row(vl, label: str, widget, required=False):
            hl = QHBoxLayout()
            hl.setSpacing(0)
            lbl_text = label + (" *" if required else "")
            lbl = QLabel(lbl_text)
            lbl.setFont(QFont(FONT_UI, 11))
            lbl.setStyleSheet(
                f"color: {C_WHITE_DIM if required else C_WHITE_MUT}; "
                f"background: transparent; min-width: 110px;"
            )
            lbl.setFixedWidth(130)
            hl.addWidget(lbl)
            hl.addWidget(widget)
            vl.addLayout(hl)

        c1, v1 = _section("BUSINESS INFORMATION")
        self.company = _field("e.g. Fatha Pvt Ltd.")
        self.gst     = _field("15-character GST number")
        self.gst.setMaxLength(15)
        self.address = _field("Works / office address")
        self.state   = _field("e.g. Haryana")
        self.pincode = _field("6-digit pincode")
        self.pincode.setMaxLength(6)
        self.cin     = _field("Company Identification Number (optional)")
        _row(v1, "Company Name", self.company, required=True)
        _row(v1, "GST Number",   self.gst,     required=True)
        _row(v1, "Address",      self.address, required=True)
        _row(v1, "State",        self.state,   required=True)
        _row(v1, "Pincode",      self.pincode)
        _row(v1, "CIN",          self.cin)
        bv.addWidget(c1)

        c2, v2 = _section("CONTACT DETAILS")
        self.mobile = _field("10-digit mobile number")
        self.mobile.setMaxLength(10)
        self.email  = _field("Business email address")
        _row(v2, "Mobile", self.mobile, required=True)
        _row(v2, "Email",  self.email)
        bv.addWidget(c2)

        c3, v3 = _section("BANK DETAILS  (shown on invoices)")
        self.bank    = _field("Bank name")
        self.account = _field("Account number")
        self.ifsc    = _field("IFSC code")
        _row(v3, "Bank Name",   self.bank)
        _row(v3, "Account No.", self.account)
        _row(v3, "IFSC Code",   self.ifsc)
        bv.addWidget(c3)

        bv.addStretch()

        actbar = QFrame()
        actbar.setFixedHeight(64)
        actbar.setStyleSheet(f"""
            QFrame {{
                background: {C_TOPBAR};
                border: none;
                border-top: 1px solid {C_BORDER};
            }}
        """)
        al = QHBoxLayout(actbar)
        al.setContentsMargins(32, 0, 32, 0)
        al.setSpacing(12)

        note = QLabel("* Required fields")
        note.setStyleSheet(
            f"color: {C_GHOST}; font-size: 11px; background: transparent;"
        )

        reg_btn = QPushButton("Create Account")
        reg_btn.setStyleSheet(BTN_PRIMARY)
        reg_btn.setMinimumHeight(40)
        reg_btn.setMinimumWidth(160)
        reg_btn.clicked.connect(self.register)

        al.addWidget(note)
        al.addStretch()
        al.addWidget(reg_btn)
        root.addWidget(actbar)


    def register(self):
        if not self.company.text().strip():
            QMessageBox.warning(self, "Validation", "Company Name is required.")
            return
        if not self.gst.text().strip():
            QMessageBox.warning(self, "Validation", "GST Number is required.")
            return
        if not self.address.text().strip():
            QMessageBox.warning(self, "Validation", "Address is required.")
            return
        if not self.state.text().strip():
            QMessageBox.warning(self, "Validation", "State is required.")
            return
        if not self.mobile.text().strip():
            QMessageBox.warning(self, "Validation", "Mobile is required.")
            return

        try:
            status, message = acc_manager.initialize_account_data(
                company=self.company.text().strip(),
                mobile=self.mobile.text().strip(),
                email=self.email.text().strip(),
                gst=self.gst.text().strip(),
                address=self.address.text().strip(),
                state=self.state.text().strip(),
                bank=self.bank.text().strip(),
                account=self.account.text().strip(),
                ifsc=self.ifsc.text().strip(),
                cin=self.cin.text().strip(),
                pincode=self.pincode.text().strip(),
            )

            if status == "Success":
                QMessageBox.information(self, "Success", message)
                self.main = MainWindow()
                self.main.show()
                self.close()
            else:
                QMessageBox.warning(self, "Error", message)

        except Exception as e:
            QMessageBox.critical(self, "Unexpected Error", str(e))
