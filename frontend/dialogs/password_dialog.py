# frontend/dialogs/password_dialog.py
from PyQt5.QtWidgets import QDialog, QVBoxLayout, QLabel, QLineEdit, QPushButton

class PasswordDialog(QDialog):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("أدخل كلمة مرور الغرفة")

        self.input = QLineEdit()
        self.input.setEchoMode(QLineEdit.Password)

        self.btn_ok = QPushButton("دخول")
        self.btn_ok.clicked.connect(self.accept)

        layout = QVBoxLayout()
        layout.addWidget(QLabel("كلمة المرور:"))
        layout.addWidget(self.input)
        layout.addWidget(self.btn_ok)

        self.setLayout(layout)

    def get_password(self):
        return self.input.text().strip()
