import sys
from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QIcon
from common import acc_manager

from ui.main_window import MainWindow, APP_STYLE
from ui.register_window import RegisterWindow


class AppController:

    def __init__(self):
        self.app = QApplication(sys.argv)
        self.app.setWindowIcon(QIcon("assets/fatha_icon.ico"))
        self.app.setApplicationName("Fatha")
        self.app.setApplicationDisplayName("Fatha — Account Manager")
        self.app.setStyleSheet(APP_STYLE)

    def run(self):
        if acc_manager.owner_exists:
            self.window = MainWindow()
        else:
            self.window = RegisterWindow()

        self.window.showMaximized()
        sys.exit(self.app.exec())


if __name__ == "__main__":
    AppController().run()