@echo off
chcp 65001 > nul
title نظام إدارة المدرسة - التشغيل على الشبكة المحلية (Offline / LAN)
color 1F

echo =====================================================================
echo          🇮🇶 نظام إدارة المدرسة الإلكتروني (النظام التعليمي العراقي)
echo =====================================================================
echo.
echo [1/3] فحص قاعدة البيانات وتطبيق التحديثات والترحيلات...
python manage.py migrate
echo.

echo [2/3] تحديد عنوان IP المحلي للأجهزة على شبكة المدرسة...
for /f "tokens=2 delims=:" %%a in ('ipconfig ^| findstr /c:"IPv4"') do (
    set LOCAL_IP=%%a
    goto :ip_found
)
:ip_found
set LOCAL_IP=%LOCAL_IP: =%

echo.
echo =====================================================================
echo                🚀 النظام جاهز ويعمل الآن على الشبكة:
echo =====================================================================
echo.
echo  * من هذا الجهاز (Localhost):
echo    - لوحة التحكم:        http://127.0.0.1:8000/admin/
echo    - واجهات الـ API:     http://127.0.0.1:8000/api/
echo    - وثيقة درجات الطالب: http://127.0.0.1:8000/api/certificates/student-transcript/1/
echo    - تأييد استمرار خدمة: http://127.0.0.1:8000/api/certificates/teacher-service/1/
echo    - شيت درجات الصف:     http://127.0.0.1:8000/api/certificates/master-sheet/1/
echo.
echo  * من هواتف وحواسيب الكادر عبر شبكة Wi-Fi / LAN للمدرسة:
echo    - لوحة التحكم:        http://%LOCAL_IP%:8000/admin/
echo    - واجهات الـ API:     http://%LOCAL_IP%:8000/api/
echo.
echo  * بيانات الدخول الافتراضية:
echo    - اسم المستخدم: admin
echo    - كلمة المرور:  admin123
echo.
echo =====================================================================
echo [3/3] تشغيل الخادم على المنفذ 0.0.0.0:8000 ...
echo للإنهاء اضغط Ctrl + C
echo =====================================================================
echo.

python manage.py runserver 0.0.0.0:8000
pause
