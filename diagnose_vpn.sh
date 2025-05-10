#!/bin/bash

# سكريبت لتشخيص وإصلاح مشاكل SoftEther VPN Server
# استخدام: ./diagnose_vpn.sh [--fix] [--restart] [--create-adapter]

# تلوين الإخراج
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
NC='\033[0m' # لا لون

# دالة للطباعة الملونة
print_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# التحقق من وجود الأدوات المطلوبة
check_prereqs() {
    print_info "التحقق من المتطلبات الأساسية..."
    
    # التحقق من تثبيت SoftEther VPN
    if [ ! -f "/usr/local/vpnserver/vpncmd" ]; then
        print_error "لم يتم العثور على أداة vpncmd في المسار المتوقع: /usr/local/vpnserver/vpncmd"
        print_info "تأكد من تثبيت SoftEther VPN Server بشكل صحيح."
        exit 1
    else
        print_info "تم العثور على أداة vpncmd ✓"
    fi
    
    # التحقق من صلاحيات التشغيل
    if [ "$(id -u)" -ne 0 ]; then
        print_warning "هذا السكريبت يعمل بدون صلاحيات الجذر (root)، قد تواجه مشاكل في إنشاء محولات الشبكة."
        print_info "من المستحسن تشغيل السكريبت باستخدام sudo أو بصلاحيات الجذر."
    else
        print_info "يعمل السكريبت بصلاحيات الجذر (root) ✓"
    fi
}

# التحقق من حالة خدمة SoftEther VPN
check_service() {
    print_info "التحقق من حالة خدمة SoftEther VPN Server..."
    
    if systemctl is-active --quiet vpnserver; then
        print_info "خدمة SoftEther VPN Server تعمل ✓"
    else
        print_error "خدمة SoftEther VPN Server لا تعمل! ✗"
        return 1
    fi
    
    return 0
}

# إعادة تشغيل الخدمة
restart_service() {
    print_info "جاري إعادة تشغيل خدمة SoftEther VPN Server..."
    
    systemctl restart vpnserver
    
    # انتظار قليلاً لإعادة التشغيل
    sleep 5
    
    if systemctl is-active --quiet vpnserver; then
        print_info "تمت إعادة تشغيل الخدمة بنجاح ✓"
        return 0
    else
        print_error "فشل في إعادة تشغيل الخدمة! ✗"
        return 1
    fi
}

# التحقق من المحولات الموجودة
check_adapters() {
    print_info "التحقق من وجود محول VPN..."
    
    # يجب تعيين كلمة المرور
    if [ -z "$SOFTETHER_ADMIN_PASSWORD" ]; then
        print_error "يجب تعيين متغير البيئة SOFTETHER_ADMIN_PASSWORD"
        return 1
    fi
    
    # الحصول على قائمة المحولات
    VPNCMD="/usr/local/vpnserver/vpncmd"
    SERVER_IP=${SOFTETHER_SERVER_IP:-"localhost"}
    SERVER_PORT=${SOFTETHER_SERVER_PORT:-443}
    
    OUTPUT=$($VPNCMD /SERVER:$SERVER_IP:$SERVER_PORT /PASSWORD:$SOFTETHER_ADMIN_PASSWORD /CMD NicList 2>&1)
    
    if echo "$OUTPUT" | grep -q "VPN"; then
        print_info "تم العثور على محول VPN ✓"
        return 0
    else
        print_warning "لم يتم العثور على محول VPN! ✗"
        echo "$OUTPUT" | head -n 10
        return 1
    fi
}

