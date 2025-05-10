from PyQt5.QtWidgets import QMainWindow, QMessageBox
from PyQt5.QtCore import Qt
from login_window import LoginWindow
from updater import Updater

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("GameRoom")
        self.setWindowFlags(Qt.Window | Qt.WindowCloseButtonHint)
        
        # تهيئة نظام التحديثات
        self.updater = Updater(self)
        
        # عرض نافذة تسجيل الدخول
        self.login_window = LoginWindow()
        self.login_window.login_successful.connect(self.on_login_success)
        self.login_window.show()
        
        # التحقق من التحديثات
        self.updater.check_for_updates()

    def on_login_success(self):
        self.login_window.close()
        self.show() 