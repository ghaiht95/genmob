# vpn_thread.py

from PyQt5.QtCore import QThread, pyqtSignal
import logging
import time

# إعداد التسجيل
logger = logging.getLogger(__name__)

class VPNThread(QThread):
    finished = pyqtSignal(bool)
    progress = pyqtSignal(int, str)  # قيمة التقدم ورسالة الحالة

    def __init__(self, vpn_manager, mode="connect", cleanup=False):
        super().__init__()
        self.vpn_manager = vpn_manager
        self.mode = mode
        self.cleanup = cleanup
        logger.info(f"VPN Thread initialized with mode: {mode}, cleanup: {cleanup}")

    def run(self):
        try:
            logger.info(f"VPN Thread started, mode: {mode}")
            if self.mode == "connect":
                # Emit progress for UI feedback
                self.progress.emit(10, "starting")
                
                # Try connection with timeout protection
                start_time = time.time()
                max_time = 60  # Maximum 60 seconds for connection
                
                logger.info("Starting VPN connection process")
                result = self.vpn_manager._connect_internal()
                
                # Check if operation took too long
                elapsed = time.time() - start_time
                if elapsed > max_time:
                    logger.warning(f"VPN connection took too long: {elapsed:.1f} seconds")
                
                logger.info(f"VPN connection result: {result}")
                
            elif self.mode == "disconnect":
                # Emit progress for UI feedback
                self.progress.emit(10, "disconnecting")
                
                logger.info("Starting VPN disconnection process")
                result = self.vpn_manager._disconnect_internal(self.cleanup)
                logger.info(f"VPN disconnection result: {result}")
            else:
                logger.error(f"Unknown VPN thread mode: {self.mode}")
                result = False
                
            # Emit final result
            self.finished.emit(result)
            
        except Exception as e:
            logger.error(f"Exception in VPN Thread: {e}", exc_info=True)
            self.finished.emit(False)
