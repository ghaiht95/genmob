import os
import subprocess
import json
from datetime import datetime
import logging

# إعداد السجلات
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class SoftEtherVPN:
    def __init__(self, server_ip=None, server_port=443, admin_password=None):
        self.server_ip = server_ip or os.getenv("SOFTETHER_SERVER_IP", "localhost")
        self.server_port = server_port
        self.admin_password = admin_password or os.getenv("SOFTETHER_ADMIN_PASSWORD")
        if not self.admin_password:
            raise ValueError("SOFTETHER_ADMIN_PASSWORD must be set in environment")
        
        # تحديد المسار الكامل لـ vpncmd
        self.vpncmd_path = os.getenv("VPNCMD_PATH", "/usr/local/vpnserver/vpncmd")
        if not os.path.exists(self.vpncmd_path):
            raise ValueError(f"vpncmd not found at {self.vpncmd_path}. Please set VPNCMD_PATH in environment variables.")

    def hub_exists(self, hub_name):
        """التحقق من وجود هاب معين"""
        cmd = f"{self.vpncmd_path} /SERVER {self.server_ip}:{self.server_port} /PASSWORD:{self.admin_password} /ADMINHUB:DEFAULT /CMD HubList"
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
        return hub_name in result.stdout

    def delete_hub(self, hub_name):
        """حذف هاب من سيرفر SoftEther"""
        try:
            # التحقق من وجود الهاب أولاً
            if not self.hub_exists(hub_name):
                logger.warning(f"Hub {hub_name} does not exist")
                return True  # نعتبر الحذف ناجحاً إذا لم يكن الهاب موجوداً

            # حذف جميع المستخدمين في الهاب أولاً
            cmd = f"{self.vpncmd_path} /SERVER {self.server_ip}:{self.server_port} /PASSWORD:{self.admin_password} /ADMINHUB:{hub_name} /CMD UserList"
            result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
            if result.returncode == 0:
                # استخراج أسماء المستخدمين من النتيجة
                users = [line.split()[0] for line in result.stdout.splitlines() if line.strip() and not line.startswith("UserList")]
                for user in users:
                    self.delete_user(hub_name, user)
                    logger.info(f"Deleted user {user} from hub {hub_name}")

            # حذف الهاب
            cmd = f"{self.vpncmd_path} /SERVER {self.server_ip}:{self.server_port} /PASSWORD:{self.admin_password} /ADMINHUB:DEFAULT /CMD HubDelete {hub_name}"
            result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
            
            if result.returncode == 0:
                # التحقق من حذف الهاب
                if not self.hub_exists(hub_name):
                    logger.info(f"Successfully deleted hub {hub_name}")
                    return True
                else:
                    logger.error(f"Hub {hub_name} still exists after deletion attempt")
                    return False
            else:
                logger.error(f"Failed to delete hub {hub_name}: {result.stderr}")
                return False

        except Exception as e:
            logger.error(f"Error deleting hub {hub_name}: {str(e)}")
            return False

    def create_hub(self, hub_name, hub_password="12345678"):
        """إنشاء هاب جديد في سيرفر SoftEther مع كلمة مرور تلقائية"""
        cmd = [
            self.vpncmd_path,
            "/SERVER", f"{self.server_ip}:{self.server_port}",
            f"/PASSWORD:{self.admin_password}",
            "/ADMINHUB:DEFAULT",
            "/CMD", "HubCreate", hub_name
        ]
        # كلمة مرور hub مرتين (الإدخال + التأكيد)
        input_data = f"{hub_password}\n{hub_password}\n"
        result = subprocess.run(cmd, input=input_data, capture_output=True, text=True)
        return result.returncode == 0

    def create_user(self, hub_name, username, password):
        """إنشاء مستخدم جديد في هاب معين"""
        cmd = f"{self.vpncmd_path} /SERVER {self.server_ip}:{self.server_port} /PASSWORD:{self.admin_password} /ADMINHUB:{hub_name} /CMD UserCreate {username} /GROUP:none /REALNAME:none /NOTE:none"
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
        if result.returncode == 0:
            # تعيين كلمة المرور للمستخدم
            cmd = f"{self.vpncmd_path} /SERVER {self.server_ip}:{self.server_port} /PASSWORD:{self.admin_password} /ADMINHUB:{hub_name} /CMD UserPasswordSet {username} /PASSWORD:{password}"
            result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
            return result.returncode == 0
        return False

    def delete_user(self, hub_name, username):
        """حذف مستخدم من هاب معين"""
        cmd = f"{self.vpncmd_path} /SERVER {self.server_ip}:{self.server_port} /PASSWORD:{self.admin_password} /ADMINHUB:{hub_name} /CMD UserDelete {username}"
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
        return result.returncode == 0

    def get_hub_status(self, hub_name):
        """الحصول على حالة الهاب"""
        cmd = f"{self.vpncmd_path} /SERVER {self.server_ip}:{self.server_port} /PASSWORD:{self.admin_password} /ADMINHUB:{hub_name} /CMD HubStatusGet"
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
        return result.stdout

    def get_user_list(self, hub_name):
        """الحصول على قائمة المستخدمين في هاب معين"""
        cmd = f"{self.vpncmd_path} /SERVER {self.server_ip}:{self.server_port} /PASSWORD:{self.admin_password} /ADMINHUB:{hub_name} /CMD UserList"
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
        return result.stdout