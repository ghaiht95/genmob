# frontend/reset_password.py
from PyQt5 import QtWidgets, uic
import requests
from PyQt5.QtWidgets import QMessageBox
from translator import Translator, _

API_BASE_URL = "http://31.220.80.192:5000"

class ResetPasswordApp(QtWidgets.QDialog):
    def __init__(self, email):
        super(ResetPasswordApp, self).__init__()
        import os
        file_path = os.path.join(os.getcwd(), 'ui', 'reset_password.ui')
        self.ui = uic.loadUi(file_path, self)

        self.email = email
        
        # ترجمة واجهة المستخدم
        self.translate_ui()
        
        self.btn_submit.clicked.connect(self.reset_password)

    def translate_ui(self):
        """ترجمة عناصر واجهة المستخدم"""
        self.setWindowTitle(_("ui.reset_password.title", "إعادة تعيين كلمة المرور"))
        self.label_new_password.setText(_("ui.reset_password.new_password", "كلمة المرور الجديدة:"))
        self.label_confirm_password.setText(_("ui.reset_password.confirm_password", "تأكيد كلمة المرور:"))
        self.btn_submit.setText(_("ui.reset_password.submit_button", "حفظ"))
        
        # Placeholder text
        self.new_password.setPlaceholderText(_("ui.reset_password.new_password_placeholder", "أدخل كلمة المرور الجديدة"))
        self.confirm_password.setPlaceholderText(_("ui.reset_password.confirm_password_placeholder", "أكد كلمة المرور الجديدة"))

    def reset_password(self):
        new_password = self.new_password.text().strip()
        confirm_password = self.confirm_password.text().strip()

        if not new_password or not confirm_password:
            self.show_message(_("ui.reset_password.fill_all_fields", "الرجاء ملء جميع الحقول."), "Error")
            return

        if new_password != confirm_password:
            self.show_message(_("ui.reset_password.passwords_not_match", "كلمات المرور غير متطابقة."), "Error")
            return

        try:
            response = requests.post(f"{API_BASE_URL}/set-new-password", json={
                "email": self.email,
                "new_password": new_password
            })
            if response.status_code == 200:
                self.show_message(_("ui.reset_password.success", "تم تغيير كلمة المرور بنجاح."), "Success")
                self.close()
            else:
                self.show_message(
                    response.json().get("error", _("ui.reset_password.failed", "فشل في إعادة تعيين كلمة المرور.")),
                    "Error"
                )
        except Exception as e:
            self.show_message(_("ui.reset_password.server_error", "خطأ في الخادم: {error}", error=str(e)), "Error")

    def show_message(self, message, title="Info"):
        msg = QMessageBox()
        msg.setIcon(QMessageBox.Information if title == "Info" or title == "Success" else QMessageBox.Warning)
        msg.setText(message)
        msg.setWindowTitle(_("ui.messages.info" if title == "Info" or title == "Success" else "ui.messages.error", title))
        msg.exec_()
