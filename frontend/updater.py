import os
import json
import requests
import subprocess
import sys
from PyQt5.QtWidgets import QMessageBox, QProgressDialog
from PyQt5.QtCore import Qt, QThread, pyqtSignal

class UpdateChecker(QThread):
    update_available = pyqtSignal(dict)
    no_update = pyqtSignal()
    error = pyqtSignal(str)

    def __init__(self):
        super().__init__()
        self.current_version = self.get_current_version()

    def get_current_version(self):
        try:
            with open('version.json', 'r', encoding='utf-8') as f:
                data = json.load(f)
                return data.get('version', '0.0.0')
        except:
            return '0.0.0'

    def run(self):
        try:
            # تحميل معلومات الإصدار من السيرفر
            response = requests.get('http://31.220.80.192:5000/version')
            if response.status_code == 200:
                server_data = response.json()
                server_version = server_data.get('version', '0.0.0')
                
                if self.compare_versions(server_version, self.current_version) > 0:
                    self.update_available.emit(server_data)
                else:
                    self.no_update.emit()
            else:
                self.error.emit("فشل في التحقق من التحديثات")
        except Exception as e:
            self.error.emit(f"خطأ في التحقق من التحديثات: {str(e)}")

    def compare_versions(self, version1, version2):
        v1_parts = [int(x) for x in version1.split('.')]
        v2_parts = [int(x) for x in version2.split('.')]
        
        for i in range(max(len(v1_parts), len(v2_parts))):
            v1 = v1_parts[i] if i < len(v1_parts) else 0
            v2 = v2_parts[i] if i < len(v2_parts) else 0
            
            if v1 > v2:
                return 1
            elif v1 < v2:
                return -1
        return 0

class Updater:
    def __init__(self, parent=None):
        self.parent = parent
        self.checker = UpdateChecker()
        self.checker.update_available.connect(self.show_update_dialog)
        self.checker.no_update.connect(self.no_update_available)
        self.checker.error.connect(self.show_error)

    def check_for_updates(self):
        self.checker.start()

    def show_update_dialog(self, update_info):
        version = update_info.get('version', '')
        changelog = update_info.get('changelog', {}).get(version, '')
        force_update = update_info.get('force_update', False)

        msg = QMessageBox(self.parent)
        msg.setWindowTitle("تحديث متوفر")
        msg.setText(f"يتوفر إصدار جديد ({version})")
        msg.setInformativeText(f"التغييرات:\n{changelog}\n\nهل تريد التحديث الآن؟")
        msg.setIcon(QMessageBox.Information)
        
        if force_update:
            msg.setStandardButtons(QMessageBox.Ok)
            msg.buttonClicked.connect(lambda: self.download_update(update_info))
        else:
            msg.setStandardButtons(QMessageBox.Yes | QMessageBox.No)
            msg.buttonClicked.connect(lambda btn: self.handle_update_choice(btn, update_info))
        
        msg.exec_()

    def handle_update_choice(self, button, update_info):
        if button.text() == "&Yes":
            self.download_update(update_info)
        else:
            QMessageBox.information(self.parent, "تحديث", "يمكنك تحديث البرنامج لاحقاً من الإعدادات")

    def download_update(self, update_info):
        try:
            # إنشاء نافذة تقدم
            progress = QProgressDialog("جاري تحميل التحديث...", "إلغال", 0, 100, self.parent)
            progress.setWindowModality(Qt.WindowModal)
            progress.setWindowTitle("تحديث البرنامج")
            progress.show()

            # تحميل الملف
            response = requests.get(update_info['download_url'], stream=True)
            total_size = int(response.headers.get('content-length', 0))
            block_size = 1024
            downloaded = 0

            update_file = "update.exe" if sys.platform == "win32" else "update"
            with open(update_file, 'wb') as f:
                for data in response.iter_content(block_size):
                    downloaded += len(data)
                    f.write(data)
                    progress.setValue(int(downloaded * 100 / total_size))
                    if progress.wasCanceled():
                        return

            progress.setValue(100)
            
            # تشغيل ملف التحديث
            if sys.platform == "win32":
                subprocess.Popen([update_file, '/SILENT'])
            else:
                os.chmod(update_file, 0o755)
                subprocess.Popen([f"./{update_file}"])

            # إغلاق البرنامج الحالي
            QMessageBox.information(self.parent, "تحديث", "سيتم إغلاق البرنامج لتطبيق التحديث")
            sys.exit()

        except Exception as e:
            QMessageBox.critical(self.parent, "خطأ", f"فشل في تحميل التحديث: {str(e)}")

    def no_update_available(self):
        if self.parent:
            QMessageBox.information(self.parent, "تحديث", "أنت تستخدم أحدث إصدار من البرنامج")

    def show_error(self, error_msg):
        if self.parent:
            QMessageBox.warning(self.parent, "خطأ", error_msg) 