# إنشاء محول VPN
create_adapter() {
    ADAPTER_NAME=${1:-"VPN"}
    print_info "محاولة إنشاء محول $ADAPTER_NAME..."
    
    # يجب تعيين كلمة المرور
    if [ -z "$SOFTETHER_ADMIN_PASSWORD" ]; then
        print_error "يجب تعيين متغير البيئة SOFTETHER_ADMIN_PASSWORD"
        return 1
    fi
    
    VPNCMD="/usr/local/vpnserver/vpncmd"
    SERVER_IP=${SOFTETHER_SERVER_IP:-"localhost"}
    SERVER_PORT=${SOFTETHER_SERVER_PORT:-443}
    
    # محاولة 1: استخدام NicCreate
    print_info "المحاولة 1: استخدام NicCreate..."
    OUTPUT1=$($VPNCMD /SERVER:$SERVER_IP:$SERVER_PORT /PASSWORD:$SOFTETHER_ADMIN_PASSWORD /CMD NicCreate $ADAPTER_NAME 2>&1)
    
    if echo "$OUTPUT1" | grep -q "successfully"; then
        print_info "تم إنشاء المحول $ADAPTER_NAME بنجاح ✓"
        return 0
    elif echo "$OUTPUT1" | grep -q "already exists"; then
        print_info "المحول $ADAPTER_NAME موجود بالفعل ✓"
        return 0
    fi
    
    # محاولة 2: استخدام LocalBridge
    print_info "المحاولة 2: استخدام BridgeCreate..."
    OUTPUT2=$($VPNCMD /SERVER:$SERVER_IP:$SERVER_PORT /PASSWORD:$SOFTETHER_ADMIN_PASSWORD /CMD BridgeCreate DEFAULT $ADAPTER_NAME /DEVICE:default 2>&1)
    
    if echo "$OUTPUT2" | grep -q "successfully"; then
        print_info "تم إنشاء جسر محلي للمحول $ADAPTER_NAME بنجاح ✓"
        return 0
    elif echo "$OUTPUT2" | grep -q "already exists"; then
        print_info "الجسر المحلي للمحول $ADAPTER_NAME موجود بالفعل ✓"
        return 0
    fi
    
    # محاولة 3: استخدام وضع العميل
    print_info "المحاولة 3: استخدام وضع العميل..."
    OUTPUT3=$($VPNCMD /CLIENT /CMD NicCreate $ADAPTER_NAME 2>&1)
    
    if echo "$OUTPUT3" | grep -q "successfully"; then
        print_info "تم إنشاء المحول $ADAPTER_NAME باستخدام وضع العميل بنجاح ✓"
        return 0
    elif echo "$OUTPUT3" | grep -q "already exists"; then
        print_info "المحول $ADAPTER_NAME موجود بالفعل في وضع العميل ✓"
        return 0
    fi
    
    print_error "فشلت جميع محاولات إنشاء المحول! ✗"
    echo "خطأ المحاولة 1:"
    echo "$OUTPUT1" | head -n 5
    echo "خطأ المحاولة 2:"
    echo "$OUTPUT2" | head -n 5
    echo "خطأ المحاولة 3:"
    echo "$OUTPUT3" | head -n 5
    
    return 1
}

# محاولة إصلاح المشاكل
fix_issues() {
    print_info "جاري محاولة إصلاح مشاكل VPN..."
    
    # إعادة تشغيل الخدمة
    restart_service
    
    # محاولة إنشاء المحول
    create_adapter "VPN"
    
    # إذا فشلت المحاولة، جرّب أسماء أخرى
    if [ $? -ne 0 ]; then
        print_info "جاري محاولة إنشاء محولات بديلة..."
        
        for i in {1..3}; do
            create_adapter "VPN$i"
            if [ $? -eq 0 ]; then
                print_info "تم إنشاء محول بديل VPN$i بنجاح ✓"
                print_warning "يجب تحديث التكوين لاستخدام المحول الجديد VPN$i"
                break
            fi
        done
    fi
    
    print_info "اكتمل الإصلاح. يرجى التحقق من عمل النظام الآن."
}

# تنفيذ التشخيص الكامل
run_diagnostics() {
    print_info "بدء تشخيص SoftEther VPN Server..."
    
    # التحقق من المتطلبات
    check_prereqs
    
    # التحقق من حالة الخدمة
    check_service
    
    # التحقق من المحولات
    check_adapters
    
    print_info "اكتمل التشخيص."
}

# معالجة معاملات سطر الأوامر
case "$1" in
    --fix)
        fix_issues
        ;;
    --restart)
        restart_service
        ;;
    --create-adapter)
        create_adapter "${2:-VPN}"
        ;;
    *)
        run_diagnostics
        ;;
esac

exit 0 