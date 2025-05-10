#!/bin/bash
echo "Building GameRoom Application..."

# تفعيل البيئة الافتراضية
source ../venv/bin/activate

# تنظيف المجلدات القديمة
rm -rf build dist

# التحقق من وجود الملفات والمجلدات المطلوبة
if [ ! -d "ui" ]; then
    echo "Error: ui directory not found!"
    exit 1
fi

if [ ! -d "translations" ]; then
    echo "Error: translations directory not found!"
    exit 1
fi

if [ ! -d "styles" ]; then
    echo "Error: styles directory not found!"
    exit 1
fi

# تجميع التطبيق
pyinstaller --clean \
    --name "GameRoom" \
    --windowed \
    --add-data "ui:ui" \
    --add-data "translations:translations" \
    --add-data "styles:styles" \
    --hidden-import PyQt5 \
    --hidden-import PyQt5.QtCore \
    --hidden-import PyQt5.QtGui \
    --hidden-import PyQt5.QtWidgets \
    --hidden-import socketio \
    --hidden-import requests \
    --hidden-import python-dotenv \
    main.py

# إضافة الملفات الاختيارية إذا كانت موجودة
if [ -f "settings.json" ]; then
    echo "Adding settings.json to the build..."
    cp settings.json dist/GameRoom/
fi

if [ -f ".env" ]; then
    echo "Adding .env to the build..."
    cp .env dist/GameRoom/
fi

# إلغاء تفعيل البيئة الافتراضية
deactivate

echo "Build completed!" 