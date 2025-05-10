import sys
import os
import socketio
import subprocess
import time
import logging
from PyQt5 import QtWidgets, uic, QtCore
from PyQt5.QtWidgets import QMessageBox
from PyQt5.QtCore import QMetaType, QTimer
from PyQt5.QtGui import QTextCursor

# إعداد السجلات
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

API_BASE_URL = "http://31.220.80.192:5000"  # رابط السيرفر

# Register QTextCursor type

class VPNManager:
    def __init__(self, room_data):
        print("[DEBUG] VPNManager.__init__ called")
        self.room_data = room_data
        self.tools_path = os.path.join(os.getcwd(), "tools")
        self.vpncmd_path = os.path.join(self.tools_path, "vpncmd.exe")
        self.vpnclient_path = os.path.join(self.tools_path, "vpnclient.exe")
        self.nicname = "VPN"
        self.account = f"room_{room_data['vpn_info']['hub']}"
        self.server_ip = room_data['vpn_info']['server_ip']
        self.port = room_data['vpn_info'].get('port', 443)
        self.vpncmd_server = "localhost"

    def _run_silent(self, cmd):
        print("[DEBUG] VPNManager._run_silent called")
        startupinfo = subprocess.STARTUPINFO()
        startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        startupinfo.wShowWindow = 0  # SW_HIDE

        CREATE_NO_WINDOW = 0x08000000

        return subprocess.run(
            cmd,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            creationflags=CREATE_NO_WINDOW,
            startupinfo=startupinfo,
            shell=False
        )

    # def _check_service_exists(self):
    #     result = subprocess.run(["sc", "query", "SEVPNCLIENT"], capture_output=True, text=True)
    #     return "SERVICE_NAME: SEVPNCLIENT" in result.stdout

    def _account_exists(self):
        print("[DEBUG] VPNManager._account_exists called")

        result = subprocess.run([
            self.vpncmd_path, self.vpncmd_server, "/CLIENT", "/CMD", "AccountList"
        ], capture_output=True, text=True)
        return self.account in result.stdout

    def connect(self):
        print("[DEBUG] VPNManager.connect called")
        try:
            # 1. Register service (once)
            # if not self._check_service_exists():
            #     logger.info("Registering VPN Client service...")
            #     self._run_silent([self.vpnclient_path, "/install"])

            # 2. Start service using sc (no GUI ever)
            logger.info("Starting VPN Client service silently...")
            self._run_silent(["sc", "start", "SEVPNCLIENT"])

            # 3. Create account if it doesn't exist
            if not self._account_exists():
                logger.info(f"Creating VPN account: {self.account}")
                self._run_silent([
                    self.vpncmd_path, self.vpncmd_server, "/CLIENT", "/CMD", "AccountCreate", self.account,
                    f"/SERVER:{self.server_ip}:{self.port}",
                    f"/HUB:{self.room_data['vpn_info']['hub']}",
                    f"/USERNAME:{self.room_data['vpn_info']['username']}",
                    f"/NICNAME:{self.nicname}"
                ])
                logger.info("Setting VPN password...")
                self._run_silent([
                    self.vpncmd_path, self.vpncmd_server, "/CLIENT", "/CMD", "AccountPasswordSet", self.account,
                    f"/PASSWORD:{self.room_data['vpn_info']['password']}", "/TYPE:standard"
                ])
            else:
                logger.info("VPN account already exists. Skipping creation.")

            # 4. Connect
            logger.info("Connecting to VPN...")
            self._run_silent([
                self.vpncmd_path, self.vpncmd_server, "/CLIENT", "/CMD", "AccountConnect", self.account
            ])
            logger.info("VPN connected successfully.")
            return True

        except Exception as e:
            logger.error(f"[VPN] Unexpected error: {e}")
            return False

    def disconnect(self, cleanup=False):
        print("[DEBUG] VPNManager.disconnect called")
        try:
            logger.info("Disconnecting from VPN...")
            self._run_silent([
                self.vpncmd_path, self.vpncmd_server, "/CLIENT", "/CMD", "AccountDisconnect", self.account
            ])
            self._run_silent([
                self.vpncmd_path, self.vpncmd_server, "/CLIENT", "/CMD", "AccountDelete", self.account
            ])

            logger.info("VPN disconnected successfully.")

            if cleanup:
                logger.info("Cleaning up VPN service...")
                self._run_silent(["sc", "stop", "SEVPNCLIENT"])
                self._run_silent([self.vpnclient_path, "/uninstall"])
                logger.info("VPN client service removed completely.")

        except Exception as e:
            logger.error(f"[VPN] Error during disconnection: {e}")

