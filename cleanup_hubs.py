#!/usr/bin/env python3
"""
سكريبت لتنظيف وحذف جميع الهابات القديمة من خادم SoftEther VPN
"""
import logging
import os
import sys
import re
import time
import subprocess
from app.services.softether import SoftEtherVPN

# تكوين التسجيل
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("vpn_cleanup.log"),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

# الحصول على المتغيرات البيئية
admin_password = os.getenv("SOFTETHER_ADMIN_PASSWORD", "")  # كلمة مرور فارغة للوصول المحلي
server_ip = "localhost"
server_port = 5555  # المنفذ الافتراضي
# قائمة الهابات التي لا يجب حذفها (مثل الهابات النظامية)
PROTECTED_HUBS = ["DEFAULT", "defaulthub"]

def cleanup_hubs():
    """حذف جميع الهابات من خادم SoftEther VPN"""
    try:
        # تهيئة VPN
        logger.info("Initializing SoftEtherVPN with parameters:")
        logger.info(f"  Server IP: {server_ip}")
        logger.info(f"  Server Port: {server_port}")
        vpn = SoftEtherVPN(admin_password, server_ip, server_port)
        
        # محاولة الحصول على قائمة الهابات مباشرة
        args = ["/SERVER", f"{server_ip}:{server_port}"]
        if admin_password:
            args.append(f"/PASSWORD:{admin_password}")
        args.extend(["/CMD", "HubList"])
        
        logger.info(f"Executing command: {' '.join(['/usr/local/vpnserver/vpncmd'] + args)}")
        
        # تنفيذ الأمر يدويًا
        result = subprocess.run(
            ["/usr/local/vpnserver/vpncmd"] + args,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=30
        )
        
        # التحقق من نتيجة الأمر
        if result.returncode != 0:
            logger.error(f"Failed to list hubs. Return code: {result.returncode}")
            logger.error(f"Error output: {result.stderr}")
            return False
            
        stdout = result.stdout
        
        # استخراج أسماء الهابات من النتيجة
        hubs = []
        for line in stdout.splitlines():
            if "|" in line:
                parts = line.split("|")
                if len(parts) > 1:
                    hub_name = parts[1].strip()
                    if hub_name and hub_name != "Hub Name" and not hub_name.startswith("-"):
                        hubs.append(hub_name)
        
        logger.info(f"Found {len(hubs)} hubs on the server")
        
        if not hubs:
            logger.info("No hubs found to delete")
            return True
            
        # عداد للهابات المحذوفة
        deleted_count = 0
        failed_count = 0
        protected_count = 0
        
        # البحث عن نمط "room_X" حيث X هو رقم
        room_pattern = re.compile(r'^room_\d+$')
        
        # حذف كل هاب
        for hub in hubs:
            if hub in PROTECTED_HUBS:
                logger.info(f"Skipping protected hub: {hub}")
                protected_count += 1
                continue
                
            # تحديد إذا كان الهاب هو غرفة
            is_room = bool(room_pattern.match(hub))
            
            logger.info(f"Deleting hub: {hub} {'(room)' if is_room else ''}")
            
            # تنفيذ أمر حذف الهاب مباشرة
            del_args = ["/SERVER", f"{server_ip}:{server_port}"]
            if admin_password:
                del_args.append(f"/PASSWORD:{admin_password}")
            del_args.extend(["/CMD", "HubDelete", hub])
            
            try:
                del_result = subprocess.run(
                    ["/usr/local/vpnserver/vpncmd"] + del_args,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                    timeout=30
                )
                
                if del_result.returncode == 0:
                    logger.info(f"Successfully deleted hub: {hub}")
                    deleted_count += 1
                else:
                    logger.error(f"Failed to delete hub: {hub}")
                    logger.error(f"Error output: {del_result.stderr}")
                    failed_count += 1
            except Exception as e:
                logger.error(f"Error deleting hub {hub}: {str(e)}")
                failed_count += 1
                
            # انتظر قليلًا بين كل عملية حذف لتجنب الضغط على الخادم
            time.sleep(0.5)
        
        # إظهار ملخص العمليات
        logger.info("=== Cleanup Summary ===")
        logger.info(f"Total hubs found: {len(hubs)}")
        logger.info(f"Protected hubs: {protected_count}")
        logger.info(f"Deleted hubs: {deleted_count}")
        logger.info(f"Failed deletions: {failed_count}")
        
        # التحقق من النتيجة النهائية
        try:
            # تحقق مرة أخرى من قائمة الهابات المتبقية
            check_result = subprocess.run(
                ["/usr/local/vpnserver/vpncmd"] + args,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                timeout=30
            )
            
            if check_result.returncode == 0:
                # قم بعد الهابات المتبقية
                remaining_hubs = []
                for line in check_result.stdout.splitlines():
                    if "|" in line:
                        parts = line.split("|")
                        if len(parts) > 1:
                            hub_name = parts[1].strip()
                            if hub_name and hub_name != "Hub Name" and not hub_name.startswith("-"):
                                remaining_hubs.append(hub_name)
                
                logger.info(f"Remaining hubs after cleanup: {len(remaining_hubs)}")
            else:
                logger.warning("Could not verify remaining hubs after cleanup")
        except Exception as e:
            logger.warning(f"Error checking remaining hubs: {str(e)}")
        
        return failed_count == 0
        
    except subprocess.TimeoutExpired:
        logger.error("Command timed out when listing hubs")
        return False
    except Exception as e:
        logger.error(f"Exception during hub cleanup: {str(e)}")
        return False

