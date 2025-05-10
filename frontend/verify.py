# frontend/verify.py
import requests
from PyQt5 import QtWidgets, uic
from reset_password import ResetPasswordApp
from PyQt5.QtWidgets import QMessageBox
from translator import Translator, _

API_BASE_URL = "http://31.220.80.192:5000"

class VerifyApp(QtWidgets.QDialog):
    def __init__(self, email, mode="verify"):
        super(VerifyApp, self).__init__()
        import os
        file_path = os.path.join(os.getcwd(), 'ui', 'verify_window.ui')
        self.ui = uic.loadUi(file_path, self)
        self.email = email
        self.mode = mode
        
        # ترجمة واجهة المستخدم
        self.translate_ui()
        
        self.btn_verify.clicked.connect(self.verify_code)
        self.btn_resend.clicked.connect(self.resend_code)

    def translate_ui(self):
        """ترجمة عناصر واجهة المستخدم"""
        if self.mode == "verify":
            self.setWindowTitle(_("ui.verify_window.title_verify", "التحقق من الحساب"))
        else:
            self.setWindowTitle(_("ui.verify_window.title_reset", "إعادة تعيين كلمة المرور"))
            
        self.label_instruction.setText(_("ui.verify_window.code_label", "أدخل الرمز المرسل إلى بريدك الإلكتروني:"))
        self.btn_verify.setText(_("ui.verify_window.verify_button", "تحقق"))
        self.btn_resend.setText(_("ui.verify_window.resend_button", "إعادة إرسال الكود"))

    def verify_code(self):
        code = self.input_code.text().strip()
        if not code:
            self.show_message(_("ui.verify_window.enter_code", "الرجاء إدخال الرمز."), "Error")
            return

        try:
            response = requests.post(f"{API_BASE_URL}/verify", json={
                "email": self.email,
                "code": code
            })

            if response.status_code == 200:
                self.show_message(_("ui.verify_window.success", "تم التحقق بنجاح!"), "Success")

                if self.mode == "reset":
                    self.reset_window = ResetPasswordApp(email=self.email)
                    self.reset_window.show()
                    self.close()
                else:
                    self.accept()

            else:
                self.show_message(response.json().get("error", _("ui.verify_window.invalid_code", "الرمز غير صحيح")), "Error")

        except Exception as e:
            self.show_message(_("ui.verify_window.server_error", "خطأ في الخادم: {error}", error=str(e)), "Error")

    def resend_code(self):
        """إعادة إرسال رمز التحقق"""
        try:
            if self.mode == "reset":
                endpoint = "/reset-password"
            else:
                endpoint = "/resend-verification"
                
            response = requests.post(f"{API_BASE_URL}{endpoint}", json={
                "email": self.email
            })
            
            if response.status_code == 200:
                self.show_message(_("ui.verify_window.resend_success", "تم إعادة إرسال الرمز بنجاح!"), "Success")
            else:
                error_msg = response.json().get("error", _("ui.verify_window.resend_failed", "فشل في إعادة إرسال الرمز"))
                self.show_message(error_msg, "Error")
                
        except Exception as e:
            self.show_message(_("ui.verify_window.server_error", "خطأ في الخادم: {error}", error=str(e)), "Error")

    def show_message(self, message, title="Info"):
        msg = QMessageBox()
        msg.setIcon(QMessageBox.Information if title == "Info" else QMessageBox.Warning)
        msg.setText(message)
        msg.setWindowTitle(_("ui.messages.info" if title == "Info" else "ui.messages.error", title))
        msg.exec_()