class RoomWindow(QtWidgets.QMainWindow):
    room_closed = QtCore.pyqtSignal()

    def __init__(self, room_data, user_username):
        print("[DEBUG] RoomWindow.__init__ called")
        print(f"[DEBUG] Room data: {room_data}")

        super().__init__()
        import os
        file_path = os.path.join(os.getcwd(), 'ui', 'room_window.ui')
        self.ui = uic.loadUi(file_path, self)

        self.room_data = room_data
        self.user_username = user_username
        
        # التحقق من وجود vpn_info
        if "vpn_info" not in room_data:
            print("[ERROR] vpn_info not found in room_data")
            raise ValueError("vpn_info is required in room_data")
            
        self.vpn_manager = VPNManager(room_data)
        self.socket = socketio.Client()
        self.players = []
        
        # إعداد مؤقت للنبضات heartbeat
        self.heartbeat_timer = QTimer(self)
        self.heartbeat_timer.timeout.connect(self.send_heartbeat)
        self.heartbeat_timer.start(30000)  # إرسال نبضة كل 30 ثانية

        self.setup_ui()
        self.setup_connections()
        self.connect_to_server()

    def setup_ui(self):
        print("[DEBUG] RoomWindow.setup_ui called")

        self.chat_display.setReadOnly(True)
        self.list_players = self.findChild(QtWidgets.QListWidget, 'list_players')
        if self.vpn_manager:
            self.lbl_vpn_info.setText(f"Hub: {self.room_data['vpn_info']['hub']}")
            # Auto-connect when window opens
            if self.vpn_manager.connect():
                self.lbl_vpn_info.setText("Connected to VPN")
            else:
                QMessageBox.critical(self, "Error", "Failed to connect to VPN")

    def setup_connections(self):
        print("[DEBUG] RoomWindow.setup_connections called")
        self.btn_send.clicked.connect(self.send_message)
        self.chat_input.returnPressed.connect(self.send_message)
        self.btn_leave.clicked.connect(self.leave_room)
        self.btn_start.clicked.connect(self.start_game)
        # Removed connect/disconnect buttons from binding
        # self.btn_connect_vpn.clicked.connect(self.connect_vpn)
        # self.btn_disconnect_vpn.clicked.connect(self.disconnect_vpn)

        self.socket.on('new_message', self.on_receive_message)
        self.socket.on('user_joined', self.on_user_joined)
        self.socket.on('user_left', self.on_user_left)
        self.socket.on('update_players', self.on_players_update)
        self.socket.on('game_started', self.on_game_started)
        self.socket.on('connect', self.on_socket_connect)
        self.socket.on('disconnect', self.on_socket_disconnect)

    def on_socket_connect(self):
        print("[DEBUG] RoomWindow.on_socket_connect called")
        logger.info("Socket.IO connected")
        self.chat_display.append("🟢 Connected to server")

    def on_socket_disconnect(self):
        print("[DEBUG] RoomWindow.on_socket_disconnect called")
        logger.warning("Socket.IO disconnected")
        self.chat_display.append("🔴 Disconnected from server")
    
    def send_heartbeat(self):
        print("[DEBUG] RoomWindow.send_heartbeat called")
        try:
            if self.socket.connected:
                self.socket.emit('heartbeat', {
                    'room_id': self.room_data["room_id"],
                    'username': self.user_username
                })
                logger.debug("Heartbeat sent")
        except Exception as e:
            logger.error(f"Error sending heartbeat: {e}")

    def connect_to_server(self):
        print("[DEBUG] RoomWindow.connect_to_server called")
        try:
            if not self.socket.connected:
                self.socket.connect(API_BASE_URL)
            
            # Send join data in all cases
            self.socket.emit('join', {
                'room_id': self.room_data["room_id"],
                'username': self.user_username
            })
        except Exception as e:
            QMessageBox.critical(self, "Connection Error", f"Failed to connect to server: {e}")
            self.close()

    def connect_vpn(self):
        # لم يعد هناك زر اتصال يدوي، الاتصال يتم تلقائيًا
        pass

    def disconnect_vpn(self):
        if self.vpn_manager:
            self.vpn_manager.disconnect()
            self.lbl_vpn_info.setText("Not connected to VPN")

    def send_message(self):
        print("[DEBUG] RoomWindow.send_message called")
        message = self.chat_input.text().strip()
        if message:
            try:
                self.socket.emit('send_message', {
                    'room_id': self.room_data["room_id"],
                    'username': self.user_username,
                    'message': message
                })
                self.chat_display.append(f"أنت: {message}")
                self.chat_input.clear()
            except Exception as e:
                print(f"Error sending message: {e}")

    def on_receive_message(self, data):
        print("[DEBUG] RoomWindow.on_receive_message called")
        username = data['sender']
        message = data['message']
        time = data.get('time', '')
        
        # عدم عرض الرسائل المرسلة من قبل المستخدم الحالي (لأنها تُعرض عند الإرسال)
        if username != self.user_username:
            if time:
                self.chat_display.append(f"[{time}] {username}: {message}")
            else:
                self.chat_display.append(f"{username}: {message}")

    def on_user_joined(self, data):
        print("[DEBUG] RoomWindow.on_user_joined called")
        username = data['username']
        self.chat_display.append(f"🟢 {username} joined the room")
        if username not in self.players:
            self.players.append(username)
            self.update_players_list()

    def on_user_left(self, data):
        print("[DEBUG] RoomWindow.on_receive_message called")
        username = data['username']
        self.chat_display.append(f"🔴 {username} left the room")
        if username in self.players:
            self.players.remove(username)
            self.update_players_list()

    def on_players_update(self, data):
        logger.info(f"Updating player list: {data}")
        self.players = data.get('players', [])
        logger.info(f"Players in room: {self.players}")
        self.update_players_list()

    def update_players_list(self):
        print("[DEBUG] RoomWindow.on_players_update called")
        self.list_players.clear()
        logger.info(f"Updating player list UI: {len(self.players)} players")
        for player in self.players:
            self.list_players.addItem(f"🟢 {player}")
        # Add message in chat when player list is updated
        self.chat_display.append(f"📋 Player list updated: {', '.join(self.players)}")

    def start_game(self):
        try:
            self.socket.emit('start_game', {'room_id': self.room_data["room_id"]})
        except Exception as e:
            print(f"Error starting game: {e}")

    def on_game_started(self, data):
        QMessageBox.information(self, "Game Started", "The game has started!")

    def leave_room(self):
        print("[DEBUG] RoomWindow.leave_room called")
        
        if self.vpn_manager:
            self.vpn_manager.disconnect()
            self.lbl_vpn_info.setText("Not connected to VPN")
        
        # Stop the heartbeat timer before leaving
        if self.heartbeat_timer.isActive():
            self.heartbeat_timer.stop()
            
        try:
            if self.socket.connected:
                # Send leave event with is_last_player flag
                players_left = len(self.players) - 1  # Subtract current player
                is_last_player = players_left == 0
                
                self.socket.emit('leave', {
                    'room_id': self.room_data["room_id"],
                    'username': self.user_username,
                    'is_last_player': is_last_player
                })
                
                # Wait for acknowledgment
                time.sleep(1)
                
                # Disconnect socket after sending leave event
                self.socket.disconnect()
                
                # Clear local data
                self.players.clear()
                self.room_closed.emit()
        except Exception as e:
            logger.error(f"Error leaving room: {e}")
        finally:
            self.close()

    def closeEvent(self, event):
        # Only handle VPN disconnection here
        if self.vpn_manager:
            self.vpn_manager.disconnect()
        
        # Ensure we're disconnected from the room
        try:
            if self.socket.connected:
                self.socket.emit('leave', {
                    'room_id': self.room_data["room_id"],
                    'username': self.user_username,
                    'is_last_player': len(self.players) <= 1
                })
                self.socket.disconnect()
        except Exception as e:
            logger.error(f"Error in closeEvent: {e}")
        
        self.room_closed.emit()
        self.players.clear()
        event.accept()