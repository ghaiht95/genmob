# frontend/reset_password.py
from PyQt5 import QtWidgets, uic
import requests

API_BASE_URL = "http://31.220.80.192:5000"

class ResetPasswordApp(QtWidgets.QDialog):
    def __init__(self, email):
        super(ResetPasswordApp, self).__init__()
        import os
        file_path = os.path.join(os.getcwd(), 'ui', 'reset_password.ui')
        self.ui = uic.loadUi(file_path, self)

        self.email = email
        self.btn_submit.clicked.connect(self.reset_password)

    def reset_password(self):
        new_password = self.new_password.text().strip()
        confirm_password = self.confirm_password.text().strip()

        if not new_password or not confirm_password:
            self.show_message("Please fill in all fields.")
            return

        if new_password != confirm_password:
            self.show_message("Passwords do not match.")
            return

        try:
            response = requests.post(f"{API_BASE_URL}/set-new-password", json={
                "email": self.email,
                "new_password": new_password
            })
            if response.status_code == 200:
                self.show_message("Password changed successfully.")
                self.close()
            else:
                self.show_message(response.json().get("error", "Failed to reset password."))
        except Exception as e:
            self.show_message(f"Server error: {str(e)}")

    def show_message(self, message):
        QtWidgets.QMessageBox.information(self, "Info", message)
