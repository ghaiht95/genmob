import os
import requests
from PyQt5 import QtWidgets, uic, QtCore
from PyQt5.QtWidgets import QMessageBox
from PyQt5.QtCore import QSettings
from verify import VerifyApp
from main_app import MainApp
from translator import Translator, _

from PyQt5.QtCore import Qt


API_BASE_URL = "http://31.220.80.192:5000"

class AuthApp(QtWidgets.QMainWindow):
    def __init__(self):
        super(AuthApp, self).__init__()
        file_path = os.path.join(os.getcwd(), 'ui', 'auth_window.ui')
        uic.loadUi(file_path, self)

        self.settings = QSettings("YourCompany", "YourApp")

        # ضبط RTL
        self.group_login.setLayoutDirection(QtCore.Qt.RightToLeft)
        self.group_register.setLayoutDirection(QtCore.Qt.RightToLeft)

        # ترجمة النصوص
        self.translate_ui()

        # ربط الأزرار
        self.btn_login.clicked.connect(self.login)
        self.btn_forgot.clicked.connect(self.forgot_password)
        self.btn_register.clicked.connect(self.register)

        self.load_saved_credentials()

    def translate_ui(self):
        # تحديد اللغة الحالية
        lang = Translator.get_instance().current_language

        # تحديد الاتجاه بناءً على اللغة
        direction = Qt.RightToLeft if lang == "ar" else Qt.LeftToRight
        self.setLayoutDirection(direction)
        self.group_login.setLayoutDirection(direction)
        self.group_register.setLayoutDirection(direction)
        self.label_title.setText(_("ui.auth_window.label_title", "مرحباً بك في التطبيق"))


        # الترجمة العادية
        self.setWindowTitle(_("ui.auth_window.title", "تسجيل الدخول / التسجيل"))
        self.group_login.setTitle(_("ui.auth_window.login_group", "تسجيل الدخول"))
        self.group_register.setTitle(_("ui.auth_window.register_group", "إنشاء حساب"))

        self.label_login_email.setText(_("ui.auth_window.email_label", "البريد الإلكتروني:"))
        self.label_login_password.setText(_("ui.auth_window.password_label", "كلمة المرور:"))
        self.remember_me.setText(_("ui.auth_window.remember_me", "تذكرني"))
        self.btn_login.setText(_("ui.auth_window.login_button", "تسجيل الدخول"))
        self.btn_forgot.setText(_("ui.auth_window.forgot_button", "نسيت كلمة المرور؟"))

        self.label_reg_username.setText(_("ui.auth_window.username_label", "اسم المستخدم:"))
        self.label_reg_email.setText(_("ui.auth_window.email_label", "البريد الإلكتروني:"))
        self.label_reg_password.setText(_("ui.auth_window.password_label", "كلمة المرور:"))
        self.label_reg_confirm.setText(_("ui.auth_window.confirm_password_label", "تأكيد كلمة المرور:"))
        self.btn_register.setText(_("ui.auth_window.register_button", "تسجيل"))

        # Placeholder
        self.reg_username.setPlaceholderText(_("ui.auth_window.username_label", "اسم المستخدم"))
        self.reg_email.setPlaceholderText(_("ui.auth_window.email_label", "البريد الإلكتروني"))
        self.reg_password.setPlaceholderText(_("ui.auth_window.password_label", "كلمة المرور"))  
        self.reg_confirm.setPlaceholderText(_("ui.auth_window.confirm_password_label", "تأكيد كلمة المرور"))

    def load_saved_credentials(self):
        email = self.settings.value("email", "")
        password = self.settings.value("password", "")
        remember = self.settings.value("remember_me", False, type=bool)

        if email:
            self.login_email.setText(email)
        if password and remember:
            self.login_password.setText(password)
            self.remember_me.setChecked(True)

    def save_credentials(self, email, password, remember):
        if remember:
            self.settings.setValue("email", email)
            self.settings.setValue("password", password)
            self.settings.setValue("remember_me", True)
        else:
            self.settings.clear()

    def show_message(self, message, title="Info"):
        msg = QMessageBox()
        msg.setIcon(QMessageBox.Information if title == "Info" else QMessageBox.Warning)
        msg.setText(message)
        msg.setWindowTitle(_("ui.auth_window.info" if title == "Info" else "ui.auth_window.error", title))
        msg.exec_()

    def login(self):
        email = self.login_email.text().strip()
        password = self.login_password.text().strip()
        remember = self.remember_me.isChecked()

        if not email or not password:
            self.show_message(_("ui.auth_window.enter_email_password", "يرجى إدخال البريد وكلمة المرور."), "Error")
            return

        try:
            response = requests.post(f"{API_BASE_URL}/login", json={
                "email": email,
                "password": password
            })

            if response.status_code == 200:
                self.save_credentials(email, password, remember)
                data = response.json()
                data["email"] = email
                self.main_window = MainApp(user_data=data)
                self.main_window.show()
                self.close()
            else:
                error_msg = response.json().get("error", "فشل تسجيل الدخول.")
                self.show_message(_(
                    "ui.auth_window.login_error",
                    "{error}",
                    error=error_msg
                ), "Error")

        except Exception as e:
            self.show_message(_("ui.auth_window.connection_error", "خطأ في الاتصال: {error}", error=str(e)), "Error")

    def register(self):
        username = self.reg_username.text().strip()
        email = self.reg_email.text().strip()
        password = self.reg_password.text().strip()
        confirm = self.reg_confirm.text().strip()

        if not username or not email or not password or not confirm:
            self.show_message(_("ui.auth_window.fill_all_fields", "يرجى ملء جميع الحقول."), "Error")
            return

        if password != confirm:
            self.show_message(_("ui.auth_window.passwords_not_match", "كلمات المرور غير متطابقة."), "Error")
            return

        try:
            response = requests.post(f"{API_BASE_URL}/register", json={
                "username": username,
                "email": email,
                "password": password
            })

            if response.status_code == 200:
                self.show_message(_("ui.auth_window.verification_sent", "تم إرسال رمز التحقق إلى بريدك."))
                self.verify_window = VerifyApp(email=email)
                self.verify_window.exec_()
            else:
                error_msg = response.json().get("error", "فشل التسجيل.")
                self.show_message(_(
                    "ui.auth_window.register_error",
                    "{error}",
                    error=error_msg
                ), "Error")
        except Exception as e:
            self.show_message(_("ui.auth_window.server_error", "خطأ في الخادم: {error}", error=str(e)), "Error")

    def forgot_password(self):
        email = self.login_email.text().strip()
        if not email:
            self.show_message(_("ui.auth_window.enter_email", "الرجاء إدخال بريدك الإلكتروني."), "Error")
            return

        try:
            response = requests.post(f"{API_BASE_URL}/reset-password", json={"email": email})

            if response.status_code == 200:
                self.show_message(_("ui.auth_window.reset_sent", "تم إرسال رمز إعادة التعيين إلى بريدك."))
                self.verify_window = VerifyApp(email=email, mode="reset")
                self.verify_window.exec_()
            else:
                try:
                    error_msg = response.json().get("error", _("ui.auth_window.reset_failed", "فشل في إرسال رمز إعادة التعيين."))
                except ValueError:
                    error_msg = _("ui.auth_window.connection_error", "استجابة غير متوقعة من الخادم.")
                self.show_message(error_msg, "Error")

        except Exception as e:
            self.show_message(_("ui.auth_window.connection_error", "خطأ في الاتصال: {error}", error=str(e)), "Error")
