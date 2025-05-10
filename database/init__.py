import os
import sys

# إضافة المسار إلى PYTHONPATH للسماح بالاستيراد
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from flask import Flask
from config import Config
from models import db

def clear_database():
    """تفريغ قاعدة البيانات وإعادة تهيئتها بجداول فارغة"""
    # إنشاء تطبيق فلاسك مؤقت
    app = Flask(__name__)
    
    # تعديل مسار قاعدة البيانات يدويًا
    app.config.from_object(Config)
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:////opt/app/dbdata/app.db?timeout=30&check_same_thread=False'
    
    # تهيئة قاعدة البيانات
    db.init_app(app)
    
    with app.app_context():
        try:
            # تحقق من وجود قاعدة البيانات
            if not os.path.exists('/opt/app/dbdata/app.db'):
                print("قاعدة البيانات غير موجودة. سيتم إنشاؤها من الصفر.")
                # إنشاء الجداول فقط
                db.create_all()
                print("✅ تم إنشاء قاعدة بيانات جديدة بنجاح!")
            else:
                # إذا كانت قاعدة البيانات موجودة، نقوم بتفريغها وإعادة إنشائها
                print("جاري حذف جميع الجداول...")
                db.drop_all()
                
                # إعادة إنشاء الجداول الفارغة
                print("جاري إعادة إنشاء الجداول...")
                db.create_all()
                
                # حفظ التغييرات
                db.session.commit()
                
                print("✅ تم تفريغ قاعدة البيانات بنجاح وإعادة تهيئة الجداول الفارغة!")
        except Exception as e:
            print(f"❌ حدث خطأ أثناء تهيئة قاعدة البيانات: {e}")
            raise

if __name__ == "__main__":
    clear_database()
