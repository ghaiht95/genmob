import os
import subprocess
import json
from datetime import datetime
import logging
import time
from functools import wraps

# إعداد السجلات
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def retry_on_failure(max_retries=3, delay=1):
    """مزخرف لإعادة المحاولة في حالة الفشل"""
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            retries = 0
            while retries < max_retries:
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    retries += 1
                    if retries == max_retries:
                        logger.error(f"Failed after {max_retries} retries: {str(e)}")
                        raise
                    logger.warning(f"Attempt {retries} failed: {str(e)}. Retrying in {delay} seconds...")
                    time.sleep(delay)
            return None
        return wrapper
    return decorator

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

    def _run_command(self, cmd, input_data=None):
        """تنفيذ أمر VPN مع معالجة الأخطاء"""
        try:
            if input_data:
                result = subprocess.run(cmd, input=input_data, capture_output=True, text=True, shell=True)
            else:
                result = subprocess.run(cmd, capture_output=True, text=True, shell=True)
            
            if result.returncode != 0:
                logger.error(f"Command failed: {cmd}")
                logger.error(f"Error output: {result.stderr}")
                raise Exception(f"Command failed with error: {result.stderr}")
            
            return result.stdout
        except subprocess.SubprocessError as e:
            logger.error(f"Subprocess error: {str(e)}")
            raise
        except Exception as e:
            logger.error(f"Unexpected error: {str(e)}")
            raise

    @retry_on_failure(max_retries=3, delay=1)
    def hub_exists(self, hub_name):
        """التحقق من وجود هاب معين"""
        cmd = f"{self.vpncmd_path} /SERVER {self.server_ip}:{self.server_port} /PASSWORD:{self.admin_password} /ADMINHUB:DEFAULT /CMD HubList"
        result = self._run_command(cmd)
        return hub_name in result

    @retry_on_failure(max_retries=3, delay=1)
    def delete_hub(self, hub_name):
        """حذف هاب من سيرفر SoftEther"""
        try:
            # التحقق من وجود الهاب أولاً
            if not self.hub_exists(hub_name):
                logger.debug(f"Hub {hub_name} does not exist")
                return True  # نعتبر الحذف ناجحاً إذا لم يكن الهاب موجوداً

            # حذف جميع المستخدمين في الهاب أولاً
            cmd = f"{self.vpncmd_path} /SERVER {self.server_ip}:{self.server_port} /PASSWORD:{self.admin_password} /ADMINHUB:{hub_name} /CMD UserList"
            result = self._run_command(cmd)
            
            # استخراج أسماء المستخدمين من النتيجة
            users = [line.split()[0] for line in result.splitlines() if line.strip() and not line.startswith("UserList")]
            for user in users:
                self.delete_user(hub_name, user)
                logger.info(f"Deleted user {user} from hub {hub_name}")

            # حذف الهاب
            cmd = f"{self.vpncmd_path} /SERVER {self.server_ip}:{self.server_port} /PASSWORD:{self.admin_password} /ADMINHUB:DEFAULT /CMD HubDelete {hub_name}"
            self._run_command(cmd)
            
            # التحقق من حذف الهاب
            if not self.hub_exists(hub_name):
                logger.info(f"Successfully deleted hub {hub_name}")
                return True
            else:
                logger.error(f"Hub {hub_name} still exists after deletion attempt")
                return False

        except Exception as e:
            logger.error(f"Error deleting hub {hub_name}: {str(e)}")
            return False

    @retry_on_failure(max_retries=3, delay=1)
    def create_hub(self, hub_name, hub_password="12345678"):
        """إنشاء هاب جديد في سيرفر SoftEther مع كلمة مرور تلقائية"""
        try:
            if self.hub_exists(hub_name):
                logger.warning(f"Hub {hub_name} already exists")
                return True

            cmd = [
                self.vpncmd_path,
                "/SERVER", f"{self.server_ip}:{self.server_port}",
                f"/PASSWORD:{self.admin_password}",
                "/ADMINHUB:DEFAULT",
                "/CMD", "HubCreate", hub_name
            ]
            # كلمة مرور hub مرتين (الإدخال + التأكيد)
            input_data = f"{hub_password}\n{hub_password}\n"
            self._run_command(" ".join(cmd), input_data)
            
            if self.hub_exists(hub_name):
                logger.info(f"Successfully created hub {hub_name}")
                return True
            else:
                logger.error(f"Failed to create hub {hub_name}")
                return False
                
        except Exception as e:
            logger.error(f"Error creating hub {hub_name}: {str(e)}")
            return False

    @retry_on_failure(max_retries=3, delay=1)
    def create_user(self, hub_name, username, password):
        """إنشاء مستخدم جديد في هاب معين"""
        try:
            if not self.hub_exists(hub_name):
                logger.error(f"Hub {hub_name} does not exist")
                return False

            if self.user_exists(hub_name, username):
                logger.warning(f"User {username} already exists in hub {hub_name}")
                return True

            # إنشاء المستخدم
            cmd = f"{self.vpncmd_path} /SERVER {self.server_ip}:{self.server_port} /PASSWORD:{self.admin_password} /ADMINHUB:{hub_name} /CMD UserCreate {username} /GROUP:none /REALNAME:none /NOTE:none"
            self._run_command(cmd)

            # تعيين كلمة المرور
            cmd = f"{self.vpncmd_path} /SERVER {self.server_ip}:{self.server_port} /PASSWORD:{self.admin_password} /ADMINHUB:{hub_name} /CMD UserPasswordSet {username} /PASSWORD:{password}"
            self._run_command(cmd)

            if self.user_exists(hub_name, username):
                logger.info(f"Successfully created user {username} in hub {hub_name}")
                return True
            else:
                logger.error(f"Failed to create user {username} in hub {hub_name}")
                return False

        except Exception as e:
            logger.error(f"Error creating user {username} in hub {hub_name}: {str(e)}")
            return False

    @retry_on_failure(max_retries=3, delay=1)
    def delete_user(self, hub_name: str, username: str) -> bool:
        """حذف مستخدم من هاب VPN"""
        try:
            # التحقق من وجود الهاب
            if not self.hub_exists(hub_name):
                logger.error(f"Hub {hub_name} does not exist")
                return False

            # التحقق من وجود المستخدم
            if not self.user_exists(hub_name, username):
                logger.debug(f"User {username} does not exist in hub {hub_name}")
                return True  # نعتبر أن الحذف ناجح إذا لم يكن المستخدم موجوداً

            # حذف المستخدم
            cmd = f"{self.vpncmd_path} /SERVER {self.server_ip}:{self.server_port} /PASSWORD:{self.admin_password} /ADMINHUB:{hub_name} /CMD UserDelete {username}"
            self._run_command(cmd)
            
            if not self.user_exists(hub_name, username):
                logger.info(f"Successfully deleted user {username} from hub {hub_name}")
                return True
            else:
                logger.error(f"Failed to delete user {username} from hub {hub_name}")
                return False
                
        except Exception as e:
            logger.error(f"Error deleting user {username} from hub {hub_name}: {str(e)}")
            return False

    @retry_on_failure(max_retries=3, delay=1)
    def get_hub_status(self, hub_name):
        """الحصول على حالة الهاب"""
        try:
            if not self.hub_exists(hub_name):
                logger.error(f"Hub {hub_name} does not exist")
                return None

            cmd = f"{self.vpncmd_path} /SERVER {self.server_ip}:{self.server_port} /PASSWORD:{self.admin_password} /ADMINHUB:{hub_name} /CMD HubStatusGet"
            return self._run_command(cmd)
        except Exception as e:
            logger.error(f"Error getting hub status: {str(e)}")
            return None

    @retry_on_failure(max_retries=3, delay=1)
    def get_user_list(self, hub_name):
        """الحصول على قائمة المستخدمين في هاب معين"""
        try:
            if not self.hub_exists(hub_name):
                logger.error(f"Hub {hub_name} does not exist")
                return None

            cmd = f"{self.vpncmd_path} /SERVER {self.server_ip}:{self.server_port} /PASSWORD:{self.admin_password} /ADMINHUB:{hub_name} /CMD UserList"
            return self._run_command(cmd)
        except Exception as e:
            logger.error(f"Error getting user list: {str(e)}")
            return None

    @retry_on_failure(max_retries=3, delay=1)
    def user_exists(self, hub_name: str, username: str) -> bool:
        """التحقق من وجود مستخدم في هاب VPN"""
        try:
            if not self.hub_exists(hub_name):
                logger.error(f"Hub {hub_name} does not exist")
                return False

            cmd = f"{self.vpncmd_path} /SERVER {self.server_ip}:{self.server_port} /PASSWORD:{self.admin_password} /ADMINHUB:{hub_name} /CMD UserGet {username}"
            result = self._run_command(cmd)
            
            # التحقق من أن المستخدم موجود وليس جزءاً من رسالة خطأ
            return "User not found" not in result
        except Exception as e:
            logger.error(f"Error checking if user {username} exists in hub {hub_name}: {str(e)}")
            return False