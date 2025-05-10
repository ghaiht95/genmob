# frontend/main.py
import sys
from PyQt5 import QtWidgets
from auth import AuthApp
from settings_window import SettingsWindow
from translator import Translator, _

def main():
    app = QtWidgets.QApplication(sys.argv)
    
    # تطبيق إعدادات اللغة والمظهر
    SettingsWindow.apply_settings(app)
    
    window = AuthApp()
    window.show()
    sys.exit(app.exec_())

if __name__ == "__main__":
    main()
