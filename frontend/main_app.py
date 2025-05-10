# main_app.py
import os
import sys
import ctypes
import requests
import subprocess
from PyQt5 import QtWidgets, uic, QtCore
from PyQt5.QtWidgets import QMessageBox, QDialog, QInputDialog, QListWidgetItem, QMenu
from PyQt5.QtGui import QTextCursor
from dialogs.room_settings_dialog import RoomSettingsDialog
from widgets.room_widget import RoomWidget
from room_window import RoomWindow    
from settings_window import SettingsWindow
from translator import Translator, _

# --------- تشغيل كمسؤول تلقائيًا ---------
def is_admin():
    try:
        return ctypes.windll.shell32.IsUserAnAdmin()
    except:
        return False

if not is_admin():
    ctypes.windll.shell32.ShellExecuteW(
        None, "runas", sys.executable, " ".join(sys.argv), None, 1
    )
    sys.exit()
# -------------------------------------------

API_BASE_URL = "http://31.220.80.192:5000"  # رابط السيرفر

class RoomLoader(QtCore.QThread):
    rooms_loaded = QtCore.pyqtSignal(list)
    def run(self):
        while True:
            try:
                resp = requests.get(f"{API_BASE_URL}/rooms")
                if resp.ok:
                    self.rooms_loaded.emit(resp.json().get("rooms", []))
                else:
                    # طباعة خطأ إذا لم تكن الاستجابة ناجحة (مثل 404, 500)
                    print(f"Error fetching rooms: Status {resp.status_code}, Response: {resp.text}") 
            except Exception as e: # <-- التعديل هنا: التقاط الخطأ المحدد وطباعته
                print(f"Exception in RoomLoader: {e}") # طباعة الخطأ الذي يحدث
            self.sleep(5)

