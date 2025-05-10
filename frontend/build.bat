@echo off
echo Building GameRoom Application...

:: تنظيف المجلدات القديمة
rmdir /s /q build
rmdir /s /q dist

:: تجميع التطبيق
pyinstaller --clean ^
    --name "GameRoom" ^
    --windowed ^
    --add-data "ui;ui" ^
    --add-data "translations;translations" ^
    --add-data "styles;styles" ^
    --add-data "settings.json;." ^
    --add-data ".env;." ^
    --hidden-import PyQt5 ^
    --hidden-import PyQt5.QtCore ^
    --hidden-import PyQt5.QtGui ^
    --hidden-import PyQt5.QtWidgets ^
    --hidden-import socketio ^
    --hidden-import requests ^
    --hidden-import python-dotenv ^
    --icon "ui/icon.ico" ^
    main.py

echo Build completed!
pause 