from PyQt5 import QtWidgets, QtCore
from PyQt5.QtWidgets import QProgressBar, QLabel, QVBoxLayout
from PyQt5.QtCore import QTimer
from translator import Translator, _
import os
import json
import logging

# إعداد التسجيل
logger = logging.getLogger(__name__)

class ProgressWindow(QtWidgets.QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        logger.info("ProgressWindow: created")
        self.setup_ui()
        self.setup_style()
        
        # إضافة مؤقت للتحديث التدريجي للشريط
        self.animation_timer = QTimer(self)
        self.animation_timer.timeout.connect(self.animate_progress)
        self.target_progress = 0
        self.current_progress = 0

    def setup_ui(self):
        # إنشاء التخطيط الرئيسي
        self.layout = QtWidgets.QVBoxLayout(self)
        self.layout.setContentsMargins(20, 20, 20, 20)
        self.layout.setSpacing(15)

        # إنشاء شريط التقدم
        self.progress_bar = QtWidgets.QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_bar.setTextVisible(True)
        self.progress_bar.setAlignment(QtCore.Qt.AlignCenter)

        # إنشاء نص الحالة
        self.status_label = QtWidgets.QLabel()
        self.status_label.setAlignment(QtCore.Qt.AlignCenter)
        self.status_label.setWordWrap(True)

        # إضافة العناصر إلى التخطيط
        self.layout.addWidget(self.progress_bar)
        self.layout.addWidget(self.status_label)

        # إعداد النافذة
        self.setWindowFlags(QtCore.Qt.Window | QtCore.Qt.CustomizeWindowHint | QtCore.Qt.WindowTitleHint)
        self.setFixedSize(400, 150)
        self.setWindowTitle(_("ui.progress.window_title", "جاري التحميل..."))

    def setup_style(self):
        """تطبيق الستايل المناسب حسب إعدادات البرنامج"""
        # قراءة ملف الإعدادات
        settings_file = os.path.join(os.path.dirname(__file__), "settings.json")
        try:
            with open(settings_file, "r", encoding="utf-8") as f:
                settings = json.load(f)
                style = settings.get("style", "default")
        except Exception as e:
            logger.error(f"Error loading settings file: {e}")
            style = "default"
        
        # تعيين خاصية الستايل للنافذة
        self.setProperty("style", style)
        
        # قراءة ملف الستايل
        style_file = os.path.join(os.path.dirname(__file__), "styles", "progress.qss")
        try:
            with open(style_file, "r", encoding="utf-8") as f:
                self.setStyleSheet(f.read())
        except Exception as e:
            logger.error(f"Error loading style file: {e}")

    def update_translations(self):
        """تحديث النصوص عند تغيير اللغة"""
        self.setWindowTitle(_("ui.progress.window_title", "جاري التحميل..."))
        if hasattr(self, 'status_label'):
            current_text = self.status_label.text()
            if current_text:
                self.status_label.setText(_(f"ui.progress.status.{current_text}", current_text))

    def animate_progress(self):
        """تحريك شريط التقدم بسلاسة"""
        if self.current_progress < self.target_progress:
            self.current_progress += 1
            self.progress_bar.setValue(self.current_progress)
        else:
            self.animation_timer.stop()

    def show_progress(self):
        logger.info("ProgressWindow: show_progress called")
        self.current_progress = 0
        self.target_progress = 0
        self.progress_bar.setValue(0)
        self.status_label.setText(_("ui.progress.status.preparing", "جاري التحضير..."))
        
        # Ensure window is on top
        self.setWindowModality(QtCore.Qt.NonModal)
        self.raise_()
        self.activateWindow()
        self.show()
        
        # Process events to make sure UI updates
        QtCore.QCoreApplication.processEvents()

    def update_status(self, status_text, progress_value):
        """تحديث حالة التقدم والنص"""
        # استخدام مفتاح الترجمة المناسب
        translation_key = f"ui.progress.status.{status_text}"
        self.status_label.setText(_(translation_key, status_text))
        
        # تعيين قيمة التقدم المستهدفة والبدء في الحركة
        self.target_progress = progress_value
        if not self.animation_timer.isActive() and self.current_progress < self.target_progress:
            self.animation_timer.start(20)  # تحديث كل 20 مللي ثانية
        else:
            # إذا كان التقدم المستهدف أقل من الحالي (مثلاً عند إعادة التشغيل)
            if self.target_progress < self.current_progress:
                self.current_progress = self.target_progress
                self.progress_bar.setValue(self.current_progress)
        
        # Process events to make sure UI updates
        QtCore.QCoreApplication.processEvents()

    def close_progress(self):
        logger.info("ProgressWindow: close_progress called")
        
        # Stop animation timer
        if self.animation_timer.isActive():
            self.animation_timer.stop()
            
        self.hide()
        
        # إيقاف مؤقت قبل الإغلاق النهائي لتجنب الوميض
        QTimer.singleShot(200, self.final_close)
        
        # Process events right away
        QtCore.QCoreApplication.processEvents()
        
    def final_close(self):
        """إغلاق نهائي للنافذة بعد تأخير قصير"""
        self.close()  # إغلاق النافذة بشكل كامل
        QtCore.QCoreApplication.processEvents()