class MainApp(QtWidgets.QMainWindow):
    def __init__(self, user_data):
        super().__init__()
        import os
        file_path = os.path.join(os.getcwd(), 'ui', 'main_window.ui')
        self.ui = uic.loadUi(file_path, self)
       
        self.user_data = user_data
        self.access_token = user_data.get('access_token', '')  # حفظ رمز الوصول للاستخدام في طلبات API
        
        # ترجمة واجهة المستخدم
        self.translate_ui()
        
        self.lbl_welcome.setText(_("ui.main_window.welcome", "مرحباً، {username}", username=user_data['username']))
        self.btn_create.clicked.connect(self.create_room)
        self.btn_logout.clicked.connect(self.logout)

        # أزرار قائمة الأصدقاء
        self.btn_friends.clicked.connect(self.show_friends_dialog)
        self.btn_add_friend.clicked.connect(self.add_friend_dialog)
        
        # ربط زر الإعدادات
        self.btn_settings.clicked.connect(self.show_settings)

        self.current_proc = None
        self.room_win = None
        self.last_rooms = []

        self.loader = RoomLoader()
        self.loader.rooms_loaded.connect(self.populate_rooms)
        self.loader.start()

    def translate_ui(self):
        """ترجمة عناصر واجهة المستخدم"""
        self.setWindowTitle(_("ui.main_window.title", "القائمة الرئيسية"))
        self.btn_create.setText(_("ui.main_window.create_room", "➕ إنشاء غرفة"))
        self.btn_logout.setText(_("ui.main_window.logout", "🚪 تسجيل خروج"))
        self.btn_friends.setText(_("ui.main_window.friends", "👥 الأصدقاء"))
        self.btn_add_friend.setText(_("ui.main_window.add_friend", "➕ إضافة صديق"))
        self.btn_settings.setText(_("ui.main_window.settings", "⚙️ الإعدادات"))

    def populate_rooms(self, rooms):
        for i in reversed(range(self.roomsLayout.count())):
            w = self.roomsLayout.itemAt(i).widget()
            if w:
                w.setParent(None)
        for room in rooms:
            w = RoomWidget(room, self.join_room_direct, view_mode="list")
            self.roomsLayout.addWidget(w)

    def create_room(self):
        dlg = RoomSettingsDialog(self)
        if dlg.exec_() != QDialog.Accepted:
            return
        s = dlg.get_settings()
        if not s["name"]:
            return self.show_message("أدخل اسم الغرفة")
        
        payload = {
            "name":        s["name"],
            "owner":       self.user_data["username"],
            "description": s["description"],
            "is_private":  s["is_private"],
            "password":    s["password"],
            "max_players": s["max_players"]
        }

        def log_error(msg):
            with open("log.txt", "a", encoding="utf-8") as f:
                f.write(msg + "\n")

        try:
            resp = requests.post(f"{API_BASE_URL}/create_room", json=payload)
            try:
                resp.raise_for_status()
            except requests.exceptions.HTTPError as e:
                log_error(f"[HTTPError] {e}\n[Response text] {resp.text}\n[Status] {resp.status_code}")
                return self.show_message(f"خطأ في الإنشاء: {e}\nتفاصيل الخادم: {resp.text}")
        except requests.exceptions.RequestException as e:
            log_error(f"[RequestException] {e}")
            return self.show_message(f"خطأ في الإنشاء: {e}")

        data = resp.json()
        
        # إنشاء معلومات الغرفة الكاملة
        room_info = {
            "room_id": data["room_id"],
            "name": s["name"],
            "description": s["description"],
            "is_private": s["is_private"],
            "max_players": s["max_players"],
            "current_players": 1,
            "owner_username": self.user_data["username"],
            "vpn_info": {
                "hub": data["vpn_hub"],
                "username": data["vpn_username"],
                "password": data["vpn_password"],
                "server_ip": data["server_ip"],
                "port": data.get("port", 443)
            }
        }
        
        self.update_rooms()
        self.open_room(room_info)

    def join_room_direct(self, room):
        if room.get("is_private"):
            return self.show_message("هذه الغرفة خاصة")
        try:
            resp = requests.post(f"{API_BASE_URL}/join_room", json={
                "room_id": room["room_id"],
                "username": self.user_data["username"]
            })
            resp.raise_for_status()
            data = resp.json()
            
            # تحديث معلومات الغرفة
            room.update({
                "name": room.get("name", ""),
                "description": room.get("description", ""),
                "is_private": room.get("is_private", False),
                "max_players": room.get("max_players", 8),
                "current_players": room.get("current_players", 0),
                "owner_username": room.get("owner_username", ""),
                "vpn_info": {
                    "hub": data["vpn_hub"],
                    "username": data["vpn_username"],
                    "password": data["vpn_password"],
                    "server_ip": data["server_ip"],
                    "port": data.get("port", 443)
                }
            })
            
            self.open_room(room)

        except requests.exceptions.RequestException as e:
            return self.show_message(f"خطأ في الانضمام: {e}")

    def open_room(self, room_info):
        if self.room_win:
            self.room_win.close()

        self.loader.terminate()

        self.room_win = RoomWindow(room_info, self.user_data["username"])
        self.room_win.room_closed.connect(self.on_room_close)
        self.room_win.show()

    def on_room_close(self):
        self.update_rooms()
        self.loader.start()
        self.room_win = None

    def update_rooms(self):
        try:
            resp = requests.get(f"{API_BASE_URL}/get_rooms")
            if resp.ok:
                new_rooms = resp.json().get("rooms", [])
                if self.is_rooms_changed(new_rooms):
                    self.populate_rooms(new_rooms)
                    self.last_rooms = new_rooms
                    self.notify_change()
        except requests.exceptions.RequestException:
            pass

    def is_rooms_changed(self, new_rooms):
        return new_rooms != self.last_rooms

    def notify_change(self):
        QMessageBox.information(self, _("ui.messages.update", "تحديث"), 
                               _("ui.messages.room_update", "📢 تم تحديث قائمة الغرف!"))

    def logout(self):
        if self.room_win:
            self.room_win.close()
        self.close()

    def show_message(self, msg, title="Info"):
        QMessageBox.information(self, _("ui.messages.info", title), msg)

    def show_friends_dialog(self):
        """عرض قائمة الأصدقاء الحالية"""
        friends_dialog = FriendsDialog(self.user_data, self.access_token, self)
        friends_dialog.exec_()

    def add_friend_dialog(self):
        """عرض مربع حوار لإضافة صديق جديد"""
        text, ok = QInputDialog.getText(
            self, "إضافة صديق", 
            "أدخل اسم المستخدم للصديق الذي تريد إضافته:"
        )
        if ok and text:
            self.send_friend_request(text)

    def send_friend_request(self, friend_username):
        """إرسال طلب صداقة إلى مستخدم آخر"""
        try:
            headers = {"Authorization": f"Bearer {self.access_token}"}
            response = requests.post(
                f"{API_BASE_URL}/friends/send_request", 
                json={"friend_username": friend_username},
                headers=headers
            )
            
            if response.status_code == 201:
                QMessageBox.information(self, "نجاح", "تم إرسال طلب الصداقة بنجاح")
            elif response.status_code == 200:
                QMessageBox.information(self, "نجاح", "تم قبول طلب الصداقة")
            else:
                error_msg = response.json().get("error", "حدث خطأ غير معروف")
                QMessageBox.warning(self, "خطأ", f"فشل في إرسال طلب الصداقة: {error_msg}")
        except Exception as e:
            QMessageBox.warning(self, "خطأ", f"فشل في إرسال طلب الصداقة: {str(e)}")

    def show_settings(self):
        """عرض نافذة الإعدادات"""
        settings_dialog = SettingsWindow(self)
        settings_dialog.exec_()

