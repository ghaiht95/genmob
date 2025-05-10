# room_window.py
from PyQt5.QtCore import QTimer, QThread, pyqtSignal
from PyQt5 import QtWidgets, uic, QtCore
from PyQt5.QtWidgets import QMessageBox
import socketio
import logging
from vpn_manager import VPNManager
from vpn_thread import VPNThread
from translator import Translator, _
import os 
from progress_window import ProgressWindow  # استيراد نافذة شريط التحميل

# إعداد التسجيل
logger = logging.getLogger(__name__)
if not logger.handlers:
    logging.basicConfig(filename='room_log.txt', level=logging.DEBUG, 
                        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    console = logging.StreamHandler()
    console.setLevel(logging.INFO)
    logger.addHandler(console)

API_BASE_URL = "http://31.220.80.192:5000"
class RoomWindow(QtWidgets.QMainWindow):
    room_closed = QtCore.pyqtSignal()

    def __init__(self, room_data, user_username):
        super().__init__()

        # إعداد البيانات الأساسية
        self.room_data = room_data
        self.user_username = user_username
        self.socket = socketio.Client()
        self.players = []
        self.connection_timer = None

        # Log room initiation
        logger.info(f"Initializing room window for: {room_data.get('room_id', 'unknown')}")

        # إعداد واجهة المستخدم
        file_path = os.path.join(os.getcwd(), 'ui', 'room_window.ui')
        try:
            self.ui = uic.loadUi(file_path, self)
            logger.info("UI loaded successfully")
        except Exception as e:
            logger.error(f"Failed to load UI: {e}")
            QtWidgets.QMessageBox.critical(None, "Error", f"Failed to load UI: {e}")
            return
        
        # إعداد نافذة شريط التحميل (نافذة واحدة فقط)
        self.progress_window = ProgressWindow(self)
        
        # Setup UI before VPN connection
        self.setup_ui()
        self.setup_connections()
        self.setup_heartbeat()
        
        # إعداد مدير VPN مع تمرير نافذة التقدم
        if "vpn_info" in room_data:
            logger.info("VPN info found, creating VPN manager")
            try:
                self.vpn_manager = VPNManager(
                    room_data,
                    self.progress_window,
                    on_connect_success=self.on_vpn_connected,
                    on_disconnect_success=self.on_vpn_disconnected
                )
            except Exception as e:
                logger.error(f"Failed to create VPN manager: {e}", exc_info=True)
                QtWidgets.QMessageBox.critical(None, "Error", f"Failed to setup VPN: {e}")
                return
        else:
            logger.info("No VPN info found")
            self.vpn_manager = None

        # Show the window immediately to provide visual feedback
        self.show()
        
        # Start connection process
        if self.vpn_manager:
            logger.info("Starting VPN connection")
            self.lbl_vpn_info.setText(_("ui.room.connecting_vpn", "جاري الاتصال بـ VPN..."))
            # Add a timeout for VPN connection
            self.connection_timer = QTimer(self)
            self.connection_timer.setSingleShot(True)
            self.connection_timer.timeout.connect(self.on_vpn_timeout)
            self.connection_timer.start(60000)  # 60 second timeout
            
            self.progress_window.show_progress()
            QtWidgets.QApplication.processEvents()  # Process UI events
            
            # Start VPN connection in a separate thread
            self.vpn_manager.connect()
        else:
            logger.info("No VPN manager, connecting directly to server")
            self.connect_to_server()

    def on_vpn_timeout(self):
        """Handler for VPN connection timeout"""
        logger.error("VPN connection timed out")
        self.progress_window.close_progress()
        QtWidgets.QMessageBox.critical(self, "Connection Error", "VPN connection timed out. Please try again later.")
        self.close()

    def setup_ui(self):
        lang = Translator.get_instance().current_language
        direction = QtCore.Qt.RightToLeft if lang == "ar" else QtCore.Qt.LeftToRight
        self.setLayoutDirection(direction)

        self.chat_display.setReadOnly(True)
        self.list_players = self.findChild(QtWidgets.QListWidget, 'list_players')
        self.lbl_vpn_info.setText(_("ui.room.vpn_info", "معلومات VPN"))
        self.btn_send.setText(_("ui.room.send_button", "إرسال"))
        self.btn_leave.setText(_("ui.room.leave_button", "مغادرة"))
        self.btn_start.setText(_("ui.room.start_button", "بدء اللعبة"))

    def setup_heartbeat(self):
        """إعداد مؤقت نبض القلب"""
        self.heartbeat_timer = QTimer(self)
        self.heartbeat_timer.timeout.connect(self.send_heartbeat)
        self.heartbeat_timer.start(30000)  # إرسال نبض كل 30 ثانية

    def on_vpn_connected(self):
        """يتم استدعاؤها عند نجاح الاتصال بـ VPN"""
        logger.info("VPN connected successfully")
        
        # Cancel the timeout timer if it's running
        if self.connection_timer and self.connection_timer.isActive():
            self.connection_timer.stop()
        
        self.lbl_vpn_info.setText(_("ui.room.connected_vpn", "متصل بـ VPN"))
        QtWidgets.QApplication.processEvents()  # Process UI events
        self.connect_to_server()  # الاتصال بالخادم بعد VPN

    def on_vpn_disconnected(self):
        """يتم استدعاؤها عند نجاح قطع الاتصال بـ VPN"""
        logger.info("VPN disconnected successfully")
        self.close()  # إغلاق نافذة الغرفة

    def connect_to_server(self):
        logger.info("Connecting to server")
        try:
            self.socket.connect(API_BASE_URL)
            self.socket.emit('join', {
                'room_id': self.room_data["room_id"],
                'username': self.user_username
            })
            self.chat_display.append("🟢 تم الاتصال بالخادم")
            logger.info("Connected to server successfully")
        except Exception as e:
            logger.error(f"Failed to connect to server: {e}", exc_info=True)
            QMessageBox.critical(self, "خطأ في الاتصال", f"فشل الاتصال بالخادم: {e}")
            self.close()

    def setup_connections(self):
        self.btn_send.clicked.connect(self.send_message)
        self.chat_input.returnPressed.connect(self.send_message)
        self.btn_leave.clicked.connect(self.leave_room)
        self.btn_start.clicked.connect(self.start_game)

        self.socket.on('new_message', self.on_receive_message)
        self.socket.on('user_joined', self.on_user_joined)
        self.socket.on('user_left', self.on_user_left)
        self.socket.on('update_players', self.on_players_update)
        self.socket.on('game_started', self.on_game_started)
        self.socket.on('connect', self.on_socket_connect)
        self.socket.on('disconnect', self.on_socket_disconnect)

    def on_socket_connect(self):
        logger.info("Socket connected event")
        self.chat_display.append("🟢 تم الاتصال بالخادم")

    def on_socket_disconnect(self):
        logger.info("Socket disconnected event")
        self.chat_display.append("🔴 انقطع الاتصال بالخادم")

    def send_heartbeat(self):
        if self.socket.connected:
            logger.debug("Sending heartbeat")
            self.socket.emit('heartbeat', {
                'room_id': self.room_data["room_id"],
                'username': self.user_username
            })

    def send_message(self):
        message = self.chat_input.text().strip()
        if message:
            logger.debug(f"Sending message: {message}")
            self.socket.emit('send_message', {
                'room_id': self.room_data["room_id"],
                'username': self.user_username,
                'message': message
            })
            self.chat_display.append(f"أنت: {message}")
            self.chat_input.clear()

    def on_receive_message(self, data):
        username = data['sender']
        message = data['message']
        time = data.get('time', '')
        logger.debug(f"Received message from {username}: {message}")
        if username != self.user_username:
            self.chat_display.append(f"[{time}] {username}: {message}" if time else f"{username}: {message}")

    def on_user_joined(self, data):
        username = data['username']
        logger.info(f"User joined: {username}")
        self.chat_display.append(f"🟢 {username} انضم إلى الغرفة")
        if username not in self.players:
            self.players.append(username)
            self.update_players_list()

    def on_user_left(self, data):
        username = data['username']
        logger.info(f"User left: {username}")
        self.chat_display.append(f"🔴 {username} غادر الغرفة")
        if username in self.players:
            self.players.remove(username)
            self.update_players_list()

    def on_players_update(self, data):
        self.players = data.get('players', [])
        logger.info(f"Players updated: {len(self.players)} players")
        self.update_players_list()

    def update_players_list(self):
        self.list_players.clear()
        for player in self.players:
            self.list_players.addItem(f"🟢 {player}")
        title = _("ui.room.window_title", "غرفة اللعب") + f" - {len(self.players)} لاعبين" if Translator.get_instance().current_language == "ar" else f"Game Room - {len(self.players)} players"
        self.setWindowTitle(title)
        self.chat_display.append(f"📋 تم تحديث قائمة اللاعبين: {', '.join(self.players)}")

    def start_game(self):
        logger.info("Starting game")
        self.socket.emit('start_game', {'room_id': self.room_data["room_id"]})

    def on_game_started(self, data):
        logger.info("Game started")
        QMessageBox.information(self, "بدء اللعبة", "تم بدء اللعبة!")

    def leave_room(self):
        logger.info("User initiated room leave")
        if self.vpn_manager:
            self.progress_window.show_progress()
            self.vpn_manager.disconnect(cleanup=True)
        else:
            self.close()

    def closeEvent(self, event):
        logger.info("Room window close event")
        # Cancel the timeout timer if it's running
        if hasattr(self, 'connection_timer') and self.connection_timer and self.connection_timer.isActive():
            self.connection_timer.stop()
            
        if hasattr(self, 'heartbeat_timer') and self.heartbeat_timer.isActive():
            self.heartbeat_timer.stop()

        if self.vpn_manager:
            logger.info("Disconnecting VPN before closing")
            self.progress_window.show_progress()
            self.vpn_manager.disconnect(cleanup=True)
        else:
            try:
                if self.socket.connected:
                    logger.info("Emitting leave event")
                    self.socket.emit('leave', {
                        'room_id': self.room_data["room_id"],
                        'username': self.user_username
                    })
                    self.socket.disconnect()
            except Exception as e:
                logger.error(f"Error during socket disconnect: {e}")
                
            self.room_closed.emit()
            event.accept()