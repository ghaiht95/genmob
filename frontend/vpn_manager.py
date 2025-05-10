import os
import subprocess
import logging
import time
from translator import Translator, _
from PyQt5 import QtWidgets
from vpn_thread import VPNThread

logger = logging.getLogger(__name__)
# Configure basic logging if not already configured
if not logger.handlers:
    logging.basicConfig(filename='vpn_log.txt', level=logging.DEBUG, 
                        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    console = logging.StreamHandler()
    console.setLevel(logging.INFO)
    logger.addHandler(console)

class VPNManager:
    def __init__(self, room_data, progress_window, on_connect_success=None, on_disconnect_success=None):
        self.room_data = room_data
        self.vpn_info = room_data.get("vpn_info", {})
        self.tools_path = os.path.join(os.getcwd(), "tools")
        self.vpncmd_path = os.path.join(self.tools_path, "vpncmd.exe")
        self.vpnclient_path = os.path.join(self.tools_path, "vpnclient.exe")
        self.nicname = "VPN"
        self.account = f"room_{room_data['vpn_info']['hub']}"
        self.server_ip = room_data['vpn_info']['server_ip']
        self.port = room_data['vpn_info'].get('port', 443)
        self.vpncmd_server = "localhost"

        self.progress_window = progress_window
        self.on_connect_success = on_connect_success
        self.on_disconnect_success = on_disconnect_success
        self._thread = None
        self._last_cleanup = False
        
        logger.info(f"VPNManager initialized for room: {self.account}, server: {self.server_ip}:{self.port}")

    def _run_silent(self, cmd):
        """تنفيذ الأمر بدون إخفاء النافذة"""
        logger.debug(f"Running command: {' '.join(cmd)}")
        try:
            result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=False, timeout=10)
            logger.debug(f"Command returned: {result.returncode}")
            return result
        except subprocess.TimeoutExpired:
            logger.error(f"Command timed out: {' '.join(cmd)}")
            return None

    def _check_service_exists(self):
        logger.debug("Checking if VPN service exists")
        result = subprocess.run(["sc", "query", "SEVPNCLIENT"], capture_output=True, text=True)
        exists = "SERVICE_NAME: SEVPNCLIENT" in result.stdout
        logger.debug(f"VPN service exists: {exists}")
        return exists

    def _account_exists(self):
        logger.debug(f"Checking if account {self.account} exists")
        result = subprocess.run([self.vpncmd_path, self.vpncmd_server, "/CLIENT", "/CMD", "AccountList"], capture_output=True, text=True)
        exists = self.account in result.stdout
        logger.debug(f"Account exists: {exists}")
        return exists

    # --- العمليات الثقيلة فقط ---
    def _connect_internal(self):
        try:
            logger.info(f"Starting VPN connection process for account: {self.account}")
            
            if self._account_exists():
                logger.info(f"Account {self.account} exists, disconnecting and deleting")
                self._run_silent([self.vpncmd_path, self.vpncmd_server, "/CLIENT", "/CMD", "AccountDisconnect", self.account])
                self._run_silent([self.vpncmd_path, self.vpncmd_server, "/CLIENT", "/CMD", "AccountDelete", self.account])
                logger.info(f"Account {self.account} disconnected and deleted")
            
            if not self._check_service_exists():
                logger.info("VPN Service does not exist, installing")
                self._run_silent([self.vpnclient_path, "/install"])
                logger.info("VPN Service installed")
            
            logger.info("Starting VPN service")
            self._run_silent(["sc", "start", "SEVPNCLIENT"])
            
            logger.info(f"Creating VPN account: {self.account}")
            create_result = self._run_silent([self.vpncmd_path, self.vpncmd_server, "/CLIENT", "/CMD", "AccountCreate", self.account,
                              f"/SERVER:{self.server_ip}:{self.port}", f"/HUB:{self.room_data['vpn_info']['hub']}",
                              f"/USERNAME:{self.room_data['vpn_info']['username']}", f"/NICNAME:{self.nicname}"])
            
            if create_result and create_result.returncode != 0:
                logger.error(f"Failed to create VPN account: {create_result.stderr.decode()}")
                return False
                
            logger.info(f"Setting VPN account password")
            passwd_result = self._run_silent([self.vpncmd_path, self.vpncmd_server, "/CLIENT", "/CMD", "AccountPasswordSet", self.account,
                              f"/PASSWORD:{self.room_data['vpn_info']['password']}", "/TYPE:standard"])
            
            if passwd_result and passwd_result.returncode != 0:
                logger.error(f"Failed to set VPN password: {passwd_result.stderr.decode()}")
                return False
                
            logger.info(f"Connecting to VPN account: {self.account}")
            connect_result = self._run_silent([self.vpncmd_path, self.vpncmd_server, "/CLIENT", "/CMD", "AccountConnect", self.account])
            
            if connect_result and connect_result.returncode != 0:
                logger.error(f"Failed to connect to VPN: {connect_result.stderr.decode()}")
                return False
            
            logger.info("Waiting for VPN connection to establish (2 seconds)...")
            time.sleep(2)
            logger.info(f"VPN connection successful to {self.account}")
            return True
        except Exception as e:
            logger.error(f"Unexpected error during VPN connection: {e}", exc_info=True)
            return False

    def _disconnect_internal(self, cleanup=False):
        try:
            logger.info(f"Starting VPN disconnection for account: {self.account}")
            disconnect_result = self._run_silent([self.vpncmd_path, self.vpncmd_server, "/CLIENT", "/CMD", "AccountDisconnect", self.account])
            
            if disconnect_result and disconnect_result.returncode != 0:
                logger.error(f"Failed to disconnect VPN: {disconnect_result.stderr.decode()}")
            
            if cleanup:
                logger.info(f"Cleaning up VPN account: {self.account}")
                self._run_silent([self.vpncmd_path, self.vpncmd_server, "/CLIENT", "/CMD", "AccountDelete", self.account])
                self._run_silent(["sc", "stop", "SEVPNCLIENT"])
                
            logger.info(f"VPN disconnection completed for {self.account}")
            return True
        except Exception as e:
            logger.error(f"Error during VPN disconnection: {e}", exc_info=True)
            return False

    # --- هذه الدوال تدير الخيط وتحدث الواجهة ---
    def connect(self):
        logger.info("Starting VPN connection thread")
        if self.progress_window:
            self.progress_window.show_progress()
            self.progress_window.update_status("preparing", 0)
        self._thread = VPNThread(self, mode="connect")
        self._thread.finished.connect(self._on_connect_finished)
        self._thread.start()

    def disconnect(self, cleanup=False):
        logger.info("Starting VPN disconnection thread")
        if self.progress_window:
            self.progress_window.show_progress()
            self.progress_window.update_status("disconnecting", 0)
        self._last_cleanup = cleanup
        self._thread = VPNThread(self, mode="disconnect", cleanup=cleanup)
        self._thread.finished.connect(self._on_disconnect_finished)
        self._thread.start()

    def _on_connect_finished(self, success):
        logger.info(f"VPN connection thread finished, success: {success}")
        if self.progress_window:
            if success:
                self.progress_window.update_status("connected", 100)
            else:
                self.progress_window.update_status("error", 0)
            QtWidgets.QApplication.processEvents()
            time.sleep(1)
            self.progress_window.close_progress()
        if success and self.on_connect_success:
            self.on_connect_success()

    def _on_disconnect_finished(self, success):
        logger.info(f"VPN disconnection thread finished, success: {success}")
        if self.progress_window:
            if success:
                self.progress_window.update_status("disconnected", 100)
            else:
                self.progress_window.update_status("error", 0)
            QtWidgets.QApplication.processEvents()
            time.sleep(1)
            self.progress_window.close_progress()
        if self.on_disconnect_success:
            self.on_disconnect_success()

