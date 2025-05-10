#!/usr/bin/env python3
"""
سكريبت اختبار للتحقق من تحسينات SoftEtherVPN
"""
import logging
import os
import sys
import time
import random
import string
from services.softether import SoftEtherVPN

# تكوين التسجيل لمشاهدة كل التفاصيل
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("vpn_test.log"),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

# الحصول على المتغيرات البيئية
admin_password = os.getenv("SOFTETHER_ADMIN_PASSWORD", "vpn")
server_ip = os.getenv("SOFTETHER_SERVER_IP", "localhost")
server_port = int(os.getenv("SOFTETHER_SERVER_PORT", 5555))

def generate_random_string(length=8):
    """توليد نص عشوائي للاختبار"""
    return ''.join(random.choices(string.ascii_letters + string.digits, k=length))

def test_vpn_operations():
    """اختبار عمليات SoftEtherVPN المحسنة"""
    try:
        # تهيئة VPN
        logger.info("Initializing SoftEtherVPN with parameters:")
        logger.info(f"  Server IP: {server_ip}")
        logger.info(f"  Server Port: {server_port}")
        vpn = SoftEtherVPN(admin_password, server_ip, server_port)
        
        # الحصول على معلومات التشخيص
        logger.info("Running initial diagnostics...")
        diag = vpn.diagnose()
        logger.info(f"Initial diagnosis: Server status: {diag.get('server_info', {}).get('status')}")
        logger.info(f"Initial diagnosis: Hubs: {len(diag.get('hubs', []))}")
        logger.info(f"Initial diagnosis: Errors: {diag.get('errors', [])}")
        
        # إنشاء هاب اختباري
        test_hub = f"test_hub_{generate_random_string()}"
        logger.info(f"Creating test hub: {test_hub}")
        
        # الاختبار 1: إنشاء هاب جديد
        hub_result = vpn.create_hub(test_hub)
        logger.info(f"Hub creation result: {'SUCCESS' if hub_result else 'FAILED'}")
        
        # الاختبار 2: التحقق من وجود الهاب
        hub_exists = vpn.hub_exists(test_hub)
        logger.info(f"Hub exists check: {'TRUE' if hub_exists else 'FALSE'}")
        
        # الاختبار 3: محاولة إنشاء نفس الهاب مرة أخرى
        logger.info(f"Attempting to create the same hub again: {test_hub}")
        hub_result2 = vpn.create_hub(test_hub)
        logger.info(f"Second hub creation result: {'SUCCESS' if hub_result2 else 'FAILED'}")
        
        # الاختبار 4: إنشاء مستخدم
        test_user = f"user_{generate_random_string()}"
        test_password = generate_random_string(12)
        logger.info(f"Creating test user: {test_user} in hub: {test_hub}")
        user_result = vpn.create_user(test_hub, test_user, test_password)
        logger.info(f"User creation result: {'SUCCESS' if user_result else 'FAILED'}")
        
        # الاختبار 5: محاولة إنشاء نفس المستخدم مرة أخرى
        logger.info(f"Attempting to create the same user again: {test_user}")
        user_result2 = vpn.create_user(test_hub, test_user, test_password)
        logger.info(f"Second user creation result: {'SUCCESS' if user_result2 else 'FAILED'}")
        
        # تنظيف: حذف المستخدم
        logger.info(f"Cleaning up: Deleting user: {test_user}")
        vpn.delete_user(test_hub, test_user)
        
        # تنظيف: حذف الهاب
        logger.info(f"Cleaning up: Deleting hub: {test_hub}")
        vpn.delete_hub(test_hub)
        
        # التحقق بعد التنظيف
        hub_exists_after = vpn.hub_exists(test_hub)
        logger.info(f"Hub exists after cleanup: {'TRUE' if hub_exists_after else 'FALSE'}")
        
        # إجراء تشخيص نهائي
        logger.info("Running final diagnostics...")
        diag_final = vpn.diagnose()
        logger.info(f"Final diagnosis: Server status: {diag_final.get('server_info', {}).get('status')}")
        
        # نتيجة الاختبار
        success = hub_result and hub_exists and hub_result2 and user_result and user_result2 and not hub_exists_after
        logger.info(f"Test {'PASSED' if success else 'FAILED'}")
        
        return success
        
    except Exception as e:
        logger.error(f"Exception during testing: {str(e)}")
        return False

if __name__ == "__main__":
    logger.info("=== Starting VPN Enhanced Test ===")
    
    try:
        success = test_vpn_operations()
        exit_code = 0 if success else 1
    except Exception as e:
        logger.error(f"Unhandled exception: {str(e)}")
        exit_code = 2
        
    logger.info("=== VPN Enhanced Test Completed ===")
    sys.exit(exit_code) 