class FriendsDialog(QDialog):
    """مربع حوار قائمة الأصدقاء"""
    def __init__(self, user_data, access_token, parent=None):
        super().__init__(parent)
        self.user_data = user_data
        self.access_token = access_token
        
        # إعداد واجهة المستخدم
        self.setWindowTitle("قائمة الأصدقاء")
        self.setMinimumSize(500, 400)
        
        self.layout = QtWidgets.QVBoxLayout(self)
        
        # التبويبات
        self.tabs = QtWidgets.QTabWidget()
        self.tab_friends = QtWidgets.QWidget()
        self.tab_pending = QtWidgets.QWidget()
        self.tab_sent = QtWidgets.QWidget()
        
        self.tabs.addTab(self.tab_friends, "الأصدقاء")
        self.tabs.addTab(self.tab_pending, "طلبات معلقة")
        self.tabs.addTab(self.tab_sent, "طلبات مرسلة")
        
        # إعداد تبويب الأصدقاء
        self.friends_layout = QtWidgets.QVBoxLayout(self.tab_friends)
        self.list_friends = QtWidgets.QListWidget()
        self.list_friends.setContextMenuPolicy(QtCore.Qt.CustomContextMenu)
        self.list_friends.customContextMenuRequested.connect(self.show_friend_context_menu)
        self.friends_layout.addWidget(self.list_friends)
        
        # إعداد تبويب الطلبات المعلقة
        self.pending_layout = QtWidgets.QVBoxLayout(self.tab_pending)
        self.list_pending = QtWidgets.QListWidget()
        self.list_pending.setContextMenuPolicy(QtCore.Qt.CustomContextMenu)
        self.list_pending.customContextMenuRequested.connect(self.show_pending_context_menu)
        self.pending_layout.addWidget(self.list_pending)
        
        # إعداد تبويب الطلبات المرسلة
        self.sent_layout = QtWidgets.QVBoxLayout(self.tab_sent)
        self.list_sent = QtWidgets.QListWidget()
        self.list_sent.setContextMenuPolicy(QtCore.Qt.CustomContextMenu)
        self.list_sent.customContextMenuRequested.connect(self.show_sent_context_menu)
        self.sent_layout.addWidget(self.list_sent)
        
        # أضف التبويبات إلى التخطيط الرئيسي
        self.layout.addWidget(self.tabs)
        
        # زر البحث عن أصدقاء
        self.btn_search = QtWidgets.QPushButton("البحث عن مستخدمين")
        self.btn_search.clicked.connect(self.search_users_dialog)
        self.layout.addWidget(self.btn_search)
        
        # تحميل البيانات
        self.load_data()
    
    def load_data(self):
        """تحميل قوائم الأصدقاء والطلبات"""
        self.load_friends()
        self.load_pending_requests()
        self.load_sent_requests()
    
    def load_friends(self):
        """تحميل قائمة الأصدقاء"""
        try:
            headers = {"Authorization": f"Bearer {self.access_token}"}
            response = requests.get(f"{API_BASE_URL}/friends/my_friends", headers=headers)
            if response.status_code == 200:
                self.list_friends.clear()
                friends = response.json().get("friends", [])
                for friend in friends:
                    item = QListWidgetItem(f"{friend['username']} ({friend['email']})")
                    item.setData(QtCore.Qt.UserRole, friend)
                    self.list_friends.addItem(item)
        except Exception as e:
            print(f"Error loading friends: {e}")
    
    def load_pending_requests(self):
        """تحميل الطلبات المعلقة"""
        try:
            headers = {"Authorization": f"Bearer {self.access_token}"}
            response = requests.get(f"{API_BASE_URL}/friends/pending_requests", headers=headers)
            if response.status_code == 200:
                self.list_pending.clear()
                requests_data = response.json().get("pending_requests", [])
                for req in requests_data:
                    item = QListWidgetItem(f"{req['username']} ({req['email']})")
                    item.setData(QtCore.Qt.UserRole, req)
                    self.list_pending.addItem(item)
        except Exception as e:
            print(f"Error loading pending requests: {e}")
    
    def load_sent_requests(self):
        """تحميل الطلبات المرسلة"""
        try:
            headers = {"Authorization": f"Bearer {self.access_token}"}
            response = requests.get(f"{API_BASE_URL}/friends/sent_requests", headers=headers)
            if response.status_code == 200:
                self.list_sent.clear()
                requests_data = response.json().get("sent_requests", [])
                for req in requests_data:
                    item = QListWidgetItem(f"{req['username']} ({req['email']})")
                    item.setData(QtCore.Qt.UserRole, req)
                    self.list_sent.addItem(item)
        except Exception as e:
            print(f"Error loading sent requests: {e}")
    
    def show_friend_context_menu(self, position):
        """عرض قائمة السياق للأصدقاء"""
        item = self.list_friends.itemAt(position)
        if not item:
            return
        
        friend_data = item.data(QtCore.Qt.UserRole)
        
        menu = QMenu()
        remove_action = menu.addAction("إزالة من قائمة الأصدقاء")
        
        action = menu.exec_(self.list_friends.mapToGlobal(position))
        
        if action == remove_action:
            self.remove_friend(friend_data["id"])
    
    def show_pending_context_menu(self, position):
        """عرض قائمة السياق للطلبات المعلقة"""
        item = self.list_pending.itemAt(position)
        if not item:
            return
        
        request_data = item.data(QtCore.Qt.UserRole)
        
        menu = QMenu()
        accept_action = menu.addAction("قبول")
        decline_action = menu.addAction("رفض")
        
        action = menu.exec_(self.list_pending.mapToGlobal(position))
        
        if action == accept_action:
            self.accept_friend_request(request_data["request_id"])
        elif action == decline_action:
            self.decline_friend_request(request_data["request_id"])
    
    def show_sent_context_menu(self, position):
        """عرض قائمة السياق للطلبات المرسلة"""
        item = self.list_sent.itemAt(position)
        if not item:
            return
        
        request_data = item.data(QtCore.Qt.UserRole)
        
        menu = QMenu()
        cancel_action = menu.addAction("إلغاء الطلب")
        
        action = menu.exec_(self.list_sent.mapToGlobal(position))
        
        if action == cancel_action:
            self.cancel_friend_request(request_data["request_id"])
    
    def remove_friend(self, friend_id):
        """إزالة صديق من القائمة"""
        try:
            headers = {"Authorization": f"Bearer {self.access_token}"}
            response = requests.post(
                f"{API_BASE_URL}/friends/remove_friend/{friend_id}", 
                headers=headers
            )
            if response.status_code == 200:
                QMessageBox.information(self, "نجاح", "تم إزالة الصديق بنجاح")
                self.load_friends()
            else:
                error_msg = response.json().get("error", "حدث خطأ غير معروف")
                QMessageBox.warning(self, "خطأ", f"فشل في إزالة الصديق: {error_msg}")
        except Exception as e:
            QMessageBox.warning(self, "خطأ", f"فشل في إزالة الصديق: {str(e)}")
    
    def accept_friend_request(self, request_id):
        """قبول طلب صداقة"""
        try:
            headers = {"Authorization": f"Bearer {self.access_token}"}
            response = requests.post(
                f"{API_BASE_URL}/friends/accept_request/{request_id}", 
                headers=headers
            )
            if response.status_code == 200:
                QMessageBox.information(self, "نجاح", "تم قبول طلب الصداقة بنجاح")
                self.load_data()
            else:
                error_msg = response.json().get("error", "حدث خطأ غير معروف")
                QMessageBox.warning(self, "خطأ", f"فشل في قبول طلب الصداقة: {error_msg}")
        except Exception as e:
            QMessageBox.warning(self, "خطأ", f"فشل في قبول طلب الصداقة: {str(e)}")
    
    def decline_friend_request(self, request_id):
        """رفض طلب صداقة"""
        try:
            headers = {"Authorization": f"Bearer {self.access_token}"}
            response = requests.post(
                f"{API_BASE_URL}/friends/decline_request/{request_id}", 
                headers=headers
            )
            if response.status_code == 200:
                QMessageBox.information(self, "نجاح", "تم رفض طلب الصداقة")
                self.load_pending_requests()
            else:
                error_msg = response.json().get("error", "حدث خطأ غير معروف")
                QMessageBox.warning(self, "خطأ", f"فشل في رفض طلب الصداقة: {error_msg}")
        except Exception as e:
            QMessageBox.warning(self, "خطأ", f"فشل في رفض طلب الصداقة: {str(e)}")
    
    def cancel_friend_request(self, request_id):
        """إلغاء طلب صداقة مرسل"""
        try:
            headers = {"Authorization": f"Bearer {self.access_token}"}
            response = requests.post(
                f"{API_BASE_URL}/friends/cancel_request/{request_id}", 
                headers=headers
            )
            if response.status_code == 200:
                QMessageBox.information(self, "نجاح", "تم إلغاء طلب الصداقة")
                self.load_sent_requests()
            else:
                error_msg = response.json().get("error", "حدث خطأ غير معروف")
                QMessageBox.warning(self, "خطأ", f"فشل في إلغاء طلب الصداقة: {error_msg}")
        except Exception as e:
            QMessageBox.warning(self, "خطأ", f"فشل في إلغاء طلب الصداقة: {str(e)}")
    
    def search_users_dialog(self):
        """عرض مربع حوار للبحث عن مستخدمين"""
        text, ok = QInputDialog.getText(
            self, "البحث عن مستخدمين", 
            "أدخل اسم المستخدم أو البريد الإلكتروني للبحث:"
        )
        if ok and text and len(text) >= 3:
            self.search_users(text)
    
    def search_users(self, search_term):
        """البحث عن مستخدمين واقتراحهم كأصدقاء محتملين"""
        try:
            headers = {"Authorization": f"Bearer {self.access_token}"}
            response = requests.get(
                f"{API_BASE_URL}/auth/search_users?q={search_term}", 
                headers=headers
            )
            if response.status_code == 200:
                users = response.json().get("users", [])
                if not users:
                    QMessageBox.information(self, "بحث", "لم يتم العثور على نتائج")
                    return
                
                # عرض المستخدمين في مربع حوار
                dialog = UserSearchResultsDialog(users, self.access_token, self)
                dialog.user_added.connect(self.load_data)
                dialog.exec_()
            else:
                error_msg = response.json().get("error", "حدث خطأ غير معروف")
                QMessageBox.warning(self, "خطأ", f"فشل في البحث: {error_msg}")
        except Exception as e:
            QMessageBox.warning(self, "خطأ", f"فشل في البحث: {str(e)}")

