#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
أداة تشخيص SoftEther VPN

هذه الأداة تفحص إعدادات SoftEther VPN Server وتحاول تشخيص وإصلاح مشاكل إنشاء المحولات
"""

import os
import sys
import subprocess
import logging
import time
import argparse
from dotenv import load_dotenv

# تحميل متغيرات البيئة
load_dotenv()

# إعداد السجلات
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger(__name__)

class VPNDiagnostics:
    def __init__(self):
        self.admin_password = os.getenv("SOFTETHER_ADMIN_PASSWORD")
        self.server_ip = os.getenv("SOFTETHER_SERVER_IP", "localhost")
        self.server_port = int(os.getenv("SOFTETHER_SERVER_PORT", 443))
        self.vpncmd_path = os.getenv("VPNCMD_PATH", "/usr/local/vpnserver/vpncmd")
        
        if not self.admin_password:
            logger.error("SOFTETHER_ADMIN_PASSWORD غير محدد في متغيرات البيئة")
            sys.exit(1)
            
        if not os.path.exists(self.vpncmd_path):
            logger.error(f"لم يتم العثور على vpncmd في المسار: {self.vpncmd_path}")
            sys.exit(1)
            
    def run_command(self, cmd, timeout=60):
        """تنفيذ أمر وإرجاع النتيجة"""
        logger.info(f"تنفيذ الأمر: {' '.join(cmd)}")
        try:
            result = subprocess.run(
                cmd, 
                capture_output=True, 
                text=True, 
                timeout=timeout
            )
            return result
        except subprocess.TimeoutExpired:
            logger.error(f"انتهت مهلة الأمر بعد {timeout} ثانية")
            return None
            
    def check_server_status(self):
        """التحقق من حالة SoftEther VPN Server"""
        cmd = [
            self.vpncmd_path,
            "/SERVER", f"{self.server_ip}:{self.server_port}",
            f"/PASSWORD:{self.admin_password}",
            "/CMD", "ServerInfoGet"
        ]
        
        result = self.run_command(cmd)
        if not result:
            return False
            
        if result.returncode != 0:
            logger.error(f"فشل الاتصال بالخادم: {result.stderr}")
            return False
            
        logger.info("✅ الاتصال بخادم SoftEther VPN ناجح")
        logger.info(f"معلومات الخادم:\n{result.stdout}")
        return True
        
    def list_adapters(self):
        """عرض قائمة المحولات المتاحة"""
        cmd = [
            self.vpncmd_path,
            "/SERVER", f"{self.server_ip}:{self.server_port}",
            f"/PASSWORD:{self.admin_password}",
            "/CMD", "NicList"
        ]
        
        result = self.run_command(cmd)
        if not result:
            return False
            
        if result.returncode != 0:
            logger.error(f"فشل في عرض قائمة المحولات: {result.stderr}")
            logger.info(f"الخطأ: {result.stdout}")
            return False
            
        logger.info("قائمة المحولات المتوفرة:")
        logger.info(result.stdout)
        
        # التحقق من وجود محول VPN
        if "VPN" in result.stdout:
            logger.info("✅ محول VPN موجود بالفعل")
            return True
        else:
            logger.info("❌ محول VPN غير موجود")
            return False
            
    def create_adapter(self, adapter_name="VPN"):
        """إنشاء محول الشبكة الافتراضي"""
        logger.info(f"محاولة إنشاء محول: {adapter_name}")
        
        # محاولة الطريقة 1: NicCreate العادية
        cmd1 = [
            self.vpncmd_path,
            "/SERVER", f"{self.server_ip}:{self.server_port}",
            f"/PASSWORD:{self.admin_password}",
            "/CMD", "NicCreate", adapter_name
        ]
        
        result1 = self.run_command(cmd1)
        if result1 and result1.returncode == 0:
            logger.info(f"✅ تم إنشاء المحول {adapter_name} بنجاح")
            return True
            
        # محاولة الطريقة 2: استخدام LocalBridge
        logger.info("محاولة إنشاء المحول باستخدام LocalBridge...")
        cmd2 = [
            self.vpncmd_path,
            "/SERVER", f"{self.server_ip}:{self.server_port}",
            f"/PASSWORD:{self.admin_password}",
            "/CMD", "BridgeCreate", "DEFAULT", adapter_name, "/DEVICE:default"
        ]
        
        result2 = self.run_command(cmd2)
        if result2 and (result2.returncode == 0 or "already exists" in result2.stdout):
            logger.info(f"✅ تم إنشاء جسر محلي للمحول {adapter_name} بنجاح")
            return True
            
        # محاولة الطريقة 3: استخدام وضع العميل
        logger.info("محاولة إنشاء المحول باستخدام وضع العميل...")
        cmd3 = [
            self.vpncmd_path,
            f"/PASSWORD:{self.admin_password}",
            "/CLIENT",
            "/CMD", "NicCreate", adapter_name
        ]
        
        result3 = self.run_command(cmd3)
        if result3 and (result3.returncode == 0 or "already exists" in result3.stdout):
            logger.info(f"✅ تم إنشاء المحول {adapter_name} باستخدام وضع العميل بنجاح")
            return True
            
        logger.error("❌ فشلت جميع محاولات إنشاء المحول")
        
        # عرض معلومات الأخطاء للتشخيص
        if result1:
            logger.error(f"خطأ الطريقة 1: {result1.stdout}\n{result1.stderr}")
        if result2:
            logger.error(f"خطأ الطريقة 2: {result2.stdout}\n{result2.stderr}")
        if result3:
            logger.error(f"خطأ الطريقة 3: {result3.stdout}\n{result3.stderr}")
            
        return False
        
    def check_hub_list(self):
        """عرض قائمة الهابات في الخادم"""
        cmd = [
            self.vpncmd_path,
            "/SERVER", f"{self.server_ip}:{self.server_port}",
            f"/PASSWORD:{self.admin_password}",
            "/CMD", "HubList"
        ]
        
        result = self.run_command(cmd)
        if not result or result.returncode != 0:
            logger.error("فشل في عرض قائمة الهابات")
            return False
            
        logger.info("قائمة الهابات الموجودة:")
        logger.info(result.stdout)
        return True
        
    def check_permissions(self):
        """التحقق من صلاحيات المستخدم والمسارات"""
        # التحقق من صلاحيات التشغيل
        try:
            euid = os.geteuid()
            logger.info(f"معرف المستخدم الفعال: {euid}")
            if euid != 0:
                logger.warning("⚠️ البرنامج لا يعمل بصلاحيات الجذر (root)، قد تكون هناك مشاكل في إنشاء المحولات")
            else:
                logger.info("✅ البرنامج يعمل بصلاحيات الجذر (root)")
        except AttributeError:
            logger.warning("⚠️ لا يمكن التحقق من صلاحيات المستخدم (نظام غير يونيكس)")
            
        # التحقق من وجود مجلدات SoftEther VPN Server
        vpnserver_dir = os.path.dirname(self.vpncmd_path)
        if os.path.exists(f"{vpnserver_dir}/vpnserver"):
            logger.info(f"✅ ملف تنفيذ SoftEther VPN Server موجود في {vpnserver_dir}/vpnserver")
        else:
            logger.error(f"❌ ملف تنفيذ SoftEther VPN Server غير موجود في {vpnserver_dir}/vpnserver")
            
        # التحقق من صلاحيات الملفات
        try:
            vpncmd_permissions = oct(os.stat(self.vpncmd_path).st_mode)[-3:]
            logger.info(f"صلاحيات vpncmd: {vpncmd_permissions}")
            if vpncmd_permissions != '755':
                logger.warning(f"⚠️ صلاحيات vpncmd قد تكون غير كافية: {vpncmd_permissions} (متوقع: 755)")
        except Exception as e:
            logger.error(f"خطأ في التحقق من صلاحيات الملفات: {e}")
            
        return True
        
    def check_service_status(self):
        """التحقق من حالة خدمة SoftEther VPN Server"""
        try:
            result = subprocess.run(
                ["systemctl", "status", "vpnserver"], 
                capture_output=True, 
                text=True
            )
            if result.returncode == 0:
                logger.info("✅ خدمة SoftEther VPN Server تعمل")
                logger.info(result.stdout)
                return True
            else:
                logger.warning("⚠️ خدمة SoftEther VPN Server قد لا تعمل")
                logger.info(result.stdout)
                logger.info(result.stderr)
                return False
        except Exception as e:
            logger.error(f"خطأ في التحقق من حالة الخدمة: {e}")
            return False
            
    def restart_vpn_service(self):
        """إعادة تشغيل خدمة SoftEther VPN Server"""
        try:
            logger.info("جاري إعادة تشغيل خدمة SoftEther VPN Server...")
            result = subprocess.run(
                ["systemctl", "restart", "vpnserver"], 
                capture_output=True, 
                text=True
            )
            if result.returncode == 0:
                logger.info("✅ تمت إعادة تشغيل الخدمة بنجاح")
                time.sleep(5)  # انتظار قليلاً لبدء تشغيل الخدمة
                return True
            else:
                logger.error("❌ فشل في إعادة تشغيل الخدمة")
                logger.error(result.stderr)
                return False
        except Exception as e:
            logger.error(f"خطأ في إعادة تشغيل الخدمة: {e}")
            return False
            
    def fix_adapter_issues(self):
        """محاولة إصلاح مشاكل المحولات"""
        logger.info("جاري محاولة إصلاح مشاكل المحولات...")
        
        # أولاً: إعادة تشغيل الخدمة
        self.restart_vpn_service()
        
        # ثانياً: محاولة إنشاء المحول
        if self.create_adapter("VPN"):
            logger.info("✅ تم إصلاح مشكلة المحول بنجاح")
            return True
            
        # إذا استمرت المشكلة، نحاول حل آخر
        logger.info("محاولة إنشاء محولات إضافية...")
        success = False
        for i in range(1, 4):
            if self.create_adapter(f"VPN{i}"):
                logger.info(f"✅ تم إنشاء محول بديل VPN{i} بنجاح")
                success = True
                break
                
        if not success:
            logger.error("❌ فشلت جميع محاولات الإصلاح")
            
        return success
        
    def run_diagnostics(self):
        """تشغيل كافة التشخيصات"""
        logger.info("بدء تشخيص SoftEther VPN Server...")
        
        # التحقق من الصلاحيات
        self.check_permissions()
        
        # التحقق من حالة الخدمة
        self.check_service_status()
        
        # التحقق من حالة الخادم
        server_ok = self.check_server_status()
        if not server_ok:
            logger.error("❌ لا يمكن الاتصال بخادم SoftEther VPN")
            return False
            
        # عرض قائمة الهابات
        self.check_hub_list()
        
        # التحقق من المحولات
        adapters_ok = self.list_adapters()
        
        # إذا لم يتم العثور على المحول، نحاول إنشاءه
        if not adapters_ok:
            logger.info("محاولة إنشاء محول VPN...")
            if self.create_adapter():
                logger.info("✅ تم إنشاء المحول بنجاح")
            else:
                logger.error("❌ فشل في إنشاء المحول")
                self.fix_adapter_issues()
                
        return True

def main():
    parser = argparse.ArgumentParser(description="أداة تشخيص وإصلاح SoftEther VPN")
    parser.add_argument("--fix", action="store_true", help="محاولة إصلاح المشاكل المكتشفة")
    parser.add_argument("--create-adapter", action="store_true", help="إنشاء محول VPN")
    parser.add_argument("--restart", action="store_true", help="إعادة تشغيل خدمة VPN")
    parser.add_argument("--adapter-name", default="VPN", help="اسم المحول الذي سيتم إنشاؤه")
    args = parser.parse_args()
    
    diag = VPNDiagnostics()
    
    if args.restart:
        diag.restart_vpn_service()
    elif args.create_adapter:
        diag.create_adapter(args.adapter_name)
    elif args.fix:
        diag.fix_adapter_issues()
    else:
        diag.run_diagnostics()

if __name__ == "__main__":
    main() 