def cleanup_rooms():
    """حذف الهابات من نوع room_X فقط"""
    try:
        # تهيئة VPN
        logger.info("Initializing SoftEtherVPN to clean up room hubs only")
        vpn = SoftEtherVPN(admin_password, server_ip, server_port)
        
        # تحديد وقت انتظار أقصر
        logger.info("Checking VPN connection...")
        
        # محاولة الحصول على قائمة الهابات مباشرة
        args = ["/SERVER", f"{server_ip}:{server_port}"]
        if admin_password:
            args.append(f"/PASSWORD:{admin_password}")
        args.extend(["/CMD", "HubList"])
        
        logger.info(f"Executing command: {' '.join(['/usr/local/vpnserver/vpncmd'] + args)}")
        
        # تنفيذ الأمر يدويًا
        result = subprocess.run(
            ["/usr/local/vpnserver/vpncmd"] + args,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=30
        )
        
        # التحقق من نتيجة الأمر
        if result.returncode != 0:
            logger.error(f"Failed to list hubs. Return code: {result.returncode}")
            logger.error(f"Error output: {result.stderr}")
            return False
            
        stdout = result.stdout
        
        # استخراج أسماء الهابات من النتيجة
        hubs = []
        for line in stdout.splitlines():
            if "|" in line:
                parts = line.split("|")
                if len(parts) > 1:
                    hub_name = parts[1].strip()
                    if hub_name and hub_name != "Hub Name" and not hub_name.startswith("-"):
                        hubs.append(hub_name)
        
        logger.info(f"Found {len(hubs)} hubs on the server")
        
        if not hubs:
            logger.info("No hubs found to delete")
            return True
        
        # البحث عن نمط "room_X" حيث X هو رقم
        room_pattern = re.compile(r'^room_\d+$')
        room_hubs = [hub for hub in hubs if room_pattern.match(hub)]
        
        logger.info(f"Found {len(room_hubs)} room hubs out of {len(hubs)} total hubs")
        
        # عداد للهابات المحذوفة
        deleted_count = 0
        failed_count = 0
        
        # حذف الهابات من نوع room فقط
        for hub in room_hubs:
            logger.info(f"Deleting room hub: {hub}")
            
            # تنفيذ أمر حذف الهاب مباشرة
            del_args = ["/SERVER", f"{server_ip}:{server_port}"]
            if admin_password:
                del_args.append(f"/PASSWORD:{admin_password}")
            del_args.extend(["/CMD", "HubDelete", hub])
            
            try:
                del_result = subprocess.run(
                    ["/usr/local/vpnserver/vpncmd"] + del_args,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                    timeout=30
                )
                
                if del_result.returncode == 0:
                    logger.info(f"Successfully deleted room hub: {hub}")
                    deleted_count += 1
                else:
                    logger.error(f"Failed to delete room hub: {hub}")
                    logger.error(f"Error output: {del_result.stderr}")
                    failed_count += 1
            except Exception as e:
                logger.error(f"Error deleting room hub {hub}: {str(e)}")
                failed_count += 1
                
            # انتظر قليلًا بين كل عملية حذف لتجنب الضغط على الخادم
            time.sleep(0.5)
        
        # إظهار ملخص العمليات
        logger.info("=== Room Cleanup Summary ===")
        logger.info(f"Total room hubs found: {len(room_hubs)}")
        logger.info(f"Deleted room hubs: {deleted_count}")
        logger.info(f"Failed deletions: {failed_count}")
        
        return failed_count == 0
        
    except subprocess.TimeoutExpired:
        logger.error("Command timed out when listing hubs")
        return False
    except Exception as e:
        logger.error(f"Exception during room hub cleanup: {str(e)}")
        return False

if __name__ == "__main__":
    logger.info("=== Starting VPN Hub Cleanup ===")
    
    if len(sys.argv) > 1 and sys.argv[1] == "--all":
        # حذف جميع الهابات
        logger.info("Executing FULL cleanup of ALL hubs (except protected ones)")
        success = cleanup_hubs()
    else:
        # حذف هابات الغرف فقط
        logger.info("Executing cleanup of ROOM hubs only")
        success = cleanup_rooms()
    
    exit_code = 0 if success else 1
    logger.info(f"=== VPN Hub Cleanup Completed with status: {'SUCCESS' if success else 'FAILURE'} ===")
    sys.exit(exit_code) 