class UserSearchResultsDialog(QDialog):
    """مربع حوار نتائج البحث عن المستخدمين"""
    user_added = QtCore.pyqtSignal()  # إشارة تُصدر عند إضافة مستخدم
    
    def __init__(self, users, access_token, parent=None):
        super().__init__(parent)
        self.users = users
        self.access_token = access_token
        
        self.setWindowTitle("نتائج البحث")
        self.setMinimumSize(400, 300)
        
        self.layout = QtWidgets.QVBoxLayout(self)
        
        self.list_users = QtWidgets.QListWidget()
        for user in users:
            item = QListWidgetItem(f"{user['username']} ({user['email']})")
            item.setData(QtCore.Qt.UserRole, user)
            self.list_users.addItem(item)
        
        self.layout.addWidget(self.list_users)
        
        self.btn_add = QtWidgets.QPushButton("إرسال طلب صداقة")
        self.btn_add.clicked.connect(self.add_selected_user)
        self.layout.addWidget(self.btn_add)
        
        self.btn_close = QtWidgets.QPushButton("إغلاق")
        self.btn_close.clicked.connect(self.close)
        self.layout.addWidget(self.btn_close)
    
    def add_selected_user(self):
        """إرسال طلب صداقة للمستخدم المحدد"""
        selected_items = self.list_users.selectedItems()
        if not selected_items:
            QMessageBox.warning(self, "تحذير", "يرجى تحديد مستخدم")
            return
        
        user_data = selected_items[0].data(QtCore.Qt.UserRole)
        try:
            headers = {"Authorization": f"Bearer {self.access_token}"}
            response = requests.post(
                f"{API_BASE_URL}/friends/send_request", 
                json={"friend_username": user_data["username"]},
                headers=headers
            )
            
            if response.status_code == 201:
                QMessageBox.information(self, "نجاح", "تم إرسال طلب الصداقة بنجاح")
                self.user_added.emit()
            elif response.status_code == 200:
                QMessageBox.information(self, "نجاح", "تم قبول طلب الصداقة")
                self.user_added.emit()
            else:
                error_msg = response.json().get("error", "حدث خطأ غير معروف")
                QMessageBox.warning(self, "خطأ", f"فشل في إرسال طلب الصداقة: {error_msg}")
        except Exception as e:
            QMessageBox.warning(self, "خطأ", f"فشل في إرسال طلب الصداقة: {str(e)}")

if __name__ == "__main__":
    app = QtWidgets.QApplication(sys.argv)
    win = MainApp({"username": "ali", "email": "ali@example.com"})
    win.show()
    sys.exit(app.exec_())