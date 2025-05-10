import os
import json
from PyQt5.QtWidgets import QDialog, QMessageBox
from PyQt5.QtCore import QTranslator, QLocale
from PyQt5 import uic
from translator import Translator, _

class SettingsWindow(QDialog):
    def __init__(self, parent=None):
        super(SettingsWindow, self).__init__(parent)
        
        # تعديل طريقة تحميل ملف الواجهة
        try:
            # محاولة 1: استخدام المسار النسبي للمجلد الحالي
            current_dir = os.path.dirname(os.path.abspath(__file__))
            ui_file = os.path.join(current_dir, 'ui', 'settings_window.ui')
            
            if not os.path.exists(ui_file):
                # محاولة 2: مسار نسبي للمجلد الأساسي بدون frontend
                ui_file = os.path.join('ui', 'settings_window.ui')
                
                if not os.path.exists(ui_file):
                    # محاولة 3: مسار نسبي للمجلد الحالي
                    ui_file = os.path.join('.', 'ui', 'settings_window.ui')
                
            uic.loadUi(ui_file, self)
            print(f"تم تحميل ملف الواجهة بنجاح: {ui_file}")
        except Exception as e:
            print(f"خطأ في تحميل ملف الواجهة: {e}")
            raise
        
        self.settings_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'settings.json')
        self.settings = self.load_settings()
        self.translator = Translator.get_instance()
        
        # تحميل الإعدادات الحالية
        self.setup_ui()
        self.translate_ui()
        
        # ربط الأزرار
        self.btn_save.clicked.connect(self.save_settings)
        self.btn_cancel.clicked.connect(self.reject)
        
    def translate_ui(self):
        """ترجمة عناصر واجهة المستخدم"""
        self.setWindowTitle(_("ui.settings_window.title", "الإعدادات"))
        self.groupBox_language.setTitle(_("ui.settings_window.language", "اللغة"))
        self.radio_arabic.setText(_("ui.settings_window.arabic", "العربية"))
        self.radio_english.setText(_("ui.settings_window.english", "الإنجليزية"))
        self.groupBox_style.setTitle(_("ui.settings_window.style", "ستايل البرنامج"))
        
        # ترجمة عناصر القائمة المنسدلة
        self.combo_style.setItemText(0, _("ui.settings_window.default_style", "الستايل الافتراضي"))
        self.combo_style.setItemText(1, _("ui.settings_window.dark_style", "ستايل داكن"))
        self.combo_style.setItemText(2, _("ui.settings_window.light_style", "ستايل فاتح"))
        
        # ترجمة الأزرار
        self.btn_save.setText(_("ui.settings_window.save", "حفظ"))
        self.btn_cancel.setText(_("ui.settings_window.cancel", "إلغاء"))
        
    def load_settings(self):
        """تحميل الإعدادات من الملف"""
        default_settings = {
            "language": "en",  # اللغة الافتراضية: الإنجليزية
            "style": "default"
        }
        
        try:
            if os.path.exists(self.settings_file):
                try:
                    with open(self.settings_file, 'r', encoding='utf-8') as f:
                        settings = json.load(f)
                    return settings
                except Exception as e:
                    print(f"خطأ في قراءة ملف الإعدادات: {e}")
                    return default_settings
            else:
                # إنشاء ملف إعدادات افتراضي
                try:
                    with open(self.settings_file, 'w', encoding='utf-8') as f:
                        json.dump(default_settings, f, ensure_ascii=False, indent=4)
                    print(f"تم إنشاء ملف إعدادات جديد: {self.settings_file}")
                except Exception as e:
                    print(f"خطأ في إنشاء ملف الإعدادات: {e}")
                
                return default_settings
        except Exception as e:
            print(f"خطأ عام في التعامل مع ملف الإعدادات: {e}")
            return default_settings
    
    def setup_ui(self):
        """إعداد واجهة المستخدم بناءً على الإعدادات المحفوظة"""
        # إعداد اللغة
        current_language = self.settings.get("language", "en")
        if current_language == "ar":
            self.radio_arabic.setChecked(True)
            self.radio_english.setChecked(False)
        else:
            self.radio_english.setChecked(True)
            self.radio_arabic.setChecked(False)
        
        # إعداد الستايل
        style_index = 0  # افتراضي
        if self.settings.get("style") == "dark":
            style_index = 1
        elif self.settings.get("style") == "light":
            style_index = 2
        self.combo_style.setCurrentIndex(style_index)
    
    def save_settings(self):
        """حفظ الإعدادات وتطبيقها"""
        # تحديد اللغة المختارة
        language = "en"
        if self.radio_arabic.isChecked():
            language = "ar"
        
        # تحديد الستايل
        style_index = self.combo_style.currentIndex()
        style = "default"
        if style_index == 1:
            style = "dark"
        elif style_index == 2:
            style = "light"
        
        # حفظ الإعدادات
        self.settings = {
            "language": language,
            "style": style
        }
        
        try:
            print(f"محاولة حفظ الإعدادات في: {self.settings_file}")
            with open(self.settings_file, 'w', encoding='utf-8') as f:
                json.dump(self.settings, f, ensure_ascii=False, indent=4)
            
            # طبق اللغة الجديدة فوراً
            self.translator.set_language(language)
            
            # محاولة تحديث الترجمة فوراً
            self.translate_ui()
            
            msg = QMessageBox()
            msg.setIcon(QMessageBox.Information)
            msg.setText(_("ui.settings_window.success_message", "Settings saved successfully"))
            msg.setInformativeText(_("ui.settings_window.restart_message", "Please restart the application for changes to take effect"))
            msg.setWindowTitle(_("ui.settings_window.success_title", "Success"))
            msg.exec_()
            
            self.accept()
        except Exception as e:
            print(f"خطأ عند حفظ الإعدادات: {e}")
            error_message = _("ui.settings_window.error_message", "An error occurred while saving settings: {error}", error=str(e))
            QMessageBox.critical(self, _("ui.settings_window.error_title", "Error"), error_message)
    
    @staticmethod
    def apply_settings(app):
        """تطبيق الإعدادات على التطبيق"""
        # البحث عن ملف الإعدادات في مسارات متعددة محتملة
        possible_paths = [
            os.path.join('frontend', 'settings.json'),
            os.path.join('.', 'settings.json'),
            os.path.join(os.path.dirname(os.path.abspath(__file__)), 'settings.json')
        ]
        
        settings_file = None
        for path in possible_paths:
            if os.path.exists(path):
                settings_file = path
                break
        
        # تهيئة المترجم
        translator = Translator.get_instance()
        
        if settings_file:
            try:
                print(f"تطبيق الإعدادات من: {settings_file}")
                with open(settings_file, 'r', encoding='utf-8') as f:
                    settings = json.load(f)
                
                # تطبيق اللغة المحددة
                language = settings.get("language", "en")
                translator.set_language(language)
                print(f"تم ضبط اللغة إلى: {language}")
                
                # تطبيق الستايل باستخدام ملفات QSS الخارجية
                style = settings.get("style", "default")
                current_dir = os.path.dirname(os.path.abspath(__file__))
                
                # تحديد مسارات محتملة لملفات الستايل
                style_paths = [
                    os.path.join(current_dir, 'styles', f'{style}.qss'),
                    os.path.join('frontend', 'styles', f'{style}.qss'),
                    os.path.join('styles', f'{style}.qss')
                ]
                
                style_file = None
                for path in style_paths:
                    if os.path.exists(path):
                        style_file = path
                        break
                
                if style_file:
                    try:
                        with open(style_file, 'r', encoding='utf-8') as f:
                            app.setStyleSheet(f.read())
                        print(f"تم تطبيق الستايل من الملف: {style_file}")
                    except Exception as e:
                        print(f"خطأ في قراءة ملف الستايل: {e}")
                else:
                    print(f"لم يتم العثور على ملف الستايل: {style}.qss")
                
            except Exception as e:
                print(f"خطأ في تطبيق الإعدادات: {e}") 