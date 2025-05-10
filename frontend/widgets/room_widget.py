from PyQt5.QtWidgets import QWidget, QLabel, QPushButton, QVBoxLayout, QHBoxLayout, QSizePolicy
from PyQt5.QtCore import Qt
from translator import _
import os

class RoomWidget(QWidget):
    def __init__(self, room, join_callback, view_mode="list"):
        super().__init__()
        self.room = room
        self.room_id = room.get("room_id", room.get("id", ""))
        self.view_mode = view_mode  # "list" or "grid"
        self.join_callback = join_callback
        
        # تعيين الحجم حسب وضع العرض
        if view_mode == "grid":
            self.setFixedSize(200, 150)
        
        # تعيين خاصية وضع العرض للستايل
        self.setProperty("viewMode", view_mode)
        
        self.setup_ui()
        self.load_style()

    def setup_ui(self):
        # اسم الغرفة
        name_label = QLabel(f"🏷️ {self.room.get('name', 'بدون اسم')}")
        name_label.setObjectName("name")

        # عدد اللاعبين
        current_players = self.room.get('current_players', 0)
        max_players = self.room.get('max_players', 8)
        players_label = QLabel(f"👥 {current_players} / {max_players}")
        players_label.setObjectName("players")

        # نوع الغرفة
        is_private = self.room.get("is_private", False)
        type_label = QLabel("🔒 خاصة" if is_private else "🌐 عامة")
        type_label.setObjectName("type")

        # زر الانضمام
        join_btn = QPushButton(_("widgets.room_card.join_button", "Join"))
        join_btn.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        join_btn.setFixedWidth(100)
        join_btn.clicked.connect(lambda: self.on_join_clicked())

        if self.view_mode == "list":
            # معلومات إضافية للوضع القائمة
            desc_label = QLabel(f"{self.room.get('description', '')}")
            desc_label.setObjectName("description")
            desc_label.setWordWrap(True)

            owner_label = QLabel(f"👤 {self.room.get('owner', self.room.get('owner_username', ''))}")
            owner_label.setObjectName("owner")

            # التنسيق الداخلي للوضع القائمة
            left_layout = QVBoxLayout()
            left_layout.addWidget(name_label)
            left_layout.addWidget(players_label)
            left_layout.addWidget(type_label)
            left_layout.addWidget(desc_label)
            left_layout.addWidget(owner_label)

            main_layout = QHBoxLayout()
            main_layout.addLayout(left_layout)
            main_layout.addStretch()
            main_layout.addWidget(join_btn)
        else:
            # التنسيق الداخلي للوضع الشبكة
            main_layout = QVBoxLayout()
            main_layout.addWidget(name_label)
            main_layout.addWidget(players_label)
            main_layout.addWidget(type_label)
            main_layout.addStretch()
            main_layout.addWidget(join_btn, alignment=Qt.AlignCenter)

        self.setLayout(main_layout)

    def load_style(self):
        """تحميل ملف الستايل"""
        style_file = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'styles', 'room_widget.qss')
        try:
            with open(style_file, 'r', encoding='utf-8') as f:
                self.setStyleSheet(f.read())
        except Exception as e:
            print(f"Error loading style file: {e}")

    def on_join_clicked(self):
        """معالجة النقر على زر الانضمام"""
        if self.join_callback:
            self.join_callback(self.room) 