#!/usr/bin/env python3
"""
سكريبت بسيط لاختبار إنشاء الهاب مرتين
"""
from app.services.softether import SoftEtherVPN
import os
import logging

# إعداد السجلات
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# التحقق من وجود المتغيرات البيئية
admin_password = os.getenv("SOFTETHER_ADMIN_PASSWORD", "vpn")
server_ip = os.getenv("SOFTETHER_SERVER_IP", "localhost")
server_port = int(os.getenv("SOFTETHER_SERVER_PORT", 5555))

def test_create_hub_twice():
    """اختبار إنشاء نفس الهاب مرتين"""
    # تهيئة كائن SoftEtherVPN
    vpn = SoftEtherVPN(admin_password, server_ip, server_port)
    
    # إنشاء هاب للاختبار
    hub_name = "test_hub_99"
    
    logger.info("=== بدء الاختبار ===")
    logger.info(f"محاولة أولى لإنشاء الهاب: {hub_name}")
    
    # المحاولة الأولى - ينبغي أن تنجح دائمًا
    result1 = vpn.create_hub(hub_name)
    logger.info(f"نتيجة المحاولة الأولى: {'نجاح' if result1 else 'فشل'}")
    
    logger.info(f"محاولة ثانية لإنشاء نفس الهاب: {hub_name}")
    
    # المحاولة الثانية - ينبغي أن تنجح أيضًا مع رسالة تفيد بأن الهاب موجود بالفعل
    result2 = vpn.create_hub(hub_name)
    logger.info(f"نتيجة المحاولة الثانية: {'نجاح' if result2 else 'فشل'}")
    
    # تنظيف - حذف الهاب
    logger.info(f"تنظيف - حذف الهاب: {hub_name}")
    delete_result = vpn.delete_hub(hub_name)
    logger.info(f"نتيجة حذف الهاب: {'نجاح' if delete_result else 'فشل'}")
    
    logger.info("=== نهاية الاختبار ===")
    
    return result1 and result2

if __name__ == "__main__":
    success = test_create_hub_twice()
    print(f"نتيجة الاختبار: {'نجاح' if success else 'فشل'}") 