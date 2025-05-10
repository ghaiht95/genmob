from PyQt5 import QtWidgets
from PyQt5.QtWidgets import QDialog, QFormLayout, QLineEdit, QSpinBox, QCheckBox, QDialogButtonBox

class RoomSettingsDialog(QDialog):
    def __init__(self, parent=None):
        super(RoomSettingsDialog, self).__init__(parent)
        self.setWindowTitle("إعدادات الغرفة")

        # Create layout and input widgets
        layout = QFormLayout(self)

        # Room name
        self.name_input = QLineEdit(self)
        self.name_input.setPlaceholderText("أدخل اسم الغرفة")
        layout.addRow("اسم الغرفة:", self.name_input)

        # Description
        self.description_input = QLineEdit(self)
        self.description_input.setPlaceholderText("أدخل وصفًا اختياريًا")
        layout.addRow("الوصف:", self.description_input)

        # Max players
        self.max_players_input = QSpinBox(self)
        self.max_players_input.setRange(2, 8)
        self.max_players_input.setValue(4)
        layout.addRow("الحد الأقصى للاعبين:", self.max_players_input)

        # Private checkbox and password
        self.private_checkbox = QCheckBox("غرفة خاصة", self)
        self.private_checkbox.stateChanged.connect(self._on_private_toggle)
        layout.addRow(self.private_checkbox)

        self.password_input = QLineEdit(self)
        self.password_input.setEchoMode(QLineEdit.Password)
        self.password_input.setPlaceholderText("أدخل كلمة المرور")
        self.password_input.setEnabled(False)
        layout.addRow("كلمة المرور:", self.password_input)

        # Dialog buttons
        self.button_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel, self)
        self.button_box.accepted.connect(self.accept)
        self.button_box.rejected.connect(self.reject)
        layout.addRow(self.button_box)

    def _on_private_toggle(self, state):
        # Enable password input only if private checked
        self.password_input.setEnabled(state == QtWidgets.Qt.Checked)

    def get_settings(self):
        return {
            'name': self.name_input.text().strip(),
            'description': self.description_input.text().strip(),
            'max_players': self.max_players_input.value(),
            'is_private': self.private_checkbox.isChecked(),
            'password': self.password_input.text().strip() if self.private_checkbox.isChecked() else ''
        }
